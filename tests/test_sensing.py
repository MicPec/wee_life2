"""Tests for the shared sensing helpers used by the eye and scent genes."""

import math
import unittest

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.organism import Organism
from wee_life2.core.world import World
from wee_life2.genes.eye import EyeGene
from wee_life2.genes.scent import ScentGene
from wee_life2.genes.sensing import fan_ray_angles, radial_ray_angles, sight_discount


class TestRayAngles(unittest.TestCase):
    def test_fan_single_ray_points_at_center(self):
        self.assertEqual(fan_ray_angles(0.5, 2.0, 1), [0.5])

    def test_fan_spans_fov_symmetrically(self):
        rays = fan_ray_angles(0.0, 2.0, 3)
        self.assertEqual(len(rays), 3)
        self.assertAlmostEqual(rays[0], -1.0)
        self.assertAlmostEqual(rays[1], 0.0)
        self.assertAlmostEqual(rays[2], 1.0)

    def test_radial_covers_full_circle(self):
        rays = radial_ray_angles(0.0, 4)
        self.assertEqual(len(rays), 4)
        for expected, actual in zip((0.0, math.pi / 2, math.pi, 3 * math.pi / 2), rays):
            self.assertAlmostEqual(expected, actual)

    def test_radial_empty(self):
        self.assertEqual(radial_ray_angles(0.0, 0), [])


class TestSightDiscount(unittest.TestCase):
    def setUp(self):
        self.world = World(200, 150, tile_size=20)
        self.world.clear_map()

    def test_water_discounts_for_landlubber(self):
        self.world.set_tile(3, 2, config.TILE_WATER)
        d = sight_discount(self.world, (30.0, 50.0), (110.0, 50.0), is_amphibious=False)
        self.assertAlmostEqual(d, config.WATER_SIGHT_DISCOUNT)

    def test_water_ignored_by_amphibious(self):
        self.world.set_tile(3, 2, config.TILE_WATER)
        d = sight_discount(self.world, (30.0, 50.0), (110.0, 50.0), is_amphibious=True)
        self.assertEqual(d, 1.0)

    def test_hazard_discounts_everyone(self):
        self.world.set_tile(3, 2, config.TILE_LAVA)
        for amphibious in (False, True):
            d = sight_discount(self.world, (30.0, 50.0), (110.0, 50.0), is_amphibious=amphibious)
            self.assertAlmostEqual(d, config.WATER_SIGHT_DISCOUNT)

    def test_clear_line_is_full_strength(self):
        d = sight_discount(self.world, (30.0, 50.0), (110.0, 50.0), is_amphibious=False)
        self.assertEqual(d, 1.0)


class TestTerrainDriveModalities(unittest.TestCase):
    """Both senses share the terrain loop; only scent reacts to heal tiles."""

    def setUp(self):
        self.world = World(200, 150, tile_size=20)
        self.world.clear_map()

    def _organism(self, gene):
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.angle = 0.0
        return org

    def test_scent_steers_toward_heal_when_hurt(self):
        self.world.set_tile(3, 2, config.TILE_HEAL)
        gene = ScentGene({"range": 100.0, "terrain_rays": 1.0})
        org = self._organism(gene)
        org.energy = 20.0  # below the default heal_threshold
        gene.apply(org, self.world, 0.0)
        self.assertTrue(org.drives)
        # Heal tile is dead ahead (angle 0); the drive should point right at it.
        self.assertAlmostEqual(org.drives[-1][0], 0.0, places=5)
        self.assertGreater(org.drives[-1][1], 0.0)

    def test_scent_ignores_heal_when_healthy(self):
        self.world.set_tile(3, 2, config.TILE_HEAL)
        gene = ScentGene({"range": 100.0, "terrain_rays": 1.0})
        org = self._organism(gene)
        org.energy = org.max_energy
        gene.apply(org, self.world, 0.0)
        # The hit is still published for memory, but produces no drive.
        self.assertTrue(any(e.tile_type == config.TILE_HEAL for e in org.perception_events))
        self.assertFalse(org.drives)

    def test_eye_does_not_seek_heal(self):
        self.world.set_tile(3, 2, config.TILE_HEAL)
        gene = EyeGene({"range": 100.0, "fov": 2.0, "terrain_rays": 1.0, "direction": 0.0})
        org = self._organism(gene)
        org.energy = 20.0
        gene.apply(org, self.world, 0.0)
        # Eyes still report the tile to memory, they just have no drive for it.
        self.assertTrue(any(e.source == "eye" for e in org.perception_events))
        self.assertFalse(org.drives)

    def test_eye_terrain_wall_repels(self):
        self.world.set_tile(3, 2, config.TILE_WALL)
        gene = EyeGene({"range": 100.0, "fov": 2.0, "terrain_rays": 1.0, "direction": 0.0, "wall_weight": -0.7})
        org = self._organism(gene)
        # Face the wall straight on; repulsion straight back reads as ~pi turn.
        gene.apply(org, self.world, 0.0)
        self.assertGreater(abs(org.combined_drive()), 1.0)


if __name__ == "__main__":
    unittest.main()
