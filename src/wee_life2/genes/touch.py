"""Touch / whisker gene: short-range feelers that steer away from walls."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class TouchGene(Gene):
    """Whiskers sense nearby walls and hazards and nudge the organism away before impact."""

    kind = "touch"
    default_params = {
        "range": 40.0,
        "spread": 0.5,  # radians between left/center/right whiskers
        "sensitivity": 1.0,
        "hazard_weight": 1.5,
        "size": 3.0,
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._side = 1 if random.random() > 0.5 else -1

    def body_parts(self, base_color):
        size = self.params["size"]
        return [
            BodyPartBlueprint(
                kind="touch",
                offset=(self._side * 4, -6),
                angle=0.2 * self._side,
                size=size,
                color=(230, 230, 150),
                params={"range": self.params["range"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        range_ = self.params["range"]
        if range_ <= 0.0:
            return  # whiskers of zero length feel nothing (and must not divide by zero)
        spread = self.params["spread"]
        sensitivity = self.params["sensitivity"]
        hazard_weight = self.params["hazard_weight"]

        pos = organism.position
        results = []

        # Non-amphibious organisms treat water like a hazard to steer clear of.
        # organism.amphibious is set from the genotype before genes run, so this
        # is independent of gene execution order.
        avoid_water = not organism.amphibious

        px, py = pos
        for angle_offset in [-spread, 0.0, spread]:
            test_angle = organism.angle + angle_offset
            obstacle = world.tile_map.distance_to_obstacle_along_ray(pos, test_angle, range_, avoid_water)
            if obstacle is None:
                results.append((angle_offset, None, 0.0, False))
                continue
            dist, is_hazard = obstacle
            hit_pos = (px + math.cos(test_angle) * dist, py + math.sin(test_angle) * dist)
            tile_type = world.tile_at(hit_pos)
            organism.add_perception(hit_pos, tile_type, "touch", world.tick)

            urgency = 1.0 - (dist / range_)
            weight = sensitivity * (hazard_weight if is_hazard else 1.0) * urgency
            away = -angle_offset
            results.append((angle_offset, away, weight, is_hazard))

        if not results:
            return

        best = max(results, key=lambda r: r[2])
        if best[2] <= 0.0:
            return

        angle_offset, away, weight, is_hazard = best

        # If the forward (center) whisker is the most blocked, pick the side
        # with more clearance instead of driving straight ahead.
        if angle_offset == 0.0:
            left = results[0]
            right = results[2]
            if left[2] < right[2]:
                away = -spread
            elif right[2] < left[2]:
                away = spread
            else:
                away = random.choice([-spread, spread])

        kind = "hazard" if is_hazard else "obstacle"
        organism.add_drive(away, weight, kind)
