"""Tests for core.snapshot round-trips and RunLogger snapshot integration."""

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.food import Food
from wee_life2.core.map_storage import MapStorage
from wee_life2.core.organism import MemoryEntry
from wee_life2.core.snapshot import world_from_dict, world_to_dict
from wee_life2.core.world import World
from wee_life2.simulation import Simulation
from wee_life2.stats import RunLogger


def _populated_world() -> World:
    world = World(240, 180, tile_size=20)
    world.clear_map()
    world.spawn_organism(DNA.random(), (50.0, 50.0))
    world.spawn_organism(DNA.random(), (150.0, 120.0))
    world.spawn_organism(DNA.random(), (200.0, 60.0))
    world.add_food(Food(position=(80.0, 90.0), energy=33.0, is_poison=True, age=12.5))
    org = world.organisms[0]
    org.parent_uids = (org.uid, 999)
    org.fat_reserve = 12.5
    org.add_venom(damage_per_tick=1.5, duration=10.0)
    org.memory.append(MemoryEntry(position=(1.0, 2.0), tile_type=config.TILE_WALL, created_tick=5.0))
    world.births = 7
    world.births_by_species = {"sp": 7}
    world.register_death("age", "sp")
    for _ in range(5):
        world.update(1.0 / config.TICKS_PER_SECOND)
    return world


def _restored(world: World) -> World:
    target = World(world.width, world.height, tile_size=world.tile_size)
    target.clear_map()
    world_from_dict(target, world_to_dict(world))
    return target


class TestSnapshotRoundTrip(unittest.TestCase):
    def test_round_trip_restores_world(self):
        world = _populated_world()
        restored = _restored(world)

        self.assertAlmostEqual(restored.tick, world.tick, delta=0.001)
        self.assertEqual(restored.save_tiles(), world.save_tiles())
        self.assertEqual(restored.births, world.births)
        self.assertEqual(restored.deaths, world.deaths)
        self.assertEqual(restored.births_by_species, world.births_by_species)
        self.assertEqual(restored.deaths_by_species, world.deaths_by_species)
        self.assertEqual(len(restored.organisms), len([o for o in world.organisms if not o.is_dead]))
        self.assertEqual(len(restored.food), len(world.food))

        by_uid = {o.uid: o for o in restored.organisms}
        for o in world.organisms:
            if o.is_dead:
                continue
            r = by_uid[o.uid]
            self.assertEqual([g.kind for g in r.dna.genes], [g.kind for g in o.dna.genes])
            # from_dict re-constrains params, so floats may shift a few ulp.
            for rg, og in zip(r.dna.genes, o.dna.genes):
                self.assertEqual(rg.params.keys(), og.params.keys())
                for key in og.params:
                    self.assertAlmostEqual(rg.params[key], og.params[key], places=10)
            self.assertAlmostEqual(r.position[0], o.position[0], delta=0.001)
            self.assertAlmostEqual(r.position[1], o.position[1], delta=0.001)
            self.assertAlmostEqual(r.velocity[0], o.velocity[0], delta=0.001)
            self.assertAlmostEqual(r.velocity[1], o.velocity[1], delta=0.001)
            self.assertAlmostEqual(r.angle, o.angle, delta=0.001)
            self.assertAlmostEqual(r.energy, o.energy, delta=0.001)
            self.assertAlmostEqual(r.age, o.age, delta=0.001)
            self.assertEqual(r.generation, o.generation)
            self.assertEqual(r.parent_uids, o.parent_uids)
            self.assertAlmostEqual(r.fat_reserve, o.fat_reserve, delta=0.001)
            self.assertEqual(
                [(s.damage_per_tick, s.remaining) for s in r.venom_stacks],
                [(s.damage_per_tick, s.remaining) for s in o.venom_stacks],
            )
            self.assertEqual(
                [(m.position, m.tile_type, m.created_tick) for m in r.memory],
                [(m.position, m.tile_type, m.created_tick) for m in o.memory],
            )

        for f, rf in zip(world.food, restored.food):
            self.assertAlmostEqual(rf.position[0], f.position[0], delta=0.001)
            self.assertAlmostEqual(rf.energy, f.energy, delta=0.001)
            self.assertEqual(rf.is_poison, f.is_poison)
            self.assertAlmostEqual(rf.age, f.age, delta=0.001)

    def test_uid_sequence_does_not_reuse_uids(self):
        world = _populated_world()
        restored = _restored(world)
        existing = {o.uid for o in restored.organisms}
        new = restored.spawn_organism(DNA.random(), (30.0, 30.0))
        self.assertIsNotNone(new)
        self.assertNotIn(new.uid, existing)

    def test_restored_world_keeps_running(self):
        world = _populated_world()
        restored = _restored(world)
        for _ in range(10):
            restored.update(1.0 / config.TICKS_PER_SECOND)
        self.assertGreater(restored.tick, world.tick - 0.001)
        # The rebuilt spatial grid must actually serve queries.
        near = list(restored.organisms_near((0.0, 0.0), 10000.0))
        self.assertEqual(len(near), len([o for o in restored.organisms if not o.is_dead]))

    def test_version_guard(self):
        world = _populated_world()
        target = World(world.width, world.height, tile_size=world.tile_size)
        with self.assertRaises(ValueError):
            world_from_dict(target, {"version": 99})

    def test_geometry_mismatch_rejected(self):
        world = _populated_world()
        data = world_to_dict(world)
        data["world"]["width"] = world.width + 1.0
        target = World(world.width, world.height, tile_size=world.tile_size)
        with self.assertRaises(ValueError):
            world_from_dict(target, data)


