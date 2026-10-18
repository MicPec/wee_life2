"""Procedural terrain: lakes, islands, wall lines, hazard patches and heal oases.

The board is grown from a fractal Perlin-noise height field instead of
scattering tiles independently: low ground floods into lakes (and the hills
left standing inside them become islands), most walls run right along the
coastline, on the last tile of land before the water, a smaller share are
free-standing lines (contours, bent straight lines, corridor pairs), and a
few hazard islands and heal oases go on land and out on the lakes.  Every tile type is placed by
*share of the interior* rather than by per-tile probability, so a randomised
board always lands inside the configured budget (e.g. 35-40% water) whatever
the seed.

Pure Python and grid-sized (a 60x45 board is ~2.6k tiles), so it needs no
numpy and runs in a few tens of milliseconds.
"""

from __future__ import annotations

import heapq
import math
import random
from collections import deque
from itertools import pairwise

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
# The main walls follow the coast: the outline of everything within
# SHORE_WALL_DISTANCE tiles (octile, i.e. near-Euclidean distance) of the
# water traces the coastline's shape, and stretches of it become walls.  At
# 1 that outline is the last tile of land before the water, so the walls sit
# right on the shore; a larger distance would leave a corridor of
# SHORE_WALL_DISTANCE - 1 open tiles between wall and water.
SHORE_WALL_SHARE = 0.7  # share of the wall budget spent on coast-following walls
SHORE_WALL_DISTANCE = (1, 1)  # one value drawn per map
# Land hazards keep this far (chessboard) from the water: a blob on the
# shore would plug the doorways in the coastal walls and cut the land off
# from the lakes.
HAZARD_SHORE_GAP = 3
SHORE_WALL_LENGTH = (14, 26)  # tiles per coastal wall; a doorway separates consecutive ones
MIN_SHORE_WALL = 8  # shorter coastal stretches are dropped
# The rest of the budget goes on free-standing one-tile-thick strokes, like
# the hand-drawn built-in map.  Lengths are tiles of travel per stroke.
WALL_LINE_LENGTH = (16.0, 34.0)
MIN_WALL_LINE = 8  # shorter strokes (clipped by the frame or water) are dropped
# Share of strokes that trace a height contour from near the shore, so the
# wall runs parallel to the coast and leaves a corridor along it.
WALL_CONTOUR_SHARE = 0.5
CONTOUR_VERTEX_STEP = 3  # contour points kept per polyline vertex (smooths the staircase)
# Share of straight strokes drawn as a parallel pair: an explicit corridor.
WALL_CORRIDOR_SHARE = 0.35
WALL_CORRIDOR_WIDTH = (3, 4)  # open tiles between the two walls of a corridor
WALL_DOOR_CHANCE = 0.5  # chance a long stroke gets a doorway cut into it
WALL_DOOR_WIDTH = 3  # path cells removed per doorway / widened pocket exit
WALL_MAX_WATER = 0.4  # strokes running mostly through a lake are rejected
# A new stroke may touch existing walls at a couple of cells (a T-junction or
# crossing) but not run alongside one, which would thicken it into a blob.
WALL_MAX_CONTACT = 2
# Hazards and heal come as a few larger islands spread across the board, not
# a scatter of specks.  One hazard island is lava (on land, seeded against a
# wall's landward side, like a volcanic vent); the others are radioactive.
# At least one radioactive island and one heal oasis sit out in a lake.
HAZARD_ISLANDS = (2, 3)  # the hazard budget is split into this many compact islands
HEAL_ISLANDS = (2, 3)  # likewise for heal oases
ISLAND_SEED_TRIES = 6  # seeds tried per island before keeping the biggest attempt
# Heal oases keep this many tiles away from any hazard.
HEAL_HAZARD_GAP = 4
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

    # Plan the hazard and heal islands first: those placed out in a lake
    # replace water, so that much extra lowland is flooded up front and the
    # water share still lands on budget once they are in.
    water_target = _budget(water_fraction, n)
    hazard_count = rng.randint(*HAZARD_ISLANDS)
    heal_count = rng.randint(*HEAL_ISLANDS)
    heal_total = _budget(heal_fraction, n)
    if heal_fraction > 0.0:
        heal_total = max(1, heal_total)
    hazard_plan = _plan_islands([LAVA] + [RADIOACTIVE] * (hazard_count - 1), _budget(hazard_fraction, n), water_fraction, rng)
    heal_plan = _plan_islands([HEAL] * heal_count, heal_total, water_fraction, rng)
    reserve = sum(size for _, medium, size in hazard_plan + heal_plan if medium == WATER)

    height = _height_field(cols, rows, rng)
    _flood_lowlands(grid, height, interior, min(n, water_target + reserve))
    wall_budget = _budget(wall_fraction, n)
    placed = _draw_shore_walls(grid, interior, round(wall_budget * SHORE_WALL_SHARE), rng)
    _draw_wall_lines(grid, height, interior, wall_budget - placed, rng)
    _connect_pockets(grid, interior)

    # Islands keep a third of the board apart.  On land, hazards stay off the
    # shore (HAZARD_SHORE_GAP), where a blob would plug the doorways in the
    # coastal walls; in a lake, islands keep a tile of open water around them
    # so they read as patches out on the water rather than stains on the shore.
    spread = max(4, max(cols, rows) // 3)
    shore = _distance_field(grid, (WATER,), _NEIGHBOURS_8)
    inland = [cell for cell in interior if shore[cell[1]][cell[0]] > HAZARD_SHORE_GAP]
    near_wall = [cell for cell in inland if _touches_inner_wall(grid, cell)]
    land_dist = _distance_field(grid, (EMPTY, WALL), _NEIGHBOURS_8)
    open_water = [cell for cell in interior if grid[cell[1]][cell[0]] == WATER and land_dist[cell[1]][cell[0]] >= 2]
    _scatter_islands(
        grid,
        interior,
        hazard_plan,
        rng,
        allowed={EMPTY: inland, WATER: open_water},
        preferred={LAVA: near_wall},
        spread=spread,
    )

    hazard_dist = _distance_field(grid, (RADIOACTIVE, LAVA))
    safe = {cell for cell in interior if hazard_dist[cell[1]][cell[0]] >= HEAL_HAZARD_GAP}
    _scatter_islands(
        grid,
        interior,
        heal_plan,
        rng,
        allowed={EMPTY: [cell for cell in interior if cell in safe], WATER: [cell for cell in open_water if cell in safe]},
        spread=spread,
    )
    # A water island that could not be placed (no lake big enough) went on
    # land instead and left its reserve flooded; drain it off the coast.
    _match_water_count(grid, height, interior, water_target)
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


def _touches_inner_wall(grid: Grid, cell: Cell, neighbours=_NEIGHBOURS_4) -> bool:
    """True if an *interior* wall (a wall line, not the frame) borders ``cell``."""
    col, row = cell
    rows = len(grid)
    cols = len(grid[0])
    for dc, dr in neighbours:
        c, r = col + dc, row + dr
        if 0 < c < cols - 1 and 0 < r < rows - 1 and grid[r][c] == WALL:
            return True
    return False


def _distance_field(grid: Grid, tiles: tuple[int, ...], neighbours=_NEIGHBOURS_4) -> list[list[float]]:
    """Tile distance from every tile to the nearest of ``tiles``.

    4-connected (Manhattan-like) by default; pass ``_NEIGHBOURS_8`` for the
    chessboard distance, whose level sets are closed staircases.
    """
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
        for dc, dr in neighbours:
            c, r = col + dc, row + dr
            if 0 <= c < cols and 0 <= r < rows and dist[r][c] > d:
                dist[r][c] = d
                queue.append((c, r))
    return dist


def _draw_shore_walls(grid: Grid, interior: list[Cell], budget: int, rng: random.Random) -> int:
    """Wall off stretches of coast; return tiles walled.

    The outline of the land within ``SHORE_WALL_DISTANCE`` (octile
    distance) of the water repeats the coastline's shape: it is the land
    just beyond that distance with a 4-neighbour inside it (at distance 1,
    every land tile touching the water).  Each stretch of outline is cut
    into walls of ``SHORE_WALL_LENGTH`` with doorways between them, and the
    longest go up until ``budget`` is spent, so each lake gets a few walled
    stretches of shore with ways through to the water.
    """
    if budget <= 0:
        return 0
    dist = _octile_distance(grid, WATER)
    gap = rng.randint(*SHORE_WALL_DISTANCE)
    band = [
        (col, row)
        for col, row in interior
        if grid[row][col] == EMPTY
        and dist[row][col] >= gap
        and any(dist[row + dr][col + dc] < gap for dc, dr in _NEIGHBOURS_4)
    ]
    if not band:
        return 0
    band_set = set(band)
    # Where the outlines of two lakes run together (a neck of land, a bay)
    # the band doubles up into 2x2 lumps; those junctions are left open.
    junctions = [cell for cell in band if _has_lump(band_set, cell)]
    cleared = {(c + dc, r + dr) for c, r in junctions for dc in (-1, 0, 1) for dr in (-1, 0, 1)}
    # Walk each stretch of outline from end to end and cut it into walls of
    # SHORE_WALL_LENGTH with a doorway between consecutive ones, so the land
    # behind a walled shore can still reach the water along the way.
    pieces: list[list[Cell]] = []
    for group in _cell_groups(band_set - cleared):
        path = _walk_path(_close_diagonals(group, grid, dist))
        i = rng.randint(0, WALL_DOOR_WIDTH)
        while i < len(path):
            length = rng.randint(*SHORE_WALL_LENGTH)
            pieces.append(path[i : i + length])
            i += length + WALL_DOOR_WIDTH
    # Longest stretches first (with a little jitter) so the budget goes on a
    # few main coastal walls rather than many stubs.
    pieces.sort(key=lambda piece: len(piece) + rng.uniform(0.0, 6.0), reverse=True)
    placed = 0
    for piece in pieces:
        piece = piece[: budget - placed]
        if len(piece) < MIN_SHORE_WALL or _has_lump(set(piece)):
            continue
        if any(_touches_inner_wall(grid, cell, _NEIGHBOURS_8) for cell in piece):
            continue
        for col, row in piece:
            grid[row][col] = WALL
        placed += len(piece)
    return placed


def _octile_distance(grid: Grid, tile: int) -> list[list[float]]:
    """Distance to the nearest ``tile`` with steps costing 1 straight, sqrt(2) diagonal.

    A close stand-in for Euclidean distance, so offset outlines follow the
    coast's curves instead of squaring off like chessboard rings.
    """
    rows = len(grid)
    cols = len(grid[0])
    dist = [[math.inf] * cols for _ in range(rows)]
    heap = []
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] == tile:
                dist[row][col] = 0.0
                heap.append((0.0, col, row))
    heapq.heapify(heap)
    while heap:
        d, col, row = heapq.heappop(heap)
        if d > dist[row][col]:
            continue
        for dc, dr in _NEIGHBOURS_8:
            c, r = col + dc, row + dr
            if 0 <= c < cols and 0 <= r < rows:
                nd = d + (1.0 if dc == 0 or dr == 0 else math.sqrt(2.0))
                if nd < dist[r][c]:
                    dist[r][c] = nd
                    heapq.heappush(heap, (nd, c, r))
    return dist


