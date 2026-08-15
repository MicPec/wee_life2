"""Top-level simulation runner."""

from __future__ import annotations

import math
import random

from .core import config
from .core.dna import DNA
from .core.map_storage import MapStorage
from .core.world import World
from .render.actions import (
    ClearAction,
    RandomizeAction,
    RemoveAction,
    ResetAction,
    SaveAction,
    SpawnAction,
    SpawnRandomAction,
)
from .render.renderer import Renderer
from .stats import RunLogger


class Simulation:
    """Runs the world and the Pygame renderer together."""

    def __init__(
        self,
        width: float = config.WORLD_WIDTH,
        height: float = config.WORLD_HEIGHT,
        storage: MapStorage | None = None,
    ) -> None:
        self.world = World(width, height)
        self.storage = storage or MapStorage()
        saved = self.storage.load()
        if saved:
            self.world.load_tiles(saved)
        else:
            self.world.generate_map()
        self.stats = RunLogger(self.world)
        self.world.run_logger = self.stats
        self.renderer = Renderer(
            width=int(width),
            height=int(height),
            fps=config.FPS,
        )
        initial_count = max(1, int(self.world.max_organisms * 0.20))
        self.world.spawn_organisms(initial_count)
        self.world.spawn_food(int(initial_count * 1.4))

    def run(self) -> None:
        while self.renderer.running:
            dt = self.renderer.tick()
            for action in self.renderer.handle_events(self.world):
                if isinstance(action, SpawnAction):
                    self.spawn_at(action.pos)
                elif isinstance(action, RemoveAction):
                    self.remove_at(action.pos)
                elif isinstance(action, SaveAction):
                    self.storage.save(self.world.save_tiles())
                elif isinstance(action, ClearAction):
                    self.world.clear_map()
                    self._start_new_run()
                elif isinstance(action, RandomizeAction):
                    self.world.generate_map()
                    self._start_new_run()
                elif isinstance(action, SpawnRandomAction):
                    self.world.spawn_organisms(random.randint(10, 20))
                elif isinstance(action, ResetAction):
                    self.reset()

            if self.renderer.edit_mode:
                self.renderer.apply_edits(self.world)
            elif not self.renderer.paused:
                self.world.update(dt)

            if not self.renderer.paused:
                self.stats.step(self.world, dt)

            self.renderer.render(self.world)
        self.stats.close()
        self.renderer.close()

    def step(self, dt: float | None = None) -> None:
        """Advance one simulation tick without rendering."""
        if dt is None:
            dt = 1.0 / config.FPS if config.FPS > 0 else 1.0 / 60.0
        self.world.update(dt)
        self.stats.step(self.world, dt)

    def spawn_at(self, screen_pos: tuple[int, int]) -> None:
        """Create a random organism at the given screen position if tile is empty."""
        if self.world.is_wall(screen_pos):
            return
        pos = (float(screen_pos[0]), float(screen_pos[1]))
        self.world.spawn_organism(DNA.random(), pos)

    def remove_at(self, screen_pos: tuple[int, int]) -> None:
        """Remove an organism under the cursor."""
        for organism in self.world.organisms:
            dx = organism.position[0] - screen_pos[0]
            dy = organism.position[1] - screen_pos[1]
            if math.hypot(dx, dy) <= organism.radius + 4:
                organism.die(self.world, cause="removed")
                self.world.remove_organism(organism)
                break

    def _start_new_run(self) -> None:
        """Close the current stats logger and start a fresh run on the current map."""
        self.stats.close()
        self.world.clear_population()
        self.renderer.clear_selections()
        self.stats = RunLogger(self.world)
        self.world.run_logger = self.stats
        initial_count = max(1, int(self.world.max_organisms * 0.20))
        self.world.spawn_organisms(initial_count)
        self.world.spawn_food(int(initial_count * 1.4))

    def reset(self) -> None:
        """Reset the simulation: clear organisms/food, keep the map, respawn."""
        self.world.clear_population()
        self.renderer.clear_selections()
        initial_count = max(1, int(self.world.max_organisms * 0.20))
        self.world.spawn_organisms(initial_count)
        self.world.spawn_food(int(initial_count * 1.4))
        self.stats.log_reset(self.world)
