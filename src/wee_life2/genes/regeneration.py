"""Regeneration gene: heals wounds and restores energy when damaged."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class RegenerationGene(Gene):
    """Regenerative tissue slowly restores energy and mends damage."""

    kind = "regeneration"
    default_params = {
        "rate": 0.3,
        "efficiency": 0.6,
        "threshold": 0.5,  # activate below this health fraction
        "size": 4.0,
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._count = max(1, int(random.uniform(1, 4)))

    def body_parts(self, base_color):
        parts = []
        for i in range(self._count):
            theta = (2 * math.pi * i) / self._count
            r = 5.0
            parts.append(
                BodyPartBlueprint(
                    kind="regeneration",
                    offset=(math.cos(theta) * r, math.sin(theta) * r),
                    angle=theta,
                    size=self.params["size"],
                    color=(80, 220, 120),
                    params={"rate": self.params["rate"]},
                )
            )
        return parts

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        rate = self.params["rate"]
        threshold = self.params["threshold"]
        efficiency = self.params["efficiency"]

        health_fraction = organism.energy / organism.max_energy
        if health_fraction < threshold:
            # Convert some reserve into healing; if no reserve, use ambient efficiency
            heal = rate * (threshold - health_fraction) * efficiency * dt * 60.0
            organism.energy = min(organism.energy + heal, organism.max_energy)

            # Slower movement while healing
            organism.velocity = (organism.velocity[0] * 0.95, organism.velocity[1] * 0.95)