def _cell_groups(cells: set[Cell]) -> list[list[Cell]]:
    """8-connected groups of ``cells`` (in a stable order for a given seed)."""
    seen: set[Cell] = set()
    groups = []
    for start in sorted(cells):
        if start in seen:
            continue
        seen.add(start)
        group = [start]
        stack = [start]
        while stack:
            col, row = stack.pop()
            for dc, dr in _NEIGHBOURS_8:
                nxt = (col + dc, row + dr)
                if nxt in cells and nxt not in seen:
                    seen.add(nxt)
                    group.append(nxt)
                    stack.append(nxt)
        groups.append(group)
    return groups


def _close_diagonals(segment: list[Cell], grid: Grid, dist: list[list[float]]) -> list[Cell]:
    """Fill the corner of every diagonal-only joint so the wall has no slit.

    The landward corner (larger distance from the water) is preferred, so
    the wall never eats into the water side, unless it would complete a
    2x2 lump.
    """
    cells = set(segment)
    for col, row in segment:
        for dc, dr in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            if (col + dc, row + dr) not in cells:
                continue
            a, b = (col + dc, row), (col, row + dr)
            if a in cells or b in cells:
                continue
            options = [corner for corner in (a, b) if grid[corner[1]][corner[0]] == EMPTY]
            options.sort(key=lambda corner: (_has_lump(cells | {corner}, corner), -dist[corner[1]][corner[0]]))
            if options:
                cells.add(options[0])
    return sorted(cells)


