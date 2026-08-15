"""Cannibal gene: removes the instinctive reluctance to prey on kin."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene
from .geometry import angle_diff, angle_to, distance

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class CannibalGene(Gene):
    """Allows the carrier's ``jaw`` to hunt and bite same-species kin.

    By default ``jaw`` refuses to treat organisms sharing the same
    ``organism.name`` (species label) as prey. This gene lifts that
    restriction. It also raises aggression when the carrier is starving,
    representing desperate cannibalism as a last resort for survival.

    It also perverts the ``pheromone`` gene's mating signal: a kin's own
    pheromone broadcast (meant to attract mates) instead lures the cannibal
    toward it from long range if it looks weaker, well beyond ``jaw``'s
    short bite reach or ``eye``/``scent``'s indiscriminate prey search.
    """

    kind = "cannibal"
    default_params = {
        "hunger_aggression": 0.4,  # extra aggression added when starving
        "hunt_range": 160.0,  # range for sensing kin via their pheromone signal
        "pheromone_lure": 0.7,  # how strongly kin pheromone attracts the hunt
        "size": 6.0,
    }

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="cannibal",
                offset=(0, -6),
                size=self.params["size"],
                color=(140, 20, 20),
                params={},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        hunger = 1.0 - min(1.0, organism.energy / organism.max_energy)
        organism.aggression = min(1.0, organism.aggression + self.params["hunger_aggression"] * hunger)

        pos = organism.position
        range_ = self.params["hunt_range"]
        lure = self.params["pheromone_lure"]
        best_score = -1e9
        best_diff = None

        for other in world.organisms:
            if other is organism or other.is_dead:
                continue
            if other.name != organism.name:
                continue
            pheromone = getattr(other, "pheromone_strength", 0.0)
            if pheromone <= 0.0 or other.energy >= organism.energy:
                continue
            dist = distance(organism, other.position)
            if dist > range_ or dist < 1:
                continue
            score = pheromone * lure * (1 - dist / range_)
            if score > best_score:
                best_score = score
                best_diff = angle_diff(angle_to(pos, other.position), organism.angle)

        if best_diff is not None:
            organism.add_drive(best_diff, organism.aggression * 0.6, "prey")
