"""Tests for DNA genetics and naming."""

import random
import unittest

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
            changed = any(
                g.kind != orig[0] or g.params != orig[1]
                for g, orig in zip(dna.genes, original)
            )
            if changed:
                break
        else:
            self.fail("Mutation did not change any gene parameters after 100 attempts")

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


if __name__ == "__main__":
    unittest.main()
