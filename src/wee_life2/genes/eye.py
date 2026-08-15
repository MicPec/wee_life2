"""Sensory gene: eyes detect nearby objects and steer the organism."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from ..core import config
from .base import BodyPartBlueprint, Gene, hsv_to_rgb
from .geometry import angle_diff, angle_to, wrap_angle

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class EyeGene(Gene):
    """An eye detects food, mates or threats and creates a steering signal."""

    AGGRESSION_THRESHOLD = 0.15
    kind = "eye"
    default_params = {
        "range": 120.0,
        "fov": 2.0,  # radians
        "acuity": 0.8,  # 0-1, influences object resolution / preference
        "food_weight": 0.6,
        "mate_weight": 0.5,
        "threat_weight": -0.9,
        "wall_weight": -0.7,
        "hazard_weight": -0.9,
        "water_weight": 0.4,
        "terrain_rays": 3.0,
        "direction": 0.0,  # radians offset from the organism's forward angle
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        # Randomise which side the eye sits on
        self._side = 1 if random.random() > 0.5 else -1
        # Give freshly-created eyes (no inherited "direction") a random facing
        # so that multiple eyes on the same organism can look different ways.
        if not params or "direction" not in params:
            self.params["direction"] = random.uniform(-1.3, 1.3)

    def mutate(self, rate: float, strength: float) -> None:
        for key in self.params:
            if random.random() >= rate:
                continue
            if key == "direction":
                noise = (random.random() * 2.0 - 1.0) * strength * math.pi
                self.params[key] = wrap_angle(self.params[key] + noise)
            else:
                noise = (random.random() * 2.0 - 1.0) * strength
                self.params[key] *= 1.0 + noise
                if key.endswith("_weight"):
                    default = self.default_params.get(key, 0.0)
                    if default < 0:
                        self.params[key] = min(0.0, self.params[key])
                    else:
                        self.params[key] = max(0.0, self.params[key])
                else:
                    self.params[key] = max(0.0, self.params[key])

    def body_parts(self, base_color):
        range_ = self.params["range"]
        size = 3 + min(range_ / 60.0, 5)
        hue = 0.55 + (self.params["acuity"] * 0.2)
        direction = self.params["direction"]
        return [
            BodyPartBlueprint(
                kind="eye",
                offset=(self._side * (size + 3), -4),
                angle=direction,
                size=size,
                color=hsv_to_rgb(hue, 0.8, 0.9),
                params={"range": range_, "fov": self.params["fov"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        pos = organism.position
        px, py = pos
        angle = organism.angle
        view_angle = angle + self.params["direction"]
        fov = self.params["fov"]
        half_fov = fov / 2
        range_ = self.params["range"]
        range_sq = range_ * range_
        range_inv = 1.0 / range_
        acuity = self.params["acuity"]
        best = None
        best_score = -1e9

        is_amphibious = organism.amphibious
        has_metabolism = organism.has_metabolism
        self_can_mate = organism.can_mate()
        food_weight = self.params["food_weight"]
        mate_weight = self.params["mate_weight"]
        threat_weight = self.params["threat_weight"]
        aggression_threshold = self.AGGRESSION_THRESHOLD
        org_aggression = organism.aggression

        view_cos = math.cos(view_angle)
        view_sin = math.sin(view_angle)
        cos_half_fov = math.cos(half_fov)

        def is_in_view(target_pos):
            tx, ty = target_pos
            dx = tx - px
            dy = ty - py
            dist_sq = dx * dx + dy * dy
            if dist_sq > range_sq or dist_sq < 1:
                return None
            dist = math.sqrt(dist_sq)
            # FOV check using dot product; avoids atan2 for every target.
            if dx * view_cos + dy * view_sin < dist * cos_half_fov:
                return None
            return dist

        def discount(target_pos):
            d = 1.0
            if not is_amphibious and world.line_crosses_water(pos, target_pos):
                d *= config.WATER_SIGHT_DISCOUNT
            if world.line_crosses_hazard(pos, target_pos):
                d *= config.WATER_SIGHT_DISCOUNT
            return d

        def direction_diff(target_pos):
            return angle_diff(angle_to(pos, target_pos), angle)

        # Look for food (organisms without a metabolism gene gain nothing
        # from eating, so they have no drive to seek it out)
        if has_metabolism:
            for food in world.food:
                dist = is_in_view(food.position)
                if dist is None:
                    continue
                base = food_weight * (1 - dist * range_inv)
                if base > best_score:
                    d = discount(food.position)
                    score = base * d
                    if score > best_score:
                        best_score = score
                        best = (direction_diff(food.position), "food", food_weight * d)

        # Scan other organisms once for both mates and threats.
        for other in organism.nearby_organisms(world, range_):
            if other.is_dead:
                continue
            dist = is_in_view(other.position)
            if dist is None:
                continue
            other_pos = other.position

            # Look for mates
            if self_can_mate and other.can_mate():
                base = mate_weight * (1 - dist * range_inv)
                if base > best_score:
                    d = discount(other_pos)
                    score = base * d
                    if score > best_score:
                        best_score = score
                        best = (direction_diff(other_pos), "mate", mate_weight * d)

            # Look for threats
            # Only flee from genuinely dangerous organisms, not a jaw count of one.
            if other.aggression > org_aggression * 1.2 and other.aggression > aggression_threshold:
                score = threat_weight * (1 - dist * range_inv)
                if score > best_score:
                    best_score = score
                    best = (direction_diff(other_pos), "threat", threat_weight)

        if best:
            diff, kind, weight = best
            organism.add_drive(diff, weight, kind)

        # Terrain sensing: walls, hazards and water within the field of view.
        # Gather all terrain observations into a single vector so that multiple
        # nearby walls/hazards do not fight each other and cause spinning.
        terrain_rays = int(self.params["terrain_rays"])
        if terrain_rays > 0:
            wall_weight = self.params["wall_weight"]
            hazard_weight = self.params["hazard_weight"]
            water_weight = self.params["water_weight"]
            fov = self.params["fov"]
            half_fov = fov / 2.0
            start_angle = view_angle - half_fov
            step = fov / max(1, terrain_rays - 1) if terrain_rays > 1 else 0.0
            total_x = 0.0
            total_y = 0.0
            for i in range(terrain_rays):
                ray_angle = start_angle + i * step
                hit = world.tile_map.first_interesting_tile_along_ray(pos, ray_angle, range_)
                if hit is None:
                    continue
                hit_pos, tile_type = hit
                organism.add_perception(hit_pos, tile_type, "eye", world.tick)
                dx = hit_pos[0] - px
                dy = hit_pos[1] - py
                dist = math.hypot(dx, dy)
                if dist < 1.0:
                    continue
                strength = (1.0 - dist * range_inv) * acuity
                if tile_type == world.TILE_WALL:
                    wx, wy = -dx, -dy
                    w = -wall_weight * strength
                elif tile_type in (world.TILE_RADIOACTIVE, world.TILE_LAVA):
                    wx, wy = -dx, -dy
                    w = -hazard_weight * strength
                elif tile_type == world.TILE_WATER:
                    wx, wy = dx, dy
                    w = water_weight * (1.0 if is_amphibious else -1.0) * strength
                else:
                    continue
                d = math.hypot(wx, wy)
                if d > 0:
                    total_x += (wx / d) * w
                    total_y += (wy / d) * w
            if total_x != 0.0 or total_y != 0.0:
                target_angle = math.atan2(total_y, total_x)
                drive = angle_diff(target_angle, angle)
                weight = min(1.0, math.hypot(total_x, total_y))
                organism.add_drive(drive, weight, "terrain")