def _walk_path(cells: list[Cell]) -> list[Cell]:
    """Order a thin 4-connected stroke from one end to the other.

    Starts at an end (a cell with at most one neighbour in the stroke; any
    cell of a closed ring) and follows unvisited neighbours.  A rare branch
    left over is dropped rather than walked.
    """
    cell_set = set(cells)

    def neighbours(cell: Cell) -> list[Cell]:
        return [(cell[0] + dc, cell[1] + dr) for dc, dr in _NEIGHBOURS_4 if (cell[0] + dc, cell[1] + dr) in cell_set]

    ends = [cell for cell in cells if len(neighbours(cell)) <= 1]
    path = [ends[0] if ends else cells[0]]
    seen = {path[0]}
    while True:
        options = [cell for cell in neighbours(path[-1]) if cell not in seen]
        if not options:
            return path
        path.append(options[0])
        seen.add(options[0])


def _has_lump(cells: set[Cell], at: Cell | None = None) -> bool:
    """True if ``cells`` contain a 2x2 block (one that includes ``at``, if given)."""
    corners = [at] if at is not None else cells
    for col, row in corners:
        for dc, dr in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
            c, r = col + dc, row + dr
            if {(c, r), (c + 1, r), (c, r + 1), (c + 1, r + 1)} <= cells:
                return True
    return False


