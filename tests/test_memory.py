"""Tests for the memory gene and the perception -> memory pipeline."""

import math
import unittest

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.organism import Organism
from wee_life2.core.world import World
from wee_life2.genes.eye import EyeGene
from wee_life2.genes.memory import MemoryGene
from wee_life2.genes.scent import ScentGene
from wee_life2.genes.touch import TouchGene


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.world = World(200, 150, tile_size=20)
        self.world.clear_map()

    def test_memory_remembers_tile_under_feet(self):
        self.world.set_tile(2, 2, config.TILE_WATER)
        dna = DNA([MemoryGene()])
        org = self.world.spawn_organism(dna, (50.0, 50.0))
        self.assertIsNotNone(org)
        self.world.update(1.0 / config.FPS)
        self.assertTrue(any(e.tile_type == config.TILE_WATER for e in org.memory))

    def test_memory_capacity_limit(self):
        # Place walls under each remembered position so validation keeps them.
        self.world.set_tile(0, 0, config.TILE_WALL)
        self.world.set_tile(1, 1, config.TILE_WALL)
        self.world.set_tile(1, 2, config.TILE_WALL)
        gene = MemoryGene({"capacity": 2.0, "retention": 1000.0, "ray_count": 0.0})
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.remember((10.0, 10.0), config.TILE_WALL, 0.0, 1.0)
        org.remember((20.0, 20.0), config.TILE_WALL, 1.0, 1.0)
        org.remember((30.0, 30.0), config.TILE_WALL, 2.0, 1.0)
        gene.apply(org, self.world, 0.0)
        self.assertEqual(len(org.memory), 2)
        self.assertEqual(org.memory[-1].position, (30.0, 30.0))

    def test_memory_retention_decay(self):
        self.world.set_tile(0, 0, config.TILE_WALL)
        gene = MemoryGene({"capacity": 5.0, "retention": 10.0, "ray_count": 0.0})
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.remember((10.0, 10.0), config.TILE_WALL, 0.0, 1.0)
        self.world.tick = 20.0
        gene.apply(org, self.world, 0.0)
        self.assertEqual(len(org.memory), 0)

    def test_memory_wall_recall_generates_drive(self):
        self.world.set_tile(4, 2, config.TILE_WALL)
        gene = MemoryGene({"capacity": 5.0, "retention": 1000.0, "recall_range": 100.0})
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        # Place the memory far enough that it is not skipped as "close".
        org.remember((90.0, 50.0), config.TILE_WALL, 0.0, 1.0)
        org.angle = 0.0
        gene.apply(org, self.world, 0.0)
        self.assertTrue(org.drives)

    def test_memory_water_amphibious(self):
        self.world.set_tile(4, 2, config.TILE_WATER)
        gene = MemoryGene(
            {"capacity": 5.0, "retention": 1000.0, "recall_range": 100.0, "water_weight": 1.0, "ray_count": 0.0}
        )
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.amphibious = True
        org.remember((80.0, 50.0), config.TILE_WATER, 0.0, 1.0)
        # Face up; the remembered water is on the right, so the organism should turn right.
        org.angle = math.pi / 2.0
        gene.apply(org, self.world, 0.0)
        # Water is remembered to the right; amphibious should turn right (toward it).
        self.assertLess(org.combined_drive(), -1.0)

    def test_memory_water_non_amphibious(self):
        self.world.set_tile(4, 2, config.TILE_WATER)
        gene = MemoryGene(
            {"capacity": 5.0, "retention": 1000.0, "recall_range": 100.0, "water_weight": 1.0, "ray_count": 0.0}
        )
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.amphibious = False
        org.remember((80.0, 50.0), config.TILE_WATER, 0.0, 1.0)
        # Face up; the remembered water is on the right, so the organism should turn left (away).
        org.angle = math.pi / 2.0
        gene.apply(org, self.world, 0.0)
        # Water is remembered to the right; non-amphibious should turn left (away).
        self.assertGreater(org.combined_drive(), 1.0)

    def test_eye_publishes_perception_event(self):
        self.world.set_tile(3, 2, config.TILE_WALL)
        gene = EyeGene({"range": 100.0, "fov": 2.0, "terrain_rays": 1.0})
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.angle = 0.0
        gene.apply(org, self.world, 0.0)
        self.assertTrue(any(e.source == "eye" for e in org.perception_events))

    def test_scent_publishes_perception_event(self):
        self.world.set_tile(3, 2, config.TILE_WALL)
        gene = ScentGene({"range": 100.0, "terrain_rays": 1.0})
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        gene.apply(org, self.world, 0.0)
        self.assertTrue(any(e.source == "scent" for e in org.perception_events))

    def test_touch_publishes_perception_event(self):
        self.world.set_tile(3, 2, config.TILE_WALL)
        gene = TouchGene({"range": 60.0})
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.angle = 0.0
        gene.apply(org, self.world, 0.0)
        self.assertTrue(any(e.source == "touch" for e in org.perception_events))

    def test_memory_consumes_perception_events(self):
        self.world.set_tile(3, 2, config.TILE_WALL)
        eye = EyeGene({"range": 100.0, "fov": 2.0, "terrain_rays": 1.0, "wall_weight": 0.0})
        memory = MemoryGene({"capacity": 5.0, "retention": 1000.0, "ray_count": 0.0})
        org = Organism(DNA([eye, memory]), position=(50.0, 50.0))
        org.angle = 0.0
        self.world.tick = 1.0
        eye.apply(org, self.world, 0.0)
        memory.apply(org, self.world, 0.0)
        self.assertTrue(any(e.tile_type == config.TILE_WALL for e in org.memory))

    def test_scent_detects_heal(self):
        self.world.set_tile(3, 2, config.TILE_HEAL)
        gene = ScentGene({"range": 100.0, "terrain_rays": 1.0})
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.angle = 0.0
        gene.apply(org, self.world, 0.0)
        self.assertTrue(any(e.source == "scent" and e.tile_type == config.TILE_HEAL for e in org.perception_events))

    def test_memory_heal_recall(self):
        self.world.set_tile(4, 2, config.TILE_HEAL)
        gene = MemoryGene({"capacity": 5.0, "retention": 1000.0, "recall_range": 100.0, "heal_weight": 1.0})
        org = Organism(DNA([gene]), position=(50.0, 50.0))
        org.energy = 80.0  # below heal threshold
        org.remember((80.0, 50.0), config.TILE_HEAL, 0.0, 1.0)
        # Face up; the remembered heal tile is on the right, so the organism should turn right.
        org.angle = math.pi / 2.0
        gene.apply(org, self.world, 0.0)
        self.assertTrue(any(d[1] > 0 for d in org.drives))

    def test_multiple_memory_aggregates_capacity_and_weights(self):
        # Two memory genes: capacities sum, recall weights sum, but logic runs once.
        m1 = MemoryGene({"capacity": 2.0, "retention": 1000.0, "ray_count": 0.0, "wall_weight": -0.5})
        m2 = MemoryGene({"capacity": 3.0, "retention": 1000.0, "ray_count": 0.0, "wall_weight": -0.7})
        org = Organism(DNA([m1, m2]), position=(50.0, 50.0))
        self.world.tick = 1.0  # avoid the tile-validation pass that runs on tick % 10 == 0
        for x in (80.0, 90.0, 100.0, 110.0, 120.0):
            self.world.set_tile(int(x / self.world.tile_size), 2, config.TILE_WALL)
            org.remember((x, 50.0), config.TILE_WALL, 1.0, 1.0)
        # Point up; walls are to the right, so the combined drive should push left/down (negative).
        org.angle = math.pi / 2.0
        m1.apply(org, self.world, 0.0)
        # Combined capacity is 5, so all 5 wall entries should remain.
        self.assertEqual(len(org.memory), 5)
        # Second memory should not run the logic again (no extra drives beyond what m1 did).
        drive_count_before = len(org.drives)
        m2.apply(org, self.world, 0.0)
        self.assertEqual(len(org.drives), drive_count_before)
        # Walls are remembered to the right; while pointing up the organism
        # should be pushed left (negative steering).
        self.assertLess(org.combined_drive(), -1.0)


if __name__ == "__main__":
    unittest.main()
