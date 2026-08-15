"""Pigmentation and bioluminescence gene."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene, hsv_to_rgb

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class ColorGene(Gene):
    """Determines the base colour of the organism and optional glow."""

    kind = "color"
    default_params = {
        "hue": 0.5,
        "saturation": 0.85,
        "value": 0.9,
        "glow": 0.1,
        "size": 10.0,
    }

    def __init__(self, params=None):
        params = dict(params) if params else {}
        if "hue" not in params:
            params["hue"] = random.random()
        if "saturation" not in params:
            params["saturation"] = random.uniform(0.6, 1.0)
        if "value" not in params:
            params["value"] = random.uniform(0.6, 1.0)
        super().__init__(params)

    def body_parts(self, base_color):
        # The main body disc
        color = hsv_to_rgb(
            self.params["hue"],
            self.params["saturation"],
            self.params["value"],
        )
        return [
            BodyPartBlueprint(
                kind="body",
                offset=(0, 0),
                angle=0.0,
                size=self.params["size"],
                color=color,
                params={"glow": self.params["glow"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        # Color is visual only, but glow could attract mates / predators later.
        # Additive so multiple color genes stack instead of overwriting.
        organism.bioluminescence += self.params["glow"]
