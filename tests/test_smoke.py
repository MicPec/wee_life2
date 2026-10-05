"""Smoke tests for the whole simulation."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from wee_life2.core import config
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

    def test_world_generates_map_with_borders(self):
        sim = Simulation(width=240.0, height=180.0)
        border = 0
        for row in sim.world.tiles:
            for tile in row:
                if tile == config.TILE_WALL:
                    border += 1
        self.assertGreater(border, 0)
        sim.renderer.close()


if __name__ == "__main__":
    unittest.main()
