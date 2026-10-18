"""Tile map: the simulation board and tile-based queries."""

from __future__ import annotations

import math
import random
from typing import Iterable

from . import config
from .map_generator import generate_terrain


class TileMap:
    """Container and manager for the 2D tile board."""

    TILE_EMPTY = config.TILE_EMPTY
    TILE_WALL = config.TILE_WALL
    TILE_RADIOACTIVE = config.TILE_RADIOACTIVE
    TILE_LAVA = config.TILE_LAVA
    TILE_WATER = config.TILE_WATER
    TILE_HEAL = config.TILE_HEAL

    def __init__(self, width: float, height: float, tile_size: float = config.TILE_SIZE) -> None:
        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.cols = int(width / tile_size)
        self.rows = int(height / tile_size)
        self.max_x = self.cols * tile_size
        self.max_y = self.rows * tile_size

        self.tiles: list[list[int]] = [[self.TILE_EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        self._obstacles_generated = False

    def tile_at(self, position: tuple[float, float]) -> int:
        col = int(position[0] / self.tile_size)
        row = int(position[1] / self.tile_size)
        # A point exactly on the far edge belongs to the last tile: the grid
        # covers the closed range [0, max_x] x [0, max_y].
        if col == self.cols and position[0] <= self.max_x + 1e-6:
            col = self.cols - 1
        if row == self.rows and position[1] <= self.max_y + 1e-6:
            row = self.rows - 1
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.tiles[row][col]
        return self.TILE_WALL

    def set_tile(self, col: int, row: int, value: int) -> None:
        if 0 <= col < self.cols and 0 <= row < self.rows:
            self.tiles[row][col] = value

    def is_wall(self, position: tuple[float, float]) -> bool:
        return self.tile_at(position) == self.TILE_WALL

    def is_hazard(self, position: tuple[float, float]) -> bool:
        """Return True if the tile at position is an environmental hazard."""
        tile = self.tile_at(position)
        return tile in (self.TILE_RADIOACTIVE, self.TILE_LAVA)

    def is_water(self, position: tuple[float, float]) -> bool:
        """Return True if the tile at position is water."""
        return self.tile_at(position) == self.TILE_WATER

    def is_heal(self, position: tuple[float, float]) -> bool:
        """Return True if the tile at position is a heal tile."""
        return self.tile_at(position) == self.TILE_HEAL

    def tiles_along_line(self, a: tuple[float, float], b: tuple[float, float]) -> Iterable[tuple[int, int]]:
        """Yield all tile column/row coordinates traversed by the line segment a->b."""
        x0, y0 = a
        x1, y1 = b
        c0 = int(x0 / self.tile_size)
        r0 = int(y0 / self.tile_size)
        c1 = int(x1 / self.tile_size)
        r1 = int(y1 / self.tile_size)
        if c0 == self.cols and x0 <= self.max_x + 1e-6:
            c0 -= 1
        if r0 == self.rows and y0 <= self.max_y + 1e-6:
            r0 -= 1
        if c1 == self.cols and x1 <= self.max_x + 1e-6:
            c1 -= 1
        if r1 == self.rows and y1 <= self.max_y + 1e-6:
            r1 -= 1

        if c0 == c1 and r0 == r1:
            yield (c0, r0)
            return

        dc = abs(c1 - c0)
        dr = abs(r1 - r0)
        sc = 1 if c0 < c1 else -1
        sr = 1 if r0 < r1 else -1
        err = dc - dr

        c, r = c0, r0
        while True:
            yield (c, r)
            if c == c1 and r == r1:
                break
            e2 = 2 * err
            if e2 > -dr:
                err -= dr
                c += sc
            if e2 < dc:
                err += dc
                r += sr

    def distance_to_obstacle_along_ray(
        self,
        position: tuple[float, float],
        angle: float,
        max_dist: float,
        avoid_water: bool = False,
    ) -> tuple[float, bool] | None:
        """Return ``(distance, is_hazard)`` for the first wall/hazard tile along a ray.

        ``is_hazard`` is ``True`` for radioactive, lava or water tiles (when
        ``avoid_water`` is set) and ``False`` for walls.  Returns ``None`` if the
        ray reaches ``max_dist`` without hitting anything.
        """
        x0, y0 = position
        end_x = x0 + math.cos(angle) * max_dist
        end_y = y0 + math.sin(angle) * max_dist
        tile_size = self.tile_size
        c0 = int(x0 / tile_size)
        r0 = int(y0 / tile_size)
        c1 = int(end_x / tile_size)
        r1 = int(end_y / tile_size)

        hazard_types = (self.TILE_RADIOACTIVE, self.TILE_LAVA)
        if c0 == c1 and r0 == r1:
            if 0 <= c0 < self.cols and 0 <= r0 < self.rows:
                tile = self.tiles[r0][c0]
                if tile == self.TILE_WALL:
                    return (0.0, False)
                if tile in hazard_types or (avoid_water and tile == self.TILE_WATER):
                    return (0.0, True)
            return None

        dc = abs(c1 - c0)
        dr = abs(r1 - r0)
        sc = 1 if c0 < c1 else -1
        sr = 1 if r0 < r1 else -1
        err = dc - dr
        c, r = c0, r0
        tiles = self.tiles
        cols = self.cols
        rows = self.rows
        while True:
            if 0 <= c < cols and 0 <= r < rows:
                tile = tiles[r][c]
                if tile == self.TILE_WALL:
                    dx = (c + 0.5) * tile_size - x0
                    dy = (r + 0.5) * tile_size - y0
                    return (math.hypot(dx, dy), False)
                if tile in hazard_types or (avoid_water and tile == self.TILE_WATER):
                    dx = (c + 0.5) * tile_size - x0
                    dy = (r + 0.5) * tile_size - y0
                    return (math.hypot(dx, dy), True)
            else:
                dx = (c + 0.5) * tile_size - x0
                dy = (r + 0.5) * tile_size - y0
                return (math.hypot(dx, dy), False)
            if c == c1 and r == r1:
                break
            e2 = 2 * err
            if e2 > -dr:
                err -= dr
                c += sc
            if e2 < dc:
                err += dc
                r += sr
        return None

    def first_interesting_tile_along_ray(
        self,
        position: tuple[float, float],
        angle: float,
        max_dist: float,
    ) -> tuple[tuple[float, float], int] | None:
        """Return ``((x, y), tile_type)`` for the first non-empty tile along a ray.

        The returned position is the centre of the hit tile.  Returns ``None``
        if the ray reaches ``max_dist`` without hitting anything.
        """
        x0, y0 = position
        end_x = x0 + math.cos(angle) * max_dist
        end_y = y0 + math.sin(angle) * max_dist
        tile_size = self.tile_size
        c0 = int(x0 / tile_size)
        r0 = int(y0 / tile_size)
        c1 = int(end_x / tile_size)
        r1 = int(end_y / tile_size)

        if c0 == c1 and r0 == r1:
            if 0 <= c0 < self.cols and 0 <= r0 < self.rows:
                tile = self.tiles[r0][c0]
                if tile != self.TILE_EMPTY:
                    return ((c0 + 0.5) * tile_size, (r0 + 0.5) * tile_size), tile
            return None

        dc = abs(c1 - c0)
        dr = abs(r1 - r0)
        sc = 1 if c0 < c1 else -1
        sr = 1 if r0 < r1 else -1
        err = dc - dr
        c, r = c0, r0
        tiles = self.tiles
        cols = self.cols
        rows = self.rows
        while True:
            if 0 <= c < cols and 0 <= r < rows:
                tile = tiles[r][c]
                if tile != self.TILE_EMPTY:
                    return ((c + 0.5) * tile_size, (r + 0.5) * tile_size), tile
            else:
                return ((c + 0.5) * tile_size, (r + 0.5) * tile_size), self.TILE_WALL
            if c == c1 and r == r1:
                break
            e2 = 2 * err
            if e2 > -dr:
                err -= dr
                c += sc
            if e2 < dc:
                err += dc
                r += sr
        return None

    def line_crosses_wall(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        """Return True if the line segment between a and b crosses a wall tile."""
        x0, y0 = a
        x1, y1 = b
        tile_size = self.tile_size
        c0 = int(x0 / tile_size)
        r0 = int(y0 / tile_size)
        c1 = int(x1 / tile_size)
        r1 = int(y1 / tile_size)
        if c0 == self.cols and x0 <= self.max_x + 1e-6:
            c0 -= 1
        if r0 == self.rows and y0 <= self.max_y + 1e-6:
            r0 -= 1
        if c1 == self.cols and x1 <= self.max_x + 1e-6:
            c1 -= 1
        if r1 == self.rows and y1 <= self.max_y + 1e-6:
            r1 -= 1
        if c0 == c1 and r0 == r1:
            return not (0 <= c0 < self.cols and 0 <= r0 < self.rows) or self.tiles[r0][c0] == self.TILE_WALL

        dc = abs(c1 - c0)
        dr = abs(r1 - r0)
        sc = 1 if c0 < c1 else -1
        sr = 1 if r0 < r1 else -1
        err = dc - dr
        c, r = c0, r0
        tiles = self.tiles
        cols = self.cols
        rows = self.rows
        while True:
            if not (0 <= c < cols and 0 <= r < rows):
                return True
            if tiles[r][c] == self.TILE_WALL:
                return True
            if c == c1 and r == r1:
                break
            e2 = 2 * err
            if e2 > -dr:
                err -= dr
                c += sc
            if e2 < dc:
                err += dc
                r += sr
        return False

    def line_crosses_water(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        return self._line_crosses_tile(a, b, (self.TILE_WATER,))

    def line_crosses_hazard(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        return self._line_crosses_tile(a, b, (self.TILE_RADIOACTIVE, self.TILE_LAVA))

    def _line_crosses_tile(self, a: tuple[float, float], b: tuple[float, float], tile_types: tuple[int, ...]) -> bool:
        """Return True if the line segment between a and b crosses any tile in ``tile_types``."""
        x0, y0 = a
        x1, y1 = b
        tile_size = self.tile_size
        c0 = int(x0 / tile_size)
        r0 = int(y0 / tile_size)
        c1 = int(x1 / tile_size)
        r1 = int(y1 / tile_size)
        if c0 == self.cols and x0 <= self.max_x + 1e-6:
            c0 -= 1
        if r0 == self.rows and y0 <= self.max_y + 1e-6:
            r0 -= 1
        if c1 == self.cols and x1 <= self.max_x + 1e-6:
            c1 -= 1
        if r1 == self.rows and y1 <= self.max_y + 1e-6:
            r1 -= 1
        if c0 == c1 and r0 == r1:
            return 0 <= c0 < self.cols and 0 <= r0 < self.rows and self.tiles[r0][c0] in tile_types

        dc = abs(c1 - c0)
        dr = abs(r1 - r0)
        sc = 1 if c0 < c1 else -1
        sr = 1 if r0 < r1 else -1
        err = dc - dr
        c, r = c0, r0
        tiles = self.tiles
        cols = self.cols
        rows = self.rows
        while True:
            if 0 <= c < cols and 0 <= r < rows and tiles[r][c] in tile_types:
                return True
            if c == c1 and r == r1:
                break
            e2 = 2 * err
            if e2 > -dr:
                err -= dr
                c += sc
            if e2 < dc:
                err += dc
                r += sr
        return False

    def generate_map(
        self,
        seed: int | None = None,
        *,
        water_fraction: float | None = None,
        wall_fraction: float | None = None,
        hazard_fraction: float | None = None,
        heal_fraction: float | None = None,
    ) -> None:
        """Grow a fresh board of lakes, islands, rock, hazards and heal oases.

        See ``map_generator.generate_terrain``; ``None`` fractions fall back to
        the ``MAP_*`` config constants.  The grid is rewritten in place so
        anything holding ``self.tiles`` keeps seeing the live board.
        """
        rng = random.Random(seed) if seed is not None else None
        terrain = generate_terrain(
            self.cols,
            self.rows,
            rng,
            water_fraction=water_fraction,
            wall_fraction=wall_fraction,
            hazard_fraction=hazard_fraction,
            heal_fraction=heal_fraction,
        )
        for row, line in zip(self.tiles, terrain):
            row[:] = line
        self._obstacles_generated = True

    def clear_map(self) -> None:
        """Clear the board, keeping the border walls."""
        for row in range(self.rows):
            for col in range(self.cols):
                if row == 0 or row == self.rows - 1 or col == 0 or col == self.cols - 1:
                    self.tiles[row][col] = self.TILE_WALL
                else:
                    self.tiles[row][col] = self.TILE_EMPTY

    def load_tiles(self, tiles: list[list[int]]) -> None:
        """Replace the board with a saved tile layout."""
        for row in range(min(self.rows, len(tiles))):
            for col in range(min(self.cols, len(tiles[row]))):
                self.tiles[row][col] = tiles[row][col]
        self._obstacles_generated = True

    def save_tiles(self) -> list[list[int]]:
        """Return a copy of the current tile layout."""
        return [row[:] for row in self.tiles]

    def random_empty_position(
        self,
        margin: float = 30.0,
        radius: float = 10.0,
        in_water: bool | None = None,
    ) -> tuple[float, float]:
        """Return a random empty position, guaranteed not to be inside a wall."""
        for _ in range(200):
            x = random.uniform(margin, self.width - margin)
            y = random.uniform(margin, self.height - margin)
            if not self.is_empty_circle((x, y), radius):
                continue
            if in_water is not None and self.is_water((x, y)) != in_water:
                continue
            return (x, y)

        # Fallback: scan tiles and return the centre of the first matching tile
        target = self.TILE_WATER if in_water else self.TILE_EMPTY
        for row in range(self.rows):
            for col in range(self.cols):
                if self.tiles[row][col] == target:
                    return (
                        (col + 0.5) * self.tile_size,
                        (row + 0.5) * self.tile_size,
                    )

        # If no matching tile exists, fall back to any empty/water tile
        opposite = self.TILE_EMPTY if in_water else self.TILE_WATER
        for row in range(self.rows):
            for col in range(self.cols):
                if self.tiles[row][col] == opposite:
                    return (
                        (col + 0.5) * self.tile_size,
                        (row + 0.5) * self.tile_size,
                    )
        return (self.width / 2, self.height / 2)

    def is_empty_circle(self, position: tuple[float, float], radius: float) -> bool:
        """Check that a circle of given radius does not intersect any wall or hazard."""
        x, y = position
        tile_size = self.tile_size
        cols = self.cols
        rows = self.rows
        tiles = self.tiles
        wall = self.TILE_WALL
        hazards = (self.TILE_RADIOACTIVE, self.TILE_LAVA)

        def _blocked(px: float, py: float) -> bool:
            cx = int(px / tile_size)
            cy = int(py / tile_size)
            if cx == cols and px <= self.max_x + 1e-6:
                cx = cols - 1
            if cy == rows and py <= self.max_y + 1e-6:
                cy = rows - 1
            if 0 <= cx < cols and 0 <= cy < rows:
                tile = tiles[cy][cx]
                return tile == wall or tile in hazards
            return True

        if _blocked(x, y):
            return False
        samples = 6
        for i in range(samples):
            angle = (2 * math.pi * i) / samples
            px = x + math.cos(angle) * radius
            py = y + math.sin(angle) * radius
            if _blocked(px, py):
                return False
        return True

    def is_wall_circle(self, position: tuple[float, float], radius: float) -> bool:
        """Return True if a circle at position overlaps any wall tile."""
        x, y = position
        tile_size = self.tile_size
        cols = self.cols
        rows = self.rows
        tiles = self.tiles
        cx = int(x / tile_size)
        cy = int(y / tile_size)
        if cx == cols and x <= self.max_x + 1e-6:
            cx = cols - 1
        if cy == rows and y <= self.max_y + 1e-6:
            cy = rows - 1
        if 0 <= cx < cols and 0 <= cy < rows:
            if tiles[cy][cx] == self.TILE_WALL:
                return True
        else:
            return True

        # Six samples give enough coverage for tile-size walls while reducing
        # the per-call cost by ~25% compared to eight.
        samples = 6
        for i in range(samples):
            angle = (2 * math.pi * i) / samples
            px = x + math.cos(angle) * radius
            py = y + math.sin(angle) * radius
            cx = int(px / tile_size)
            cy = int(py / tile_size)
            if cx == cols and px <= self.max_x + 1e-6:
                cx = cols - 1
            if cy == rows and py <= self.max_y + 1e-6:
                cy = rows - 1
            if 0 <= cx < cols and 0 <= cy < rows:
                if tiles[cy][cx] == self.TILE_WALL:
                    return True
            else:
                return True
        return False

    def nearest_empty_position(self, position: tuple[float, float]) -> tuple[float, float]:
        """Find the closest empty tile centre to the given position."""
        start_col = max(0, min(self.cols - 1, int(position[0] / self.tile_size)))
        start_row = max(0, min(self.rows - 1, int(position[1] / self.tile_size)))

        max_radius = max(self.cols, self.rows)
        for r in range(max_radius):
            for row in range(max(0, start_row - r), min(self.rows, start_row + r + 1)):
                for col in range(max(0, start_col - r), min(self.cols, start_col + r + 1)):
                    if abs(row - start_row) != r and abs(col - start_col) != r:
                        continue
                    if self.tiles[row][col] == self.TILE_EMPTY:
                        return ((col + 0.5) * self.tile_size, (row + 0.5) * self.tile_size)
        return position

    def nearest_water(self, position: tuple[float, float], max_dist: float) -> tuple[float, float] | None:
        """Find the closest water tile centre within max_dist, or None."""
        start_col = max(0, min(self.cols - 1, int(position[0] / self.tile_size)))
        start_row = max(0, min(self.rows - 1, int(position[1] / self.tile_size)))
        tile_radius = max(1, int(max_dist / self.tile_size))

        best = None
        best_dist = float("inf")
        max_dist_sq = max_dist * max_dist
        for r in range(tile_radius + 1):
            rmin = max(0, start_row - r)
            rmax = min(self.rows, start_row + r + 1)
            cmin = max(0, start_col - r)
            cmax = min(self.cols, start_col + r + 1)

            # Top and bottom rows.
            if start_row - r >= 0:
                for col in range(cmin, cmax):
                    if self.tiles[start_row - r][col] != self.TILE_WATER:
                        continue
                    candidate = ((col + 0.5) * self.tile_size, (start_row - r + 0.5) * self.tile_size)
                    d2 = (candidate[0] - position[0]) ** 2 + (candidate[1] - position[1]) ** 2
                    if d2 <= max_dist_sq and d2 < best_dist * best_dist:
                        d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])
                        best_dist = d
                        best = candidate
            if r > 0 and start_row + r < self.rows:
                for col in range(cmin, cmax):
                    if self.tiles[start_row + r][col] != self.TILE_WATER:
                        continue
                    candidate = ((col + 0.5) * self.tile_size, (start_row + r + 0.5) * self.tile_size)
                    d2 = (candidate[0] - position[0]) ** 2 + (candidate[1] - position[1]) ** 2
                    if d2 <= max_dist_sq and d2 < best_dist * best_dist:
                        d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])
                        best_dist = d
                        best = candidate
            # Left and right columns (excluding corners already handled above).
            if start_col - r >= 0:
                for row in range(rmin + 1, rmax - 1):
                    if self.tiles[row][start_col - r] != self.TILE_WATER:
                        continue
                    candidate = ((start_col - r + 0.5) * self.tile_size, (row + 0.5) * self.tile_size)
                    d2 = (candidate[0] - position[0]) ** 2 + (candidate[1] - position[1]) ** 2
                    if d2 <= max_dist_sq and d2 < best_dist * best_dist:
                        d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])
                        best_dist = d
                        best = candidate
            if r > 0 and start_col + r < self.cols:
                for row in range(rmin + 1, rmax - 1):
                    if self.tiles[row][start_col + r] != self.TILE_WATER:
                        continue
                    candidate = ((start_col + r + 0.5) * self.tile_size, (row + 0.5) * self.tile_size)
                    d2 = (candidate[0] - position[0]) ** 2 + (candidate[1] - position[1]) ** 2
                    if d2 <= max_dist_sq and d2 < best_dist * best_dist:
                        d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])
                        best_dist = d
                        best = candidate
        return best

    def nearest_heal(self, position: tuple[float, float], max_dist: float) -> tuple[float, float] | None:
        """Find the closest heal tile centre within max_dist, or None."""
        start_col = max(0, min(self.cols - 1, int(position[0] / self.tile_size)))
        start_row = max(0, min(self.rows - 1, int(position[1] / self.tile_size)))
        tile_radius = max(1, int(max_dist / self.tile_size))

        best = None
        best_dist = float("inf")
        max_dist_sq = max_dist * max_dist
        for r in range(tile_radius + 1):
            rmin = max(0, start_row - r)
            rmax = min(self.rows, start_row + r + 1)
            cmin = max(0, start_col - r)
            cmax = min(self.cols, start_col + r + 1)

            if start_row - r >= 0:
                for col in range(cmin, cmax):
                    if self.tiles[start_row - r][col] != self.TILE_HEAL:
                        continue
                    candidate = ((col + 0.5) * self.tile_size, (start_row - r + 0.5) * self.tile_size)
                    d2 = (candidate[0] - position[0]) ** 2 + (candidate[1] - position[1]) ** 2
                    if d2 <= max_dist_sq and d2 < best_dist * best_dist:
                        d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])
                        best_dist = d
                        best = candidate
            if r > 0 and start_row + r < self.rows:
                for col in range(cmin, cmax):
                    if self.tiles[start_row + r][col] != self.TILE_HEAL:
                        continue
                    candidate = ((col + 0.5) * self.tile_size, (start_row + r + 0.5) * self.tile_size)
                    d2 = (candidate[0] - position[0]) ** 2 + (candidate[1] - position[1]) ** 2
                    if d2 <= max_dist_sq and d2 < best_dist * best_dist:
                        d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])
                        best_dist = d
                        best = candidate
            if start_col - r >= 0:
                for row in range(rmin + 1, rmax - 1):
                    if self.tiles[row][start_col - r] != self.TILE_HEAL:
                        continue
                    candidate = ((start_col - r + 0.5) * self.tile_size, (row + 0.5) * self.tile_size)
                    d2 = (candidate[0] - position[0]) ** 2 + (candidate[1] - position[1]) ** 2
                    if d2 <= max_dist_sq and d2 < best_dist * best_dist:
                        d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])
                        best_dist = d
                        best = candidate
            if r > 0 and start_col + r < self.cols:
                for row in range(rmin + 1, rmax - 1):
                    if self.tiles[row][start_col + r] != self.TILE_HEAL:
                        continue
                    candidate = ((start_col + r + 0.5) * self.tile_size, (row + 0.5) * self.tile_size)
                    d2 = (candidate[0] - position[0]) ** 2 + (candidate[1] - position[1]) ** 2
                    if d2 <= max_dist_sq and d2 < best_dist * best_dist:
                        d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])
                        best_dist = d
                        best = candidate
        return best

    def push_out_of_walls(self, position: tuple[float, float], radius: float) -> tuple[float, float]:
        """Move a circle out of any wall tiles it overlaps without crossing walls."""
        if not self.is_wall_circle(position, radius):
            return position

        col0 = int(position[0] / self.tile_size)
        row0 = int(position[1] / self.tile_size)
        col0 = max(0, min(self.cols - 1, col0))
        row0 = max(0, min(self.rows - 1, row0))

        max_radius = min(10, max(self.cols, self.rows))
        best_any = None
        best_any_dist = float("inf")

        for r in range(max_radius):
            for row in range(max(0, row0 - r), min(self.rows, row0 + r + 1)):
                for col in range(max(0, col0 - r), min(self.cols, col0 + r + 1)):
                    if abs(row - row0) != r and abs(col - col0) != r:
                        continue
                    if self.tiles[row][col] != self.TILE_EMPTY:
                        continue

                    candidate = ((col + 0.5) * self.tile_size, (row + 0.5) * self.tile_size)
                    d = math.hypot(candidate[0] - position[0], candidate[1] - position[1])

                    if not self.line_crosses_wall(position, candidate):
                        if d < best_any_dist:
                            best_any_dist = d
                            best_any = (row, col, candidate)

        if best_any is not None:
            search_row, search_col, _ = best_any
            for r in range(4):
                for row in range(max(0, search_row - r), min(self.rows, search_row + r + 1)):
                    for col in range(max(0, search_col - r), min(self.cols, search_col + r + 1)):
                        if abs(row - search_row) != r and abs(col - search_col) != r:
                            continue
                        if self.tiles[row][col] != self.TILE_EMPTY:
                            continue
                        candidate = ((col + 0.5) * self.tile_size, (row + 0.5) * self.tile_size)
                        if not self.line_crosses_wall(position, candidate):
                            if self.is_empty_circle(candidate, radius):
                                return candidate

            return best_any[2]

        # Fallback: jump to the nearest empty tile centre regardless of path
        nearest = self.nearest_empty_position(position)
        if not self.line_crosses_wall(position, nearest):
            return nearest

        # Last resort: small random jitter away from the wall tile centre
        x, y = position
        for _ in range(20):
            if not self.is_wall_circle((x, y), radius):
                return (x, y)
            col = int(x / self.tile_size)
            row = int(y / self.tile_size)
            col = max(0, min(self.cols - 1, col))
            row = max(0, min(self.rows - 1, row))
            wall_x = (col + 0.5) * self.tile_size
            wall_y = (row + 0.5) * self.tile_size
            dx = x - wall_x
            dy = y - wall_y
            dist = math.hypot(dx, dy)
            if dist < 1:
                dx, dy = random.uniform(-1, 1), random.uniform(-1, 1)
                dist = math.hypot(dx, dy)
            step = self.tile_size
            x += (dx / dist) * step
            y += (dy / dist) * step
            x = max(radius, min(self.width - radius, x))
            y = max(radius, min(self.height - radius, y))
        return nearest
