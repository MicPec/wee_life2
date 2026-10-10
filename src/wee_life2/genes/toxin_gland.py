"""Toxin gene: produces poison on death and grants poison resistance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class ToxinGlandGene(Gene):
    """A toxin gland makes the remains of the organism poisonous on death.

    It also gives the carrier some resistance to poison in food.
    """

    kind = "toxin_gland"
    default_params = {
        "toxicity": 0.5,
        "resistance": 0.2,
        "size": 5.0,
        "side": 0.5,  # 0-1, body side the gland sits on (thresholded at 0.5)
    }
    param_bounds = {
        "side": (0.0, 1.0),
    }

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="toxin_gland",
                offset=(self.side * 5, 6),
                angle=0.0,
                size=self.params["size"],
                color=(180, 60, 220),
                params={"toxicity": self.params["toxicity"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        # Additive so multiple toxin_gland/venom genes stack instead of the
        # last-applied gene overwriting everyone else's contribution.
        organism.toxin_resistance += self.params["resistance"]