def _draw_wall_lines(grid: Grid, height: list[list[float]], interior: list[Cell], budget: int, rng: random.Random) -> None:
    """Draw long, one-tile-thick wall strokes until ``budget`` tiles are walled.

    Three kinds of stroke, mirroring the hand-drawn built-in map: contour
    lines started near the shore that follow the height field's isoline, so
    they run parallel to the coast and leave a corridor along it; straight
    lines with a bend or two; and parallel pairs of straight lines that form
    an explicit corridor.  Lines are 4-connected staircases (no diagonal
    gaps to slip through) and long ones get a doorway.
    """
    if budget <= 0:
        return
    shore = _distance_field(grid, (WATER,))
    land = [cell for cell in interior if grid[cell[1]][cell[0]] == EMPTY]
    if not land:
        return
    coastal = [cell for cell in land if 2 <= shore[cell[1]][cell[0]] <= 4]
    placed = 0
    for _ in range(300):
        if placed >= budget:
            return
        if coastal and rng.random() < WALL_CONTOUR_SHARE:
            strokes = [_contour_stroke(grid, height, rng.choice(coastal), rng)]
        else:
            strokes = _straight_strokes(grid, rng.choice(land), rng)
        # Check every stroke before drawing any, so the two walls of a
        # corridor are judged against the same board.
        strokes = [stroke for stroke in strokes if _stroke_fits(grid, stroke)]
        for stroke in strokes:
            stroke = _cut_doorway(stroke[: budget - placed], rng)
            for col, row in stroke:
                # Only land is walled: a stroke crossing an inlet breaks off at
                # the water, so the lake keeps the share it was flooded to.
                if grid[row][col] == EMPTY:
                    grid[row][col] = WALL
                    placed += 1


