"""Fat gene: stores surplus energy and acts as a buffer during starvation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core import config
from .base import BodyPartBlueprint, Gene

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class FatGene(Gene):
    """Fat cells increase energy capacity and slowly release energy when hungry."""

    kind = "fat"
    default_params = {
        "storage": 0.4,
        "reserve_factor": 0.3,
        "size": 5.0,
        "count": 2.0,
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._count = max(1, int(self.params["count"]))

    def body_parts(self, base_color):
        parts = []
        for i in range(self._count):
            side = 1 if i % 2 == 0 else -1
            row = i // 2
            parts.append(
                BodyPartBlueprint(
                    kind="fat",
                    offset=(side * 10, -6 - row * 8),
                    angle=0.0,
                    size=self.params["size"],
                    color=(min(255, base_color[0] + 50), min(255, base_color[1] + 30), min(255, base_color[2])),
                    params={"storage": self.params["storage"]},
                )
            )
        return parts

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        storage = self.params["storage"]
        reserve_factor = self.params["reserve_factor"]

        # Increase max energy capacity
        organism.max_energy = max(organism.max_energy, config.BASE_ENERGY * (1.0 + storage))

        # When hungry, burn reserves slowly
        hunger = 1.0 - organism.energy / organism.max_energy
        if hunger > reserve_factor and organism.energy < organism.max_energy:
            release = storage * hunger * 0.1 * dt * 60.0
            organism.energy = min(organism.energy + release, organism.max_energy)
