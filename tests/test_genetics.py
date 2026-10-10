"""Regression tests for the core genetic machinery and energy budget."""

import math
import random
import unittest

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.organism import Organism
from wee_life2.core.world import World
from wee_life2.genes import GENE_REGISTRY
from wee_life2.genes.asexual import AsexualGene
from wee_life2.genes.base import Gene
from wee_life2.genes.fat import FatGene
from wee_life2.genes.metabolism import MetabolismGene
from wee_life2.genes.regeneration import RegenerationGene


class TestCrossover(unittest.TestCase):
    def test_single_copy_gene_is_inherited(self):
        """A gene carried once by one parent must be transmissible.

        The old count-averaging crossover computed int(round(0.5)) == 0
        (banker's rounding) and dropped such genes in 100% of matings.
        """
        a = DNA([GENE_REGISTRY["leg"](), GENE_REGISTRY["jaw"](), GENE_REGISTRY["venom"]()])
        b = DNA([GENE_REGISTRY["leg"](), GENE_REGISTRY["jaw"]()])
        inherited = sum(1 for _ in range(400) if any(g.kind == "venom" for g in a.crossover(b).genes))
        self.assertTrue(100 < inherited < 300, f"expected ~50% inheritance, got {inherited}/400")

    def test_blended_parameters_are_intermediate(self):
        """Arithmetic crossover: some children get averaged parameter values."""
        a = DNA([GENE_REGISTRY["leg"]({"strength": 1.0})])
        b = DNA([GENE_REGISTRY["leg"]({"strength": 2.0})])
        intermediates = [
            g.params["strength"] for _ in range(200) for g in a.crossover(b).genes if 1.0 < g.params["strength"] < 2.0
        ]
        self.assertGreater(len(intermediates), 0)


