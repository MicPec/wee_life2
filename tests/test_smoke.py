"""Smoke tests for the whole simulation."""

import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from wee_life2.core import config
from wee_life2.core.map_storage import MapStorage
from wee_life2.simulation import Simulation


class TestSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stats_enabled = config.STATS_ENABLED
        config.STATS_ENABLED = False

    @classmethod
    def tearDownClass(cls):
        config.STATS_ENABLED = cls._stats_enabled

    def test_simulation_initializes_and_steps(self):
        sim = Simulation(width=240.0, height=180.0)
        self.assertGreater(len(sim.world.organisms), 0)
        self.assertGreater(len(sim.world.food), 0)

        for _ in range(10):
            sim.step(dt=1.0 / 60.0)

        self.assertGreaterEqual(len(sim.world.organisms), 0)
        self.assertGreaterEqual(sim.world.tick, 0.0)

        sim.renderer.close()

    def test_action_dispatch_covers_every_action(self):
        """A dispatch table can silently drop an action; assert full coverage.

        The old isinstance chain had the same risk, but at least crashed
        loudly on a typo. This guards the table against a new Action being
        added to render/actions.py without a handler.
        """
        from wee_life2.render import actions

        declared = {
            obj
            for name, obj in vars(actions).items()
            if isinstance(obj, type) and issubclass(obj, actions.Action) and obj is not actions.Action
        }
        missing = declared - set(Simulation._ACTION_HANDLERS)
        self.assertEqual(missing, set(), f"actions without a handler: {sorted(c.__name__ for c in missing)}")

    def test_unknown_action_is_ignored(self):
        from wee_life2.render.actions import Action

        sim = Simulation(width=240.0, height=180.0)
        try:
            sim._handle_action(Action())  # must not raise
        finally:
            sim.renderer.close()

    def test_world_generates_a_map_when_none_is_saved(self):
        """Without a saved map the simulation grows one (lakes and land, no frame).

        The storage points at a path that does not exist: the default
        `world_map.json` is whatever the developer last saved in the editor,
        which made the old "has border walls" version of this test depend on
        local state.
        """
        with tempfile.TemporaryDirectory() as tmp:
            storage = MapStorage(os.path.join(tmp, "missing_map.json"))
            sim = Simulation(width=240.0, height=180.0, storage=storage)
        try:
            tiles = [tile for row in sim.world.tiles for tile in row]
            self.assertIn(config.TILE_WATER, tiles)
            self.assertIn(config.TILE_EMPTY, tiles)
            self.assertFalse(storage.exists(), "generating must not save over the map file")
        finally:
            sim.renderer.close()


if __name__ == "__main__":
    unittest.main()
