"""Tests for the drive-sign convention shared by all steering genes.

``Organism.add_drive`` takes the angle *toward* a point of interest plus a
signed weight: positive attracts, negative repels.  Reversing the angle *and*
using a negative weight cancels out and produces the exact opposite behaviour,
which is a mistake that is invisible unless the resulting heading is asserted.
"""

import math
import unittest

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.organism import Organism
from wee_life2.core.world import World
from wee_life2.genes.fear import FearGene
from wee_life2.genes.geometry import steer_away, steer_toward


def heading_error_to(organism: Organism, target: tuple[float, float]) -> float:
    """Absolute angle between the organism's desired heading and the target."""
    from wee_life2.core.geometry import angle_diff, angle_to

    desired = organism.angle + organism.combined_drive()
    return abs(angle_diff(desired, angle_to(organism.position, target)))


class TestSteeringHelpers(unittest.TestCase):
    def setUp(self):
        self.world = World(400, 300, tile_size=20)
        self.world.clear_map()

    def test_steer_toward_points_at_target(self):
        org = Organism(DNA([]), position=(100.0, 100.0))
        org.angle = math.pi  # facing away from the target
        steer_toward(org, (200.0, 100.0), 1.0)
        self.assertLess(heading_error_to(org, (200.0, 100.0)), 0.01)

    def test_steer_away_points_opposite_the_target(self):
        org = Organism(DNA([]), position=(100.0, 100.0))
        org.angle = 0.0  # facing the target
        steer_away(org, (200.0, 100.0), 1.0)
        # Desired heading must be ~180 deg from the target direction.
        self.assertGreater(heading_error_to(org, (200.0, 100.0)), math.pi - 0.01)

    def test_steer_away_ignores_weight_sign(self):
        """steer_away must repel for both positive and negative weights."""
        for weight in (1.0, -1.0):
            org = Organism(DNA([]), position=(100.0, 100.0))
            org.angle = 0.0
            steer_away(org, (200.0, 100.0), weight)
            self.assertGreater(
                heading_error_to(org, (200.0, 100.0)),
                math.pi - 0.01,
                msg=f"weight={weight} should still repel",
            )


class TestFearFlees(unittest.TestCase):
    def setUp(self):
        self.world = World(400, 300, tile_size=20)
        self.world.clear_map()

    def _make_pair(self, threat_offset: tuple[float, float]) -> tuple[Organism, FearGene]:
        gene = FearGene()
        prey = self.world.spawn_organism(DNA([gene]), (200.0, 150.0))
        prey.angle = 0.0
        threat = self.world.spawn_organism(DNA([]), (200.0 + threat_offset[0], 150.0 + threat_offset[1]))
        # Make the other organism unambiguously threatening.
        threat.energy = 10_000.0
        threat.aggression = 1.0
        self.world._rebuild_spatial_grid()
        prey.drives.clear()
        prey._nearby_organisms = None
        return prey, gene

    def test_fear_steers_away_from_threat_ahead(self):
        prey, gene = self._make_pair((50.0, 0.0))
        gene.apply(prey, self.world, 1.0 / config.FPS)
        self.assertTrue(prey.drives, "fear should produce a drive for a visible threat")
        threat_pos = (250.0, 150.0)
        self.assertGreater(
            heading_error_to(prey, threat_pos),
            math.pi / 2.0,
            msg="fear must turn the organism away from the threat, not into it",
        )

    def test_fear_steers_away_from_threat_to_the_side(self):
        prey, gene = self._make_pair((0.0, 40.0))
        gene.apply(prey, self.world, 1.0 / config.FPS)
        self.assertTrue(prey.drives)
        self.assertGreater(heading_error_to(prey, (200.0, 190.0)), math.pi / 2.0)

    def test_fear_alarm_propagates_away_from_alarmed_kin(self):
        """Kin panic is a beacon to flee from, even with no threat in sight."""
        gene = FearGene()
        dna = DNA([gene])
        prey = self.world.spawn_organism(dna, (200.0, 150.0))
        prey.angle = 0.0
        # Same species label, already panicking, and not itself a threat.
        kin = self.world.spawn_organism(dna.clone(), (250.0, 150.0))
        kin.energy = prey.energy * 0.1
        kin.aggression = 0.0
        kin.alarm_level = 1.0
        self.assertEqual(prey.name, kin.name)
        self.world._rebuild_spatial_grid()
        prey.drives.clear()
        prey._nearby_organisms = None

        gene.apply(prey, self.world, 1.0 / config.FPS)
        self.assertTrue(prey.drives, "secondhand alarm should produce a drive")
        self.assertGreater(heading_error_to(prey, kin.position), math.pi / 2.0)


class TestHealTile(unittest.TestCase):
    def setUp(self):
        self.world = World(400, 300, tile_size=20)
        self.world.clear_map()

    def _energy_delta_on_heal_tile(self, amphibious: bool) -> float:
        col, row = 5, 5
        self.world.set_tile(col, row, config.TILE_HEAL)
        pos = ((col + 0.5) * self.world.tile_size, (row + 0.5) * self.world.tile_size)
        org = Organism(DNA([]), position=pos)
        org.amphibious = amphibious
        org.energy = org.max_energy * 0.5
        before = org.energy
        org._apply_hazards_and_water(self.world, 1.0 / config.FPS)
        return org.energy - before

    def test_heal_tile_restores_energy(self):
        self.assertGreater(self._energy_delta_on_heal_tile(amphibious=False), 0.0)

    def test_amphibious_also_heals_on_heal_tile(self):
        """The land drain must not swallow the heal branch for amphibians."""
        delta = self._energy_delta_on_heal_tile(amphibious=True)
        self.assertGreater(
            delta,
            0.0,
            msg="amphibious organisms used to never benefit from heal tiles",
        )


if __name__ == "__main__":
    unittest.main()
