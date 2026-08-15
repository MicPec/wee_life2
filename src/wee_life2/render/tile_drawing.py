"""Shared tile drawing helpers for the renderer and map editor."""

from __future__ import annotations

import math

import pygame

from ..core import config

if config.TILE_SIZE > 0:
    TILE_RECT_SIZE = config.TILE_SIZE
else:
    TILE_RECT_SIZE = 10


def tile_color(tile: int, time_ms: int | None = None) -> tuple[int, int, int]:
    """Return the display color for a tile, including pulse effects."""
    if time_ms is None:
        time_ms = pygame.time.get_ticks()

    if tile == config.TILE_WALL:
        return config.COLOR_WALL
    if tile == config.TILE_RADIOACTIVE:
        pulse = 0.5 + 0.5 * math.sin(time_ms / 300)
        return tuple(int(c + (255 - c) * pulse * 0.25) for c in config.COLOR_RADIOACTIVE)
    if tile == config.TILE_LAVA:
        pulse = 0.5 + 0.5 * math.sin(time_ms / 200)
        return tuple(int(c + (255 - c) * pulse * 0.25) for c in config.COLOR_LAVA)
    if tile == config.TILE_WATER:
        wave = 0.5 + 0.5 * math.sin(time_ms / 400)
        return tuple(int(c + (255 - c) * wave * 0.12) for c in config.COLOR_WATER)
    if tile == config.TILE_HEAL:
        pulse = 0.5 + 0.5 * math.sin(time_ms / 350)
        return tuple(int(c + (255 - c) * pulse * 0.2) for c in config.COLOR_HEAL)
    return config.COLOR_BACKGROUND


def _tile_rect(col: int, row: int, tile_size: float) -> pygame.Rect:
    return pygame.Rect(
        int(col * tile_size),
        int(row * tile_size),
        int(tile_size),
        int(tile_size),
    )


def draw_tiles(
    surface: pygame.Surface,
    world,
    border: bool = False,
    time_ms: int | None = None,
) -> None:
    """Draw all non-empty tiles; optionally draw a border around every tile."""
    if time_ms is None:
        time_ms = pygame.time.get_ticks()

    tile_size = world.tile_size
    border_color = (50, 50, 60)

    for row in range(world.rows):
        for col in range(world.cols):
            tile = world.tiles[row][col]
            if tile == config.TILE_EMPTY and not border:
                continue
            rect = _tile_rect(col, row, tile_size)
            if tile != config.TILE_EMPTY:
                pygame.draw.rect(surface, tile_color(tile, time_ms), rect)
            if border:
                pygame.draw.rect(surface, border_color, rect, 1)


def draw_grid(surface: pygame.Surface, tile_size: float, width: int, height: int, color=(50, 50, 60)) -> None:
    """Draw a full-screen tile grid."""
    tile_size = int(tile_size)
    for x in range(0, width, tile_size):
        pygame.draw.line(surface, color, (x, 0), (x, height))
    for y in range(0, height, tile_size):
        pygame.draw.line(surface, color, (0, y), (width, y))


def draw_tile_highlight(
    surface: pygame.Surface,
    col: int,
    row: int,
    tile_size: float,
    color=(255, 255, 255),
    thickness: int = 2,
) -> None:
    """Draw a highlighted border around a single tile."""
    rect = _tile_rect(col, row, tile_size)
    pygame.draw.rect(surface, color, rect, thickness)