def _line_cells(a: Cell, b: Cell) -> list[Cell]:
    """4-connected Bresenham line from ``a`` to ``b`` (both ends included).

    A plain Bresenham line steps diagonally, and two wall tiles meeting only
    at a corner leave a gap organisms can slip through; splitting each
    diagonal step into two straight ones draws a closed staircase instead.
    """
    (c, r), (c1, r1) = a, b
    cells = [(c, r)]
    dc = abs(c1 - c)
    dr = abs(r1 - r)
    sc = 1 if c1 > c else -1
    sr = 1 if r1 > r else -1
    err = dc - dr
    while (c, r) != (c1, r1):
        e2 = 2 * err
        if e2 > -dr:
            err -= dr
            c += sc
            cells.append((c, r))
        if e2 < dc:
            err += dc
            r += sr
            cells.append((c, r))
    return cells


def _polyline_cells(points: list[tuple[float, float]], grid: Grid) -> list[Cell]:
    """Rasterise a polyline, keeping its longest run inside the interior."""
    rows = len(grid)
    cols = len(grid[0])
    cells: list[Cell] = []
    for a, b in pairwise(points):
        segment = _line_cells((round(a[0]), round(a[1])), (round(b[0]), round(b[1])))
        cells.extend(segment[1:] if cells else segment)
    best: list[Cell] = []
    run: list[Cell] = []
    for col, row in cells:
        if 0 < col < cols - 1 and 0 < row < rows - 1:
            if (col, row) not in run:
                run.append((col, row))
            continue
        if len(run) > len(best):
            best = run
        run = []
    return _trim_self_contact(run if len(run) > len(best) else best)


def _trim_self_contact(cells: list[Cell]) -> list[Cell]:
    """Cut a stroke where it curls back alongside itself.

    A contour squeezed through a narrow neck of land can spiral, and a line
    running next to its own earlier cells reads as a lump, not a wall.  The
    two previous cells always touch a staircase cell, so only contact with
    anything older counts.
    """
    seen: set[Cell] = set()
    for i, (col, row) in enumerate(cells):
        if any((col + dc, row + dr) in seen for dc, dr in _NEIGHBOURS_8):
            return cells[:i]
        if i >= 2:
            seen.add(cells[i - 2])
    return cells


def _straight_strokes(grid: Grid, start: Cell, rng: random.Random) -> list[list[Cell]]:
    """A straight wall with up to two bends, sometimes doubled into a corridor."""
    angle = rng.uniform(0.0, 2.0 * math.pi)
    length = rng.uniform(*WALL_LINE_LENGTH)
    corridor = rng.random() < WALL_CORRIDOR_SHARE
    # Corridors bend at most once and gently, so the pair stays parallel.
    bends = rng.randint(0, 1) if corridor else rng.randint(0, 2)
    points = [(float(start[0]), float(start[1]))]
    heading = angle
    for _ in range(bends + 1):
        seg = length / (bends + 1)
        x, y = points[-1]
        points.append((x + math.cos(heading) * seg, y + math.sin(heading) * seg))
        turn = rng.uniform(0.2, 0.45) if corridor else rng.uniform(0.35, 0.9)
        heading += rng.choice((-1.0, 1.0)) * turn
    lines = [points]
    if corridor:
        offset = rng.randint(*WALL_CORRIDOR_WIDTH) + 1
        nx, ny = -math.sin(angle) * offset, math.cos(angle) * offset
        lines.append([(x + nx, y + ny) for x, y in points])
    return [_polyline_cells(line, grid) for line in lines]


