"""Genes define both the body plan and the behaviour of organisms."""

from __future__ import annotations

from .base import Gene, GeneParams, BodyPartBlueprint
from .eye import EyeGene
from .jaw import JawGene
from .leg import LegGene
from .spike import SpikeGene
from .armor import ArmorGene
from .toxin_gland import ToxinGlandGene
from .color import ColorGene
from .metabolism import MetabolismGene
from .scent import ScentGene
from .pheromone import PheromoneGene
from .fat import FatGene
from .regeneration import RegenerationGene
from .fear import FearGene
from .touch import TouchGene
from .herd import HerdGene
from .amphibious import AmphibiousGene
from .venom import VenomGene
from .asexual import AsexualGene
from .cannibal import CannibalGene
from .memory import MemoryGene

__all__ = [
    "Gene",
    "GeneParams",
    "BodyPartBlueprint",
    "EyeGene",
    "JawGene",
    "LegGene",
    "SpikeGene",
    "ArmorGene",
    "ToxinGlandGene",
    "ColorGene",
    "MetabolismGene",
    "ScentGene",
    "PheromoneGene",
    "FatGene",
    "RegenerationGene",
    "FearGene",
    "TouchGene",
    "HerdGene",
    "AmphibiousGene",
    "VenomGene",
    "AsexualGene",
    "CannibalGene",
    "MemoryGene",
    "GENE_REGISTRY",
    "register_gene",
    "random_dna_length",
]

GENE_REGISTRY: dict[str, type[Gene]] = {
    "eye": EyeGene,
    "jaw": JawGene,
    "leg": LegGene,
    "spike": SpikeGene,
    "armor": ArmorGene,
    "toxin_gland": ToxinGlandGene,
    "color": ColorGene,
    "metabolism": MetabolismGene,
    "scent": ScentGene,
    "pheromone": PheromoneGene,
    "fat": FatGene,
    "regeneration": RegenerationGene,
    "fear": FearGene,
    "touch": TouchGene,
    "herd": HerdGene,
    "amphibious": AmphibiousGene,
    "venom": VenomGene,
    "asexual": AsexualGene,
    "cannibal": CannibalGene,
    "memory": MemoryGene,
}


def register_gene(gene_cls: type[Gene]) -> type[Gene]:
    """Decorator for adding new genes to the registry at runtime."""
    GENE_REGISTRY[gene_cls.kind] = gene_cls
    return gene_cls


def random_dna_length() -> int:
    """Default number of gene copies in a random genome."""
    return 12
