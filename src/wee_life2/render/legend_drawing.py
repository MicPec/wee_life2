"""Simplified body-part icon drawing used by the in-simulation legend.

These icons are intentionally smaller and more stylised than the full
organism body-part renderers in ``body_drawing.py`` so they read clearly
inside the legend panel.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pygame

# A legend drawer paints one icon: (surface, x, y, size, color).
LegendDrawer = Callable[[pygame.Surface, int, int, int, tuple[int, int, int]], None]


def _draw_legend_body(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pygame.draw.circle(surface, color, (cx, cy), r)
    pygame.draw.circle(
        surface,
        (max(0, color[0] - 30), max(0, color[1] - 30), max(0, color[2] - 30)),
        (cx, cy),
        r,
        1,
    )


def _draw_legend_eye(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pygame.draw.circle(surface, color, (cx, cy), r)
    pygame.draw.circle(surface, (20, 20, 20), (cx + 2, cy), max(1, size // 5))


def _draw_legend_pincer(surface, x, y, size, color):
    """Two thick claw lines in a V opening downward — crab pincers."""
    cx = x + size // 2
    w = max(2, size // 4)
    spread = size // 3
    base = (cx, y + 2)
    for side in (-1, 1):
        tip = (cx + side * spread, y + size - 2)
        pygame.draw.line(surface, color, base, tip, w)
        pygame.draw.circle(surface, color, tip, w // 2)


def _draw_legend_limb(surface, x, y, size, color):
    cy = y + size // 2
    half = max(1, size // 4)
    start = (x + 3, cy)
    end = (x + size - 3, cy)
    pygame.draw.line(surface, color, start, end, half)
    pygame.draw.circle(surface, color, start, half)
    pygame.draw.circle(surface, color, end, half)


def _draw_legend_barb(surface, x, y, size, color):
    # Right-pointing barbed thorn, matching the body-part spike orientation.
    cy = y + size // 2
    # Scale so the spike (tip at right, barb sticking left) fits the icon cell.
    s = max(1, (size - 4) / 1.97)
    cx = x + int(abs(math.cos(2.2)) * 0.8 * s) + 2
    tip = (x + size - 2, cy)
    base_l = (cx + int(math.cos(2.5) * 0.18 * s), cy + int(math.sin(2.5) * 0.18 * s))
    base_r = (cx + int(math.cos(-2.5) * 0.18 * s), cy + int(math.sin(-2.5) * 0.18 * s))
    barb = (cx + int(math.cos(-2.2) * 0.8 * s), cy + int(math.sin(-2.2) * 0.8 * s))
    pts = [tip, base_r, barb, base_l]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (120, 40, 40), pts, 1)


def _draw_legend_antenna(surface, x, y, size, color):
    cx = x + size // 2
    tip = (cx, y + 2)
    pygame.draw.line(surface, color, (cx, y + size - 2), tip, 2)
    pygame.draw.circle(surface, color, tip, 2)


def _draw_legend_ellipse(surface, x, y, size, color):
    pygame.draw.ellipse(surface, color, (x + 2, y + size // 4, size - 4, size // 2))


def _draw_legend_cross(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    t = size * 0.35
    w = size * 0.22
    pts = [
        (cx - w, cy - t),
        (cx + w, cy - t),
        (cx + w, cy - w),
        (cx + t, cy - w),
        (cx + t, cy + w),
        (cx + w, cy + w),
        (cx + w, cy + t),
        (cx - w, cy + t),
        (cx - w, cy + w),
        (cx - t, cy + w),
        (cx - t, cy - w),
        (cx - w, cy - w),
    ]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (40, 120, 80), pts, 1)


def _draw_legend_exclamation(surface, x, y, size, color):
    """Exclamation mark — alarm state."""
    cx = x + size // 2
    bar_w = max(3, size // 4)
    bar_h = int(size * 0.55)
    bar_rect = (cx - bar_w // 2, y + 2, bar_w, bar_h)
    pygame.draw.rect(surface, color, bar_rect, border_radius=bar_w // 2)
    pygame.draw.circle(surface, color, (cx, y + size - 3), max(2, size // 5))


def _draw_legend_sonar(surface, x, y, size, color):
    """Sonar — two bold arcs radiating upward (proximity sense)."""
    cx = x + size // 2
    cy = y + size - 2
    span = 1.8
    steps = 8
    for frac in (0.5, 0.85):
        r = (size - 2) * frac
        pts = []
        for i in range(steps + 1):
            t = -math.pi / 2 - span / 2 + span * i / steps
            pts.append((cx + int(math.cos(t) * r), cy + int(math.sin(t) * r)))
        if len(pts) >= 2:
            pygame.draw.lines(surface, color, False, pts, 2)


def _draw_legend_cluster(surface, x, y, size, color):
    """Three dots in a cluster — herd / group attraction."""
    cx, cy = x + size // 2, y + size // 2
    r = max(2, size // 5)
    for ang_offset in (0, 2 * math.pi / 3, 4 * math.pi / 3):
        dx = int(math.cos(ang_offset - math.pi / 2) * size * 0.25)
        dy = int(math.sin(ang_offset - math.pi / 2) * size * 0.25)
        pygame.draw.circle(surface, color, (cx + dx, cy + dy), r)


def _draw_legend_shield(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pts = [
        (cx - r, cy - r),
        (cx + r, cy - r),
        (cx + r, cy + int(r * 0.3)),
        (cx, cy + int(r * 1.3)),
        (cx - r, cy + int(r * 0.3)),
    ]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (100, 100, 110), pts, 1)


def _draw_legend_diamond(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    pts = [
        (cx, y + 2),
        (x + size - 2, cy),
        (cx, y + size - 2),
        (x + 2, cy),
    ]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (255, 150, 220), pts, 1)


def _draw_legend_hexagon(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pts = []
    for i in range(6):
        ang = i * math.pi / 3
        pts.append((cx + int(math.cos(ang) * r), cy + int(math.sin(ang) * r)))
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.circle(surface, (90, 30, 120), (cx, cy), max(1, r // 2))


def _draw_legend_ring(surface, x, y, size, color):
    """Hollow blue ring (amphibious)."""
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pygame.draw.circle(surface, color, (cx, cy), r, 2)
    pygame.draw.circle(surface, (20, 90, 110), (cx, cy), r, 1)


def _draw_legend_drop(surface, x, y, size, color):
    """Crossed bones (X) — universal poison/death symbol."""
    cx, cy = x + size // 2, y + size // 2
    d = size // 2 - 1
    tip_r = max(2, size // 5)
    pygame.draw.line(surface, color, (cx - d, cy - d), (cx + d, cy + d), 2)
    pygame.draw.line(surface, color, (cx - d, cy + d), (cx + d, cy - d), 2)
    for px, py in ((cx - d, cy - d), (cx + d, cy + d), (cx - d, cy + d), (cx + d, cy - d)):
        pygame.draw.circle(surface, color, (px, py), tip_r)


def _draw_legend_mitosis(surface, x, y, size, color):
    """Mitosis — two touching circles (cell division)."""
    cy = y + size // 2
    r = max(2, (size - 4) // 3)
    gap = max(1, r // 3)
    cx1 = x + size // 2 - r + gap // 2
    cx2 = x + size // 2 + r - gap // 2
    pygame.draw.circle(surface, color, (cx1, cy), r)
    pygame.draw.circle(surface, color, (cx2, cy), r)
    pygame.draw.circle(surface, (120, 140, 60), (cx1, cy), r, 1)
    pygame.draw.circle(surface, (120, 140, 60), (cx2, cy), r, 1)
    pygame.draw.line(surface, (120, 140, 60), (x + size // 2, cy - r // 2), (x + size // 2, cy + r // 2), 1)


def _draw_legend_maw(surface, x, y, size, color):
    """Single downward fang — predator's bite."""
    cx = x + size // 2
    r = size // 2 - 1
    tip = (cx, y + size - 2)
    base_l = (cx - r, y + 2)
    base_r = (cx + r, y + 2)
    pygame.draw.polygon(surface, color, [base_l, base_r, tip])
    pygame.draw.polygon(surface, (20, 20, 30), [base_l, base_r, tip], 1)


