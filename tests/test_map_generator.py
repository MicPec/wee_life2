"""Tests for the noise-based terrain generator behind the editor's R key."""

import random
import unittest
from itertools import pairwise

from wee_life2.core import config
from wee_life2.core.map_generator import (
    HAZARD_ISLANDS,
    HEAL_HAZARD_GAP,
    HEAL_ISLANDS,
    SHORE_WALL_DISTANCE,
    PerlinNoise,
    _cell_groups,
    _components,
    _connect_pockets,
    _line_cells,
    _octile_distance,
    _trim_self_contact,
    generate_terrain,
)
from wee_life2.core.tile_map import TileMap

COLS, ROWS = 60, 45  # the default 1200x900 window at TILE_SIZE 20


def interior(cols=COLS, rows=ROWS):
    return [(c, r) for r in range(1, rows - 1) for c in range(1, cols - 1)]


def share(grid, tile, cells):
    return sum(1 for c, r in cells if grid[r][c] == tile) / len(cells)


def wall_lines(grid):
    """Sizes of the 4-connected wall pieces inside the frame."""
    rows, cols = len(grid), len(grid[0])
    seen = set()
    sizes = []
    for start in interior(cols, rows):
        if start in seen or grid[start[1]][start[0]] != config.TILE_WALL:
            continue
        seen.add(start)
        stack = [start]
        size = 0
        while stack:
            c, r = stack.pop()
            size += 1
            for nc, nr in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
                inside = 0 < nc < cols - 1 and 0 < nr < rows - 1
                if inside and (nc, nr) not in seen and grid[nr][nc] == config.TILE_WALL:
                    seen.add((nc, nr))
                    stack.append((nc, nr))
        sizes.append(size)
    return sizes


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

    def test_walls_are_thin_lines_not_blobs(self):
        """Walls are drawn as one-tile-thick strokes, like the built-in map."""
        for seed, grid in self._maps():
            walls = sum(row[1:-1].count(config.TILE_WALL) for row in grid[1:-1])
            lumps = sum(
                1
                for r in range(1, ROWS - 2)
                for c in range(1, COLS - 2)
                if all(grid[r + dr][c + dc] == config.TILE_WALL for dc in (0, 1) for dr in (0, 1))
            )
            self.assertLessEqual(lumps, 0.02 * walls, f"seed {seed}: {lumps} 2x2 wall lumps")

    def test_walls_form_long_lines(self):
        for seed, grid in self._maps():
            sizes = wall_lines(grid)
            self.assertGreaterEqual(sum(sizes) / len(sizes), 8.0, f"seed {seed}: wall pieces {sorted(sizes)}")

    def test_main_walls_follow_the_coast(self):
        """Most wall tiles sit a corridor's width from the water, tracing the shore."""
        shares = []
        for seed, grid in self._maps():
            dist = _octile_distance(grid, config.TILE_WATER)
            walls = [(c, r) for c, r in interior() if grid[r][c] == config.TILE_WALL]
            low, high = SHORE_WALL_DISTANCE
            coastal = sum(1 for c, r in walls if low <= dist[r][c] < high + 1.5)
            shares.append(coastal / len(walls))
            self.assertGreater(coastal / len(walls), 0.3, f"seed {seed}")
        self.assertGreater(sum(shares) / len(shares), 0.6)

    def test_hazards_and_heal_come_as_a_few_compact_islands(self):
        for seed, grid in self._maps():
            for tiles, (low, high) in (((config.TILE_LAVA, config.TILE_RADIOACTIVE), HAZARD_ISLANDS), ((config.TILE_HEAL,), HEAL_ISLANDS)):
                groups = _cell_groups({(c, r) for c, r in interior() if grid[r][c] in tiles})
                self.assertGreaterEqual(len(groups), low, f"seed {seed}: {tiles}")
                self.assertLessEqual(len(groups), high, f"seed {seed}: {tiles}")
                for group in groups:
                    width = max(c for c, _ in group) - min(c for c, _ in group) + 1
                    height = max(r for _, r in group) - min(r for _, r in group) + 1
                    self.assertLessEqual(max(width, height) / min(width, height), 4.0, f"seed {seed}: strip-like island")
            lava = _cell_groups({(c, r) for c, r in interior() if grid[r][c] == config.TILE_LAVA})
            self.assertEqual(len(lava), 1, f"seed {seed}: one lava island")

    def _islands(self, grid, tiles):
        """(sits_in_water, cells) per 8-connected island of ``tiles``."""
        out = []
        for group in _cell_groups({(c, r) for c, r in interior() if grid[r][c] in tiles}):
            cells = set(group)
            around = {
                grid[r + dr][c + dc]
                for c, r in group
                for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if (c + dc, r + dr) not in cells
            }
            out.append((around <= {config.TILE_WATER}, group))
        return out

    def test_lakes_get_hazards_and_heal_too(self):
        """At least one radioactive island and one heal oasis sit out in a lake."""
        for seed, grid in self._maps():
            hazards = self._islands(grid, (config.TILE_RADIOACTIVE,))
            heal = self._islands(grid, (config.TILE_HEAL,))
            self.assertTrue(any(in_water for in_water, _ in hazards), f"seed {seed}: no hazard on the water")
            self.assertTrue(any(in_water for in_water, _ in heal), f"seed {seed}: no heal on the water")
            self.assertTrue(any(not in_water for in_water, _ in heal), f"seed {seed}: no heal on land")
            lava = self._islands(grid, (config.TILE_LAVA,))
            self.assertFalse(any(in_water for in_water, _ in lava), f"seed {seed}: lava out in a lake")

    def test_land_hazards_keep_out_of_the_shore_corridors(self):
        for seed, grid in self._maps():
            dist = _octile_distance(grid, config.TILE_WATER)
            for in_water, group in self._islands(grid, (config.TILE_LAVA, config.TILE_RADIOACTIVE)):
                if in_water:
                    continue
                for c, r in group:
                    self.assertGreater(dist[r][c], SHORE_WALL_DISTANCE[1] - 0.5, f"seed {seed} at {(c, r)}")

    def test_tile_budgets(self):
        cells = interior()
        for seed, grid in self._maps():
            walls = share(grid, config.TILE_WALL, cells)
            hazards = share(grid, config.TILE_LAVA, cells) + share(grid, config.TILE_RADIOACTIVE, cells)
            heal = share(grid, config.TILE_HEAL, cells)
            budget = round(config.MAP_WALL_FRACTION * len(cells))
            self.assertLessEqual(walls * len(cells), budget, f"seed {seed}")
            self.assertGreaterEqual(walls * len(cells), 0.8 * budget, f"seed {seed}: wall lines did not fit")
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