class TestRunLoggerSnapshot(unittest.TestCase):
    def test_snapshot_written_at_interval(self):
        old_interval = config.STATS_SNAPSHOT_INTERVAL
        old_base = config.STATS_BASE_DIR
        config.STATS_SNAPSHOT_INTERVAL = 10
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.STATS_BASE_DIR = tmp
                world = World(240, 180, tile_size=20)
                world.clear_map()
                world.spawn_organism(DNA.random(), (50.0, 50.0))
                logger = RunLogger(world, enabled=True)
                try:
                    shots = []
                    world.tick = 11.0
                    logger.step(world, 0.0, screenshot=shots.append)
                    snaps = list((logger.run_dir / "snapshots").glob("snapshot_*.json"))
                    self.assertEqual(len(snaps), 1)
                    self.assertEqual(len(shots), 1)
                    self.assertTrue(str(shots[0]).endswith(".png"))
                    data = json.loads(snaps[0].read_text(encoding="utf-8"))
                    target = World(240, 180, tile_size=20)
                    world_from_dict(target, data)
                    self.assertEqual(len(target.organisms), len(world.organisms))
                finally:
                    logger.close()
        finally:
            config.STATS_SNAPSHOT_INTERVAL = old_interval
            config.STATS_BASE_DIR = old_base


class TestSimulationSnapshotLoad(unittest.TestCase):
    """`Simulation(snapshot=...)` restores instead of seeding a throwaway
    population, and the restored organisms land in organisms.jsonl."""

    def test_snapshot_skips_seeding_and_logs_restored_population(self):
        world = _populated_world()
        data = world_to_dict(world)
        snap_uids = {rec["uid"] for rec in data["organisms"]}
        old_base = config.STATS_BASE_DIR
        old_enabled = config.STATS_ENABLED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.STATS_BASE_DIR = tmp
                config.STATS_ENABLED = True
                storage = MapStorage(os.path.join(tmp, "missing_map.json"))
                sim = Simulation(
                    width=world.width,
                    height=world.height,
                    storage=storage,
                    snapshot=data,
                )
                try:
                    # Exactly the snapshot's population: no seeded extras and
                    # none lost.
                    self.assertEqual({o.uid for o in sim.world.organisms}, snap_uids)
                    self.assertAlmostEqual(sim.world.tick, data["tick"], delta=0.001)
                    lines = (
                        (Path(sim.stats.run_dir) / "organisms.jsonl").read_text(encoding="utf-8").strip().split("\n")
                    )
                    self.assertEqual(len(lines), len(snap_uids))
                    logged_uids = {json.loads(line)["uid"] for line in lines}
                    self.assertEqual(logged_uids, snap_uids)
                finally:
                    sim.stats.close()
                    sim.renderer.close()
        finally:
            config.STATS_BASE_DIR = old_base
            config.STATS_ENABLED = old_enabled


if __name__ == "__main__":
    unittest.main()
