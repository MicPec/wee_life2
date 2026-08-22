"""Tests for Organism."""

import math
import unittest

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.organism import Organism
from wee_life2.core.world import World
from wee_life2.genes.leg import LegGene


class TestOrganism(unittest.TestCase):
    def setUp(self):
        self.world = World(240, 180, tile_size=20)
        self.world.clear_map()

    def test_build_body_creates_parts(self):
        dna = DNA.random()
        organism = Organism(dna)
        self.assertGreater(len(organism.body_parts), 0)
        self.assertTrue(any(bp.blueprint.kind == "body" for bp in organism.body_parts))

    def test_radius_cap(self):
        dna = DNA.random(length=20)
        organism = Organism(dna)
        if config.MAX_ORGANISM_RADIUS > 0:
            self.assertLessEqual(organism.radius, config.MAX_ORGANISM_RADIUS)

    def test_body_parts_sorted_by_size(self):
        dna = DNA.random()
        organism = Organism(dna)
        sizes = [bp.blueprint.size for bp in organism.body_parts]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_nearby_organisms_cache(self):
        dna = DNA.random()
        a = self.world.spawn_organism(dna, (50.0, 50.0))
        b = self.world.spawn_organism(dna, (60.0, 60.0))
        c = self.world.spawn_organism(dna, (200.0, 200.0))
        self.world._rebuild_spatial_grid()
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertIsNotNone(c)
        nearby = a.nearby_organisms(self.world, 100.0)
        self.assertIn(b, nearby)
        self.assertNotIn(c, nearby)
        self.assertNotIn(a, nearby)
        # A smaller radius should still use the cached list.
        nearby2 = a.nearby_organisms(self.world, 50.0)
        self.assertIn(b, nearby2)
        # A larger radius must rebuild and include the distant organism.
        nearby3 = a.nearby_organisms(self.world, 250.0)
        self.assertIn(b, nearby3)
        self.assertIn(c, nearby3)

    def test_update_starvation(self):
        dna = DNA.random()
        organism = Organism(dna, (50.0, 50.0))
        organism.energy = -1.0
        organism.update(self.world, 0.001)
        self.assertTrue(organism.is_dead)

    def test_die_leaves_food(self):
        dna = DNA.random()
        organism = Organism(dna, (100.0, 100.0))
        food_before = len(self.world.food)
        organism.die(self.world)
        self.assertTrue(organism.is_dead)
        # Food is probabilistic; run enough times to almost guarantee at least one
        found = False
        for _ in range(100):
            if len(self.world.food) > food_before:
                found = True
                break
            organism = Organism(dna, (100.0, 100.0))
            organism.die(self.world)
        self.assertTrue(found)

    def test_mate(self):
        dna = DNA.random()
        a = Organism(dna, (80.0, 80.0))
        b = Organism(dna, (80.0, 80.0))
        a.age = a.maturity_min_age + 1
        b.age = b.maturity_min_age + 1
        a.energy = 1000.0
        b.energy = 1000.0
        child = a.mate(b)
        self.assertIsNotNone(child)
        self.assertIsInstance(child.dna, DNA)
        self.assertEqual(child.generation, max(a.generation, b.generation) + 1)

    def test_water_penalty(self):
        # Ensure we use a non-amphibious DNA sample.
        dna = DNA.random()
        for _ in range(100):
            if not any(g.kind == "amphibious" for g in dna.genes):
                break
            dna = DNA.random()
        organism = Organism(dna, (100.0, 100.0))
        self.assertTrue(self.world.add_organism(organism))
        # Place organism in a water tile
        col = int(organism.position[0] / self.world.tile_size)
        row = int(organism.position[1] / self.world.tile_size)
        self.world.tile_map.tiles[row][col] = config.TILE_WATER
        energy_before = organism.energy
        organism.update(self.world, 1.0)
        # Non-amphibious organisms lose energy in water
        self.assertLess(organism.energy, energy_before)

    def test_hazard_damage(self):
        # Use an empty genome so metabolism/regeneration genes cannot mask the damage.
        dna = DNA([])
        organism = Organism(dna, (100.0, 100.0))
        self.assertTrue(self.world.add_organism(organism))
        col = int(organism.position[0] / self.world.tile_size)
        row = int(organism.position[1] / self.world.tile_size)
        self.world.tile_map.tiles[row][col] = config.TILE_LAVA
        energy_before = organism.energy
        organism.update(self.world, 1.0)
        self.assertLess(organism.energy, energy_before)

    def test_heal_energy_gain(self):
        # Use an empty genome so metabolism/regeneration genes cannot mask the heal.
        dna = DNA([])
        organism = Organism(dna, (100.0, 100.0))
        organism.energy = 80.0  # below max
        self.assertTrue(self.world.add_organism(organism))
        col = int(organism.position[0] / self.world.tile_size)
        row = int(organism.position[1] / self.world.tile_size)
        self.world.tile_map.tiles[row][col] = config.TILE_HEAL
        energy_before = organism.energy
        organism.update(self.world, 1.0)
        self.assertGreater(organism.energy, energy_before)

    def test_leg_age_slowdown(self):
        """Older organisms move slower than young ones."""
        dna = DNA([LegGene({"strength": 0.5, "agility": 1.0})])
        organism = Organism(dna, (100.0, 100.0))
        organism.angle = 0.0
        self.assertTrue(self.world.add_organism(organism))

        # Young organism at 50% of lifespan should have full speed.
        organism.age = organism.lifespan * 0.5
        organism.drives = [(0.0, 1.0)]
        organism.update(self.world, 1.0)
        young_speed = math.hypot(organism.velocity[0], organism.velocity[1])

        # Old organism at 90% of lifespan should be significantly slower.
        organism.position = (100.0, 100.0)
        organism.velocity = (0.0, 0.0)
        organism.angle = 0.0
        organism.age = organism.lifespan * 0.9
        organism.drives = [(0.0, 1.0)]
        organism.update(self.world, 1.0)
        old_speed = math.hypot(organism.velocity[0], organism.velocity[1])

        self.assertGreater(young_speed, old_speed)

    def test_baby_visual_scale(self):
        """Newborn organisms start at BABY_SIZE_FRACTION visual scale."""
        dna = DNA.random()
        organism = Organism(dna, (100.0, 100.0))
        organism.age = 0.0
        self.assertAlmostEqual(organism.visual_scale, config.BABY_SIZE_FRACTION)

    def test_mature_visual_scale(self):
        """Organisms at maturity age have full visual scale."""
        dna = DNA.random()
        organism = Organism(dna, (100.0, 100.0))
        organism.age = organism.base_lifespan * config.MATURITY_MIN_FRACTION
        self.assertAlmostEqual(organism.visual_scale, 1.0)
        organism.age = organism.base_lifespan * config.MATURITY_MIN_FRACTION + 1
        self.assertAlmostEqual(organism.visual_scale, 1.0)

    def test_visual_scale_linear(self):
        """Visual scale grows linearly between baby and maturity."""
        dna = DNA.random()
        organism = Organism(dna, (100.0, 100.0))
        target_age = organism.base_lifespan * config.MATURITY_MIN_FRACTION
        organism.age = target_age / 2
        expected = config.BABY_SIZE_FRACTION + (1.0 - config.BABY_SIZE_FRACTION) * 0.5
        self.assertAlmostEqual(organism.visual_scale, expected)

    def test_visual_scale_does_not_affect_radius(self):
        """Visual growth must not change the physical radius."""
        dna = DNA.random()
        organism = Organism(dna, (100.0, 100.0))
        radius_at_birth = organism.radius
        organism.age = organism.base_lifespan * config.MATURITY_MIN_FRACTION
        self.assertEqual(organism.radius, radius_at_birth)
        organism.age = organism.base_lifespan * config.MATURITY_MIN_FRACTION + 100
        self.assertEqual(organism.radius, radius_at_birth)


if __name__ == "__main__":
    unittest.main()