class TestMutation(unittest.TestCase):
    def test_zero_parameter_can_evolve_up(self):
        gene = MetabolismGene()
        self.assertEqual(gene.params["radiation_resistance"], 0.0)
        for _ in range(2000):
            gene.mutate(rate=1.0, strength=0.5)
            if gene.params["radiation_resistance"] > 0.0:
                return
        self.fail("radiation_resistance stayed pinned at 0.0")

    def test_no_downward_drift(self):
        """Neutral mutation must not systematically shrink a parameter."""
        values = []
        for _ in range(200):
            gene = GENE_REGISTRY["leg"]({"strength": 1.0})
            for _ in range(200):
                gene.mutate(rate=1.0, strength=config.MUTATION_STRENGTH)
            values.append(gene.params["strength"])
        values.sort()
        self.assertGreater(values[len(values) // 2], 0.5)

    def test_param_bounds_are_respected(self):
        gene = MetabolismGene()
        fat = FatGene()
        for _ in range(5000):
            gene.mutate(rate=1.0, strength=0.9)
            self.assertLessEqual(gene.params["efficiency"], 0.85)  # higher would delete the idle drain
            self.assertGreaterEqual(gene.params["lifespan_factor"], 0.2)
            fat.mutate(rate=1.0, strength=0.9)
            self.assertLessEqual(fat.params["reserve_factor"], 1.0)  # higher would never mobilise

    def test_constructor_sanitizes_out_of_domain_params(self):
        """Genomes loaded from disk or hand-written get the same domain rules
        as mutated ones: bounds, angle wrapping and default-sign locking."""
        gene = MetabolismGene({"efficiency": 1.2, "lifespan_factor": 0.0})
        self.assertEqual(gene.params["efficiency"], 0.85)
        self.assertEqual(gene.params["lifespan_factor"], 0.2)
        eye = GENE_REGISTRY["eye"]({"direction": 7.0})
        self.assertLessEqual(abs(eye.params["direction"]), math.pi)
        fear = GENE_REGISTRY["fear"]({"danger_weight": 1.8})
        self.assertEqual(fear.params["danger_weight"], 0.0)

    def test_asexual_constructor_sanitizes_out_of_domain_params(self):
        """Reproduction limiters loaded or hand-written to zero must be
        clamped back into bounds, same as mutated ones."""
        gene = AsexualGene({"cooldown": 0.0, "energy_cost": 0.0, "mutation_multiplier": 0.0})
        self.assertEqual(gene.params["cooldown"], 100.0)
        self.assertEqual(gene.params["energy_cost"], float(config.ENERGY_COST_MATE))
        self.assertEqual(gene.params["mutation_multiplier"], 0.5)

    def test_asexual_bounds_survive_mutation_pressure(self):
        """Unbounded, cooldown/energy_cost can mutate to zero and bypass the
        density check and cost guard entirely."""
        gene = AsexualGene()
        for _ in range(500):
            gene.mutate(rate=1.0, strength=1.0)
            self.assertGreaterEqual(gene.params["cooldown"], 100.0)
            self.assertLessEqual(gene.params["cooldown"], 5000.0)
            self.assertGreaterEqual(gene.params["energy_cost"], float(config.ENERGY_COST_MATE))
            self.assertLessEqual(gene.params["energy_cost"], 400.0)
            self.assertGreaterEqual(gene.params["mutation_multiplier"], 0.5)
            self.assertLessEqual(gene.params["mutation_multiplier"], 5.0)
            # __init__ calls random.uniform(0.0, self._effective_cooldown());
            # a non-positive cooldown would be a latent crash/degenerate timer.
            self.assertGreater(gene._effective_cooldown(), 0.0)

    def test_repulsive_weights_keep_their_sign(self):
        gene = GENE_REGISTRY["eye"]()
        for _ in range(2000):
            gene.mutate(rate=1.0, strength=0.9)
            self.assertLessEqual(gene.params["threat_weight"], 0.0)


class TestHeritability(unittest.TestCase):
    def test_regeneration_count_survives_cloning(self):
        """count is a genome parameter, not random instance state.

        The old RegenerationGene.__init__ re-rolled _count at random, so every
        clone could rebuild the body with a different number of parts (and a
        different upkeep), detached from the genome.
        """
        parent = RegenerationGene({"count": 3.0})
        expected = len(parent.body_parts((0, 0, 0)))
        self.assertEqual(expected, 3)
        for _ in range(20):
            clone = parent.clone()
            self.assertEqual(len(clone.body_parts((0, 0, 0))), expected)

    def test_gene_side_is_heritable(self):
        """clone() rebuilds from params alone, so body side must live in
        params or it re-rolls on every clone."""
        covered = [k for k, c in GENE_REGISTRY.items() if "side" in c.default_params]
        self.assertEqual(len(covered), 8, msg=f"side-carrying genes changed: {covered}")
        for kind, gene_cls in GENE_REGISTRY.items():
            if "side" not in gene_cls.default_params:
                continue
            gene = gene_cls()
            clone = gene.clone()
            self.assertEqual(clone.params["side"], gene.params["side"], msg=kind)
            self.assertEqual(clone.side, gene.side, msg=kind)

    def test_fresh_genes_get_random_sides(self):
        """Founders must still vary: a gene created without an inherited
        `side` randomises it rather than defaulting to 0.5."""
        sides = {GENE_REGISTRY["eye"]().side for _ in range(60)}
        self.assertEqual(sides, {1, -1})

    def test_side_survives_blend_and_mutation(self):
        gene = GENE_REGISTRY["eye"]()
        for _ in range(500):
            gene.mutate(rate=1.0, strength=1.0)
            self.assertGreaterEqual(gene.params["side"], 0.0)
            self.assertLessEqual(gene.params["side"], 1.0)
        a = GENE_REGISTRY["eye"]({"side": 0.1})
        b = GENE_REGISTRY["eye"]({"side": 0.9})
        child = a.blend(b)
        self.assertGreaterEqual(child.params["side"], 0.0)
        self.assertLessEqual(child.params["side"], 1.0)

    def test_body_layout_is_reproducible_from_dna(self):
        """A cloned genome must rebuild the same body-part layout.

        Colours are excluded on purpose: _build_body() calls random_color()
        when the genome has no color gene, so colours legitimately differ."""
        dna = DNA(
            [
                GENE_REGISTRY[kind]({"direction": 0.0} if kind == "eye" else {})
                for kind in (
                    "eye",
                    "scent",
                    "fear",
                    "memory",
                    "venom",
                    "touch",
                    "toxin_gland",
                    "pheromone",
                )
            ]
        )
        expected = sorted(bp.blueprint.offset for bp in Organism(dna).body_parts)
        # Seed each clone so a pre-fix all-same-side streak can't fluke a pass.
        for i in range(20):
            random.seed(i)
            clone = Organism(dna.clone())
            actual = sorted(bp.blueprint.offset for bp in clone.body_parts)
            self.assertEqual(actual, expected)

    def test_mutated_count_expresses_immediately(self):
        """A count changed after construction (mutation/blend) must show up in
        this generation's body, not only in the next clone."""
        gene = GENE_REGISTRY["leg"]({"count": 5.0})
        self.assertEqual(len(gene.body_parts((0, 0, 0))), 5)
        gene.params["count"] = 9.0  # simulate a post-construction mutation
        self.assertEqual(gene.part_count, 9)
        self.assertEqual(len(gene.body_parts((0, 0, 0))), 9)


class TestAngularParams(unittest.TestCase):
    def test_no_gene_overrides_mutate(self):
        """All genes must mutate through the shared Gene.mutate implementation.

        An old EyeGene.mutate override silently kept the pre-rework
        multiplicative logic and ignored param_bounds/wrap_params entirely.
        """
        for gene_cls in GENE_REGISTRY.values():
            self.assertIs(gene_cls.mutate, Gene.mutate, msg=gene_cls.kind)

    def test_angular_mutation_wraps_within_pi(self):
        gene = GENE_REGISTRY["jaw"]({"angle": 3.13})
        for _ in range(500):
            gene.mutate(rate=1.0, strength=1.0)
            self.assertLessEqual(abs(gene.params["angle"]), math.pi)

    def test_blended_angles_take_the_short_arc(self):
        """Blending two near-backward angles must not produce a forward child."""
        a = GENE_REGISTRY["eye"]({"direction": 3.1})
        b = GENE_REGISTRY["eye"]({"direction": -3.1})
        child = a.blend(b)
        self.assertGreater(abs(child.params["direction"]), 3.0)

    def test_antipodal_blend_keeps_a_parent_angle(self):
        """Exactly opposite angles have no circular mean; atan2(0, 0) == 0
        would fabricate a forward-facing child out of two sideways eyes."""
        a = GENE_REGISTRY["eye"]({"direction": math.pi / 2})
        b = GENE_REGISTRY["eye"]({"direction": -math.pi / 2})
        child = a.blend(b)
        self.assertAlmostEqual(abs(child.params["direction"]), math.pi / 2, places=5)


class TestEnergyBudget(unittest.TestCase):
    def setUp(self):
        self.world = World(400, 300, tile_size=20)
        self.world.clear_map()

    def _drain(self, dna, ticks=200):
        organism = Organism(dna, (200.0, 150.0))
        self.world.add_organism(organism)
        before = organism.energy + organism.fat_reserve
        for _ in range(ticks):
            organism.update(self.world, 1.0 / 60.0)
        return before - (organism.energy + organism.fat_reserve)

    def test_heavier_genome_costs_more_upkeep(self):
        light = DNA([GENE_REGISTRY["metabolism"]()])
        heavy = DNA([GENE_REGISTRY["metabolism"]()] + [GENE_REGISTRY["armor"]() for _ in range(6)])
        self.assertGreater(Organism(heavy).upkeep, Organism(light).upkeep)
        self.assertGreater(self._drain(heavy), self._drain(light))

    def test_fat_gene_creates_no_energy(self):
        """Fat may only return energy it previously stored."""
        organism = Organism(DNA([FatGene({"storage": 0.8, "reserve_factor": 0.3})]), (200.0, 150.0))
        self.world.add_organism(organism)
        organism.energy = organism.max_energy * 0.4
        total_before = organism.energy + organism.fat_reserve
        for _ in range(300):
            organism.update(self.world, 1.0 / 60.0)
            self.assertLessEqual(organism.energy + organism.fat_reserve, total_before + 1e-6)

    def test_fat_stores_surplus_and_mobilises_it(self):
        organism = Organism(DNA([FatGene({"storage": 0.8, "reserve_factor": 0.3})]), (200.0, 150.0))
        self.world.add_organism(organism)
        for _ in range(200):  # well-fed: deposits surplus
            organism.energy = organism.max_energy
            organism.update(self.world, 1.0 / 60.0)
        self.assertGreater(organism.fat_reserve, 0.0)
        stored = organism.fat_reserve
        organism.energy = organism.max_energy * 0.2
        for _ in range(200):  # hungry: mobilises the reserve
            organism.update(self.world, 1.0 / 60.0)
        self.assertLess(organism.fat_reserve, stored)

    def test_mixed_fat_genes_share_one_capacity(self):
        """Mixed-storage fat genes must not truncate or destroy the shared reserve.

        The per-gene capacity clamp used to pin the reserve at the smallest
        gene's storage and annihilate the other genes' deposits every tick.
        """
        organism = Organism(
            DNA(
                [
                    FatGene({"storage": 0.3, "reserve_factor": 0.3}),
                    FatGene({"storage": 0.1, "reserve_factor": 0.3}),
                ]
            ),
            (200.0, 150.0),
        )
        self.world.add_organism(organism)
        for _ in range(800):  # well-fed: deposits surplus until the shared cap
            organism.energy = organism.max_energy
            organism.update(self.world, 1.0 / 60.0)
        # The smaller gene's storage no longer caps the shared pool
        self.assertGreater(organism.fat_reserve, config.BASE_ENERGY * 0.1 + 1.0)
        self.assertAlmostEqual(organism.fat_reserve, organism.fat_capacity, delta=0.1)
        # A fed tick at saturation must cost only upkeep, not destroy deposits
        organism.energy = organism.max_energy
        before = organism.energy + organism.fat_reserve
        organism.update(self.world, 1.0 / 60.0)
        self.assertAlmostEqual(before - (organism.energy + organism.fat_reserve), organism.upkeep, places=3)

    def test_metabolism_efficiency_slows_idle_drain(self):
        """efficiency must scale the real upkeep, not a fixed side drain."""
        wasteful = DNA([GENE_REGISTRY["metabolism"]({"efficiency": 0.0})])
        thrifty = DNA([GENE_REGISTRY["metabolism"]({"efficiency": 0.8})])
        self.assertGreater(self._drain(wasteful), self._drain(thrifty))

    def test_regeneration_draws_from_fat_reserve(self):
        """Healing must tap the fat reserve before the ambient trickle.

        The old apply() only added energy out of nothing according to a
        docstring that claimed it converted a reserve.
        """
        organism = Organism(
            DNA(
                [
                    FatGene({"storage": 0.8, "reserve_factor": 1.0}),  # never mobilises
                    RegenerationGene({"rate": 0.5, "efficiency": 0.6, "threshold": 0.9}),
                ]
            ),
            (200.0, 150.0),
        )
        self.world.add_organism(organism)
        organism.fat_reserve = 10.0
        # The fat gene lifts max_energy to BASE_ENERGY * 1.8 during the tick
        organism.energy = config.BASE_ENERGY * 1.8 * 0.2
        before = organism.energy + organism.fat_reserve
        organism.update(self.world, 1.0 / 60.0)
        # heal = 0.5 * (0.9 - 0.2) = 0.35, taken entirely from the reserve
        self.assertAlmostEqual(organism.fat_reserve, 10.0 - 0.35, places=5)
        # Total energy only dropped by upkeep; no free energy was created
        self.assertAlmostEqual(before - (organism.energy + organism.fat_reserve), organism.upkeep, places=5)

    def test_capped_bulk_still_costs_upkeep(self):
        """Mass is measured before the radius cap, so two organisms shrunk to
        the same MAX_ORGANISM_RADIUS must not pay the same upkeep."""
        compact = DNA([GENE_REGISTRY["leg"]({"count": 4.0})])
        bulky = DNA([GENE_REGISTRY["leg"]({"count": 16.0})])
        a, b = Organism(compact), Organism(bulky)
        self.assertEqual(a.radius, config.MAX_ORGANISM_RADIUS)
        self.assertEqual(b.radius, config.MAX_ORGANISM_RADIUS)
        self.assertGreater(b.mass_ratio, a.mass_ratio)
        self.assertGreater(b.upkeep, a.upkeep)

    def test_zero_range_sensors_do_not_crash(self):
        """A range mutated down to exactly 0 disables the sensor; it must not
        divide by zero (eye/scent compute 1/range up front, and touch can hit
        a same-tile obstacle at distance 0)."""
        organism = Organism(
            DNA(
                [
                    GENE_REGISTRY["eye"]({"range": 0.0}),
                    GENE_REGISTRY["scent"]({"range": 0.0}),
                    GENE_REGISTRY["touch"]({"range": 0.0}),
                    GENE_REGISTRY["fear"]({"range": 0.0, "alarm_range": 0.0}),
                    GENE_REGISTRY["cannibal"]({"hunt_range": 0.0}),
                ]
            ),
            (200.0, 150.0),
        )
        self.world.add_organism(organism)
        # Stand on a lava tile so touch's same-cell obstacle path is exercised
        col = int(200.0 // self.world.tile_map.tile_size)
        row = int(150.0 // self.world.tile_map.tile_size)
        self.world.tile_map.tiles[row][col] = self.world.TILE_LAVA
        for _ in range(20):
            organism.update(self.world, 1.0 / 60.0)

    def test_upkeep_never_goes_negative(self):
        """An oversized MASS_UPKEEP_FACTOR must not make idle upkeep an energy source."""
        original = config.MASS_UPKEEP_FACTOR
        config.MASS_UPKEEP_FACTOR = 5.0
        try:
            organism = Organism(DNA([GENE_REGISTRY["leg"]()]))
            self.assertGreaterEqual(organism.upkeep, 0.0)
        finally:
            config.MASS_UPKEEP_FACTOR = original


class TestLineage(unittest.TestCase):
    def setUp(self):
        self.world = World(400, 300, tile_size=20)
        self.world.clear_map()

    def test_children_record_parent_uids(self):
        dna = DNA.random()
        a = self.world.spawn_organism(dna.clone(), (100.0, 100.0))
        b = self.world.spawn_organism(dna.clone(), (110.0, 100.0))
        for parent in (a, b):
            parent.age = parent.maturity_min_age + 1
            parent.energy = 1000.0
        child = a.mate(b)
        self.assertIsNotNone(child)
        self.assertEqual(set(child.parent_uids), {a.uid, b.uid})

        clone = self.world.spawn_child_from_dna(a.dna.clone(), (120.0, 100.0), parent=a)
        self.assertEqual(clone.parent_uids, (a.uid,))


if __name__ == "__main__":
    unittest.main()
