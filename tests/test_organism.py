"""Tests for Organism."""

import math
import unittest

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.food import Food
from wee_life2.core.organism import Organism
from wee_life2.core.world import World
from wee_life2.genes.cannibal import CannibalGene
from wee_life2.genes.jaw import JawGene
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

    def test_zero_lifespan_does_not_crash(self):
        """A degenerate LIFESPAN_BASE=0 override must not divide by zero."""
        organism = Organism(DNA([LegGene()]), position=(100.0, 90.0))
        organism.base_lifespan = 0.0
        organism.lifespan = 0.0
        organism.update(self.world, 1.0 / config.FPS)  # must not raise
        self.assertTrue(organism.is_dead, "a zero-lifespan organism dies of age")

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

    def test_venom_damage_scales_with_dt(self):
        """Venom drains damage_per_tick * ticks per call, like every other
        drain in the file -- a 2-tick step must cost 2x damage."""
        organism = Organism(DNA([]), (100.0, 100.0))
        organism.energy = 100.0
        organism.add_venom(damage_per_tick=2.0, duration=10.0)
        organism._process_venom(self.world, 2.0 / config.TICKS_PER_SECOND)
        self.assertAlmostEqual(100.0 - organism.energy, 4.0, places=6)

    def test_venom_total_damage_is_dt_invariant(self):
        """Same stack, different step sizes: total damage must match (to
        within one step's worth -- an expiring stack is dropped before its
        final partial damage, which is a known off-by-one)."""
        a = Organism(DNA([]), (100.0, 100.0))
        b = Organism(DNA([]), (100.0, 100.0))
        for org in (a, b):
            org.energy = 200.0
            org.add_venom(damage_per_tick=1.5, duration=6.0)
        one_tick = 1.0 / config.TICKS_PER_SECOND
        while a.venom_stacks:
            a._process_venom(self.world, one_tick)
        while b.venom_stacks:
            b._process_venom(self.world, 2 * one_tick)
        self.assertAlmostEqual(
            200.0 - a.energy,
            200.0 - b.energy,
            delta=1.5 * 2.0,  # one 2-tick step's worth of damage
            msg="total venom damage must be dt-invariant to within one step",
        )

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

    def _edge_world(self):
        # No clear_map(): a border of wall tiles would exercise the wall
        # collision branch instead of the world-bounds branch.
        return World(1200, 900)

    def test_right_edge_bounce_reflects_heading(self):
        """An organism thrusting into the right edge must turn inward, not
        keep pressing against the edge and sliding along it."""
        world = self._edge_world()
        organism = Organism(DNA([LegGene()]), (0.0, 0.0))
        organism.angle = 0.0  # Organism.__init__ randomises angle; pin it.
        organism.wander_angle = 0.0
        organism.wander_timer = 1e9  # keep wander from re-randomising the heading
        organism.position = (world.max_x - organism.radius, 450.0)
        self.assertTrue(world.add_organism(organism))

        organism.update(world, 1.0 / config.FPS)
        self.assertLess(math.cos(organism.angle), 0.0)

        for _ in range(120):
            organism.update(world, 1.0 / config.FPS)
        self.assertLess(organism.position[0], world.max_x - organism.radius - 2.0)

    def test_top_edge_bounce_reflects_heading(self):
        world = self._edge_world()
        organism = Organism(DNA([LegGene()]), (600.0, 0.0))
        organism.angle = -math.pi / 2
        organism.wander_angle = -math.pi / 2
        organism.wander_timer = 1e9
        organism.position = (600.0, organism.radius)
        self.assertTrue(world.add_organism(organism))

        organism.update(world, 1.0 / config.FPS)
        self.assertGreater(math.sin(organism.angle), 0.0)

        for _ in range(120):
            organism.update(world, 1.0 / config.FPS)
        self.assertGreater(organism.position[1], organism.radius + 2.0)


class TestWallCollision(unittest.TestCase):
    """Bounce-first wall collision in `_apply_physics_and_movement`."""

    def setUp(self):
        self.world = World(240, 180, tile_size=20)
        self.world.clear_map()

    def _wall_column(self, col):
        for row in range(self.world.rows):
            self.world.set_tile(col, row, config.TILE_WALL)

    def _organism(self, position, angle, velocity):
        organism = Organism(DNA([]), position)
        organism.angle = angle  # Organism.__init__ randomises angle; pin it.
        organism.wander_angle = angle
        organism.velocity = velocity
        self.world.add_organism(organism)
        return organism

    def test_wall_bounce_reflects_heading(self):
        """Heading into a wall with open space behind must reflect both the
        blocked velocity component and the heading away from the wall."""
        self._wall_column(6)  # x in [120, 140)
        organism = self._organism((114.0, 90.0), angle=0.0, velocity=(1.5, 0.0))
        organism.update(self.world, 1.0 / config.FPS)
        # The bounce moves the organism to the reflected position, away from
        # the wall column at x in [120, 140).
        self.assertLess(organism.position[0], 114.0)
        self.assertLess(organism.velocity[0], 0.0)
        self.assertLess(math.cos(organism.angle), 0.0)
        self.assertEqual(organism.wander_angle, organism.angle)

    def test_wall_bounce_is_deterministic(self):
        """The wall branch consumes no randomness: identical state must give
        an identical resulting angle (the old random kick would differ)."""
        self._wall_column(6)
        organism = self._organism((114.0, 90.0), angle=0.0, velocity=(1.5, 0.0))
        organism.update(self.world, 1.0 / config.FPS)
        angle_first = organism.angle
        organism.position = (114.0, 90.0)
        organism.velocity = (1.5, 0.0)
        organism.angle = 0.0
        organism.wander_angle = 0.0
        organism.update(self.world, 1.0 / config.FPS)
        self.assertEqual(organism.angle, angle_first)

    def test_wall_slide_when_bounce_blocked(self):
        """In a dead end where the reflected step is also blocked, the
        organism slides along the open axis with the blocked component
        zeroed and its heading aligned to the slide direction."""
        self._wall_column(4)  # x in [80, 100): wall behind on -x
        self._wall_column(6)  # x in [120, 140): wall ahead on +x
        organism = self._organism((110.0, 90.0), angle=math.pi / 4, velocity=(1.0, 1.0))
        # dt=1.0 (60 ticks) makes both the forward and the reflected step
        # overshoot the corridor, so the bounce fails and the slide wins.
        organism.update(self.world, 1.0)
        self.assertEqual(organism.position[0], 110.0)
        self.assertGreater(organism.position[1], 90.0)
        self.assertEqual(organism.velocity[0], 0.0)
        self.assertGreater(organism.velocity[1], 0.0)
        self.assertAlmostEqual(organism.angle, math.pi / 2)


