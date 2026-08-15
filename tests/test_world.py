"""Tests for World."""

import unittest

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.organism import Organism
from wee_life2.core.world import World


class TestWorld(unittest.TestCase):
    def setUp(self):
        self.world = World(240, 180, tile_size=20)
        self.world.clear_map()

    def test_spawn_organism(self):
        dna = DNA.random()
        organism = self.world.spawn_organism(dna, (50.0, 50.0))
        self.assertIsNotNone(organism)
        self.assertIn(organism, self.world.organisms)

    def test_organism_cap(self):
        dna = DNA.random()
        for _ in range(1000):
            self.world.spawn_organism(dna, (50.0, 50.0))
        self.assertLessEqual(len(self.world.organisms), self.world.max_organisms)

    def test_remove_organism(self):
        dna = DNA.random()
        organism = self.world.spawn_organism(dna, (50.0, 50.0))
        self.assertIsNotNone(organism)
        self.world.remove_organism(organism)
        self.assertNotIn(organism, self.world.organisms)

    def test_local_density(self):
        dna = DNA.random()
        a = self.world.spawn_organism(dna, (50.0, 50.0))
        b = self.world.spawn_organism(dna, (55.0, 55.0))
        c = self.world.spawn_organism(dna, (200.0, 150.0))
        # rebuild grid manually since update() wasn't called
        self.world._rebuild_spatial_grid()
        density = self.world.local_density((50.0, 50.0), 30)
        self.assertGreaterEqual(density, 2)

    def test_organisms_near(self):
        dna = DNA.random()
        a = self.world.spawn_organism(dna, (50.0, 50.0))
        b = self.world.spawn_organism(dna, (55.0, 55.0))
        self.world._rebuild_spatial_grid()
        near = list(self.world.organisms_near((50.0, 50.0), 30))
        self.assertIn(a, near)
        self.assertIn(b, near)

    def test_add_food(self):
        self.world.spawn_food(count=5)
        self.assertEqual(len(self.world.food), 5)

    def test_update_advances_tick(self):
        tick_before = self.world.tick
        self.world.spawn_organisms(5)
        self.world.update(1.0 / 60.0)
        self.assertGreater(self.world.tick, tick_before)

    def test_clear_population(self):
        self.world.spawn_organisms(5)
        self.world.spawn_food(count=3)
        self.world.clear_population()
        self.assertEqual(len(self.world.organisms), 0)
        self.assertEqual(len(self.world.food), 0)
        self.assertEqual(self.world.births, 0)

    def test_spawn_child_from_dna(self):
        dna = DNA.random()
        child = self.world.spawn_child_from_dna(dna, (50.0, 50.0))
        self.assertIsNotNone(child)
        self.assertIn(child, self.world.organisms)
        self.assertEqual(self.world.births, 1)

    def test_record_birth_and_death(self):
        dna = DNA.random()
        organism = Organism(dna, (50.0, 50.0))
        self.world.record_birth(organism)
        self.assertEqual(self.world.births, 1)
        self.world.register_death("age", organism.name)
        self.assertEqual(self.world.deaths.get("age"), 1)

    def test_resolve_collision(self):
        dna = DNA.random()
        a = Organism(dna, (50.0, 50.0))
        b = Organism(dna, (50.0, 50.0))
        self.world.add_organism(a)
        self.world.add_organism(b)
        # Place them overlapping
        a.position = (100.0, 100.0)
        b.position = (100.0 + a.radius * 0.5, 100.0)
        self.world._resolve_collision(a, b)
        # They should no longer be overlapping
        dist = ((a.position[0] - b.position[0]) ** 2 + (a.position[1] - b.position[1]) ** 2) ** 0.5
        self.assertGreaterEqual(dist, a.radius + b.radius - 0.1)

    def test_stats(self):
        stats = self.world.stats()
        self.assertIn("organisms", stats)
        self.assertIn("food", stats)
        self.assertIn("tick", stats)


if __name__ == "__main__":
    unittest.main()