class TestWallStrokes(unittest.TestCase):
    def test_line_cells_are_a_closed_staircase(self):
        """No diagonal steps: corner-touching walls would leave a gap to slip through."""
        for end in ((5, 3), (-4, 7), (6, -6), (0, 5), (-3, 0)):
            cells = _line_cells((0, 0), end)
            self.assertEqual(cells[0], (0, 0))
            self.assertEqual(cells[-1], end)
            for (c0, r0), (c1, r1) in pairwise(cells):
                self.assertEqual(abs(c1 - c0) + abs(r1 - r0), 1, f"diagonal step in line to {end}")

    def test_stroke_is_cut_where_it_curls_back(self):
        hook = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (2, 1), (1, 1)]
        # (3, 1) is an ordinary staircase corner; (2, 1) is the first cell
        # that runs alongside the stroke's own earlier cells.
        self.assertEqual(_trim_self_contact(hook), hook[:5])
        straight = [(c, 0) for c in range(10)]
        self.assertEqual(_trim_self_contact(straight), straight)


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
        # One wall tile opens a one-thick ring; the exit is widened along the
        # wall to a three-tile doorway so big organisms fit through.
        self.assertEqual(sum(row.count(config.TILE_WALL) for row in grid), 36 + 16 - 3)


if __name__ == "__main__":
    unittest.main()
