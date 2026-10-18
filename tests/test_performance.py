"""Performance smoke tests to detect regressions."""

import time
import unittest

import pygame

from wee_life2.core import config
from wee_life2.core.dna import DNA
from wee_life2.core.world import World
from wee_life2.render.renderer import Renderer


class TestPerformanceSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stats_enabled = config.STATS_ENABLED
        config.STATS_ENABLED = False

    @classmethod
    def tearDownClass(cls):
        config.STATS_ENABLED = cls._stats_enabled

    def test_simulation_and_render_runs_at_interactive_speed(self):
        """A small world with ~100 organisms should run without timeouts."""
        pygame.init()
        world = World(400, 300, tile_size=20)
        world.generate_map()
        for _ in range(100):
            dna = DNA.random()
            is_amphibious = any(g.kind == "amphibious" for g in dna.genes)
            pos = world.random_empty_position(in_water=is_amphibious)
            world.spawn_organism(dna, pos)
        renderer = Renderer(400, 300, fps=30)
        for _ in range(10):
            world.update(1.0)
            renderer.render(world)
        start = time.perf_counter()
        for _ in range(50):
            world.update(1.0)
            renderer.render(world)
        elapsed = time.perf_counter() - start
        per_frame_ms = elapsed / 50 * 1000
        # This is a generous smoke threshold; it catches severe regressions
        # while tolerating slow CI runners.
        self.assertLess(per_frame_ms, 200.0, f"too slow: {per_frame_ms:.1f} ms/frame")


if __name__ == "__main__":
    unittest.main()
