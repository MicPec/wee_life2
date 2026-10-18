"""Top-level simulation runner."""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from .core import config
from .core.dna import DNA
from .core.map_storage import MapStorage
from .core.world import World
from .render.actions import (
    Action,
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

    # Fraction of the world's organism cap seeded at the start of a run, and
    # how much food is scattered per seeded organism.
    INITIAL_POPULATION_FRACTION = 0.20
    INITIAL_FOOD_PER_ORGANISM = 1.4

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
        self._seed_population()

    def _seed_population(self) -> None:
        """Scatter the starting organisms and food onto the current map."""
        count = max(1, int(self.world.max_organisms * self.INITIAL_POPULATION_FRACTION))
        self.world.spawn_organisms(count)
        self.world.spawn_food(int(count * self.INITIAL_FOOD_PER_ORGANISM))

    def _handle_action(self, action: Action) -> None:
        """Dispatch one renderer action to its handler."""
        handler = self._ACTION_HANDLERS.get(type(action))
        if handler is not None:
            handler(self, action)

    def _on_save(self, _action: Action) -> None:
        self.storage.save(self.world.save_tiles())

    def _on_clear(self, _action: Action) -> None:
        self.world.clear_map()
        self._start_new_run()

    def _on_randomize(self, _action: Action) -> None:
        self.world.generate_map()
        self._start_new_run()

    def _on_spawn_random(self, _action: Action) -> None:
        self.world.spawn_organisms(random.randint(10, 20))

    # Built after the methods above exist; keyed on the exact action type.
    _ACTION_HANDLERS: dict[type[Action], Callable[["Simulation", Action], None]] = {}

    def run(self) -> None:
        while self.renderer.running:
            dt = self.renderer.tick()
            for action in self.renderer.handle_events(self.world):
                self._handle_action(action)

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
        """Create a random organism at the given screen position if tile is empty.

        The genome matches the clicked medium (amphibious in water, not on
        land), like :meth:`World.spawn_organisms`, so a click never drops a
        land creature into a lake to drown or an amphibian onto dry land.
        """
        if self.world.is_wall(screen_pos):
            return
        pos = (float(screen_pos[0]), float(screen_pos[1]))
        self.world.spawn_organism(DNA.random_for(amphibious=self.world.is_water(pos)), pos)

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
        self._seed_population()

    def reset(self) -> None:
        """Reset the simulation: clear organisms/food, keep the map, respawn."""
        self.world.clear_population()
        self.renderer.clear_selections()
        self._seed_population()
        self.stats.log_reset(self.world)


# Filled in here because the handlers are unbound methods of the class above.
Simulation._ACTION_HANDLERS = {
    SpawnAction: lambda sim, action: sim.spawn_at(action.pos),
    RemoveAction: lambda sim, action: sim.remove_at(action.pos),
    SaveAction: Simulation._on_save,
    ClearAction: Simulation._on_clear,
    RandomizeAction: Simulation._on_randomize,
    SpawnRandomAction: Simulation._on_spawn_random,
    ResetAction: lambda sim, _action: sim.reset(),
}
