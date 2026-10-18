"""Procedural terrain: lakes, islands, rock outcrops, hazard patches and heal oases.

The board is grown from a fractal Perlin-noise height field instead of
scattering tiles independently: low ground floods into lakes (and the hills
left standing inside them become islands), the highest ground away from the
shore is raised into rock outcrops (walls), and small hazard patches and heal
oases are dropped onto the remaining land.  Every tile type is placed by
*share of the interior* rather than by per-tile probability, so a randomised
board always lands inside the configured budget (e.g. 35-40% water) whatever
the seed.

Pure Python and grid-sized (a 60x45 board is ~2.6k tiles), so it needs no
numpy and runs in a few tens of milliseconds.
"""

from __future__ import annotations

import math
import random
from collections import deque

from . import config

Grid = list[list[int]]
Cell = tuple[int, int]  # (col, row)

EMPTY = config.TILE_EMPTY
WALL = config.TILE_WALL
RADIOACTIVE = config.TILE_RADIOACTIVE
LAVA = config.TILE_LAVA
WATER = config.TILE_WATER
HEAL = config.TILE_HEAL

# Water bodies / islands smaller than this are dissolved into their
# surroundings: single-tile puddles and specks read as noise, not terrain.
MIN_LAKE_TILES = 4
MIN_ISLAND_TILES = 3
# Rock never touches the shore, so coasts stay walkable, and keeps off the
# frame so outcrops do not just read as a thicker border wall.
ROCK_SHORE_GAP = 2
ROCK_FRAME_GAP = 3
# Share of the hazard budget that becomes lava (seeded against rock, like
# volcanic vents); the rest is radioactive ground.
LAVA_SHARE = 0.35
HAZARD_PATCH_SIZE = (3, 7)
HEAL_PATCH_SIZE = (2, 4)
# Heal oases keep this many tiles away from any hazard.
HEAL_HAZARD_GAP = 3
# How far (in noise units) the low-frequency warp field bends the height
# field's sample points; it makes coasts meander instead of following the
# noise lattice.
DOMAIN_WARP = 1.2

_NEIGHBOURS_4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
_NEIGHBOURS_8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
_GRADIENTS = ((1.0, 1.0), (-1.0, 1.0), (1.0, -1.0), (-1.0, -1.0), (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0))


class PerlinNoise:
    """Classic 2D gradient (Perlin) noise with a seeded permutation table."""

    def __init__(self, rng: random.Random) -> None:
        perm = list(range(256))
        rng.shuffle(perm)
        self._perm = perm + perm

    def noise(self, x: float, y: float) -> float:
        """Noise at ``(x, y)``, roughly in [-1, 1] (exactly 0 on lattice points)."""
        fx = math.floor(x)
        fy = math.floor(y)
        xf = x - fx
        yf = y - fy
        xi = int(fx) & 255
        yi = int(fy) & 255
        perm = self._perm
        u = xf * xf * xf * (xf * (xf * 6.0 - 15.0) + 10.0)
        v = yf * yf * yf * (yf * (yf * 6.0 - 15.0) + 10.0)
        a = perm[xi] + yi
        b = perm[xi + 1] + yi
        top = _lerp(_grad(perm[a], xf, yf), _grad(perm[b], xf - 1.0, yf), u)
        bottom = _lerp(_grad(perm[a + 1], xf, yf - 1.0), _grad(perm[b + 1], xf - 1.0, yf - 1.0), u)
        return _lerp(top, bottom, v)

    def fbm(self, x: float, y: float, octaves: int, lacunarity: float = 2.0, gain: float = 0.5) -> float:
        """Fractal sum of ``octaves`` noise layers, normalised back to ~[-1, 1]."""
        total = 0.0
        amplitude = 1.0
        frequency = 1.0
        norm = 0.0
        for _ in range(max(1, octaves)):
            total += self.noise(x * frequency, y * frequency) * amplitude
            norm += amplitude
            amplitude *= gain
            frequency *= lacunarity
        return total / norm


