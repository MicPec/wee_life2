"""Amphibious gene: lets an organism move freely through water tiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene
from .geometry import angle_diff, angle_to

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class AmphibiousGene(Gene):
    """Marks the organism as amphibious.

    Without this gene, organisms swimming across ``World.TILE_WATER`` tiles
    suffer a speed penalty (``config.WATER_SPEED_PENALTY``) and slowly drain
    energy (``config.WATER_DROWN_DAMAGE``), see ``Organism.update``. With this
    gene, water is a safe niche: full speed and no drowning damage. The trade-off
    is a speed and energy penalty on land.

    The gene also emits a water-return drive: once energy falls below
    ``urgency_threshold`` it steers toward ``World.nearest_water``, with the
    weight ramping up as energy falls (same urgency pattern as
    ``scent``'s ``heal_weight``/``heal_threshold``). The drive only fires for
    carriers of an ``eye`` or ``scent`` gene -- a blind amphibian should not
    magically sense water -- and only from the first ``amphibious`` gene in
    the genome, so duplicates cannot stack copies of the same vector. Land
    itself can never be a *sensed* hazard: ``first_interesting_tile_along_ray``
    treats ``TILE_EMPTY`` as pass-through, so stopping rays on land would
    blind every sense; heading home when drained is the workable version of
    that idea. Honest caveat: water holds only about as much food as its
    share of the map, so a starving amphibian trades the land drain for
    poorer foraging; whether that nets out is left to selection on the three
    heritable parameters below.
    """

    kind = "amphibious"
    default_params = {
        "size": 7.0,
        "water_weight": 0.9,  # steering weight toward water when the drive fires
        "search_range": 220.0,  # how far nearest_water looks for a lake
        "urgency_threshold": 0.5,  # energy fraction below which the organism heads home
    }
    param_bounds = {
        "water_weight": (0.0, 3.0),
        "search_range": (0.0, 600.0),
        "urgency_threshold": (0.0, 1.0),
    }

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="amphibious",
                offset=(0, -10),
                size=self.params["size"],
                color=(70, 190, 210),
                params={},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        organism.amphibious = True

        # Only the first amphibious gene runs the drive logic (same pattern
        # as memory): a duplicated gene must not stack N copies of the vector.
        amphibious_genes = [g for g in organism.dna.genes if isinstance(g, AmphibiousGene)]
        if not amphibious_genes or amphibious_genes[0] is not self:
            return

        # A blind amphibian should not magically sense water: the drive needs
        # an eye or scent gene in the genome (checked via dna.genes, like the
        # food-drive metabolism gate, so it is independent of gene order).
        if not any(g.kind in ("eye", "scent") for g in organism.dna.genes):
            return

        search_range = self.params["search_range"]
        if search_range <= 0.0:
            return  # range mutated away: a landlocked amphibian still pays upkeep
        if world.is_water(organism.position):
            return  # already home
        threshold = self.params["urgency_threshold"]
        if threshold <= 0.0:
            return
        health = organism.energy / organism.max_energy if organism.max_energy > 0 else 0.0
        if health >= threshold:
            return  # well-fed: free to forage on land

        target = world.nearest_water(organism.position, search_range)
        if target is None:
            return

        urgency = (threshold - health) / threshold
        weight = self.params["water_weight"] * urgency
        if weight <= 0.0:
            return
        # Positive weight attracts: pass the un-reversed angle toward the
        # water (steering sign convention, AGENTS.md).
        organism.add_drive(angle_diff(angle_to(organism.position, target), organism.angle), weight, "water")
