"""Base gene abstraction and helpers."""

from __future__ import annotations

import colorsys
import copy
import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..core import config
from ..core.geometry import wrap_angle

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
    # Optional per-parameter (low, high) mutation limits for parameters whose
    # semantics break outside that range; e.g. metabolism efficiency above 1.0
    # would turn the energy drain into free energy.
    param_bounds: dict[str, tuple[float, float]] = {}
    # Angular parameters (radians): mutation steps are pi-scaled and wrap
    # around +-pi instead of clamping, and blending uses the circular mean.
    wrap_params: frozenset[str] = frozenset()

    def __init__(self, params: GeneParams | None = None) -> None:
        self.params: GeneParams = {
            key: float(params.get(key, default)) if params else float(default)
            for key, default in self.default_params.items()
        }
        # Genomes can arrive from outside mutation (loaded saves, hand-written
        # DNA); run every parameter through the same domain rules so a Gene is
        # valid by construction, not only after a mutation round.
        for key in self.params:
            self.params[key] = self._constrain(key, self.params[key])
        # A freshly created gene (no inherited value) gets a random body side
        # so founder organisms are visually varied.  Children inherit it
        # through clone()/blend() like any other parameter -- this is the same
        # shape as EyeGene's handling of an uninherited `direction`.
        if "side" in self.default_params and (not params or "side" not in params):
            self.params["side"] = random.random()

    @property
    def part_count(self) -> int:
        """Body-part count expressed by ``count``-carrying genes (always >= 1).

        Derived from the live parameter rather than cached at construction, so
        a mutated/blended ``count`` expresses in this organism's body instead
        of one generation late.  Genes without a ``count`` parameter express a
        single part rather than raising ``KeyError``.
        """
        return max(1, int(self.params.get("count", 1)))

    @property
    def side(self) -> int:
        """Body side (+1/-1) expressed by the heritable ``side`` parameter.

        Derived from the live parameter rather than randomised per instance:
        ``Gene.clone()`` rebuilds from ``params`` alone, so an
        ``__init__``-time random side re-rolled on every clone and a child's
        body layout never matched its parent's.  Genes without a ``side``
        parameter express the +1 side.
        """
        return 1 if self.params.get("side", 1.0) >= 0.5 else -1

    def body_parts(self, base_color: tuple[int, int, int]) -> list[BodyPartBlueprint]:
        """Return the body parts this gene contributes to the organism."""
        return []

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        """Hook called every simulation tick for this gene."""

    def _constrain(self, key: str, value: float) -> float:
        """Clamp a parameter back into its valid domain.

        Parameters with explicit ``param_bounds`` are clamped to that range;
        angular parameters wrap around +-pi; the rest keep the sign of their
        default so a repulsive weight (e.g. ``wall_weight``) cannot silently
        become an attractor.
        """
        if key in self.wrap_params:
            return wrap_angle(value)
        if key in self.param_bounds:
            low, high = self.param_bounds[key]
            return clamp(value, low, high)
        if self.default_params.get(key, 0.0) < 0:
            return min(0.0, value)
        return max(0.0, value)

    def mutate(self, rate: float, strength: float) -> None:
        """Perturb gene parameters in place.

        Steps are additive, scaled by each parameter's default: unlike the old
        multiplicative form (``param *= 1 + u``) there is no downward drift in
        log space, and a parameter sitting at exactly 0.0 is no longer an
        absorbing state.  Angular parameters listed in ``wrap_params`` take
        pi-scaled steps and wrap around +-pi instead of being clamped, so they
        can evolve past the boundary.  Every step ends in ``_constrain``.
        """
        for key in self.params:
            if random.random() >= rate:
                continue
            if key in self.wrap_params:
                noise = (random.random() * 2.0 - 1.0) * strength * math.pi
            else:
                default = self.default_params.get(key, 0.0)
                noise = (random.random() * 2.0 - 1.0) * strength * max(abs(default), config.MUTATION_STEP_FLOOR)
            self.params[key] = self._constrain(key, self.params[key] + noise)

    def blend(self, other: "Gene") -> "Gene":
        """Recombine two homologous genes by averaging their parameters."""
        child = self.clone()
        for key, value in other.params.items():
            if key not in child.params:
                continue
            if key in self.wrap_params:
                # Circular mean: a linear average across the +-pi wrap would
                # turn two near-backward angles into a forward one.  Exactly
                # antipodal angles have no mean (the vector sum cancels) and
                # atan2(0, 0) would fabricate a forward child, so keep this
                # gene's angle instead.
                a = child.params[key]
                sin_sum = math.sin(a) + math.sin(value)
                cos_sum = math.cos(a) + math.cos(value)
                if sin_sum * sin_sum + cos_sum * cos_sum < 1e-24:
                    continue
                child.params[key] = math.atan2(sin_sum, cos_sum)
            else:
                child.params[key] = (child.params[key] + value) / 2.0
        return child

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
    """Convert HSV in the 0-1 range to an 8-bit RGB tuple."""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s, 0.0, 1.0), clamp(v, 0.0, 1.0))
    return (int(r * 255), int(g * 255), int(b * 255))
