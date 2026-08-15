"""Defensive gene: armor reduces incoming damage and adds body plating."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class ArmorGene(Gene):
    """Plates reduce damage taken."""

    kind = "armor"
    default_params = {
        "thickness": 2.0,
        "coverage": 0.3,
        "size": 9.0,
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._plates = max(1, int(self.params["coverage"] * 6))

    def body_parts(self, base_color):
        parts = []
        for i in range(self._plates):
            theta = (2 * math.pi * i) / self._plates
            r = 6.0
            parts.append(
                BodyPartBlueprint(
                    kind="armor",
                    offset=(math.cos(theta) * r, math.sin(theta) * r),
                    angle=theta,
                    size=self.params["size"],
                    color=(min(255, base_color[0] + 30), min(255, base_color[1] + 30), min(255, base_color[2] + 30)),
                    params={"thickness": self.params["thickness"]},
                )
            )
        return parts

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        # Armor is mostly passive: it contributes to armor_value used by jaw/spike.
        # Additive so multiple armor genes stack instead of the last one winning.
        organism.armor_value += self.params["thickness"]
