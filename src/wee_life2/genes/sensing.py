"""Shared sensing helpers for the distance senses (``eye``, ``scent``).

Both genes cast a fan of rays at the tile map, publish what they saw as
``PerceptionEvent``s and fold the hits into a single steering vector. Only the
ray *layout* and the sharpness factor differ, so the loop itself lives here.

Steering sign convention (see AGENTS.md): the accumulated vector always points
*toward* the observed tile and the weight carries the sign, so a negative
``wall_weight``/``hazard_weight`` repels. Never negate both.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import TYPE_CHECKING

from ..core import config
from .geometry import angle_diff

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World

Vec = tuple[float, float]

# Upper bound on the magnitude of the combined terrain drive.
MAX_TERRAIN_WEIGHT = 1.0


def sight_discount(world: World, origin: Vec, target_pos: Vec, *, is_amphibious: bool) -> float:
    """Multiplier for a target seen across water or a hazard.

    Water only obscures the view of organisms that cannot swim; radioactive and
    lava tiles obscure it for everyone. The two discounts stack.
    """
    discount = 1.0
    if not is_amphibious and world.line_crosses_water(origin, target_pos):
        discount *= config.WATER_SIGHT_DISCOUNT
    if world.line_crosses_hazard(origin, target_pos):
        discount *= config.WATER_SIGHT_DISCOUNT
    return discount


def terrain_drive(
    organism: Organism,
    world: World,
    *,
    ray_angles: Iterable[float],
    range_: float,
    sharpness: float,
    source: str,
    wall_weight: float,
    hazard_weight: float,
    water_weight: float,
    is_amphibious: bool,
    heal_weight: float | None = None,
    heal_threshold: float | None = None,
) -> None:
    """Cast rays at the tile map and add one aggregated terrain drive.

    Hits are summed into a single vector rather than emitted as separate drives:
    several walls on different sides would otherwise fight each other and make
    the organism spin in place.

    ``heal_weight``/``heal_threshold`` are optional; only ``scent`` smells heal
    tiles, and only while the organism is below the health threshold.
    """
    if range_ <= 0.0:
        return
    pos = organism.position
    px, py = pos
    range_inv = 1.0 / range_
    tile_map = world.tile_map
    tick = world.tick

    water_sign = 1.0 if is_amphibious else -1.0
    heal_enabled = heal_weight is not None and heal_threshold is not None
    if heal_enabled:
        health_fraction = organism.energy / organism.max_energy

    total_x = 0.0
    total_y = 0.0
    for ray_angle in ray_angles:
        hit = tile_map.first_interesting_tile_along_ray(pos, ray_angle, range_)
        if hit is None:
            continue
        hit_pos, tile_type = hit
        organism.add_perception(hit_pos, tile_type, source, tick)

        dx = hit_pos[0] - px
        dy = hit_pos[1] - py
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            continue
        strength = (1.0 - dist * range_inv) * sharpness

        if tile_type == world.TILE_WALL:
            weight = wall_weight * strength
        elif tile_type in (world.TILE_RADIOACTIVE, world.TILE_LAVA):
            weight = hazard_weight * strength
        elif tile_type == world.TILE_WATER:
            weight = water_weight * water_sign * strength
        elif heal_enabled and tile_type == world.TILE_HEAL:
            if health_fraction >= heal_threshold:
                continue
            weight = heal_weight * strength
        else:
            continue

        total_x += (dx / dist) * weight
        total_y += (dy / dist) * weight

    if total_x != 0.0 or total_y != 0.0:
        drive = angle_diff(math.atan2(total_y, total_x), organism.angle)
        organism.add_drive(drive, min(MAX_TERRAIN_WEIGHT, math.hypot(total_x, total_y)), "terrain")


def fan_ray_angles(center: float, fov: float, count: int) -> list[float]:
    """``count`` ray angles spread evenly across ``fov``, centred on ``center``."""
    if count <= 1:
        return [center]
    step = fov / (count - 1)
    start = center - fov / 2.0
    return [start + i * step for i in range(count)]


def radial_ray_angles(center: float, count: int) -> list[float]:
    """``count`` ray angles spread around a full circle, starting at ``center``."""
    if count <= 0:
        return []
    step = 2.0 * math.pi / count
    return [center + i * step for i in range(count)]
