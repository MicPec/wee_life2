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
