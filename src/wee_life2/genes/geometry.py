"""Shared geometry / steering helpers for genes."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..core.geometry import angle_diff as _angle_diff
from ..core.geometry import angle_to as _angle_to
from ..core.geometry import distance as _distance
from ..core.geometry import distance_sq as _distance_sq
from ..core.geometry import wrap_angle as _wrap_angle

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


def wrap_angle(angle: float) -> float:
    return _wrap_angle(angle)


def angle_to(origin: tuple[float, float], target: tuple[float, float]) -> float:
    return _angle_to(origin, target)


def angle_diff(target: float, current: float) -> float:
    return _angle_diff(target, current)


def direction_to(organism: Organism, target_pos: tuple[float, float]) -> float:
    """Return the relative steering angle from organism to a target position."""
    return angle_diff(angle_to(organism.position, target_pos), organism.angle)


def distance(organism: Organism, target_pos: tuple[float, float]) -> float:
    return _distance(organism.position, target_pos)


def distance_sq(organism: Organism, target_pos: tuple[float, float]) -> float:
    return _distance_sq(organism.position, target_pos)


def is_in_fov(view_angle: float, target_pos: tuple[float, float], half_fov: float, origin: tuple[float, float]) -> bool:
    """Return True if target_pos is within the field of view centered at view_angle."""
    target_angle = angle_to(origin, target_pos)
    return abs(angle_diff(target_angle, view_angle)) <= half_fov


def steer_toward(
    organism: Organism,
    target_pos: tuple[float, float],
    weight: float,
    kind: str | None = None,
) -> None:
    """Add a drive that turns the organism toward a target."""
    organism.add_drive(direction_to(organism, target_pos), weight, kind)


def steer_away(
    organism: Organism,
    target_pos: tuple[float, float],
    weight: float,
    kind: str | None = None,
) -> None:
    """Add a drive that turns the organism away from a target."""
    organism.add_drive(direction_to(organism, target_pos) + math.pi, -abs(weight), kind)
