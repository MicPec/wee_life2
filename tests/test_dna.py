"""Tests for DNA genetics and naming."""

import random
import os
import subprocess
import sys
import unittest

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.genes import GENE_REGISTRY


class TestDNA(unittest.TestCase):
    def test_random_genome_length(self):
        dna = DNA.random(length=8)
        self.assertGreaterEqual(len(dna.genes), 1)
        self.assertLessEqual(len(dna.genes), 8)

    def test_random_genome_uses_only_registered_genes(self):
        dna = DNA.random()
        for gene in dna.genes:
            self.assertIn(gene.kind, GENE_REGISTRY)

    def test_name_is_deterministic(self):
        dna = DNA.random()
        name1 = dna.name()
        name2 = dna.name()
        self.assertEqual(name1, name2)
        self.assertIsInstance(name1, str)

    def test_signature_is_tuple(self):
        dna = DNA.random()
        sig = dna.signature()
        self.assertIsInstance(sig, tuple)
        self.assertEqual(len(sig), 6)

    def test_mutation_changes_something(self):
        dna = DNA.random(length=4)
        # Force a high mutation rate to almost guarantee a change
        original = [(g.kind, dict(g.params)) for g in dna.genes]
        for _ in range(100):
            dna.mutate(rate=0.9, strength=0.5)
            changed = any(g.kind != orig[0] or g.params != orig[1] for g, orig in zip(dna.genes, original))
            if changed:
                break
        else:
            self.fail("Mutation did not change any gene parameters after 100 attempts")

    def test_insertion_mutation_respects_spawn_weights(self):
        """Insertion must use GENE_SPAWN_WEIGHTS, not a flat pick -- otherwise
        structural mutation reintroduces deliberately rare genes at a uniform
        rate."""
        original_weights = config.GENE_SPAWN_WEIGHTS
        original_default = config.GENE_DEFAULT_SPAWN_WEIGHT
        try:
            config.GENE_SPAWN_WEIGHTS = {kind: 0.0 for kind in GENE_REGISTRY}
            config.GENE_SPAWN_WEIGHTS["jaw"] = 1.0
            config.GENE_DEFAULT_SPAWN_WEIGHT = 0.0
            for _ in range(50):
                dna = DNA([GENE_REGISTRY["leg"]()])
                dna.mutate(rate=0.0, strength=0.0, insertion_rate=1.0, deletion_rate=0.0)
                inserted = [g.kind for g in dna.genes if g.kind != "leg"]
                self.assertEqual(inserted, ["jaw"])
        finally:
            config.GENE_SPAWN_WEIGHTS = original_weights
            config.GENE_DEFAULT_SPAWN_WEIGHT = original_default

    def test_random_genome_respects_spawn_weights(self):
        """The founder-genome path shares the same weighted pick."""
        original_weights = config.GENE_SPAWN_WEIGHTS
        original_default = config.GENE_DEFAULT_SPAWN_WEIGHT
        try:
            config.GENE_SPAWN_WEIGHTS = {kind: 0.0 for kind in GENE_REGISTRY}
            config.GENE_SPAWN_WEIGHTS["jaw"] = 1.0
            config.GENE_DEFAULT_SPAWN_WEIGHT = 0.0
            for _ in range(20):
                dna = DNA.random(length=6)
                self.assertTrue(dna.genes)
                self.assertTrue(all(g.kind == "jaw" for g in dna.genes))
        finally:
            config.GENE_SPAWN_WEIGHTS = original_weights
            config.GENE_DEFAULT_SPAWN_WEIGHT = original_default

    def test_clone_is_equal(self):
        dna = DNA.random()
        cloned = dna.clone()
        self.assertEqual([g.kind for g in dna.genes], [g.kind for g in cloned.genes])

    def test_crossover_produces_child_with_parents_genes(self):
        random.seed(42)
        a = DNA.random(length=6)
        b = DNA.random(length=6)
        child = a.crossover(b)
        self.assertGreater(len(child.genes), 0)
        for gene in child.genes:
            self.assertIn(gene.kind, set(g.kind for g in a.genes + b.genes))

    def test_diversity_bounds(self):
        a = DNA.random(length=4)
        b = DNA.random(length=4)
        d = a.diversity(b)
        self.assertGreaterEqual(d, 0.0)
        self.assertLessEqual(d, 1.0)
        self.assertEqual(a.diversity(a), 0.0)

    def test_to_from_dict_roundtrip(self):
        dna = DNA.random()
        data = dna.to_dict()
        restored = DNA.from_dict(data)
        self.assertEqual([g.kind for g in dna.genes], [g.kind for g in restored.genes])

    def test_crossover_is_reproducible_across_hash_seeds(self):
        """A seeded crossover must not depend on set iteration order.

        `crossover` consumes RNG draws per gene kind, so iterating an unordered
        set made both the child's genome and every later random draw depend on
        PYTHONHASHSEED -- seeded runs were not reproducible between processes.
        """
        script = (
            "import random;"
            "from wee_life2.core.dna import DNA;"
            "random.seed(7);"
            "a=DNA.random(length=10); b=DNA.random(length=10);"
            "c=a.crossover(b);"
            "print(','.join(g.kind for g in c.genes), round(random.random(), 12))"
        )
        outputs = set()
        for hash_seed in ("0", "1", "2"):
            env = dict(os.environ, PYTHONHASHSEED=hash_seed)
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            outputs.add(result.stdout.strip())
        self.assertEqual(len(outputs), 1, f"crossover differed across hash seeds: {outputs}")


if __name__ == "__main__":
    unittest.main()