class TestJawGene(unittest.TestCase):
    """Jaw reach: the mouth is a point `reach` ahead whose grab radius is
    the jaw's own aperture (its `size`), not `reach` a second time."""

    def setUp(self):
        self.world = World(400, 300, tile_size=20)
        self.world.clear_map()

    def _biter(self, genes=None, aggression=0.9):
        genes = [JawGene()] if genes is None else genes
        jaw = next((g for g in genes if isinstance(g, JawGene)), None)
        org = Organism(DNA(genes), position=(200.0, 150.0))
        org.angle = 0.0
        org.aggression = aggression
        org.energy = 200.0
        self.world.add_organism(org)
        return org, jaw

    def _prey(self, position):
        prey = Organism(DNA([]), position=position)
        prey.energy = 50.0  # below biter.energy * prey_threshold (200 * 0.6)
        self.world.add_organism(prey)
        return prey

    def _finish_setup(self, org):
        self.world._rebuild_spatial_grid()
        org.drives.clear()
        org._nearby_organisms = None

    # With defaults (reach=12, size=7) the mouth sits at x=212 and the old
    # disc reached it out to x=230; the aperture band is x=212 +/- (7+r).

    def test_jaw_does_not_eat_food_behind_it(self):
        org, jaw = self._biter(aggression=0.0)
        food = Food(position=(196.0, 150.0))  # 16 behind the mouth; old disc grabbed it
        self.world.add_food(food)
        self._finish_setup(org)
        energy_before = org.energy
        jaw.apply(org, self.world, 0.0)
        self.assertIn(food, self.world.food)
        self.assertEqual(org.energy, energy_before)

    def test_jaw_eats_food_in_front(self):
        org, jaw = self._biter(aggression=0.0)
        food = Food(position=(218.0, 150.0))  # 6 ahead of the mouth, inside aperture
        self.world.add_food(food)
        self._finish_setup(org)
        energy_before = org.energy
        jaw.apply(org, self.world, 0.0)
        self.assertNotIn(food, self.world.food)
        self.assertGreater(org.energy, energy_before)

    def test_jaw_bite_range_is_not_doubled(self):
        """Prey inside the old 2x-reach band but outside the aperture must
        not be bitten."""
        org, jaw = self._biter()
        prey = self._prey((228.0, 150.0))  # 16 from the mouth; old band reached to ~17
        self._finish_setup(org)
        jaw.apply(org, self.world, 0.0)
        self.assertEqual(prey.energy, 50.0)
        self.assertFalse(prey.is_dead)

    def test_jaw_still_bites_prey_at_the_mouth(self):
        org, jaw = self._biter()
        prey = self._prey((216.0, 150.0))  # 4 from the mouth, inside aperture
        self._finish_setup(org)
        jaw.apply(org, self.world, 0.0)
        self.assertLess(prey.energy, 50.0)
        self.assertFalse(prey.is_dead)

    def test_bite_self_cost_comes_from_config(self):
        """The attacker's per-bite energy cost is config.ENERGY_COST_ATTACK,
        not a hardcoded literal."""
        org, jaw = self._biter()
        self._prey((216.0, 150.0))
        self._finish_setup(org)
        original = config.ENERGY_COST_ATTACK
        config.ENERGY_COST_ATTACK = 3.33
        try:
            energy_before = org.energy
            jaw.apply(org, self.world, 0.0)
            # The bite path changes nothing else on the attacker.
            self.assertAlmostEqual(energy_before - org.energy, 3.33, places=6)
        finally:
            config.ENERGY_COST_ATTACK = original

    def test_jaw_uses_neighbour_cache(self):
        """Bite/prey scanning must go through the per-tick spatial-grid cache
        like the other senses, not the full population list."""
        org, jaw = self._biter()
        self._prey((216.0, 150.0))
        self._finish_setup(org)
        self.assertIsNone(org._nearby_organisms)
        jaw.apply(org, self.world, 0.0)
        self.assertIsNotNone(org._nearby_organisms)

    def test_cannibal_uses_neighbour_cache(self):
        gene = CannibalGene()
        org = Organism(DNA([gene]), position=(200.0, 150.0))
        org.angle = 0.0
        self.world.add_organism(org)
        self._finish_setup(org)
        self.assertIsNone(org._nearby_organisms)
        gene.apply(org, self.world, 0.0)
        self.assertIsNotNone(org._nearby_organisms)


if __name__ == "__main__":
    unittest.main()