def _sample(height: list[list[float]], x: float, y: float) -> float:
    """Bilinear height at a fractional tile position (clamped to the board)."""
    rows = len(height)
    cols = len(height[0])
    x = min(max(x, 0.0), cols - 1.001)
    y = min(max(y, 0.0), rows - 1.001)
    c = int(x)
    r = int(y)
    fx = x - c
    fy = y - r
    top = _lerp(height[r][c], height[r][c + 1], fx)
    bottom = _lerp(height[r + 1][c], height[r + 1][c + 1], fx)
    return _lerp(top, bottom, fy)


def _contour_stroke(grid: Grid, height: list[list[float]], start: Cell, rng: random.Random) -> list[Cell]:
    """Trace the height isoline through ``start`` for one stroke length.

    The coast is itself an isoline of the height field, so a contour started
    a few tiles inland runs parallel to the shore.  Each step moves one tile
    along the tangent, plus a small Newton correction back onto the starting
    level so the line does not drift uphill or into the lake.
    """
    x, y = float(start[0]), float(start[1])
    level = _sample(height, x, y)
    direction = None
    points = [(x, y)]
    for _ in range(int(rng.uniform(*WALL_LINE_LENGTH))):
        gx = _sample(height, x + 0.5, y) - _sample(height, x - 0.5, y)
        gy = _sample(height, x, y + 0.5) - _sample(height, x, y - 0.5)
        g = math.hypot(gx, gy)
        if g < 1e-9:
            break
        tx, ty = -gy / g, gx / g
        if direction is None:
            if rng.random() < 0.5:
                tx, ty = -tx, -ty
        elif tx * direction[0] + ty * direction[1] < 0.0:
            tx, ty = -tx, -ty
        direction = (tx, ty)
        correction = max(-0.5, min(0.5, (_sample(height, x, y) - level) / g))
        x += tx - gx / g * correction
        y += ty - gy / g * correction
        points.append((x, y))
    # Rasterising every one-tile step makes the rounding jitter back and
    # forth into 2x2 lumps; a polyline through every third point keeps the
    # contour's shape but draws it as a clean staircase.
    points = points[::CONTOUR_VERTEX_STEP] + ([points[-1]] if (len(points) - 1) % CONTOUR_VERTEX_STEP else [])
    cells = _polyline_cells(points, grid)
    # Stop at the first water tile: a contour line belongs on land.
    for i, (col, row) in enumerate(cells):
        if grid[row][col] == WATER:
            return cells[:i]
    return cells


def _stroke_fits(grid: Grid, stroke: list[Cell]) -> bool:
    if len(stroke) < MIN_WALL_LINE:
        return False
    if sum(1 for col, row in stroke if grid[row][col] == WATER) > WALL_MAX_WATER * len(stroke):
        return False
    contact = sum(1 for cell in stroke if _touches_inner_wall(grid, cell, _NEIGHBOURS_8))
    return contact <= WALL_MAX_CONTACT


