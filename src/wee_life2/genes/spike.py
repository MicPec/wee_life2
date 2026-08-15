"""Offensive body part: spikes damage organisms that touch the carrier."""

from __future__ import annotations

import math
import weakref
from typing import TYPE_CHECKING

from ..core import config
from .base import BodyPartBlueprint, Gene

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class SpikeGene(Gene):
    """Spikes deal passive damage to colliding organisms."""

    kind = "spike"
    default_params = {
        "damage": 0.4,
        "size": 6.0,
        "count": 3.0,
        "cooldown": 1.0,
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._count = max(1, int(self.params["count"]))
        self._last_hit: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    def body_parts(self, base_color):
        parts = []
        for i in range(self._count):
            theta = (2 * math.pi * i) / self._count
            r = 8.0
            parts.append(
                BodyPartBlueprint(
                    kind="spike",
                    offset=(math.cos(theta) * r, math.sin(theta) * r),
                    angle=theta,
                    size=self.params["size"],
                    color=(220, 60, 60),
                    params={"damage": self.params["damage"]},
                )
            )
        return parts

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        now = organism.age
        cooldown = self.params["cooldown"]
        damage = self.params["damage"]

        # Prune old cooldown entries
        for key in list(self._last_hit.keys()):
            if now - self._last_hit[key] > cooldown:
                del self._last_hit[key]

        max_reach = organism.radius + self.params["size"] + config.MAX_ORGANISM_RADIUS
        ox, oy = organism.position
        for other in organism.nearby_organisms(world, max_reach):
            if other is organism or other.is_dead:
                continue
            # Avoid attacking organisms that are much bigger / stronger
            if other.energy > organism.energy * 1.3:
                continue
            dx = other.position[0] - ox
            dy = other.position[1] - oy
            d2 = dx * dx + dy * dy
            other_reach = max_reach + other.radius
            if d2 > other_reach * other_reach:
                continue
            dist = math.hypot(dx, dy)
            if dist < organism.radius + other.radius + self.params["size"]:
                if other in self._last_hit:
                    continue
                self._last_hit[other] = now
                other.energy -= damage
                if other.energy <= 0 and not other.is_dead:
                    other.die(world, cause="combat")
