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
from wee_life2.core.food import Food
from wee_life2.core.geometry import angle_diff
from wee_life2.core.organism import Organism
from wee_life2.core.world import World
from wee_life2.genes.amphibious import AmphibiousGene
from wee_life2.genes.eye import EyeGene
from wee_life2.genes.fear import FearGene
from wee_life2.genes.geometry import steer_away, steer_toward
from wee_life2.genes.metabolism import MetabolismGene
from wee_life2.genes.scent import ScentGene


def heading_error_to(organism: Organism, target: tuple[float, float]) -> float:
    """Absolute angle between the organism's desired heading and the target."""
    from wee_life2.core.geometry import angle_diff, angle_to

    desired = organism.angle + organism.combined_drive()
    return abs(angle_diff(desired, angle_to(organism.position, target)))


def resulting_heading(org: Organism) -> float:
    """Absolute heading the organism's combined drives are steering toward."""
    return org.angle + org.combined_drive()


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


class TestSenseThreatSelection(unittest.TestCase):
    """eye/scent must flee the *nearest* threat, even with food in view."""

    CENTER = (400.0, 400.0)

    def setUp(self):
        self.world = World(800, 800, tile_size=20)
        self.world.clear_map()

    @staticmethod
    def _bearing_pos(bearing: float, dist: float) -> tuple[float, float]:
        return (
            400.0 + dist * math.cos(bearing),
            400.0 + dist * math.sin(bearing),
        )

    def _sensing_organism(self, genes):
        org = Organism(DNA(genes), position=self.CENTER)
        org.angle = 0.0
        org.aggression = 0.0
        self.world.add_organism(org)
        return org

    def _threat(self, bearing: float, dist: float) -> Organism:
        threat = Organism(DNA([]), position=self._bearing_pos(bearing, dist))
        threat.aggression = 0.9
        self.world.add_organism(threat)
        return threat

    def _finish_setup(self, org):
        self.world._rebuild_spatial_grid()
        org.drives.clear()
        org._nearby_organisms = None

    def _eye(self) -> EyeGene:
        return EyeGene({"range": 200.0, "fov": 2.4, "terrain_rays": 0.0, "direction": 0.0})

    def _scent(self) -> ScentGene:
        # precision=1.0 makes angle_noise() exactly zero, so the emitted
        # bearing is deterministic.
        return ScentGene({"range": 200.0, "terrain_rays": 0.0, "precision": 1.0})

    def test_eye_flees_nearest_threat(self):
        gene = self._eye()
        org = self._sensing_organism([gene])
        self._threat(-0.5, 40.0)
        self._threat(0.5, 180.0)
        self._finish_setup(org)

        gene.apply(org, self.world, 1.0 / config.FPS)
        self.assertEqual(org.seen_target, "threat")
        self.assertLess(
            abs(angle_diff(resulting_heading(org), -0.5 + math.pi)),
            0.1,
            msg="eye must flee the near threat, not the farthest one",
        )

    def test_eye_threat_not_suppressed_by_food(self):
        gene = self._eye()
        org = self._sensing_organism([gene, MetabolismGene()])
        self._threat(0.0, 30.0)
        self.world.add_food(Food(position=self._bearing_pos(0.9, 150.0)))
        self._finish_setup(org)

        gene.apply(org, self.world, 1.0 / config.FPS)
        self.assertEqual(org.seen_target, "threat")
        self.assertLess(
            abs(angle_diff(resulting_heading(org), math.pi)),
            0.1,
            msg="a visible food item must not suppress the threat response",
        )

    def test_scent_flees_nearest_threat(self):
        gene = self._scent()
        org = self._sensing_organism([gene])
        self._threat(-0.5, 40.0)
        self._threat(0.5, 180.0)
        self._finish_setup(org)

        gene.apply(org, self.world, 1.0 / config.FPS)
        self.assertEqual(org.seen_target, "danger")
        self.assertLess(
            abs(angle_diff(resulting_heading(org), -0.5 + math.pi)),
            0.1,
            msg="scent must flee the near threat, not the farthest one",
        )

    def test_scent_danger_not_suppressed_by_food(self):
        gene = self._scent()
        org = self._sensing_organism([gene, MetabolismGene()])
        self._threat(0.0, 30.0)
        self.world.add_food(Food(position=self._bearing_pos(0.9, 150.0)))
        self._finish_setup(org)

        gene.apply(org, self.world, 1.0 / config.FPS)
        self.assertEqual(org.seen_target, "danger")
        self.assertLess(
            abs(angle_diff(resulting_heading(org), math.pi)),
            0.1,
            msg="a smelt food item must not suppress the danger response",
        )


