"""Pheromone gene: emits a mating signal that other organisms can sense."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core import config
from .base import BodyPartBlueprint, Gene

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class PheromoneGene(Gene):
    """Emits chemical signals that attract potential mates.

    The signal strength depends on the organism's readiness to mate.
    """

    kind = "pheromone"
    default_params = {
        "strength": 0.5,
        "range": 100.0,
        "cost": 0.05,
        "size": 4.0,
        "side": 0.5,  # 0-1, body side the gland sits on (thresholded at 0.5)
    }
    param_bounds = {
        "side": (0.0, 1.0),
    }

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="pheromone",
                offset=(self.side * 6, 6),
                angle=0.0,
                size=self.params["size"],
                color=(230, 120, 200),
                params={"strength": self.params["strength"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        # Additive so multiple pheromone glands stack into a stronger signal
        # instead of the last-applied gene overwriting the rest. Resets to
        # 0.0 once per tick in Organism.update(), so no else-branch needed.
        if organism.can_mate():
            strength = self.params["strength"] * (organism.energy / organism.max_energy)
            organism.pheromone_strength += strength
            organism.energy -= self.params["cost"] * dt * config.TICKS_PER_SECOND
