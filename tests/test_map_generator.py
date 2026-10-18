"""Tests for the noise-based terrain generator behind the editor's R key."""

import random
import unittest

from wee_life2.core import config
from wee_life2.core.map_generator import (
    HEAL_HAZARD_GAP,
    ROCK_SHORE_GAP,
    PerlinNoise,
    _components,
    _connect_pockets,
    generate_terrain,
)
from wee_life2.core.tile_map import TileMap

COLS, ROWS = 60, 45  # the default 1200x900 window at TILE_SIZE 20


def interior(cols=COLS, rows=ROWS):
    return [(c, r) for r in range(1, rows - 1) for c in range(1, cols - 1)]


def share(grid, tile, cells):
    return sum(1 for c, r in cells if grid[r][c] == tile) / len(cells)


class TestPerlinNoise(unittest.TestCase):
    def test_zero_on_lattice_and_bounded(self):
        noise = PerlinNoise(random.Random(1))
        self.assertEqual(noise.noise(3.0, 7.0), 0.0)
        rng = random.Random(2)
        for _ in range(500):
            x, y = rng.uniform(-50, 50), rng.uniform(-50, 50)
            self.assertLessEqual(abs(noise.fbm(x, y, 4)), 1.0)

    def test_noise_is_smooth(self):
        noise = PerlinNoise(random.Random(1))
        self.assertLess(abs(noise.noise(4.30, 2.70) - noise.noise(4.31, 2.70)), 0.05)


