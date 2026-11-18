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
        "rate": 0.15,
        "efficiency": 0.4,
        "threshold": 0.5,  # activate below this health fraction
        "size": 4.0,
        "count": 2.0,
    }
    # The ambient path creates energy from nothing, so cap how far it can
    # evolve: below these bounds free healing can't beat idle upkeep.
    param_bounds = {"rate": (0.0, 0.3), "efficiency": (0.0, 0.8), "threshold": (0.0, 1.0)}

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
        # Regeneration does not stack: exactly one copy acts per tick, the
        # copy that would heal the most at the current health, taken WHOLE.
        # Averaging would let a fresh default copy dilute an evolved one, and
        # a per-parameter max would build a chimera stronger than any real
        # copy — stacking through the back door. Extra copies only cost
        # upkeep and mass.
        copies = [g for g in organism.dna.genes if isinstance(g, RegenerationGene)]
        if copies[0] is not self:
            return
        health_fraction = organism.energy / organism.max_energy
        best = max(copies, key=lambda g: g.params["rate"] * (g.params["threshold"] - health_fraction))

        rate = best.params["rate"]
        threshold = best.params["threshold"]
        efficiency = best.params["efficiency"]

        if health_fraction < threshold and rate > 0.0:
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
                # Energy created from nothing is paid for in lifespan: one
                # unit keeps an idle organism alive ~20 ticks, so 10 ticks of
                # age per unit roughly halves what free healing buys instead
                # of making the carrier unstarvable.
                organism.age += ambient * config.REGENERATION_AGE_COST

            # Slower movement while healing
            organism.velocity = (organism.velocity[0] * 0.95, organism.velocity[1] * 0.95)