def _lerp(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


def _grad(h: int, x: float, y: float) -> float:
    gx, gy = _GRADIENTS[h & 7]
    return gx * x + gy * y


def generate_terrain(
    cols: int,
    rows: int,
    rng: random.Random | None = None,
    *,
    water_fraction: float | None = None,
    wall_fraction: float | None = None,
    hazard_fraction: float | None = None,
    heal_fraction: float | None = None,
) -> Grid:
    """Return a ``rows x cols`` tile grid with border walls and noise terrain.

    Fractions are shares of the interior (everything inside the border wall).
    ``None`` reads the ``MAP_*`` constants from ``config`` at call time, so
    ``--set``/``--config-file`` overrides apply; the water share is drawn
    uniformly from ``[MAP_WATER_FRACTION_MIN, MAP_WATER_FRACTION_MAX]``.
    Without an explicit ``rng`` the generator is seeded from the global
    ``random`` state, so a seeded run stays reproducible.
    """
    if rng is None:
        rng = random.Random(random.getrandbits(64))
    if water_fraction is None:
        low = config.MAP_WATER_FRACTION_MIN
        high = max(low, config.MAP_WATER_FRACTION_MAX)
        water_fraction = rng.uniform(low, high)
    if wall_fraction is None:
        wall_fraction = config.MAP_WALL_FRACTION
    if hazard_fraction is None:
        hazard_fraction = config.MAP_HAZARD_FRACTION
    if heal_fraction is None:
        heal_fraction = config.MAP_HEAL_FRACTION

    grid = [
        [WALL if row in (0, rows - 1) or col in (0, cols - 1) else EMPTY for col in range(cols)] for row in range(rows)
    ]
    interior = [(col, row) for row in range(1, rows - 1) for col in range(1, cols - 1)]
    if not interior:
        return grid
    n = len(interior)

    height = _height_field(cols, rows, rng)
    _flood_lowlands(grid, height, interior, _budget(water_fraction, n))
    _raise_rocks(grid, height, interior, _budget(wall_fraction, n), rng)
    _connect_pockets(grid, interior)

    hazard_total = _budget(hazard_fraction, n)
    lava_total = round(hazard_total * LAVA_SHARE)
    near_rock = [cell for cell in interior if grid[cell[1]][cell[0]] == EMPTY and _touches_rock(grid, cell)]
    _scatter_patches(grid, interior, LAVA, lava_total, HAZARD_PATCH_SIZE, rng, preferred=near_rock)
    _scatter_patches(grid, interior, RADIOACTIVE, hazard_total - lava_total, HAZARD_PATCH_SIZE, rng)

    heal_total = _budget(heal_fraction, n)
    if heal_fraction > 0.0:
        heal_total = max(1, heal_total)
    hazard_dist = _distance_field(grid, (RADIOACTIVE, LAVA))
    safe = [cell for cell in interior if hazard_dist[cell[1]][cell[0]] >= HEAL_HAZARD_GAP]
    spread = max(4, max(cols, rows) // 5)
    _scatter_patches(grid, interior, HEAL, heal_total, HEAL_PATCH_SIZE, rng, preferred=safe, allowed=safe, spread=spread)
    return grid


def _budget(fraction: float, n: int) -> int:
    return max(0, min(n, round(fraction * n)))


def _height_field(cols: int, rows: int, rng: random.Random) -> list[list[float]]:
    """Domain-warped fractal noise height per tile (border tiles included)."""
    elevation = PerlinNoise(rng)
    warp = PerlinNoise(rng)
    scale = max(1.0, config.MAP_NOISE_SCALE)
    octaves = max(1, int(config.MAP_NOISE_OCTAVES))
    # Random fractional offsets: Perlin noise is 0 on every lattice point, and
    # an unshifted grid would sample the same lattice for every seed.
    ox, oy = rng.uniform(0.0, 200.0), rng.uniform(0.0, 200.0)
    wx0, wy0 = rng.uniform(0.0, 200.0), rng.uniform(0.0, 200.0)
    field = []
    for row in range(rows):
        line = []
        for col in range(cols):
            x = col / scale
            y = row / scale
            dx = warp.fbm(x * 0.5 + wx0, y * 0.5 + wy0, 2)
            dy = warp.fbm(x * 0.5 + wy0, y * 0.5 + wx0, 2)
            line.append(elevation.fbm(x + ox + DOMAIN_WARP * dx, y + oy + DOMAIN_WARP * dy, octaves))
        field.append(line)
    return field


def _flood_lowlands(grid: Grid, height: list[list[float]], interior: list[Cell], target: int) -> None:
    """Turn the ``target`` lowest interior tiles into water, then tidy the coast."""
    order = sorted(interior, key=lambda cell: height[cell[1]][cell[0]])
    for col, row in order[:target]:
        grid[row][col] = WATER
    _smooth_coast(grid, interior)
    _dissolve_specks(grid, interior, WATER, MIN_LAKE_TILES, EMPTY)
    _dissolve_specks(grid, interior, EMPTY, MIN_ISLAND_TILES, WATER)
    _match_water_count(grid, height, interior, target)


def _smooth_coast(grid: Grid, interior: list[Cell]) -> None:
    """One synchronous majority pass so coasts are rounded, not pixel-jagged."""
    changes = []
    for col, row in interior:
        water = 0
        for dc, dr in _NEIGHBOURS_8:
            neighbour = grid[row + dr][col + dc]
            # The border wall votes like the tile itself, so the frame does
            # not drag the coast inward or outward.
            if neighbour == WALL:
                neighbour = grid[row][col]
            water += neighbour == WATER
        if water >= 5 and grid[row][col] != WATER:
            changes.append((col, row, WATER))
        elif water <= 3 and grid[row][col] == WATER:
            changes.append((col, row, EMPTY))
    for col, row, tile in changes:
        grid[row][col] = tile


def _components(grid: Grid, interior: list[Cell], member) -> list[list[Cell]]:
    """4-connected components of interior tiles for which ``member(tile)`` holds."""
    seen = set()
    comps = []
    for start in interior:
        if start in seen or not member(grid[start[1]][start[0]]):
            continue
        seen.add(start)
        comp = [start]
        queue = deque([start])
        while queue:
            col, row = queue.popleft()
            for dc, dr in _NEIGHBOURS_4:
                nxt = (col + dc, row + dr)
                if nxt in seen:
                    continue
                tile = grid[nxt[1]][nxt[0]]
                # The border is always wall, so membership alone keeps the
                # walk inside the interior for every non-wall predicate.
                if member(tile) and tile != WALL:
                    seen.add(nxt)
                    comp.append(nxt)
                    queue.append(nxt)
        comps.append(comp)
    return comps


def _dissolve_specks(grid: Grid, interior: list[Cell], tile: int, min_size: int, replacement: int) -> None:
    for comp in _components(grid, interior, lambda t: t == tile):
        if len(comp) < min_size:
            for col, row in comp:
                grid[row][col] = replacement


def _match_water_count(grid: Grid, height: list[list[float]], interior: list[Cell], target: int) -> None:
    """Grow or shrink water along the coast until exactly ``target`` tiles are wet.

    Smoothing and speck removal shift the count a little; correcting from the
    coastline (lowest land floods first, highest water drains first) keeps
    the shapes intact while landing the water share exactly on budget.
    """
    for _ in range(len(interior)):
        count = sum(1 for col, row in interior if grid[row][col] == WATER)
        if count == target:
            return
        flooding = count < target
        source, dest = (EMPTY, WATER) if flooding else (WATER, EMPTY)
        coast = [cell for cell in interior if grid[cell[1]][cell[0]] == source and _touches(grid, cell, dest)]
        if not coast:
            coast = [cell for cell in interior if grid[cell[1]][cell[0]] == source]
        if not coast:
            return
        coast.sort(key=lambda cell: height[cell[1]][cell[0]], reverse=not flooding)
        for col, row in coast[: abs(target - count)]:
            grid[row][col] = dest


def _touches(grid: Grid, cell: Cell, tile: int) -> bool:
    col, row = cell
    return any(grid[row + dr][col + dc] == tile for dc, dr in _NEIGHBOURS_4)


def _touches_rock(grid: Grid, cell: Cell) -> bool:
    """True if an *interior* wall (an outcrop, not the frame) borders ``cell``."""
    col, row = cell
    rows = len(grid)
    cols = len(grid[0])
    for dc, dr in _NEIGHBOURS_4:
        c, r = col + dc, row + dr
        if 0 < c < cols - 1 and 0 < r < rows - 1 and grid[r][c] == WALL:
            return True
    return False


def _distance_field(grid: Grid, tiles: tuple[int, ...]) -> list[list[float]]:
    """4-connected tile distance from every tile to the nearest of ``tiles``."""
    rows = len(grid)
    cols = len(grid[0])
    dist = [[math.inf] * cols for _ in range(rows)]
    queue = deque()
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] in tiles:
                dist[row][col] = 0
                queue.append((col, row))
    while queue:
        col, row = queue.popleft()
        d = dist[row][col] + 1
        for dc, dr in _NEIGHBOURS_4:
            c, r = col + dc, row + dr
            if 0 <= c < cols and 0 <= r < rows and dist[r][c] > d:
                dist[r][c] = d
                queue.append((c, r))
    return dist


def _raise_rocks(grid: Grid, height: list[list[float]], interior: list[Cell], count: int, rng: random.Random) -> None:
    """Raise rock outcrops on the highest inland ground.

    Height alone would pile every rock onto one or two summits, so it is
    mixed with a finer ridged-noise layer that breaks the outcrops into
    ragged ridges and scattered boulder fields.
    """
    if count <= 0:
        return
    ridge = PerlinNoise(rng)
    scale = max(1.0, config.MAP_NOISE_SCALE) / 2.5
    ox, oy = rng.uniform(0.0, 200.0), rng.uniform(0.0, 200.0)
    shore = _distance_field(grid, (WATER,))
    rows = len(grid)
    cols = len(grid[0])
    land = [
        (col, row)
        for col, row in interior
        if grid[row][col] == EMPTY
        and shore[row][col] >= ROCK_SHORE_GAP
        and ROCK_FRAME_GAP <= col < cols - ROCK_FRAME_GAP
        and ROCK_FRAME_GAP <= row < rows - ROCK_FRAME_GAP
    ]
    if not land:
        return
    lo = min(height[row][col] for col, row in land)
    span = max(1e-9, max(height[row][col] for col, row in land) - lo)

    def score(cell: Cell) -> float:
        col, row = cell
        elevation = (height[row][col] - lo) / span
        crest = 1.0 - abs(ridge.fbm(col / scale + ox, row / scale + oy, 3))
        return 0.55 * elevation + 0.45 * crest

    land.sort(key=score, reverse=True)
    for col, row in land[:count]:
        grid[row][col] = WALL


def _connect_pockets(grid: Grid, interior: list[Cell]) -> None:
    """Carve the cheapest path through rock from every walled-in pocket to the main area.

    Rock can close a ring around a patch of land; organisms spawned there
    could never leave.  A 0-1 BFS (rock costs 1, open ground 0) finds the
    path that removes the fewest rock tiles.
    """
    for _ in range(len(interior)):
        comps = _components(grid, interior, lambda t: t != WALL)
        if len(comps) <= 1:
            return
        comps.sort(key=len, reverse=True)
        main = set(comps[0])
        pocket = comps[1]
        rows = len(grid)
        cols = len(grid[0])
        cost = {cell: 0 for cell in pocket}
        parent: dict[Cell, Cell | None] = {cell: None for cell in pocket}
        queue = deque(pocket)
        reached = None
        while queue:
            cell = queue.popleft()
            if cell in main:
                reached = cell
                break
            col, row = cell
            for dc, dr in _NEIGHBOURS_4:
                c, r = col + dc, row + dr
                if not (0 < c < cols - 1 and 0 < r < rows - 1):
                    continue
                step = 1 if grid[r][c] == WALL else 0
                nxt = (c, r)
                new_cost = cost[cell] + step
                if new_cost < cost.get(nxt, math.inf):
                    cost[nxt] = new_cost
                    parent[nxt] = cell
                    if step:
                        queue.append(nxt)
                    else:
                        queue.appendleft(nxt)
        if reached is None:
            return
        cell = reached
        while cell is not None:
            col, row = cell
            if grid[row][col] == WALL:
                grid[row][col] = EMPTY
            cell = parent[cell]


def _scatter_patches(
    grid: Grid,
    interior: list[Cell],
    tile: int,
    total: int,
    size_range: tuple[int, int],
    rng: random.Random,
    *,
    preferred: list[Cell] | None = None,
    allowed: list[Cell] | None = None,
    spread: int = 3,
) -> None:
    """Drop ``total`` tiles of ``tile`` onto open land as small organic blobs.

    Seeds come from ``preferred`` cells when any are still open, and keep
    ``spread`` tiles (Chebyshev) from earlier seeds of this call so patches
    are scattered across the map rather than merged into one pool; the gap
    is relaxed if the map runs out of room.  ``allowed`` restricts growth.
    """
    allowed_set = set(allowed) if allowed is not None else None

    def open_land(cell: Cell) -> bool:
        col, row = cell
        if grid[row][col] != EMPTY:
            return False
        return allowed_set is None or cell in allowed_set

    seeds: list[Cell] = []
    placed = 0
    gap = spread
    while placed < total:
        pool = [cell for cell in (preferred or interior) if open_land(cell)]
        if not pool and preferred is not None and allowed_set is None:
            pool = [cell for cell in interior if open_land(cell)]
        pool = [cell for cell in pool if all(max(abs(cell[0] - s[0]), abs(cell[1] - s[1])) >= gap for s in seeds)]
        if not pool:
            if gap <= 1:
                return
            gap -= 1
            continue
        start = rng.choice(pool)
        seeds.append(start)
        size = min(rng.randint(*size_range), total - placed)
        placed += _grow_patch(grid, start, size, tile, rng, open_land)


def _grow_patch(grid: Grid, start: Cell, size: int, tile: int, rng: random.Random, can_take) -> int:
    """Grow a random 4-connected blob of up to ``size`` tiles from ``start``."""
    grid[start[1]][start[0]] = tile
    grown = 1
    frontier = [start]
    while grown < size and frontier:
        col, row = rng.choice(frontier)
        options = [(col + dc, row + dr) for dc, dr in _NEIGHBOURS_4 if can_take((col + dc, row + dr))]
        if not options:
            frontier.remove((col, row))
            continue
        nxt = rng.choice(options)
        grid[nxt[1]][nxt[0]] = tile
        frontier.append(nxt)
        grown += 1
    return grown
