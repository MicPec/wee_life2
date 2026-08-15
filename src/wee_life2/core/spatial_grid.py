"""Spatial grid for fast organism neighbourhood queries."""

from __future__ import annotations

import math
from typing import Any, Iterable


class SpatialGrid:
    """Bucket-based spatial index for living organisms."""

    def __init__(self, cell_size: float = 100.0, width: float = 0.0, height: float = 0.0) -> None:
        self.cell_size = cell_size
        self.width = width
        self.height = height
        self._grid: dict[tuple[int, int], list[Any]] = {}

    def _cell(self, position: tuple[float, float]) -> tuple[int, int]:
        return (int(position[0] / self.cell_size), int(position[1] / self.cell_size))

    def clear(self) -> None:
        self._grid.clear()

    def add(self, organism: Any) -> None:
        """Add a living organism to the grid."""
        if getattr(organism, "is_dead", False):
            return
        cx, cy = self._cell(organism.position)
        self._grid.setdefault((cx, cy), []).append(organism)

    def remove(self, organism: Any) -> None:
        """Remove an organism from the grid."""
        cx, cy = self._cell(organism.position)
        cell = self._grid.get((cx, cy))
        if cell and organism in cell:
            cell.remove(organism)

    def rebuild(self, organisms: Iterable[Any]) -> None:
        """Re-bucket all living organisms from an iterable."""
        self.clear()
        for organism in organisms:
            if not getattr(organism, "is_dead", False):
                self.add(organism)

    def near(
        self,
        position: tuple[float, float],
        radius: float,
        exclude: tuple[Any, ...] = (),
    ) -> list[Any]:
        """Return a list of organisms within ``radius`` of ``position``."""
        if radius <= 0:
            return []
        x, y = position
        cell_size = self.cell_size
        cmin = int((x - radius) / cell_size)
        cmax = int((x + radius) / cell_size)
        rmin = int((y - radius) / cell_size)
        rmax = int((y + radius) / cell_size)
        r2 = radius * radius
        grid = self._grid
        result: list[Any] = []
        append = result.append
        for cx in range(cmin, cmax + 1):
            for cy in range(rmin, rmax + 1):
                cell = grid.get((cx, cy))
                if not cell:
                    continue
                for organism in cell:
                    if organism.is_dead:
                        continue
                    if exclude and organism in exclude:
                        continue
                    dx = organism.position[0] - x
                    dy = organism.position[1] - y
                    if dx * dx + dy * dy <= r2:
                        append(organism)
        return result

    def local_density(
        self,
        position: tuple[float, float],
        radius: float,
        exclude: tuple[Any, ...] = (),
    ) -> int:
        """Count living organisms (other than those in ``exclude``) within ``radius``."""
        return sum(1 for _ in self.near(position, radius, exclude))
