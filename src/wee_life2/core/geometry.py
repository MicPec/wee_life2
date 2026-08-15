"""Small 2D geometry helpers used across the simulation."""

from __future__ import annotations

import math
from typing import TypeAlias

Vec: TypeAlias = tuple[float, float]


def wrap_angle(angle: float) -> float:
    """Wrap an angle to the range [-pi, pi]."""
    return ((angle + math.pi) % (2 * math.pi)) - math.pi


def angle_diff(a: float, b: float) -> float:
    """Return the smallest signed difference from angle b to angle a (a - b)."""
    return wrap_angle(a - b)


def angle_to(origin: Vec, target: Vec) -> float:
    """Return the angle from origin to target."""
    return math.atan2(target[1] - origin[1], target[0] - origin[0])


def distance_sq(a: Vec, b: Vec) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return dx * dx + dy * dy


def distance(a: Vec, b: Vec) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def normalize(v: Vec) -> Vec:
    """Return a unit vector in the same direction, or (0, 0) for a zero vector."""
    x, y = v
    d = math.hypot(x, y)
    if d == 0:
        return (0.0, 0.0)
    return (x / d, y / d)


def point_in_circle(center: Vec, radius: float, pos: Vec) -> bool:
    return distance_sq(center, pos) <= radius * radius


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