class TestGenerateTerrain(unittest.TestCase):
    SEEDS = range(12)

    @classmethod
    def setUpClass(cls):
        # Generated once: each board takes tens of milliseconds.
        cls.maps = [(seed, generate_terrain(COLS, ROWS, random.Random(seed))) for seed in cls.SEEDS]

    def _maps(self):
        return self.maps

    def test_border_is_wall(self):
        for _, grid in self._maps():
            self.assertTrue(all(t == config.TILE_WALL for t in grid[0] + grid[-1]))
            self.assertTrue(all(row[0] == config.TILE_WALL and row[-1] == config.TILE_WALL for row in grid))

    def test_water_share_stays_in_configured_band(self):
        cells = interior()
        for seed, grid in self._maps():
            water = share(grid, config.TILE_WATER, cells)
            self.assertGreaterEqual(water, config.MAP_WATER_FRACTION_MIN - 1e-9, f"seed {seed}")
            self.assertLessEqual(water, config.MAP_WATER_FRACTION_MAX + 1e-9, f"seed {seed}")

    def test_explicit_water_fraction_is_exact(self):
        cells = interior()
        grid = generate_terrain(COLS, ROWS, random.Random(5), water_fraction=0.30)
        self.assertEqual(sum(1 for c, r in cells if grid[r][c] == config.TILE_WATER), round(0.30 * len(cells)))

    def test_water_forms_lakes_not_specks(self):
        """The point of the generator: coherent bodies of water, not scatter."""
        cells = interior()
        for seed, grid in self._maps():
            lakes = _components(grid, cells, lambda t: t == config.TILE_WATER)
            biggest = max(len(lake) for lake in lakes)
            water = sum(len(lake) for lake in lakes)
            self.assertLess(len(lakes), 25, f"seed {seed}: {len(lakes)} separate water bodies")
            self.assertGreater(biggest, 0.25 * water, f"seed {seed}")

    def test_every_open_tile_is_reachable(self):
        cells = interior()
        for seed, grid in self._maps():
            walkable = _components(grid, cells, lambda t: t != config.TILE_WALL)
            self.assertEqual(len(walkable), 1, f"seed {seed}: walled-in pocket")

    def test_rock_keeps_off_the_shore(self):
        cells = interior()
        for seed, grid in self._maps():
            for c, r in cells:
                if grid[r][c] != config.TILE_WALL:
                    continue
                for dc in range(-ROCK_SHORE_GAP + 1, ROCK_SHORE_GAP):
                    for dr in range(-ROCK_SHORE_GAP + 1, ROCK_SHORE_GAP):
                        if abs(dc) + abs(dr) < ROCK_SHORE_GAP:
                            self.assertNotEqual(grid[r + dr][c + dc], config.TILE_WATER, f"seed {seed} at {(c, r)}")

    def test_tile_budgets(self):
        cells = interior()
        for seed, grid in self._maps():
            walls = share(grid, config.TILE_WALL, cells)
            hazards = share(grid, config.TILE_LAVA, cells) + share(grid, config.TILE_RADIOACTIVE, cells)
            heal = share(grid, config.TILE_HEAL, cells)
            self.assertLessEqual(walls * len(cells), round(config.MAP_WALL_FRACTION * len(cells)), f"seed {seed}")
            self.assertAlmostEqual(hazards, config.MAP_HAZARD_FRACTION, delta=0.005, msg=f"seed {seed}")
            self.assertGreater(heal, 0.0, f"seed {seed}")
            self.assertLessEqual(heal, 0.015, f"seed {seed}: too many heal tiles")
            self.assertGreater(share(grid, config.TILE_EMPTY, cells), 0.45, f"seed {seed}")

    def test_heal_oases_keep_away_from_hazards(self):
        cells = interior()
        hazards = (config.TILE_LAVA, config.TILE_RADIOACTIVE)
        for seed, grid in self._maps():
            for c, r in cells:
                if grid[r][c] != config.TILE_HEAL:
                    continue
                for hc, hr in cells:
                    if grid[hr][hc] in hazards:
                        self.assertGreaterEqual(abs(hc - c) + abs(hr - r), HEAL_HAZARD_GAP, f"seed {seed}")

    def test_same_seed_same_map_and_seeds_differ(self):
        a = generate_terrain(COLS, ROWS, random.Random(42))
        b = generate_terrain(COLS, ROWS, random.Random(42))
        c = generate_terrain(COLS, ROWS, random.Random(43))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_global_random_seed_makes_unseeded_maps_reproducible(self):
        random.seed(7)
        a = generate_terrain(COLS, ROWS)
        random.seed(7)
        b = generate_terrain(COLS, ROWS)
        self.assertEqual(a, b)

    def test_tiny_and_extreme_boards_do_not_crash(self):
        for cols, rows in ((2, 2), (3, 3), (10, 7), (5, 40)):
            for water in (0.0, 0.5, 1.0):
                grid = generate_terrain(cols, rows, random.Random(0), water_fraction=water)
                self.assertEqual(len(grid), rows)
                self.assertTrue(all(len(row) == cols for row in grid))

    def test_config_overrides_apply_at_call_time(self):
        """--set MAP_*=... must reach the generator (defaults are read late)."""
        old = config.MAP_WATER_FRACTION_MIN, config.MAP_WATER_FRACTION_MAX
        try:
            config.MAP_WATER_FRACTION_MIN = config.MAP_WATER_FRACTION_MAX = 0.2
            grid = generate_terrain(COLS, ROWS, random.Random(1))
            self.assertAlmostEqual(share(grid, config.TILE_WATER, interior()), 0.2, delta=0.001)
        finally:
            config.MAP_WATER_FRACTION_MIN, config.MAP_WATER_FRACTION_MAX = old


class TestConnectPockets(unittest.TestCase):
    def test_carves_a_ring_of_rock_open(self):
        tile_map = TileMap(200, 200, tile_size=20)
        tile_map.clear_map()
        grid = tile_map.tiles
        for c in range(3, 8):
            for r in range(3, 8):
                if c in (3, 7) or r in (3, 7):
                    grid[r][c] = config.TILE_WALL
        cells = interior(10, 10)
        self.assertEqual(len(_components(grid, cells, lambda t: t != config.TILE_WALL)), 2)
        _connect_pockets(grid, cells)
        self.assertEqual(len(_components(grid, cells, lambda t: t != config.TILE_WALL)), 1)
        # Only one rock tile is needed to open a one-thick ring.
        self.assertEqual(sum(row.count(config.TILE_WALL) for row in grid), 36 + 16 - 1)


if __name__ == "__main__":
    unittest.main()