def _draw_legend_generic(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pygame.draw.circle(surface, color, (cx, cy), max(1, r))


def _draw_legend_memory(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pts = [
        (cx, cy - r),
        (cx + r, cy),
        (cx, cy + r),
        (cx - r, cy),
    ]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (120, 80, 140), pts, 1)
    pygame.draw.circle(surface, (240, 220, 255), (cx, cy), max(1, r // 3))


LEGEND_DRAWERS: dict[str, LegendDrawer] = {
    "body": _draw_legend_body,
    "eye": _draw_legend_eye,
    "pincer": _draw_legend_pincer,
    "limb": _draw_legend_limb,
    "barb": _draw_legend_barb,
    "antenna": _draw_legend_antenna,
    "ellipse": _draw_legend_ellipse,
    "cross": _draw_legend_cross,
    "exclamation": _draw_legend_exclamation,
    "sonar": _draw_legend_sonar,
    "cluster": _draw_legend_cluster,
    "shield": _draw_legend_shield,
    "diamond": _draw_legend_diamond,
    "hexagon": _draw_legend_hexagon,
    "ring": _draw_legend_ring,
    "drop": _draw_legend_drop,
    "mitosis": _draw_legend_mitosis,
    "maw": _draw_legend_maw,
    "memory": _draw_legend_memory,
}


def draw_legend_icon(
    surface: pygame.Surface,
    x: int,
    y: int,
    size: int,
    color: tuple[int, int, int],
    shape: str,
) -> None:
    """Draw a small legend icon for the given shape."""
    drawer = LEGEND_DRAWERS.get(shape, _draw_legend_generic)
    drawer(surface, x, y, size, color)