class TestAmphibiousWaterReturn(unittest.TestCase):
    """An amphibious on land steers back toward water (positive weight =
    attraction; the angle toward the water is passed un-reversed)."""

    def setUp(self):
        self.world = World(400, 300, tile_size=20)
        self.world.clear_map()

    def _organism(self, genes, energy=100.0, position=(200.0, 150.0)):
        org = Organism(DNA(genes), position=position)
        org.angle = math.pi / 2.0  # facing "down"; the water sits to its right
        org.energy = energy
        self.world.add_organism(org)
        org.drives.clear()
        org._nearby_organisms = None
        return org

    def _water_east(self):
        # Tile (12, 7) centre is (250, 150): dead right of a south-facing organism.
        self.world.set_tile(12, 7, config.TILE_WATER)

    def test_drained_amphibious_steers_toward_water(self):
        gene = AmphibiousGene()
        org = self._organism([gene, EyeGene()])
        self._water_east()
        gene.apply(org, self.world, 0.0)
        self.assertTrue(org.drives)
        # Water is on the right; a positive water_weight must turn right (< 0).
        self.assertLess(org.combined_drive(), -1.0)

    def test_well_fed_amphibious_is_still_tethered_to_water(self):
        """Land drains amphibians fast, so even a full one feels base_pull."""
        gene = AmphibiousGene()
        org = self._organism([gene])
        org.energy = org.max_energy
        self._water_east()
        gene.apply(org, self.world, 0.0)
        self.assertEqual(len(org.drives), 1)
        self.assertAlmostEqual(org.drives[0][1], gene.params["water_weight"] * gene.params["base_pull"])
        self.assertLess(org.combined_drive(), -1.0)

    def test_zero_base_pull_frees_a_well_fed_amphibious(self):
        """Selection can loosen the tether: base_pull 0 restores free foraging."""
        gene = AmphibiousGene({"base_pull": 0.0})
        org = self._organism([gene])
        org.energy = org.max_energy
        self._water_east()
        gene.apply(org, self.world, 0.0)
        self.assertFalse(org.drives)

    def test_blind_amphibious_still_senses_water(self):
        """The gene senses water itself; an eye/scent gate stranded blind carriers."""
        gene = AmphibiousGene()
        org = self._organism([gene])  # no eye/scent in the genome
        self._water_east()
        gene.apply(org, self.world, 0.0)
        self.assertLess(org.combined_drive(), -1.0)

    def test_no_drive_while_already_on_water(self):
        gene = AmphibiousGene()
        self._water_east()
        org = self._organism([gene], position=(250.0, 150.0))
        gene.apply(org, self.world, 0.0)
        self.assertFalse(org.drives)

    def test_no_drive_when_no_water_in_range(self):
        gene = AmphibiousGene()
        org = self._organism([gene])
        gene.apply(org, self.world, 0.0)
        self.assertFalse(org.drives)

    def test_zero_search_range_disables_without_crash(self):
        gene = AmphibiousGene({"search_range": 0.0})
        org = self._organism([gene])
        self._water_east()
        gene.apply(org, self.world, 0.0)
        self.assertFalse(org.drives)

    def test_urgency_ramps_up_as_energy_falls(self):
        gene = AmphibiousGene()
        full = gene.water_pull(1.0)
        at_threshold = gene.water_pull(gene.params["urgency_threshold"])
        half = gene.water_pull(0.4)
        empty = gene.water_pull(0.0)
        self.assertAlmostEqual(full, at_threshold)
        self.assertGreater(half, at_threshold)
        self.assertGreater(empty, half)
        self.assertAlmostEqual(empty, gene.params["water_weight"])

    def test_drained_pull_outweighs_a_seen_food_item(self):
        """At low energy heading home must beat the strongest food drive."""
        gene = AmphibiousGene()
        scent_food_max = 0.8 * ScentGene.default_params["food_weight"]
        self.assertGreater(gene.water_pull(0.1), scent_food_max)

    def test_cached_target_is_rescanned_when_water_disappears(self):
        gene = AmphibiousGene()
        org = self._organism([gene])
        self._water_east()
        gene.apply(org, self.world, 0.0)
        self.assertTrue(org.drives)
        # Turn the lake into land; the cached target must not keep pulling.
        self.world.set_tile(12, 7, config.TILE_EMPTY)
        org.drives.clear()
        gene.apply(org, self.world, 0.0)
        self.assertFalse(org.drives)

    def test_target_lookup_is_throttled(self):
        gene = AmphibiousGene()
        org = self._organism([gene])
        self._water_east()
        calls = []
        real = self.world.nearest_water

        def counting(pos, max_dist):
            calls.append(pos)
            return real(pos, max_dist)

        self.world.nearest_water = counting
        dt = 1.0 / config.TICKS_PER_SECOND
        for _ in range(int(AmphibiousGene.RETARGET_TICKS)):
            gene.apply(org, self.world, dt)
        self.assertEqual(len(calls), 1)
        gene.apply(org, self.world, dt)
        self.assertEqual(len(calls), 2)

    def test_duplicate_amphibious_genes_emit_one_drive(self):
        g1 = AmphibiousGene()
        g2 = AmphibiousGene()
        org = self._organism([g1, g2, EyeGene()])
        self._water_east()
        g1.apply(org, self.world, 0.0)
        g2.apply(org, self.world, 0.0)
        # Only the amphibious genes are applied here, so any drive present is
        # the water drive; both genes firing would emit two.
        self.assertEqual(len(org.drives), 1)

    def test_water_drive_params_are_bounded(self):
        gene = AmphibiousGene(
            {"urgency_threshold": 5.0, "water_weight": -3.0, "search_range": -10.0, "base_pull": 2.0}
        )
        self.assertEqual(gene.params["urgency_threshold"], 1.0)
        self.assertEqual(gene.params["water_weight"], 0.0)
        self.assertEqual(gene.params["search_range"], 0.0)
        self.assertEqual(gene.params["base_pull"], 1.0)


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
