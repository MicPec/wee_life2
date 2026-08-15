"""Simplified body-part icon drawing used by the in-simulation legend.

These icons are intentionally smaller and more stylised than the full
organism body-part renderers in ``body_drawing.py`` so they read clearly
inside the legend panel.
"""

from __future__ import annotations

import math

import pygame


Kind = str


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
    cx = x + size // 2
    p1 = (cx, y + 2)
    p2 = (x + 2, y + size - 2)
    p3 = (cx, y + size // 2)
    p4 = (x + size - 2, y + size - 2)
    pts = [p1, p2, p3, p4]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (100, 60, 50), pts, 1)


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


def _draw_legend_bolt(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    pts = [
        (cx - 2, y + 2),
        (cx + size // 4, cy),
        (cx - size // 4, cy),
        (cx + 2, y + size - 2),
    ]
    pygame.draw.polygon(surface, color, pts)


def _draw_legend_whiskers(surface, x, y, size, color):
    cx = x + size // 2
    for offset in (-1, 0, 1):
        start = (cx + offset * (size // 4), y + size - 3)
        end = (cx + offset * (size // 2), y + 3)
        pygame.draw.line(surface, color, start, end, 1)


def _draw_legend_flag(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    pole_top = (cx, y + 2)
    pygame.draw.line(surface, color, (cx, y + size - 2), pole_top, 2)
    pts = [pole_top, (x + size - 2, y + 2 + size // 4), (x + size - 2, y + size // 2), (cx, cy)]
    pygame.draw.polygon(surface, color, pts)


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


def _draw_legend_tadpole(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pygame.draw.circle(surface, color, (cx, cy), r - 1)
    tip = (cx, y + 2)
    left = (x + 2, y + size - 4)
    right = (x + size - 2, y + size - 4)
    pygame.draw.polygon(surface, color, [tip, left, right])
    pygame.draw.circle(surface, (20, 90, 110), (cx, cy), r - 1, 1)


def _draw_legend_fangs(surface, x, y, size, color):
    cx = x + size // 2
    base = (cx, y + size - 2)
    base_l = (cx - size // 3, y + size // 2)
    tip_l = (cx - 2, y + 2)
    tip_r = (cx + 2, y + 2)
    base_r = (cx + size // 3, y + size // 2)
    pts = [base, base_l, tip_l, tip_r, base_r]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (40, 100, 40), pts, 1)


def _draw_legend_bud(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    # Arrow-shaped body pointing right, with a small bud behind.
    tip = (cx + r, cy)
    base_l = (cx - r // 2, cy - r)
    base_r = (cx - r // 2, cy + r)
    pts = [tip, base_l, base_r]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (120, 140, 60), pts, 1)
    bud_x = cx - r // 2
    bud_y = cy
    pygame.draw.circle(surface, color, (bud_x, bud_y), max(1, r // 3))


def _draw_legend_maw(surface, x, y, size, color):
    cx, cy = x + size // 2, y + size // 2
    r = size // 2 - 1
    pygame.draw.circle(surface, color, (cx, cy), r)
    mouth = [
        (cx - size // 3, cy + 2),
        (cx - size // 5, y + size - 3),
        (cx, cy + size // 3),
        (cx + size // 5, y + size - 3),
        (cx + size // 3, cy + 2),
    ]
    pygame.draw.polygon(surface, (20, 20, 30), mouth)


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


LEGEND_DRAWERS: dict[Kind, type] = {
    "body": _draw_legend_body,
    "eye": _draw_legend_eye,
    "pincer": _draw_legend_pincer,
    "limb": _draw_legend_limb,
    "barb": _draw_legend_barb,
    "antenna": _draw_legend_antenna,
    "ellipse": _draw_legend_ellipse,
    "cross": _draw_legend_cross,
    "bolt": _draw_legend_bolt,
    "whiskers": _draw_legend_whiskers,
    "flag": _draw_legend_flag,
    "shield": _draw_legend_shield,
    "diamond": _draw_legend_diamond,
    "hexagon": _draw_legend_hexagon,
    "tadpole": _draw_legend_tadpole,
    "fangs": _draw_legend_fangs,
    "bud": _draw_legend_bud,
    "maw": _draw_legend_maw,
    "memory": _draw_legend_memory,
}


def draw_legend_icon(
    surface,
    x: int,
    y: int,
    size: int,
    color: tuple[int, int, int],
    shape: str,
) -> None:
    """Draw a small legend icon for the given shape."""
    drawer = LEGEND_DRAWERS.get(shape, _draw_legend_generic)
    drawer(surface, x, y, size, color)
