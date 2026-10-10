"""Mouth / jaw gene: eating food and biting other organisms."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..core import config
from .base import BodyPartBlueprint, Gene
from .geometry import angle_diff, angle_to

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class JawGene(Gene):
    """The jaw lets an organism eat remains / food and bite competitors."""

    kind = "jaw"
    default_params = {
        "strength": 1.5,
        "reach": 12.0,
        "angle": 0.0,  # forward by default
        "size": 7.0,
        "digestion": 0.5,
        "prey_threshold": 0.6,
    }
    param_bounds = {
        "digestion": (0.0, 1.0),  # above 1.0 eating yields more energy than the food had
    }
    wrap_params = frozenset({"angle"})  # signed, so mirrored jaws can evolve

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="jaw",
                offset=(self.params["reach"] * 0.7, 0),
                angle=self.params["angle"],
                size=self.params["size"],
                color=(min(255, base_color[0] + 40), base_color[1], base_color[2]),
                params={"strength": self.params["strength"]},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        reach = self.params["reach"]
        strength = self.params["strength"]
        pos = organism.position
        fwd = (math.cos(organism.angle), math.sin(organism.angle))
        mouth_pos = (pos[0] + fwd[0] * reach, pos[1] + fwd[1] * reach)

        # The mouth is a point `reach` ahead of the body centre; the grab
        # radius is the jaw part's own aperture, NOT `reach` a second time --
        # that made the effective range 2 * reach and let the jaw grab things
        # behind the body.  Floored so a mutated-to-zero `size` still leaves a
        # usable mouth.
        aperture = max(2.0, self.params["size"])

        # Eat food / remains
        for food in list(world.food):
            dist = math.hypot(food.position[0] - mouth_pos[0], food.position[1] - mouth_pos[1])
            if dist < aperture + food.radius:
                gain = food.energy * (0.4 + self.params["digestion"] * 0.6)
                if food.is_poison:
                    # Poison damage depends on own toxin resistance from toxin gene
                    resist = getattr(organism, "toxin_resistance", 0.0)
                    damage = gain * (1.0 - resist)
                    organism.energy -= damage
                else:
                    organism.energy += gain
                world.remove_food(food)
                organism.energy = min(organism.energy, organism.max_energy)
                break

        # Seek and bite other organisms
        if organism.aggression > 0.2:
            is_cannibal = any(g.kind == "cannibal" for g in organism.dna.genes)
            threshold = self.params["prey_threshold"]
            hunt_range = reach * 3
            # nearby_organisms() may return a superset of the requested radius
            # (it caches the widest query of the tick), so every candidate is
            # still distance-filtered below.
            query_radius = max(hunt_range, reach + aperture + max(config.MAX_ORGANISM_RADIUS, 0.0))
            target = None
            best_dist = float("inf")
            victim = None
            for other in organism.nearby_organisms(world, query_radius):
                if other is organism or other.is_dead:
                    continue
                # Kin are off the menu unless the carrier has a cannibal gene
                if not is_cannibal and other.name == organism.name:
                    continue
                # Only hunt organisms with significantly less energy
                if other.energy > organism.energy * threshold:
                    continue
                dist = math.hypot(other.position[0] - pos[0], other.position[1] - pos[1])
                if dist < hunt_range and dist < best_dist:
                    best_dist = dist
                    target = other
                if victim is None:
                    mouth_dist = math.hypot(other.position[0] - mouth_pos[0], other.position[1] - mouth_pos[1])
                    if mouth_dist < aperture + other.radius:
                        victim = other

            if target is not None:
                diff = angle_diff(angle_to(pos, target.position), organism.angle)
                organism.add_drive(diff, organism.aggression * 0.5, "prey")

            if victim is not None:
                armor = getattr(victim, "armor_value", 0.0)
                damage = max(0.0, strength - armor)
                victim.energy -= damage
                organism.energy -= config.ENERGY_COST_ATTACK
                # Inject venom if the attacker has a venom gene
                venom_genes = [g for g in organism.dna.genes if g.kind == "venom"]
                if venom_genes:
                    resist = getattr(victim, "toxin_resistance", 0.0)
                    for vg in venom_genes:
                        dmg_per_tick = vg.params["toxicity"] * (1.0 - resist)
                        duration = vg.params["duration"]
                        victim.add_venom(dmg_per_tick, duration)
                if victim.energy <= 0 and not victim.is_dead:
                    victim.die(world, cause="combat")
