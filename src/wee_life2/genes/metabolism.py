"""Metabolism gene: controls energy burn, lifespan and radiation resistance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core import config
from .base import Gene

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class MetabolismGene(Gene):
    """Governs how fast energy is consumed and how long the organism lives."""

    kind = "metabolism"
    default_params = {
        "efficiency": 0.5,
        "lifespan_factor": 1.0,
        "radiation_resistance": 0.0,
        "regeneration": 0.0,
    }
    param_bounds = {
        "efficiency": (0.0, 0.85),  # 1.0 would delete the idle drain; keep at least 15% of it
        "lifespan_factor": (0.2, 3.0),  # at/below 0 every newborn dies instantly
        "regeneration": (0.0, 0.1),  # heals from nothing: keep the leak negligible
    }

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        efficiency = self.params["efficiency"]
        lifespan_factor = self.params["lifespan_factor"]
        radiation = self.params["radiation_resistance"]
        regen = self.params["regeneration"]

        # Efficiency reduces the organism's idle upkeep (higher = slower drain).
        # Multiplicative so several metabolism genes compound.
        organism.upkeep_efficiency *= 1.0 - efficiency

        # Regeneration restores health/energy slowly
        if regen > 0 and organism.energy < organism.max_energy:
            organism.energy += regen * 0.05 * dt * config.TICKS_PER_SECOND
            organism.energy = min(organism.energy, organism.max_energy)

        # Resistance to environmental hazards accumulates across metabolism genes
        organism.radiation_resistance = min(1.0, organism.radiation_resistance + radiation)

        # Age limits lifespan. Multiplicative so multiple metabolism genes
        # compound instead of the last-applied gene overwriting the rest.
        organism.lifespan *= lifespan_factor
