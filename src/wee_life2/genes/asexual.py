"""Asexual reproduction gene: lets an organism clone itself without a mate."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene
from ..core import config

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class AsexualGene(Gene):
    """Allows solitary reproduction: no partner or courtship needed.

    On a cooldown, if the carrier is of mating age and has enough spare
    energy, it spawns a mutated clone of its own genome next to itself.
    The mutation rate/strength is boosted relative to normal sexual
    reproduction (no crossover to introduce variation, so more noise is
    added per copy instead) to keep genetic diversity from stalling.
    """

    kind = "asexual"
    default_params = {
        "cooldown": 800.0,  # ticks between reproduction attempts
        "energy_cost": 80.0,
        "mutation_multiplier": 1.5,
        "size": 5.0,
    }
    param_bounds = {
        # A zero cooldown means a clone attempt every single tick, which
        # defeats the density check below; a huge one just makes the gene
        # inert, which is self-limiting but still worth bounding.
        "cooldown": (100.0, 5000.0),
        # At zero cost the `energy < cost * 1.25` guard never fires and
        # cloning becomes free.  Floor it at the per-parent cost of sexual
        # reproduction so asexual reproduction is never the cheaper option.
        "energy_cost": (float(config.ENERGY_COST_MATE), 400.0),
        # Feeds `MUTATION_RATE * multiplier`; above ~10x the effective rate
        # exceeds 1.0 and every parameter mutates on every clone.
        "mutation_multiplier": (0.5, 5.0),
    }

    def __init__(self, params=None) -> None:
        super().__init__(params)
        # Desync carriers so they don't all reproduce on the same tick
        self._timer = random.uniform(0.0, self._effective_cooldown())

    def _effective_cooldown(self) -> float:
        return self.params["cooldown"] * config.ASEXUAL_COOLDOWN_RATE

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="asexual",
                offset=(0, 8),
                size=self.params["size"],
                color=(200, 220, 100),
                params={},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        self._timer -= dt * config.TICKS_PER_SECOND
        if self._timer > 0.0:
            return

        cost = self.params["energy_cost"]
        if (
            not (
                organism.age > organism.lifespan * config.ASEXUAL_MATURITY_MIN_FRACTION
                and organism.age < organism.maturity_max_age
            )
            or organism.energy < cost * 1.25
        ):
            return

        # Respect the same crowd-control limit as sexual mating, otherwise
        # asexual reproduction bypasses it entirely and can cause runaway
        # clone avalanches in dense clusters. Don't reset the cooldown here
        # so it retries next tick once the area thins out.
        density = world.local_density(organism.position, config.MATING_DENSITY_RADIUS, exclude=(organism,))
        # Asexual cloning is stricter than sexual mating to stop it from
        # filling every free pocket and smothering sexual reproduction.
        if density >= config.MATING_DENSITY_LIMIT:
            return

        child_dna = organism.dna.clone()
        child_dna.mutate(
            config.MUTATION_RATE * self.params["mutation_multiplier"],
            config.MUTATION_STRENGTH,
        )

        offset = (random.uniform(-12, 12), random.uniform(-12, 12))
        pos = (organism.position[0] + offset[0], organism.position[1] + offset[1])
        child = world.spawn_child_from_dna(child_dna, pos, parent=organism)

        if child is None:
            return

        organism.energy -= cost

        # Match the sexual reproduction death-on-birth risk: sometimes asexual
        # cloning fails catastrophically and the mother dies, while the child
        # is already in the world. The mother pays the cost before this roll.
        if random.random() < config.MATING_DEATH_CHANCE:
            organism.die(world, cause="asexual_failure")
            return

        # spawn_child_from_dna already records the birth; just reset the timer.
        self._timer = self._effective_cooldown()
