"""Food / remains left by dead organisms."""

from __future__ import annotations

from dataclasses import dataclass

from . import config


@dataclass
class Food:
    """A piece of edible or poisonous matter left by a dead organism."""

    position: tuple[float, float]
    energy: float = 20.0
    radius: float = 6.0
    is_poison: bool = False
    age: float = 0.0
    decay_time: float = 1500.0

    def update(self, dt: float) -> None:
        self.age += dt * config.TICKS_PER_SECOND

    @property
    def is_gone(self) -> bool:
        return self.age > self.decay_time
