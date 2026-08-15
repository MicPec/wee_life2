"""Smoke test for module imports."""

import unittest


class TestImports(unittest.TestCase):
    def test_core_imports(self):
        from wee_life2.core import config, dna, organism, world, map_storage
        from wee_life2.core.dna import DNA
        from wee_life2.core.organism import Organism, BodyPart
        from wee_life2.core.world import World

    def test_gene_imports(self):
        from wee_life2.genes import GENE_REGISTRY, Gene, BodyPartBlueprint
        from wee_life2.genes.eye import EyeGene
        from wee_life2.genes.scent import ScentGene
        from wee_life2.genes.jaw import JawGene
        from wee_life2.genes.leg import LegGene

    def test_render_imports(self):
        from wee_life2.render import Renderer, MapEditor

    def test_simulation_and_main_imports(self):
        from wee_life2.simulation import Simulation
        from wee_life2.main import main


if __name__ == "__main__":
    unittest.main()
