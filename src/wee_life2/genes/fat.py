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
    param_bounds = {
        "storage": (0.0, 1.5),  # unbounded storage means an arbitrarily large energy buffer
        "reserve_factor": (0.0, 1.0),  # above 1.0 hunger can never trigger mobilisation
    }

    def body_parts(self, base_color):
        parts = []
        for i in range(self.part_count):
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
        ticks = dt * config.TICKS_PER_SECOND

        # Increase max energy capacity; the reserve limit is shared by all fat
        # genes (largest storage wins, like max_energy) so mixed-storage
        # carriers fill one pool instead of truncating each other's deposits.
        organism.max_energy = max(organism.max_energy, config.BASE_ENERGY * (1.0 + storage))
        organism.fat_capacity = max(organism.fat_capacity, config.BASE_ENERGY * storage)
        organism.fat_reserve = min(organism.fat_reserve, organism.fat_capacity)

        hunger = 1.0 - organism.energy / organism.max_energy
        if organism.energy > organism.max_energy * 0.8:
            # Deposit surplus into the reserve, losing 30% in conversion.
            amount = min(
                0.1 * ticks,
                organism.energy - organism.max_energy * 0.8,
                (organism.fat_capacity - organism.fat_reserve) / 0.7,
            )
            organism.energy -= amount
            organism.fat_reserve += amount * 0.7
        elif hunger > reserve_factor and organism.fat_reserve > 0.0:
            # Mobilise the reserve; fat only returns energy it previously stored.
            amount = min(0.1 * ticks, organism.fat_reserve, organism.max_energy - organism.energy)
            organism.fat_reserve -= amount
            organism.energy += amount
