"""Venom gene: injects poison into bitten prey, causing damage over time."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene, hsv_to_rgb

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class VenomGene(Gene):
    """A venom gland injects poison into prey bitten by the carrier's jaw.

    Unlike ``toxin_gland`` (which only poisons remains on death), venom
    actively applies a damage-over-time effect to any organism bitten by
    the carrier's jaw gene.
    """

    kind = "venom"
    default_params = {
        "toxicity": 0.8,
        "duration": 60.0,
        "size": 5.0,
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._side = 1 if random.random() > 0.5 else -1

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="venom",
                offset=(self._side * 6, 4),
                angle=0.0,
                size=self.params["size"],
                color=hsv_to_rgb(0.33, 0.9, 0.7),
                params={"toxicity": self.params["toxicity"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        # Venom resistance stacks with toxin resistance
        organism.toxin_resistance = min(1.0, organism.toxin_resistance + 0.15 * self.params["toxicity"])
