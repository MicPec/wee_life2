"""Scent gene: 360-degree chemical sensing for food, mates and danger."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene, hsv_to_rgb
from .geometry import angle_diff, angle_to
from .sensing import radial_ray_angles, sight_discount, terrain_drive

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class ScentGene(Gene):
    """A scent sensor detects smells in all directions with low precision."""

    AGGRESSION_THRESHOLD = 0.15

    kind = "scent"
    default_params = {
        "range": 180.0,
        "precision": 0.4,  # 0-1, how well it can resolve direction
        "food_weight": 0.7,
        "mate_weight": 0.5,
        "danger_weight": -0.8,
        "poison_discrimination": 0.3,  # chance to avoid poison
        "wall_weight": -0.6,
        "hazard_weight": -0.8,
        "water_weight": 0.3,
        "heal_weight": 0.5,
        "heal_threshold": 0.7,
        "terrain_rays": 5.0,
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._side = 1 if random.random() > 0.5 else -1

    def body_parts(self, base_color):
        size = 2 + self.params["precision"] * 4
        return [
            BodyPartBlueprint(
                kind="scent",
                offset=(self._side * (4 + size), -8),
                angle=0.3 * self._side,
                size=size,
                color=hsv_to_rgb(0.8, 0.6, 0.9),
                params={"range": self.params["range"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        range_ = self.params["range"]
        if range_ <= 0.0:
            return  # range mutated away: an anosmic nose still pays upkeep but smells nothing
        pos = organism.position
        px, py = pos
        range_sq = range_ * range_
        range_inv = 1.0 / range_
        precision = max(0.05, self.params["precision"])

        best = None
        best_score = -1e9

        is_amphibious = organism.amphibious
        has_metabolism = organism.has_metabolism
        self_can_mate = organism.can_mate()
        org_angle = organism.angle
        org_aggression = organism.aggression
        org_energy = organism.energy
        threshold = self.AGGRESSION_THRESHOLD
        poison_discrimination = self.params["poison_discrimination"]
        food_weight = self.params["food_weight"]
        mate_weight = self.params["mate_weight"]
        danger_weight = self.params["danger_weight"]

        def angle_noise():
            # Scale noise by (1 - precision) but keep it small enough that the
            # vector still points toward the smelt target; old +/- pi was
            # essentially random steering and made scent-driven foraging fail.
            return random.uniform(-1.0, 1.0) * (1.0 - precision) * 0.5

        def discount(target_pos):
            return sight_discount(world, pos, target_pos, is_amphibious=is_amphibious)

        # Smell food / poison (organisms without a metabolism gene gain
        # nothing from eating, so they have no drive to seek it out)
        if has_metabolism:
            for food in world.food:
                fx, fy = food.position
                dx = fx - px
                dy = fy - py
                dist_sq = dx * dx + dy * dy
                if dist_sq > range_sq or dist_sq < 1:
                    continue
                if food.is_poison and random.random() < poison_discrimination:
                    continue
                dist = math.sqrt(dist_sq)
                base = food_weight * (1 - dist * range_inv)
                if base > best_score:
                    d = discount(food.position)
                    s = base * d
                    if s > best_score:
                        best_score = s
                        diff = angle_diff(angle_to(pos, food.position), org_angle)
                        best = (diff + angle_noise(), "food", food_weight * d)

        # Scan nearby organisms once for both mates and danger.
        for other in organism.nearby_organisms(world, range_):
            if other.is_dead:
                continue
            ox, oy = other.position
            dx = ox - px
            dy = oy - py
            dist_sq = dx * dx + dy * dy
            if dist_sq > range_sq or dist_sq < 1:
                continue
            dist = math.sqrt(dist_sq)
            other_pos = other.position

            if self_can_mate and other.can_mate():
                # Pheromones increase attractiveness
                attract = 1.0 + 0.5 * other.pheromone_strength
                base = mate_weight * (1 - dist * range_inv) * attract
                if base > best_score:
                    d = discount(other_pos)
                    s = base * d
                    if s > best_score:
                        best_score = s
                        diff = angle_diff(angle_to(pos, other_pos), org_angle)
                        best = (diff + angle_noise(), "mate", mate_weight * attract * d)

            # Danger: avoid organisms with a clear aggression/energy advantage.
            if (
                other.aggression > org_aggression * 1.1
                and other.aggression > threshold
                and other.energy > org_energy * 0.8
            ):
                s = danger_weight * (1 - dist * range_inv)
                if s > best_score:
                    best_score = s
                    diff = angle_diff(angle_to(pos, other_pos), org_angle)
                    best = (diff + angle_noise(), "danger", danger_weight)

        if best:
            diff, kind, weight = best
            organism.add_drive(diff, 0.8 * weight, kind)

        # Terrain sensing: scent can "smell" walls, hazards, water and heal tiles.
        terrain_rays = int(self.params["terrain_rays"])
        if terrain_rays > 0:
            terrain_drive(
                organism,
                world,
                ray_angles=radial_ray_angles(org_angle, terrain_rays),
                range_=range_,
                sharpness=max(0.05, self.params["precision"]),
                source="scent",
                wall_weight=self.params["wall_weight"],
                hazard_weight=self.params["hazard_weight"],
                water_weight=self.params["water_weight"],
                is_amphibious=is_amphibious,
                heal_weight=self.params["heal_weight"],
                heal_threshold=self.params["heal_threshold"],
            )
