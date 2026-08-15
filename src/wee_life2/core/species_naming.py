"""Deterministic, Latin-sounding species names derived from a genome."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dna import DNA


_LATIN_GENERA = [
    "Agrum",
    "Aculeus",
    "Bestia",
    "Carnis",
    "Celer",
    "Chromis",
    "Corpus",
    "Cursor",
    "Ferox",
    "Flavum",
    "Furax",
    "Gigas",
    "Lentum",
    "Lorica",
    "Lumen",
    "Magnus",
    "Mandibula",
    "Medius",
    "Minimus",
    "Mutans",
    "Nasus",
    "Oculus",
    "Olfactus",
    "Parvus",
    "Pictus",
    "Pinguis",
    "Rapax",
    "Renatus",
    "Rubrum",
    "Sentis",
    "Spina",
    "Tactus",
    "Timidus",
    "Toxicum",
    "Venen",
    "Vibrissus",
    "Viridis",
    "Anguis",
    "Branchia",
    "Cauda",
    "Draco",
    "Echinus",
    "Fungus",
    "Glacies",
    "Grex",
    "Halitus",
    "Ignis",
    "Juba",
    "Krakenus",
    "Larva",
    "Mensura",
    "Natrix",
    "Nebula",
    "Ossa",
    "Pluma",
    "Quies",
    "Radix",
    "Squama",
    "Terra",
    "Turba",
    "Umbra",
    "Vesica",
    "Xenus",
]

_LATIN_EPITHETS = [
    "albus",
    "ater",
    "aurantiacus",
    "caeruleus",
    "crassus",
    "flavus",
    "ferox",
    "gigas",
    "lentus",
    "magnus",
    "medius",
    "minimus",
    "mutans",
    "nanus",
    "nitens",
    "obscurus",
    "pallidus",
    "parvus",
    "pinguis",
    "purpureus",
    "rapax",
    "ruber",
    "rubicundus",
    "silvestris",
    "spinosus",
    "timidus",
    "toxicus",
    "velox",
    "venenosus",
    "viridis",
    "violaceus",
    "vivax",
    "acutus",
    "brevis",
    "durus",
    "elegans",
    "fragilis",
    "gracilis",
    "horridus",
    "immensus",
    "levis",
    "mobilis",
    "notabilis",
    "opacus",
    "placidus",
    "quietus",
    "robustus",
    "solitarius",
    "tenuis",
    "urgens",
    "validus",
    "vagus",
    "amphibius",
    "aquaticus",
    "gregarius",
    "natans",
    "socialis",
]

# Latin-ish stems for building genotype-reflecting species names.
# Each gene kind maps to a short root; top gene -> genus, 2nd/3rd -> epithet.
_GENE_STEMS = {
    "eye": "ocul",
    "jaw": "mand",
    "leg": "ped",
    "spike": "spin",
    "armor": "loric",
    "toxin_gland": "toxic",
    "color": "chrom",
    "metabolism": "metab",
    "scent": "olfact",
    "pheromone": "ferom",
    "fat": "adip",
    "regeneration": "regen",
    "fear": "pavor",
    "touch": "tact",
    "herd": "greg",
    "amphibious": "amphib",
    "venom": "venen",
    "asexual": "solit",
    "cannibal": "vor",
}

_LATIN_NOUN_ENDINGS = ("us", "a", "um", "is", "or")
_LATIN_ADJ_ENDINGS = ("us", "a", "um", "is", "ax", "or", "ens")
_LATIN_CONNECTORS = ("o", "i", "a", "u")


def _latin_word(stem: str, role: str, endings: tuple[str, ...]) -> str:
    """Deterministically pick a Latin-sounding ending for a stem."""
    idx = int(hashlib.md5(f"{role}:{stem}".encode("utf-8")).hexdigest(), 16) % len(endings)
    return stem + endings[idx]


def _genus_word(stem: str) -> str:
    return _latin_word(stem, "genus", _LATIN_NOUN_ENDINGS).capitalize()


def _epithet_word(stem: str) -> str:
    return _latin_word(stem, "epithet", _LATIN_ADJ_ENDINGS)


def signature_for_dna(dna: "DNA") -> tuple:
    """Return a coarse genome fingerprint for naming.

    Similar genomes (same dominant gene kinds, similar color and size)
    produce the same signature, so they get the same name.
    """
    counts: dict[str, int] = {}
    for g in dna.genes:
        counts[g.kind] = counts.get(g.kind, 0) + 1
    sorted_kinds = [k for k, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
    top = sorted_kinds[0] if sorted_kinds else "body"
    second = sorted_kinds[1] if len(sorted_kinds) > 1 else top
    third = sorted_kinds[2] if len(sorted_kinds) > 2 else second

    color_genes = [g for g in dna.genes if g.kind == "color"]
    h = color_genes[0].params.get("hue", 0.0) if color_genes else 0.0
    s = color_genes[0].params.get("saturation", 0.0) if color_genes else 0.0
    hue_bucket = int((h % 1.0) * 8)
    saturation_bucket = int(max(0.0, min(0.999, s)) * 4)

    length_bucket = 0 if len(dna.genes) < 8 else 1 if len(dna.genes) < 14 else 2
    return (top, second, third, hue_bucket, saturation_bucket, length_bucket)


def name_for_dna(dna: "DNA") -> str:
    """Return a deterministic, Latin-sounding name built from the top 3 genes.

    The genus is formed from the most-common gene's Latin stem. The epithet
    combines the second and third most-common gene stems, so the name itself
    visibly reflects the dominant genotype.
    """
    top, second, third, *_ = signature_for_dna(dna)
    top_stem = _GENE_STEMS.get(top, top)
    second_stem = _GENE_STEMS.get(second, second)
    third_stem = _GENE_STEMS.get(third, third)

    genus = _genus_word(top_stem)

    if second == third:
        epithet_stem = second_stem
    else:
        connector = _LATIN_CONNECTORS[
            int(hashlib.md5(f"{second}:{third}".encode("utf-8")).hexdigest(), 16) % len(_LATIN_CONNECTORS)
        ]
        epithet_stem = second_stem + connector + third_stem

    epithet = _epithet_word(epithet_stem)
    return f"{genus} {epithet}"
