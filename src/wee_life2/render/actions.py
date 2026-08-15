"""Typed actions emitted by the renderer and consumed by the simulation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    """Base class for renderer actions."""


@dataclass(frozen=True)
class SpawnAction(Action):
    pos: tuple[int, int]


@dataclass(frozen=True)
class RemoveAction(Action):
    pos: tuple[int, int]


@dataclass(frozen=True)
class SaveAction(Action):
    pass


@dataclass(frozen=True)
class ClearAction(Action):
    pass


@dataclass(frozen=True)
class RandomizeAction(Action):
    pass


@dataclass(frozen=True)
class SpawnRandomAction(Action):
    pass


@dataclass(frozen=True)
class ResetAction(Action):
    pass
