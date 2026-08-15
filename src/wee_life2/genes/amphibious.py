"""Amphibious gene: lets an organism move freely through water tiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BodyPartBlueprint, Gene

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

    Water-seeking behaviour is now handled by the ``eye``/``scent``/``memory``
    genes; ``amphibious`` only sets the phenotype flag.
    """

    kind = "amphibious"
    default_params = {
        "size": 4.0,
    }

    def body_parts(self, base_color):
        return [
            BodyPartBlueprint(
                kind="amphibious",
                offset=(0, -7),
                size=self.params["size"],
                color=(70, 190, 210),
                params={},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        organism.amphibious = True