def _cut_doorway(stroke: list[Cell], rng: random.Random) -> list[Cell]:
    """Leave a gap in the middle of a long stroke, with probability WALL_DOOR_CHANCE."""
    if len(stroke) < 2 * MIN_WALL_LINE or rng.random() >= WALL_DOOR_CHANCE:
        return stroke
    i = rng.randint(len(stroke) // 4, 3 * len(stroke) // 4 - WALL_DOOR_WIDTH)
    return stroke[:i] + stroke[i + WALL_DOOR_WIDTH :]


def _connect_pockets(grid: Grid, interior: list[Cell]) -> None:
    """Carve the cheapest way out of every walled-in pocket to the main area.

    Wall lines (with each other or the frame) can close a ring around a patch
    of land; organisms spawned there could never leave.  A 0-1 BFS (wall
    costs 1, open ground 0) finds the path that removes the fewest walls.
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
        carved = []
        while cell is not None:
            col, row = cell
            if grid[row][col] == WALL:
                grid[row][col] = EMPTY
                carved.append(cell)
            cell = parent[cell]
        # A one-tile slit through a thin wall is narrower than a big
        # organism, so also open the wall cells along the line on either side.
        for col, row in carved:
            for dc, dr in _NEIGHBOURS_4:
                c, r = col + dc, row + dr
                if 0 < c < cols - 1 and 0 < r < rows - 1 and grid[r][c] == WALL:
                    grid[r][c] = EMPTY


def _plan_islands(kinds: list[int], total: int, water_fraction: float, rng: random.Random) -> list[tuple[int, int, int]]:
    """Split ``total`` tiles into one ``(tile, medium, size)`` island per kind.

    ``medium`` is what the island replaces: open land (``EMPTY``) or open
    water.  Lava always sits on land; of the rest, the first goes out on the
    water (so lakes get hazards and heal too, not only the land) and any
    further one lands in water with the board's water share as probability.
    """
    plan = []
    base, extra = divmod(max(0, total), max(1, len(kinds)))
    water_left = 1 if water_fraction > 0.0 else 0
    for i, kind in enumerate(kinds):
        size = base + (1 if i < extra else 0)
        medium = EMPTY
        if kind != LAVA and water_fraction > 0.0:
            if i > 0 and water_left:
                medium = WATER
                water_left = 0
            elif i > 0 and rng.random() < water_fraction:
                medium = WATER
        plan.append((kind, medium, size))
    return plan


def _scatter_islands(
    grid: Grid,
    interior: list[Cell],
    islands: list[tuple[int, int, int]],
    rng: random.Random,
    *,
    allowed: dict[int, list[Cell]],
    preferred: dict[int, list[Cell]] | None = None,
    spread: int = 3,
) -> None:
    """Grow one compact island per planned ``(tile, medium, size)``.

    Seeds come from ``preferred[tile]`` cells when any are still open, and
    keep ``spread`` tiles (Chebyshev) from every earlier seed of this call so
    the islands sit apart instead of merging.  An island grows only into
    ``allowed[medium]`` cells, falling back to any cell of its medium if
    those are used up; a water island with no lake to sit in goes on land.
    """
    seeds: list[Cell] = []
    for tile, medium, size in islands:
        if size <= 0:
            continue
        for where in (medium, EMPTY) if medium == WATER else (medium,):
            blob = _best_island(
                grid, interior, tile, where, size, rng, allowed.get(where), (preferred or {}).get(tile), seeds, spread
            )
            if blob:
                seeds.append(blob[0])
                break


def _best_island(grid, interior, tile, medium, size, rng, allowed, preferred, seeds, spread) -> list[Cell]:
    """Grow the best of a few attempts at one island; return its cells.

    A seed boxed in by walls or the shore grows a stunted island or a strip
    along a corridor, so a few seeds are tried and the first good island
    (or the best attempt) is kept; the others are reverted to ``medium``.
    """
    allowed_set = set(allowed) if allowed is not None else None
    best: list[Cell] = []
    best_quality = -1.0
    tried: list[Cell] = []
    for _ in range(ISLAND_SEED_TRIES):
        start = None
        for restrict in (allowed_set, None):

            def open_cell(cell: Cell, restrict=restrict) -> bool:
                return grid[cell[1]][cell[0]] == medium and (restrict is None or cell in restrict)

            roomy = _roomy(grid, open_cell, size)
            start = _pick_seed(interior, preferred, open_cell, seeds + tried, spread, rng, roomy)
            if start is not None:
                break
        if start is None:
            break
        tried.append(start)
        blob = _grow_patch(grid, start, size, tile, rng, open_cell)
        quality = _island_quality(blob, size)
        if quality > best_quality:
            for col, row in best:
                grid[row][col] = medium
            best, best_quality = blob, quality
        else:
            for col, row in blob:
                grid[row][col] = medium
        if best_quality >= 0.8:
            break
    return best


def _island_quality(blob: list[Cell], size: int) -> float:
    """1.0 for a full-size island no more than twice as long as it is wide."""
    width = max(c for c, _ in blob) - min(c for c, _ in blob) + 1
    height = max(r for _, r in blob) - min(r for _, r in blob) + 1
    elongation = max(width, height) / min(width, height)
    return len(blob) / size * min(1.0, 2.0 / elongation)


def _pick_seed(interior, preferred, open_land, seeds, spread, rng, roomy) -> Cell | None:
    """A random open, roomy cell ``spread`` away from ``seeds``.

    Keeping islands apart comes first: the gap may shrink to half of
    ``spread`` with room required, then without it, and only then further,
    so a crowded board still gets its islands without merging them.
    """
    gaps = range(spread, 0, -1)
    tiers = ([g for g in gaps if g >= spread // 2], [g for g in gaps if g < spread // 2])
    for tier, need_room in ((tiers[0], True), (tiers[0], False), (tiers[1], True), (tiers[1], False)):
        for gap in tier:
            for source in (preferred, interior):
                if not source:
                    continue
                pool = [
                    cell
                    for cell in source
                    if open_land(cell)
                    and (not need_room or roomy(cell))
                    and all(max(abs(cell[0] - s[0]), abs(cell[1] - s[1])) >= gap for s in seeds)
                ]
                if pool:
                    return rng.choice(pool)
    return None


def _roomy(grid: Grid, open_land, size: int):
    """Predicate: does the square around a cell hold enough open land for ``size``?

    A summed-area table over ``open_land`` makes each query O(1).  Without
    it an island seeded in a corridor between a wall and the frame grows
    into a long strip instead of a blob.
    """
    rows = len(grid)
    cols = len(grid[0])
    table = [[0] * (cols + 1) for _ in range(rows + 1)]
    for row in range(rows):
        running = 0
        for col in range(cols):
            running += open_land((col, row))
            table[row + 1][col + 1] = table[row][col + 1] + running
    # The square must be mostly open, not merely hold ``size`` cells: half
    # a square of frame or wall still fits the cells, but only as a strip.
    radius = max(1, math.ceil(math.sqrt(size) / 2))
    need = 0.75 * (2 * radius + 1) ** 2

    def roomy(cell: Cell) -> bool:
        c0 = max(0, cell[0] - radius)
        r0 = max(0, cell[1] - radius)
        c1 = min(cols, cell[0] + radius + 1)
        r1 = min(rows, cell[1] + radius + 1)
        return table[r1][c1] - table[r0][c1] - table[r1][c0] + table[r0][c0] >= need

    return roomy


def _grow_patch(grid: Grid, start: Cell, size: int, tile: int, rng: random.Random, can_take) -> list[Cell]:
    """Grow a compact 4-connected blob of up to ``size`` tiles from ``start``.

    Each step takes the open neighbour of the blob closest to the seed, with
    a little jitter, so the island comes out roundish with a ragged edge
    instead of a random-walk tendril.
    """
    grid[start[1]][start[0]] = tile
    grown = 1
    blob = [start]
    sc, sr = start
    while grown < size:
        options = {
            (col + dc, row + dr) for col, row in blob for dc, dr in _NEIGHBOURS_4 if can_take((col + dc, row + dr))
        }
        if not options:
            break
        nxt = min(options, key=lambda cell: math.hypot(cell[0] - sc, cell[1] - sr) + rng.uniform(0.0, 1.6))
        grid[nxt[1]][nxt[0]] = tile
        blob.append(nxt)
        grown += 1
    return blob
