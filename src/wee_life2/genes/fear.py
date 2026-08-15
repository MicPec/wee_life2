"""Fear gene: detects danger and steers the organism away."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene
from .geometry import angle_diff

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class FearGene(Gene):
    """Ears / antennae detect threats and trigger a strong escape drive."""

    kind = "fear"
    default_params = {
        "range": 90.0,
        "danger_weight": -1.8,
        "reaction": 0.8,
        "alarm_range": 130.0,  # radius for sensing panicking kin
        "alarm_sensitivity": 0.6,  # how strongly secondhand kin alarm is trusted
        "size": 4.0,
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._side = 1 if random.random() > 0.5 else -1

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="fear",
                offset=(self._side * 7, -2),
                angle=0.5 * self._side,
                size=self.params["size"],
                color=(240, 200, 80),
                params={"range": self.params["range"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        pos = organism.position
        range_ = self.params["range"]
        range_sq = range_ * range_
        best_score = 0.0
        best_angle = None

        for other in organism.nearby_organisms(world, range_):
            if other.is_dead:
                continue
            # A threat is bigger, more aggressive or currently biting
            threat_level = other.energy / max(1.0, organism.energy) + other.aggression * 2.0
            if threat_level < 1.2:
                continue
            dx = other.position[0] - pos[0]
            dy = other.position[1] - pos[1]
            d2 = dx * dx + dy * dy
            if d2 > range_sq or d2 < 1:
                continue
            dist = math.hypot(dx, dy)
            # Direction away from the threat
            away_angle = math.atan2(-dy, -dx)
            diff = angle_diff(away_angle, organism.angle)
            score = (threat_level - 1.0) * (1 - dist / range_)
            if score > best_score:
                best_score = score
                best_angle = diff

        # Broadcast how scared we are so panicking kin can be sensed by others
        organism.alarm_level = max(organism.alarm_level, min(1.0, best_score))

        # If nothing directly spotted, pick up secondhand panic from nearby
        # kin (same organism.name) who are already alarmed. Their position
        # itself becomes a warning beacon to steer away from, letting fear
        # ripple through a herd faster than any one organism's own eyes.
        if best_angle is None:
            alarm_range = self.params["alarm_range"]
            alarm_range_sq = alarm_range * alarm_range
            sensitivity = self.params["alarm_sensitivity"]
            for other in organism.nearby_organisms(world, alarm_range):
                if other.is_dead:
                    continue
                if other.name != organism.name or other.alarm_level <= 0.0:
                    continue
                dx = other.position[0] - pos[0]
                dy = other.position[1] - pos[1]
                d2 = dx * dx + dy * dy
                if d2 > alarm_range_sq or d2 < 1:
                    continue
                dist = math.hypot(dx, dy)
                away_angle = math.atan2(-dy, -dx)
                diff = angle_diff(away_angle, organism.angle)
                score = other.alarm_level * sensitivity * (1 - dist / alarm_range)
                if score > best_score:
                    best_score = score
                    best_angle = diff

        if best_angle is not None:
            reaction = self.params["reaction"]
            organism.add_drive(best_angle, self.params["danger_weight"] * best_score * reaction, "danger")
