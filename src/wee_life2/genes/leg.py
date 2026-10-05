"""Locomotion gene: legs push the organism forward and turn it."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from ..core import config
from .base import BodyPartBlueprint, Gene
from .geometry import angle_diff

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class LegGene(Gene):
    """Legs translate the organism's desired direction into movement."""

    kind = "leg"
    default_params = {
        "strength": 0.5,
        "agility": 0.5,
        "count": 2.0,
        "size": 8.0,
    }

    def body_parts(self, base_color):
        parts = []
        for i in range(self.part_count):
            side = 1 if i % 2 == 0 else -1
            row = i // 2
            parts.append(
                BodyPartBlueprint(
                    kind="leg",
                    offset=(side * 8, 6 + row * 8),
                    angle=0.0,
                    size=self.params["size"],
                    color=(max(0, base_color[0] - 20), max(0, base_color[1] - 20), max(0, base_color[2] - 20)),
                    params={"strength": self.params["strength"]},
                )
            )
        return parts

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        # All leg genes share one movement system: only the first one runs the
        # logic, but it aggregates strength and agility from every copy so that
        # extra legs make the organism faster/more agile without multiplying
        # the steering command itself (which would cause spinning).
        leg_genes = [g for g in organism.dna.genes if isinstance(g, LegGene)]
        if not leg_genes or leg_genes[0] is not self:
            return

        speed = sum(g.params["strength"] for g in leg_genes) * 2.5
        agility = max(g.params["agility"] for g in leg_genes)

        # Default wandering if no strong steering
        if not organism.drives:
            organism.wander_timer -= dt
            if organism.wander_timer <= 0:
                organism.wander_angle = random.uniform(-math.pi, math.pi)
                organism.wander_timer = random.uniform(0.5, 2.0)
            diff = angle_diff(organism.wander_angle, organism.angle)
            organism.add_drive(diff, 0.3)

        combined = organism.combined_drive()
        organism.steer(combined * agility * 0.5)

        ax = math.cos(organism.angle) * speed
        ay = math.sin(organism.angle) * speed
        organism.accelerate(ax, ay)

        # Moving costs mass: heavy bodies pay proportionally more per tick.
        # ENERGY_COST_MOVE is the base rate; the speed term scales the burn.
        # A MAX_SPEED of 0 (degenerate config) means no thrust is applied, so
        # it must not crash the cost formula either.
        speed_ratio = speed / config.MAX_SPEED if config.MAX_SPEED > 0.0 else 0.0
        cost = config.ENERGY_COST_MOVE * (0.2 + 0.5 * speed_ratio) * organism.mass_ratio * dt * config.TICKS_PER_SECOND
        organism.energy -= cost
