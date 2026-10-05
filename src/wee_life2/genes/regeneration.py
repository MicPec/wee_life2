"""Regeneration gene: heals wounds and restores energy when damaged."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..core import config
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
        "count": 2.0,
    }
    # Healing draws from nothing, so cap how far it can evolve.
    param_bounds = {"rate": (0.0, 0.5), "efficiency": (0.0, 1.0), "threshold": (0.0, 1.0)}

    def body_parts(self, base_color):
        parts = []
        for i in range(self.part_count):
            theta = (2 * math.pi * i) / self.part_count
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
            # Convert fat reserve into healing; if no reserve, fall back to an
            # ambient trickle scaled by efficiency (the capped free-energy leak).
            heal = rate * (threshold - health_fraction) * dt * config.TICKS_PER_SECOND
            from_reserve = min(heal, organism.fat_reserve)
            if from_reserve > 0.0:
                organism.fat_reserve -= from_reserve
                organism.energy = min(organism.energy + from_reserve, organism.max_energy)
            remaining = heal - from_reserve
            if remaining > 0.0:
                ambient = remaining * efficiency
                organism.energy = min(organism.energy + ambient, organism.max_energy)

            # Slower movement while healing
            organism.velocity = (organism.velocity[0] * 0.95, organism.velocity[1] * 0.95)
