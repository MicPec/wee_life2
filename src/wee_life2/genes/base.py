"""Base gene abstraction and helpers."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


@dataclass
class BodyPartBlueprint:
    """Description of one body segment produced by a gene.

    The body is assembled from such parts like building blocks.  Each part has
    a local position/orientation relative to the organism center, a colour, and
    a size.  The meaning of the part (eye, jaw, leg, etc.) is taken from the
    gene that generated it.
    """

    kind: str
    offset: tuple[float, float] = (0.0, 0.0)
    angle: float = 0.0
    size: float = 6.0
    color: tuple[int, int, int] = (200, 200, 200)
    params: dict[str, Any] = field(default_factory=dict)

    def clone(self) -> BodyPartBlueprint:
        return BodyPartBlueprint(
            kind=self.kind,
            offset=self.offset,
            angle=self.angle,
            size=self.size,
            color=self.color,
            params=copy.deepcopy(self.params),
        )


GeneParams = dict[str, float]


class Gene:
    """Abstract gene.

    Every concrete gene class has a unique ``kind`` string, a parameter
    dictionary, and it can produce ``BodyPartBlueprint`` instances so the
    organism can be rendered as a composite creature.  Genes also contribute to
    the update logic through ``apply``.
    """

    kind: str = "base"
    default_params: GeneParams = {}

    def __init__(self, params: GeneParams | None = None) -> None:
        self.params: GeneParams = {
            key: float(params.get(key, default)) if params else float(default)
            for key, default in self.default_params.items()
        }

    def body_parts(self, base_color: tuple[int, int, int]) -> list[BodyPartBlueprint]:
        """Return the body parts this gene contributes to the organism."""
        return []

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        """Hook called every simulation tick for this gene."""

    def mutate(self, rate: float, strength: float) -> None:
        """Perturb gene parameters in place.

        Steering weights keep the sign from their default so that a repulsive
        weight (e.g. ``wall_weight``) does not silently become an attractor
        after a single mutation.  Size/range-like parameters are floored at
        zero.
        """
        for key in self.params:
            if random.random() < rate:
                noise = (random.random() * 2.0 - 1.0) * strength
                self.params[key] *= 1.0 + noise
                if key.endswith("_weight"):
                    default = self.default_params.get(key, 0.0)
                    if default < 0:
                        self.params[key] = min(0.0, self.params[key])
                    else:
                        self.params[key] = max(0.0, self.params[key])
                else:
                    self.params[key] = max(0.0, self.params[key])

    def clone(self) -> Gene:
        other = self.__class__(dict(self.params))
        return other

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Gene:
        return cls(data.get("params", {}))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def random_color() -> tuple[int, int, int]:
    return (random.randint(20, 240), random.randint(20, 240), random.randint(20, 240))


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """Convert HSV in 0-1 range to RGB tuple."""
    h = h % 1.0
    s = clamp(s, 0.0, 1.0)
    v = clamp(v, 0.0, 1.0)
    if s == 0.0:
        return (int(v * 255), int(v * 255), int(v * 255))
    i = int(h * 6)
    f = (h * 6) - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    i %= 6
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return (int(r * 255), int(g * 255), int(b * 255))
