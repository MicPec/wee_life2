"""Tests for per-organism generation tracking."""

import unittest
from unittest.mock import patch

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.organism import Organism
from wee_life2.core.world import World
from wee_life2.genes.asexual import AsexualGene


class TestGeneration(unittest.TestCase):
    def setUp(self):
        self.world = World(240, 180, tile_size=20)
        self.world.clear_map()

    def test_default_generation_is_one(self):
        organism = Organism(DNA.random(), (50.0, 50.0))
        self.assertEqual(organism.generation, 1)

    def test_sexual_generation_uses_max_parent(self):
        dna = DNA.random()
        a = Organism(dna, (80.0, 80.0), generation=3)
        b = Organism(dna, (80.0, 80.0), generation=7)
        a.age = a.maturity_min_age + 1
        b.age = b.maturity_min_age + 1
        a.energy = 1000.0
        b.energy = 1000.0
        child = a.mate(b)
        self.assertIsNotNone(child)
        self.assertEqual(child.generation, 8)

    def test_asexual_increments_generation(self):
        gene = AsexualGene({"cooldown": 1.0, "energy_cost": 1.0, "mutation_multiplier": 1.0})
        dna = DNA([gene])
        organism = Organism(dna, (100.0, 100.0), generation=5)
        self.assertTrue(self.world.add_organism(organism))
        organism.age = organism.lifespan * (config.ASEXUAL_MATURITY_MIN_FRACTION + 0.05)
        organism.energy = 1000.0
        gene._timer = 0.0
        # Keep random.random() high so the death-on-birth chance never triggers.
        with patch("wee_life2.genes.asexual.random.random", return_value=0.99):
            gene.apply(organism, self.world, 1.0 / 60.0)
        children = [o for o in self.world.organisms if o is not organism]
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].generation, 6)
        # record_birth must be counted once, not twice.
        self.assertEqual(self.world.births, 1)

    def test_world_stats_generation(self):
        self.world.spawn_organism(DNA.random(), (50.0, 50.0))
        stats = self.world.stats()
        self.assertEqual(stats["max_generation"], 1)
        self.assertEqual(stats["min_generation"], 1)

    def test_clear_population_resets_generation_stats(self):
        self.world.spawn_organism(DNA.random(), (50.0, 50.0))
        self.world.clear_population()
        stats = self.world.stats()
        self.assertEqual(stats["max_generation"], 0)
        self.assertEqual(stats["min_generation"], 0)


if __name__ == "__main__":
    unittest.main()
