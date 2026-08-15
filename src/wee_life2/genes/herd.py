"""Herd gene: draws the organism toward others of the same species."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene
from .geometry import angle_diff

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class HerdGene(Gene):
    """A social instinct that creates a steering drive toward nearby kin.

    "Kin" is approximated by comparing ``organism.name``, the Latin-sounding
    species label derived from ``DNA.signature()``. Organisms with the same
    name are treated as the same species and attract each other, producing
    flocking / clustering behaviour without needing to compare full genomes.
    """

    kind = "herd"
    default_params = {
        "range": 110.0,
        "cohesion": 0.5,  # steering weight toward the group centroid
        "size": 3.0,
    }

    def body_parts(self, base_color):
        size = self.params["size"]
        return [
            BodyPartBlueprint(
                kind="herd",
                offset=(0, 6),
                angle=math.pi,
                size=size,
                color=(255, 215, 90),
                params={"range": self.params["range"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        pos = organism.position
        range_ = self.params["range"]
        sum_x = 0.0
        sum_y = 0.0
        count = 0

        for other in world.organisms:
            if other is organism or other.is_dead:
                continue
            if other.name != organism.name:
                continue
            dx = other.position[0] - pos[0]
            dy = other.position[1] - pos[1]
            dist = math.hypot(dx, dy)
            if dist > range_ or dist < 1:
                continue
            sum_x += dx
            sum_y += dy
            count += 1

        if count == 0:
            return

        target_angle = math.atan2(sum_y / count, sum_x / count)
        diff = angle_diff(target_angle, organism.angle)
        # Weaker pull when only one or two kin are around, capped once a
        # decent-sized group is nearby so it doesn't dominate other drives.
        strength = min(1.0, count / 5.0)
        organism.add_drive(diff, self.params["cohesion"] * strength, "ally")
