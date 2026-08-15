"""Genome representation, crossover and mutation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ..genes import GENE_REGISTRY
from ..genes.base import Gene
from . import config
from . import species_naming


@dataclass
class DNA:
    """A genome is a list of gene instances.

    The order and multiplicity of genes determine the body plan and the
    behaviour of an organism.  New genes can be added without changing this
    module thanks to the registry lookup.
    """

    genes: list[Gene] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Hard global cap on genome length: any construction path that
        # accidentally overproduces genes (random, crossover, clone, from_dict)
        # is truncated to the configured maximum.
        if len(self.genes) > config.MAX_GENES:
            self.genes = self.genes[: config.MAX_GENES]

    @classmethod
    def random(cls, length: int = 12) -> "DNA":
        """Create a random genome with a variable number of genes."""
        kinds = list(GENE_REGISTRY.keys())
        weights = [config.GENE_SPAWN_WEIGHTS.get(k, config.GENE_DEFAULT_SPAWN_WEIGHT) for k in kinds]
        genes = []
        max_len = min(length, config.MAX_GENES)
        min_len = min(4, max_len)
        actual_length = random.randint(min_len, max_len)
        for _ in range(actual_length):
            kind = random.choices(kinds, weights=weights, k=1)[0]
            gene_cls = GENE_REGISTRY[kind]
            genes.append(gene_cls())
        return cls(genes)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DNA":
        genes = []
        for g in data.get("genes", []):
            kind = g["kind"]
            gene_cls = GENE_REGISTRY.get(kind)
            if gene_cls:
                genes.append(gene_cls.from_dict(g))
        return cls(genes)

    def to_dict(self) -> dict[str, Any]:
        return {"genes": [g.to_dict() for g in self.genes]}

    def mutate(
        self, rate: float, strength: float, insertion_rate: float | None = None, deletion_rate: float = 0.02
    ) -> None:
        """Mutate the genome: each gene's parameters can be perturbed,
        and genes can be duplicated, lost or reordered."""
        if insertion_rate is None:
            insertion_rate = config.MUTATION_INSERTION_RATE
        # Parametric mutation
        for gene in self.genes:
            gene.mutate(rate, strength)

        # Structural mutations
        if len(self.genes) < config.MAX_GENES and random.random() < insertion_rate:
            kind = random.choice(list(GENE_REGISTRY.keys()))
            idx = random.randint(0, len(self.genes))
            self.genes.insert(idx, GENE_REGISTRY[kind]())

        if len(self.genes) > 1 and random.random() < deletion_rate:
            idx = random.randint(0, len(self.genes) - 1)
            self.genes.pop(idx)

        if len(self.genes) > 1 and random.random() < 0.1:
            i, j = random.sample(range(len(self.genes)), 2)
            self.genes[i], self.genes[j] = self.genes[j], self.genes[i]

    def crossover(self, other: "DNA") -> "DNA":
        """Create a child genome from two parents.

        Genes are aligned by kind where possible, then spliced with a chance
        for a random gene from either parent.  This is a simple starting point;
        more sophisticated crossover can be added later.
        """
        child_genes: list[Gene] = []

        # Group genes by kind for both parents
        def group(dna: DNA) -> dict[str, list[Gene]]:
            groups: dict[str, list[Gene]] = {}
            for gene in dna.genes:
                groups.setdefault(gene.kind, []).append(gene)
            return groups

        a = group(self)
        b = group(other)
        all_kinds = set(a.keys()) | set(b.keys())

        for kind in all_kinds:
            a_genes = a.get(kind, [])
            b_genes = b.get(kind, [])
            # Average number of copies from both parents
            count = int(round((len(a_genes) + len(b_genes)) / 2.0))
            if count == 0:
                continue
            for i in range(count):
                if i < len(a_genes) and i < len(b_genes):
                    if random.random() < 0.5:
                        child_genes.append(a_genes[i].clone())
                    else:
                        child_genes.append(b_genes[i].clone())
                elif i < len(a_genes):
                    child_genes.append(a_genes[i].clone())
                elif i < len(b_genes):
                    child_genes.append(b_genes[i].clone())

        # Random shuffle to simulate recombination, then enforce the global
        # genome length cap before construction so the child can't exceed it.
        random.shuffle(child_genes)
        child_genes = child_genes[: config.MAX_GENES]
        return DNA(child_genes)

    def clone(self) -> "DNA":
        return DNA([g.clone() for g in self.genes])

    def diversity(self, other: "DNA") -> float:
        """Normalized genome distance: 0 means identical, 1 means no shared gene kinds."""
        all_kinds = set(GENE_REGISTRY.keys())
        total = len(self.genes) + len(other.genes)
        if total == 0:
            return 0.0
        diff = 0
        for k in all_kinds:
            ca = sum(1 for g in self.genes if g.kind == k)
            cb = sum(1 for g in other.genes if g.kind == k)
            diff += abs(ca - cb)
        return diff / total

    def signature(self) -> tuple:
        """Return a coarse genome fingerprint for naming."""
        return species_naming.signature_for_dna(self)

    def name(self) -> str:
        """Return a deterministic, Latin-sounding name built from the genome."""
        return species_naming.name_for_dna(self)

    def __repr__(self) -> str:
        counts: dict[str, int] = {}
        for g in self.genes:
            counts[g.kind] = counts.get(g.kind, 0) + 1
        return f"DNA({counts})"
