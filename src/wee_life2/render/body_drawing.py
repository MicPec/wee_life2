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
    """Pincer / open jaw."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    base = (x, y)
    outer_l = (x + int(math.cos(a - 0.45) * s), y + int(math.sin(a - 0.45) * s))
    outer_r = (x + int(math.cos(a + 0.45) * s), y + int(math.sin(a + 0.45) * s))
    inner_l = (x + int(math.cos(a - 0.08) * s * 0.55), y + int(math.sin(a - 0.08) * s * 0.55))
    inner_r = (x + int(math.cos(a + 0.08) * s * 0.55), y + int(math.sin(a + 0.08) * s * 0.55))
    pts = [base, outer_l, inner_l, inner_r, outer_r]
    pygame.draw.polygon(ctx.surface, ctx.color, pts)
    pygame.draw.polygon(ctx.surface, (100, 60, 50), pts, ctx.thickness or 1)


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
    """Antenna with a bulb tip."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    tip = (x + int(math.cos(a) * s * 2.5), y + int(math.sin(a) * s * 2.5))
    pygame.draw.line(ctx.surface, ctx.color, (x, y), tip, ctx.thickness or 2)
    pygame.draw.circle(ctx.surface, ctx.color, tip, max(1, s // 2))


def draw_pheromone(ctx: DrawContext) -> None:
    """Diamond with pink outline."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    front = s * 1.1
    side = s * 0.6
    p1 = (x + int(math.cos(a) * front), y + int(math.sin(a) * front))
    p2 = (x + int(math.cos(a + math.pi / 2) * side), y + int(math.sin(a + math.pi / 2) * side))
    p3 = (x + int(math.cos(a + math.pi) * front), y + int(math.sin(a + math.pi) * front))
    p4 = (x + int(math.cos(a - math.pi / 2) * side), y + int(math.sin(a - math.pi / 2) * side))
    pygame.draw.polygon(ctx.surface, ctx.color, [p1, p2, p3, p4])
    pygame.draw.polygon(ctx.surface, (255, 150, 220), [p1, p2, p3, p4], ctx.thickness or 1)


def draw_fat(ctx: DrawContext) -> None:
    """Energy-storage ellipse."""
    s = ctx.size
    pygame.draw.ellipse(ctx.surface, ctx.color, (ctx.x - s, ctx.y - s // 2, s * 2, s))


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
    """Lightning bolt."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    pts = [
        (x + int(math.cos(a - 0.2) * s * 0.3), y + int(math.sin(a - 0.2) * s * 0.3)),
        (x + int(math.cos(a + 0.5) * s * 0.15), y + int(math.sin(a + 0.5) * s * 0.15)),
        (x + int(math.cos(a) * s * 0.05), y + int(math.sin(a) * s * 0.05)),
        (x + int(math.cos(a + 0.75) * s * 0.7), y + int(math.sin(a + 0.75) * s * 0.7)),
        (x + int(math.cos(a) * s * 1.4), y + int(math.sin(a) * s * 1.4)),
    ]
    pygame.draw.polygon(ctx.surface, ctx.color, pts)


def draw_touch(ctx: DrawContext) -> None:
    """Three whiskers fanned out."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    for offset in (-0.3, 0.0, 0.3):
        tip = (x + int(math.cos(a + offset) * s * 2.8), y + int(math.sin(a + offset) * s * 2.8))
        pygame.draw.line(ctx.surface, ctx.color, (x, y), tip, ctx.thickness or 1)


def draw_herd(ctx: DrawContext) -> None:
    """Flag / banner on a pole."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    pole_tip = (x + int(math.cos(a) * s * 1.8), y + int(math.sin(a) * s * 1.8))
    pygame.draw.line(ctx.surface, ctx.color, (x, y), pole_tip, ctx.thickness or 2)
    flag_tip = (x + int(math.cos(a) * s * 2.6), y + int(math.sin(a) * s * 2.6))
    flag_top = (x + int(math.cos(a + 0.8) * s * 0.7), y + int(math.sin(a + 0.8) * s * 0.7))
    flag_bot = (x + int(math.cos(a - 0.4) * s * 0.7), y + int(math.sin(a - 0.4) * s * 0.7))
    pygame.draw.polygon(ctx.surface, ctx.color, [pole_tip, flag_top, flag_tip, flag_bot])


def draw_amphibious(ctx: DrawContext) -> None:
    """Tadpole shape."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    pygame.draw.circle(ctx.surface, ctx.color, (x, y), s)
    tail = (x + int(math.cos(a) * s * 1.5), y + int(math.sin(a) * s * 1.5))
    tail_l = (x + int(math.cos(a + 0.5) * s * 0.7), y + int(math.sin(a + 0.5) * s * 0.7))
    tail_r = (x + int(math.cos(a - 0.5) * s * 0.7), y + int(math.sin(a - 0.5) * s * 0.7))
    pygame.draw.polygon(ctx.surface, ctx.color, [tail, tail_l, tail_r])
    pygame.draw.circle(ctx.surface, (20, 90, 110), (x, y), s, ctx.thickness or 1)


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
    """Pair of fangs / fork."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    base = (x, y)
    base_l = (x + int(math.cos(a - 0.45) * s * 0.2), y + int(math.sin(a - 0.45) * s * 0.2))
    tip_l = (x + int(math.cos(a - 0.15) * s * 1.5), y + int(math.sin(a - 0.15) * s * 1.5))
    tip_r = (x + int(math.cos(a + 0.15) * s * 1.5), y + int(math.sin(a + 0.15) * s * 1.5))
    base_r = (x + int(math.cos(a + 0.45) * s * 0.2), y + int(math.sin(a + 0.45) * s * 0.2))
    pts = [base, base_l, tip_l, tip_r, base_r]
    pygame.draw.polygon(ctx.surface, ctx.color, pts)
    pygame.draw.polygon(ctx.surface, (40, 100, 40), pts, ctx.thickness or 1)


def draw_asexual(ctx: DrawContext) -> None:
    """Asexual reproduction shown as a pointed cell with a budding clone behind."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    # Main arrow-shaped body pointing in the organism's forward direction.
    tip = (x + int(math.cos(a) * s), y + int(math.sin(a) * s))
    base_l = (x + int(math.cos(a + 2.5) * s * 0.7), y + int(math.sin(a + 2.5) * s * 0.7))
    base_r = (x + int(math.cos(a - 2.5) * s * 0.7), y + int(math.sin(a - 2.5) * s * 0.7))
    pts = [tip, base_l, base_r]
    pygame.draw.polygon(ctx.surface, ctx.color, pts)
    pygame.draw.polygon(ctx.surface, (120, 140, 60), pts, ctx.thickness or 1)
    # Small bud attached to the back, ready to split off.
    bud_x = x + int(math.cos(a + math.pi) * s * 0.6)
    bud_y = y + int(math.sin(a + math.pi) * s * 0.6)
    pygame.draw.circle(ctx.surface, ctx.color, (bud_x, bud_y), max(1, s // 3))


def draw_cannibal(ctx: DrawContext) -> None:
    """Monster maw with jagged teeth."""
    x, y, s, a = ctx.x, ctx.y, ctx.size, ctx.angle
    pygame.draw.circle(ctx.surface, ctx.color, (x, y), s)
    mouth = [
        (x + int(math.cos(a + 0.9) * s * 0.6), y + int(math.sin(a + 0.9) * s * 0.6)),
        (x + int(math.cos(a + 0.45) * s * 1.05), y + int(math.sin(a + 0.45) * s * 1.05)),
        (x + int(math.cos(a) * s * 0.75), y + int(math.sin(a) * s * 0.75)),
        (x + int(math.cos(a - 0.45) * s * 1.05), y + int(math.sin(a - 0.45) * s * 1.05)),
        (x + int(math.cos(a - 0.9) * s * 0.6), y + int(math.sin(a - 0.9) * s * 0.6)),
    ]
    pygame.draw.polygon(ctx.surface, (20, 20, 30), mouth)


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
