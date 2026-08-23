"""Body part drawing registry shared by renderer and legend."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import pygame


@dataclass
class DrawContext:
    """All information a body-part drawer needs."""

    surface: pygame.Surface
    x: int
    y: int
    size: int
    angle: float
    color: tuple[int, int, int]
    organism: Any | None = None
    overlays: dict[str, pygame.Surface] | None = None
    thickness: int = 0
    params: dict[str, Any] | None = None


BodyDrawer = Callable[[DrawContext], None]


def _outline_color(color: tuple[int, int, int], dark: int = 30) -> tuple[int, int, int]:
    return (max(0, color[0] - dark), max(0, color[1] - dark), max(0, color[2] - dark))


def draw_body(ctx: DrawContext) -> None:
    """Main body disc."""
    pygame.draw.circle(ctx.surface, ctx.color, (ctx.x, ctx.y), ctx.size)
    pygame.draw.circle(ctx.surface, _outline_color(ctx.color, 30), (ctx.x, ctx.y), ctx.size, ctx.thickness or 1)


def draw_eye(ctx: DrawContext) -> None:
    """White sclera + dark pupil and optional FOV overlay."""
    size = ctx.size
    x, y = ctx.x, ctx.y
    a = ctx.angle

    pygame.draw.circle(ctx.surface, (240, 240, 240), (x, y), size)
    pupil = (
        x + int(math.cos(a) * size * 0.3),
        y + int(math.sin(a) * size * 0.3),
    )
    pygame.draw.circle(ctx.surface, (20, 20, 20), pupil, max(1, size // 3))

    if ctx.overlays:
        params = ctx.params or {}
        reach = params.get("range", 50) * 1.0
        fov = params.get("fov", 1.0)
        half_fov = fov / 2
        left = (
            x + int(math.cos(a - half_fov) * reach),
            y + int(math.sin(a - half_fov) * reach),
        )
        right = (
            x + int(math.cos(a + half_fov) * reach),
            y + int(math.sin(a + half_fov) * reach),
        )
        fill = ctx.overlays.get("fill")
        line = ctx.overlays.get("line")
        if fill:
            pygame.draw.polygon(fill, (255, 255, 255, 5), [(x, y), left, right])
        if line:
            line_color = (255, 255, 255, 13)
            pygame.draw.line(line, line_color, (x, y), left)
            pygame.draw.line(line, line_color, (x, y), right)


def draw_jaw(ctx: DrawContext) -> None:
    """Two thick claw lines in a V opening forward — crab pincers."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    w = max(2, s // 2)
    spread = 0.45
    for side in (-1, 1):
        tip = (x + int(math.cos(a + side * spread) * s), y + int(math.sin(a + side * spread) * s))
        pygame.draw.line(ctx.surface, ctx.color, (x, y), tip, w)
        pygame.draw.circle(ctx.surface, ctx.color, tip, w // 2)


def draw_spike(ctx: DrawContext) -> None:
    """Barbed thorn."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    tip = (x + int(math.cos(a) * s * 1.5), y + int(math.sin(a) * s * 1.5))
    base_l = (x + int(math.cos(a + 2.5) * s * 0.18), y + int(math.sin(a + 2.5) * s * 0.18))
    base_r = (x + int(math.cos(a - 2.5) * s * 0.18), y + int(math.sin(a - 2.5) * s * 0.18))
    barb = (x + int(math.cos(a - 2.2) * s * 0.8), y + int(math.sin(a - 2.2) * s * 0.8))
    pts = [tip, base_r, barb, base_l]
    pygame.draw.polygon(ctx.surface, ctx.color, pts)
    pygame.draw.polygon(ctx.surface, (120, 40, 40), pts, ctx.thickness or 1)


def draw_scent(ctx: DrawContext) -> None:
    """Antenna with a hollow bulb tip (ring) — distinct from touch's sonar arcs."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    tip = (x + int(math.cos(a) * s * 2.5), y + int(math.sin(a) * s * 2.5))
    pygame.draw.line(ctx.surface, ctx.color, (x, y), tip, ctx.thickness or 2)
    pygame.draw.circle(ctx.surface, ctx.color, tip, max(2, s // 2), max(1, s // 4))


def draw_pheromone(ctx: DrawContext) -> None:
    """Concentric broadcast rings (mating signal radiating outward)."""
    x, y, s = ctx.x, ctx.y, ctx.size
    for i, frac in enumerate((1.0, 0.65, 0.3)):
        r = max(1, int(s * frac))
        # Fade outer rings by drawing them thinner.
        width = 1 if i == 0 else 2
        pygame.draw.circle(ctx.surface, ctx.color, (x, y), r, width)
    pygame.draw.circle(ctx.surface, (255, 150, 220), (x, y), max(1, s), 1)


def draw_fat(ctx: DrawContext) -> None:
    """Barrel / cask — energy storage magazine."""
    s = ctx.size
    x, y = ctx.x, ctx.y
    rect = (x - s, y - s // 2, s * 2, s)
    pygame.draw.ellipse(ctx.surface, ctx.color, rect)
    pygame.draw.ellipse(ctx.surface, _outline_color(ctx.color, 40), rect, 1)
    # Two hoops to read as a barrel.
    pygame.draw.line(ctx.surface, _outline_color(ctx.color, 40), (x - s // 3, y - s // 2), (x - s // 3, y + s // 2), 1)
    pygame.draw.line(ctx.surface, _outline_color(ctx.color, 40), (x + s // 3, y - s // 2), (x + s // 3, y + s // 2), 1)
    pygame.draw.line(ctx.surface, _outline_color(ctx.color, 40), (x - s, y), (x + s, y), 1)


def draw_regeneration(ctx: DrawContext) -> None:
    """Medical cross / plus."""
    x, y, s = ctx.x, ctx.y, ctx.size
    t = s * 0.35
    w = s * 0.22
    pts = [
        (x - w, y - t),
        (x + w, y - t),
        (x + w, y - w),
        (x + t, y - w),
        (x + t, y + w),
        (x + w, y + w),
        (x + w, y + t),
        (x - w, y + t),
        (x - w, y + w),
        (x - t, y + w),
        (x - t, y - w),
        (x - w, y - w),
    ]
    pygame.draw.polygon(ctx.surface, ctx.color, pts)
    pygame.draw.polygon(ctx.surface, (40, 120, 80), pts, ctx.thickness or 1)


def draw_fear(ctx: DrawContext) -> None:
    """Exclamation mark — alarm state."""
    x, y, s = ctx.x, ctx.y, ctx.size
    bar_w = max(2, int(s * 0.55))
    bar_h = int(s * 1.3)
    bar_rect = (x - bar_w // 2, y - bar_h, bar_w, bar_h)
    pygame.draw.rect(ctx.surface, ctx.color, bar_rect, border_radius=bar_w // 2)
    pygame.draw.circle(ctx.surface, ctx.color, (x, y + s // 2 + 1), max(2, int(s * 0.4)))


def draw_touch(ctx: DrawContext) -> None:
    """Sonar — two bold arcs radiating forward (proximity sense)."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    span = 1.8
    steps = 7
    w = max(2, s // 2)
    for frac in (1.0, 1.7):
        r = s * frac
        pts = []
        for i in range(steps + 1):
            t = -span / 2 + span * i / steps
            pts.append((x + int(math.cos(a + t) * r), y + int(math.sin(a + t) * r)))
        if len(pts) >= 2:
            pygame.draw.lines(ctx.surface, ctx.color, False, pts, w)


def draw_herd(ctx: DrawContext) -> None:
    """Three dots in a cluster — herd / group attraction."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    r = max(2, s // 2)
    for ang_offset in (0, 2 * math.pi / 3, 4 * math.pi / 3):
        dx = int(math.cos(a + ang_offset) * s * 0.7)
        dy = int(math.sin(a + ang_offset) * s * 0.7)
        pygame.draw.circle(ctx.surface, ctx.color, (x + dx, y + dy), r)


def draw_amphibious(ctx: DrawContext) -> None:
    """Hollow blue ring marking water-safe organisms."""
    x, y, s = ctx.x, ctx.y, ctx.size
    pygame.draw.circle(ctx.surface, ctx.color, (x, y), s, max(2, s // 3))
    pygame.draw.circle(ctx.surface, (20, 90, 110), (x, y), s, 1)


def draw_armor(ctx: DrawContext) -> None:
    """Shield shape."""
    x, y, s = ctx.x, ctx.y, ctx.size
    pts = [
        (x - s, y - s),
        (x + s, y - s),
        (x + s, y + int(s * 0.3)),
        (x, y + int(s * 1.3)),
        (x - s, y + int(s * 0.3)),
    ]
    pygame.draw.polygon(ctx.surface, ctx.color, pts)
    pygame.draw.polygon(ctx.surface, (100, 100, 110), pts, ctx.thickness or 1)


def draw_toxin_gland(ctx: DrawContext) -> None:
    """Hexagonal poison gland."""
    x, y, s = ctx.x, ctx.y, ctx.size
    pts = []
    for i in range(6):
        ang = i * math.pi / 3
        pts.append((x + int(math.cos(ang) * s), y + int(math.sin(ang) * s)))
    pygame.draw.polygon(ctx.surface, ctx.color, pts)
    pygame.draw.circle(ctx.surface, (90, 30, 120), (x, y), max(1, s // 2))

    if ctx.organism and getattr(ctx.organism, "toxin_resistance", 0.0) > 0.1:
        pygame.draw.circle(ctx.surface, (200, 80, 220), (x, y), s + (ctx.thickness or 2), ctx.thickness or 1)


def draw_venom(ctx: DrawContext) -> None:
    """Crossed bones (X) — universal poison/death symbol."""
    x, y, s = ctx.x, ctx.y, ctx.size
    w = max(2, s // 2)
    tip_r = max(1, s // 3)
    # Two diagonal bones crossing through center.
    d = s + 1
    pygame.draw.line(ctx.surface, ctx.color, (x - d, y - d), (x + d, y + d), w)
    pygame.draw.line(ctx.surface, ctx.color, (x - d, y + d), (x + d, y - d), w)
    # Bone caps (small circles at each tip).
    for px, py in ((x - d, y - d), (x + d, y + d), (x - d, y + d), (x + d, y - d)):
        pygame.draw.circle(ctx.surface, ctx.color, (px, py), tip_r)


def draw_asexual(ctx: DrawContext) -> None:
    """Mitosis — two touching circles (cell division in progress)."""
    x, y, s = ctx.x, ctx.y, ctx.size
    r = max(2, int(s * 0.7))
    gap = max(1, r // 3)
    cx1 = x - r + gap // 2
    cx2 = x + r - gap // 2
    pygame.draw.circle(ctx.surface, ctx.color, (cx1, y), r)
    pygame.draw.circle(ctx.surface, ctx.color, (cx2, y), r)
    pygame.draw.circle(ctx.surface, (120, 140, 60), (cx1, y), r, 1)
    pygame.draw.circle(ctx.surface, (120, 140, 60), (cx2, y), r, 1)
    # Division line between the two cells.
    pygame.draw.line(ctx.surface, (120, 140, 60), (x, y - r // 2), (x, y + r // 2), 1)


def draw_cannibal(ctx: DrawContext) -> None:
    """Single downward fang — predator's bite."""
    x, y, s = ctx.x, ctx.y, ctx.size
    tip = (x, y + s * 2)
    base_l = (x - s, y - s // 2)
    base_r = (x + s, y - s // 2)
    pygame.draw.polygon(ctx.surface, ctx.color, [base_l, base_r, tip])
    pygame.draw.polygon(ctx.surface, (20, 20, 30), [base_l, base_r, tip], 1)


def draw_memory(ctx: DrawContext) -> None:
    """Memory core drawn as a diamond / rhombus, distinct from round body parts."""
    x, y, s = ctx.x, ctx.y, ctx.size
    pts = [
        (x, y - s),
        (x + s, y),
        (x, y + s),
        (x - s, y),
    ]
    pygame.draw.polygon(ctx.surface, ctx.color, pts)
    pygame.draw.polygon(ctx.surface, (120, 80, 140), pts, ctx.thickness or 1)
    # Inner highlight to suggest a stored memory point.
    pygame.draw.circle(ctx.surface, (240, 220, 255), (x, y), max(1, s // 3))


def draw_leg(ctx: DrawContext) -> None:
    """Stubby limb pointing outward from the body."""
    x, y, s = ctx.x, ctx.y, ctx.size
    if ctx.organism:
        a = math.atan2(y - ctx.organism.position[1], x - ctx.organism.position[0])
    else:
        a = ctx.angle
    half = ctx.thickness or max(2, s // 3)
    start = (x - int(math.cos(a) * s * 0.4), y - int(math.sin(a) * s * 0.4))
    end = (x + int(math.cos(a) * s * 0.9), y + int(math.sin(a) * s * 0.9))
    pygame.draw.line(ctx.surface, ctx.color, start, end, half)
    pygame.draw.circle(ctx.surface, ctx.color, start, half // 2)
    pygame.draw.circle(ctx.surface, ctx.color, end, half // 2)


def draw_generic(ctx: DrawContext) -> None:
    """Fallback body part."""
    pygame.draw.circle(ctx.surface, ctx.color, (ctx.x, ctx.y), max(1, ctx.size))


BODY_DRAWERS: dict[str, BodyDrawer] = {
    "body": draw_body,
    "eye": draw_eye,
    "jaw": draw_jaw,
    "spike": draw_spike,
    "scent": draw_scent,
    "pheromone": draw_pheromone,
    "fat": draw_fat,
    "regeneration": draw_regeneration,
    "fear": draw_fear,
    "touch": draw_touch,
    "herd": draw_herd,
    "amphibious": draw_amphibious,
    "armor": draw_armor,
    "toxin_gland": draw_toxin_gland,
    "venom": draw_venom,
    "asexual": draw_asexual,
    "cannibal": draw_cannibal,
    "memory": draw_memory,
    "leg": draw_leg,
}
