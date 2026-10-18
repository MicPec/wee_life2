"""Amphibious gene: lets an organism move freely through water tiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core import config
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
    is an energy drain on land (``config.AMPHIBIOUS_LAND_DRAIN``), which on its own
    empties a full-energy amphibian in under a minute at the default 0.05.

    The gene therefore also emits a water-return drive whenever the organism
    is on land: it steers toward ``World.nearest_water`` with weight
    ``water_weight * (base_pull + (1 - base_pull) * urgency)``. ``base_pull``
    keeps even a well-fed carrier tethered to the shore, and ``urgency`` ramps
    from 0 to 1 as energy falls below ``urgency_threshold`` (same urgency
    pattern as ``scent``'s ``heal_weight``/``heal_threshold``), so a drained
    amphibian heads home over any food it sees. All four parameters are
    heritable and bounded, so selection can loosen the tether (``base_pull``
    toward 0) if foraging on land pays off.

    Water is sensed by the gene itself (moist skin), not through ``eye`` or
    ``scent``: gating the drive on a distance sense left every blind
    amphibian to wander inland and die. ``search_range`` bounds that sense.
    Only the first ``amphibious`` gene in the genome emits the drive, so
    duplicates cannot stack copies of the same vector. Land itself can never
    be a *sensed* hazard: ``first_interesting_tile_along_ray`` treats
    ``TILE_EMPTY`` as pass-through, so stopping rays on land would blind every
    sense.
    """

    kind = "amphibious"
    default_params = {
        "size": 7.0,
        "water_weight": 1.2,  # steering weight toward water at full urgency
        "base_pull": 0.4,  # fraction of water_weight felt on land even when well-fed
        "search_range": 240.0,  # how far the gene senses the nearest water
        "urgency_threshold": 0.8,  # energy fraction below which the pull ramps up to full
    }
    param_bounds = {
        "water_weight": (0.0, 3.0),
        "base_pull": (0.0, 1.0),
        "search_range": (0.0, 600.0),
        "urgency_threshold": (0.0, 1.0),
    }

    # Ticks between nearest-water lookups. nearest_water scans a square of
    # tiles around the organism, and the shore barely moves relative to an
    # organism in a few ticks, so re-scanning every tick for every beached
    # amphibian would be wasted work on the hot path.
    RETARGET_TICKS = 10.0

    def __init__(self, params=None) -> None:
        super().__init__(params)
        self._water_target: tuple[float, float] | None = None
        self._retarget_in = 0.0

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

    def water_pull(self, health: float) -> float:
        """Steering weight toward water for an energy fraction ``health``."""
        threshold = self.params["urgency_threshold"]
        urgency = 0.0
        if threshold > 0.0 and health < threshold:
            urgency = min(1.0, (threshold - health) / threshold)
        base = self.params["base_pull"]
        return self.params["water_weight"] * (base + (1.0 - base) * urgency)

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        organism.amphibious = True

        # Only the first amphibious gene runs the drive logic (same pattern
        # as memory): a duplicated gene must not stack N copies of the vector.
        amphibious_genes = [g for g in organism.dna.genes if isinstance(g, AmphibiousGene)]
        if not amphibious_genes or amphibious_genes[0] is not self:
            return

        search_range = self.params["search_range"]
        if search_range <= 0.0:
            return  # range mutated away: a landlocked amphibian still pays upkeep
        if world.is_water(organism.position):
            # Already home; look the shore up afresh once it leaves again.
            self._retarget_in = 0.0
            return

        health = organism.energy / organism.max_energy if organism.max_energy > 0 else 0.0
        weight = self.water_pull(health)
        if weight <= 0.0:
            return

        target = self._find_water(organism.position, world, search_range, dt)
        if target is None:
            return
        # Positive weight attracts: pass the un-reversed angle toward the
        # water (steering sign convention, AGENTS.md).
        organism.add_drive(angle_diff(angle_to(organism.position, target), organism.angle), weight, "water")

    def _find_water(
        self, position: tuple[float, float], world: World, search_range: float, dt: float
    ) -> tuple[float, float] | None:
        """Nearest water tile centre, re-scanned every ``RETARGET_TICKS``.

        A miss (``None``) is cached too, so an amphibian stranded far from any
        lake does not re-scan the whole square every tick. A cached target
        that stopped being water (map edited) forces an immediate re-scan.
        """
        self._retarget_in -= dt * config.TICKS_PER_SECOND
        target = self._water_target
        if self._retarget_in <= 0.0 or (target is not None and not world.is_water(target)):
            target = world.nearest_water(position, search_range)
            self._water_target = target
            self._retarget_in = self.RETARGET_TICKS
        return target
