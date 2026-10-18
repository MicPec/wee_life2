"""The simulation world: organisms, food, and life-cycle orchestration."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Any

from . import config
from .dna import DNA
from .food import Food
from .organism import Organism
from .spatial_grid import SpatialGrid
from .tile_map import TileMap

if TYPE_CHECKING:
    from ..stats import RunLogger


class World:
    """Container and manager for all dynamic world state."""

    TILE_EMPTY = config.TILE_EMPTY
    TILE_WALL = config.TILE_WALL
    TILE_RADIOACTIVE = config.TILE_RADIOACTIVE
    TILE_LAVA = config.TILE_LAVA
    TILE_WATER = config.TILE_WATER
    TILE_HEAL = config.TILE_HEAL

    def __init__(self, width: float, height: float, tile_size: float = config.TILE_SIZE) -> None:
        self.width = width
        self.height = height

        self.tile_map = TileMap(width, height, tile_size)
        self.spatial_grid = SpatialGrid(cell_size=100.0, width=width, height=height)

        self.organisms: list[Organism] = []
        self.food: list[Food] = []
        self.deaths: dict[str, int] = {}
        self.births: int = 0
        self.births_by_species: dict[str, int] = {}
        self.deaths_by_species: dict[str, int] = {}

        self._food_spawn_accum = 0.0
        self._next_organism_uid = 0
        self.max_organisms = int(self.cols * self.rows * config.POPULATION_CAP)

        self.run_logger: RunLogger | None = None
        self.tick = 0.0

    # ------------------------------------------------------------------
    # Tile map properties and thin wrappers (backward compatibility)
    # ------------------------------------------------------------------
    @property
    def tiles(self) -> list[list[int]]:
        return self.tile_map.tiles

    @property
    def cols(self) -> int:
        return self.tile_map.cols

    @property
    def rows(self) -> int:
        return self.tile_map.rows

    @property
    def tile_size(self) -> float:
        return self.tile_map.tile_size

    @property
    def max_x(self) -> float:
        return self.tile_map.max_x

    @property
    def max_y(self) -> float:
        return self.tile_map.max_y

    def tile_at(self, position: tuple[float, float]) -> int:
        return self.tile_map.tile_at(position)

    def set_tile(self, col: int, row: int, value: int) -> None:
        self.tile_map.set_tile(col, row, value)

    def is_wall(self, position: tuple[float, float]) -> bool:
        return self.tile_map.is_wall(position)

    def is_hazard(self, position: tuple[float, float]) -> bool:
        return self.tile_map.is_hazard(position)

    def is_water(self, position: tuple[float, float]) -> bool:
        return self.tile_map.is_water(position)

    def is_heal(self, position: tuple[float, float]) -> bool:
        return self.tile_map.is_heal(position)

    def is_empty_circle(self, position: tuple[float, float], radius: float) -> bool:
        return self.tile_map.is_empty_circle(position, radius)

    def is_wall_circle(self, position: tuple[float, float], radius: float) -> bool:
        return self.tile_map.is_wall_circle(position, radius)

    def line_crosses_water(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        return self.tile_map.line_crosses_water(a, b)

    def line_crosses_hazard(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        return self.tile_map.line_crosses_hazard(a, b)

    def line_crosses_wall(self, a: tuple[float, float], b: tuple[float, float]) -> bool:
        return self.tile_map.line_crosses_wall(a, b)

    def generate_map(
        self,
        seed: int | None = None,
        *,
        water_fraction: float | None = None,
        wall_fraction: float | None = None,
        hazard_fraction: float | None = None,
        heal_fraction: float | None = None,
    ) -> None:
        self.tile_map.generate_map(
            seed,
            water_fraction=water_fraction,
            wall_fraction=wall_fraction,
            hazard_fraction=hazard_fraction,
            heal_fraction=heal_fraction,
        )

    def clear_map(self) -> None:
        self.tile_map.clear_map()

    def load_tiles(self, tiles: list[list[int]]) -> None:
        self.tile_map.load_tiles(tiles)

    def save_tiles(self) -> list[list[int]]:
        return self.tile_map.save_tiles()

    def random_empty_position(
        self,
        margin: float = 30.0,
        radius: float = 10.0,
        in_water: bool | None = None,
    ) -> tuple[float, float]:
        return self.tile_map.random_empty_position(margin, radius, in_water)

    def nearest_empty_position(self, position: tuple[float, float]) -> tuple[float, float]:
        return self.tile_map.nearest_empty_position(position)

    def nearest_water(self, position: tuple[float, float], max_dist: float) -> tuple[float, float] | None:
        return self.tile_map.nearest_water(position, max_dist)

    def nearest_heal(self, position: tuple[float, float], max_dist: float) -> tuple[float, float] | None:
        return self.tile_map.nearest_heal(position, max_dist)

    def push_out_of_walls(self, position: tuple[float, float], radius: float) -> tuple[float, float]:
        return self.tile_map.push_out_of_walls(position, radius)

    # ------------------------------------------------------------------
    # Organisms and spatial grid
    # ------------------------------------------------------------------
    def add_organism(self, organism: Organism) -> bool:
        if len(self.organisms) >= self.max_organisms:
            return False
        species_cap = int(self.max_organisms * config.SPECIES_CAP_FRACTION)
        species_count = sum(1 for o in self.organisms if not o.is_dead and o.name == organism.name)
        if species_count + 1 > species_cap:
            return False
        if organism.uid is None:
            organism.uid = self._next_organism_uid
            self._next_organism_uid += 1
        self.organisms.append(organism)
        self.spatial_grid.add(organism)
        if self.run_logger is not None:
            self.run_logger.log_organism(organism)
        return True

    def remove_organism(self, organism: Organism) -> None:
        if organism in self.organisms:
            self.organisms.remove(organism)
            self.spatial_grid.remove(organism)

    def local_density(self, pos: tuple[float, float], radius: float, exclude: tuple[Organism, ...] = ()) -> int:
        """Count living organisms (other than those in ``exclude``) within ``radius`` of ``pos``."""
        return self.spatial_grid.local_density(pos, radius, exclude)

    def _rebuild_spatial_grid(self) -> None:
        """Bucket all living organisms into the spatial grid for fast queries."""
        self.spatial_grid.rebuild(self.organisms)

    def organisms_near(self, position: tuple[float, float], radius: float, exclude: tuple[Organism, ...] = ()):
        """Return living organisms within ``radius`` of ``position``."""
        return self.spatial_grid.near(position, radius, exclude)

    def spawn_organism(self, dna: DNA, pos: tuple[float, float], record_birth: bool = False) -> Organism | None:
        """Create, place and add a single organism, returning it on success."""
        organism = Organism(dna, pos)
        organism.position = self.tile_map.push_out_of_walls(organism.position, organism.radius)
        if self.add_organism(organism):
            if record_birth:
                self.record_birth(organism)
            return organism
        return None

    def spawn_organisms(self, count: int) -> None:
        for _ in range(count):
            dna = DNA.random()
            is_amphibious = any(g.kind == "amphibious" for g in dna.genes)
            pos = self.random_empty_position(in_water=is_amphibious)
            self.spawn_organism(dna, pos)

    def spawn_child_from_dna(
        self, dna: DNA, position: tuple[float, float], parent: Organism | None = None
    ) -> Organism | None:
        """Create an organism from DNA, place it and record the birth if successful.

        If ``parent`` is given, the child's generation is set to
        ``parent.generation + 1``; otherwise it defaults to ``1``.
        """
        generation = parent.generation + 1 if parent is not None else 1
        organism = Organism(dna, position, generation=generation)
        if parent is not None and parent.uid is not None:
            organism.parent_uids = (parent.uid,)
        organism.position = self.tile_map.push_out_of_walls(organism.position, organism.radius)
        if self.add_organism(organism):
            self.record_birth(organism)
            return organism
        return None

    def add_child(self, child: Organism) -> bool:
        """Push a child out of walls and try to add it to the world."""
        child.position = self.tile_map.push_out_of_walls(child.position, child.radius)
        return self.add_organism(child)

    def add_food(self, food: Food) -> None:
        self.food.append(food)

    def remove_food(self, food: Food) -> None:
        if food in self.food:
            self.food.remove(food)

    def spawn_food(self, count: int = 1, energy: float = 20.0, poison: bool = False) -> None:
        for _ in range(count):
            pos = self.random_empty_position()
            food = Food(position=pos, energy=energy, is_poison=poison)
            food.position = self.tile_map.push_out_of_walls(food.position, food.radius)
            self.add_food(food)

    # ------------------------------------------------------------------
    # Population management
    # ------------------------------------------------------------------
    def clear_population(self) -> None:
        """Remove all organisms and food, reset counters, keep the map."""
        self.organisms.clear()
        self.food.clear()
        self.spatial_grid.clear()
        self.births = 0
        self.births_by_species.clear()
        self.deaths = {}
        self.deaths_by_species.clear()
        self.tick = 0.0

    # ------------------------------------------------------------------
    # Physics and reproduction
    # ------------------------------------------------------------------
    def _resolve_collision(self, a: Organism, b: Organism) -> None:
        dx = b.position[0] - a.position[0]
        dy = b.position[1] - a.position[1]
        min_dist = a.radius + b.radius
        if dx * dx + dy * dy > min_dist * min_dist:
            return
        dist = math.hypot(dx, dy)
        if dist == 0:
            dx, dy = random.uniform(-1, 1), random.uniform(-1, 1)
            dist = math.hypot(dx, dy)
        if dist < min_dist:
            overlap = (a.radius + b.radius - dist) / 2
            nx = dx / dist
            ny = dy / dist
            ax, ay = a.position
            bx, by = b.position
            new_a = (ax - nx * overlap, ay - ny * overlap)
            new_b = (bx + nx * overlap, by + ny * overlap)

            a_safe = not self.tile_map.is_wall_circle(new_a, a.radius) and not self.tile_map.line_crosses_wall(
                a.position, new_a
            )
            b_safe = not self.tile_map.is_wall_circle(new_b, b.radius) and not self.tile_map.line_crosses_wall(
                b.position, new_b
            )

            if a_safe and b_safe:
                a.position = new_a
                b.position = new_b

                # Exchange some momentum
                avx, avy = a.velocity
                bvx, bvy = b.velocity
                a.velocity = (avx * 0.7 + bvx * 0.3, avy * 0.7 + bvy * 0.3)
                b.velocity = (bvx * 0.7 + avx * 0.3, bvy * 0.7 + avy * 0.3)
            elif a_safe:
                a.position = new_a
            elif b_safe:
                b.position = new_b

    def _try_mating(self, a: Organism, b: Organism) -> Organism | None:
        if a is b or a.is_dead or b.is_dead:
            return None
        if len(self.organisms) >= self.max_organisms:
            return None
        dx = a.position[0] - b.position[0]
        dy = a.position[1] - b.position[1]
        mate_dist = a.radius + b.radius + 4
        if dx * dx + dy * dy > mate_dist * mate_dist:
            return None
        dist = math.hypot(dx, dy)
        if dist < mate_dist:
            if a.can_mate() and b.can_mate():
                a_asexual = sum(1 for g in a.dna.genes if g.kind == "asexual")
                b_asexual = sum(1 for g in b.dna.genes if g.kind == "asexual")
                effective_mating_rate = config.MATING_RATE * (0.75 ** (a_asexual + b_asexual))
                if a.dna.diversity(b.dna) <= config.MATING_DIVERSITY and random.random() < effective_mating_rate:
                    # Block reproduction in dense clusters to avoid avalanche chains
                    cx = (a.position[0] + b.position[0]) / 2
                    cy = (a.position[1] + b.position[1]) / 2
                    if (
                        self.local_density((cx, cy), config.MATING_DENSITY_RADIUS, exclude=(a, b))
                        > config.MATING_DENSITY_LIMIT
                    ):
                        return None
                    # Small chance one parent dies instead of reproducing
                    if random.random() < config.MATING_DEATH_CHANCE:
                        random.choice([a, b]).die(self, cause="mating_failure")
                        return None
                    return a.mate(b)
        return None

    # ------------------------------------------------------------------
    # Main update loop
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Advance the world by one tick."""
        # Convert wall-clock dt to simulation ticks. This must use the same
        # time base as every other per-tick rate (config.TICKS_PER_SECOND),
        # not the rendering FPS, or the tick counter would drift away from
        # gene timers and energy drains whenever FPS is changed.
        self.tick += dt * config.TICKS_PER_SECOND

        # Update organisms. The spatial grid from the previous tick is used by
        # sensory genes, then we rebuild it for physics and mating.
        self._update_organisms(dt)
        self._remove_dead_organisms()
        self._rebuild_spatial_grid()
        self._resolve_and_mate_pairs()
        self._update_food(dt)
        self._spawn_food(dt)

    def _update_organisms(self, dt: float) -> None:
        for organism in list(self.organisms):
            organism.update(self, dt)

    def _remove_dead_organisms(self) -> None:
        # Single rebuild instead of a list.remove() per corpse, which scanned
        # the list twice (membership test + removal) for every death.
        living = [o for o in self.organisms if not o.is_dead]
        if len(living) == len(self.organisms):
            return
        for organism in self.organisms:
            if organism.is_dead:
                self.spatial_grid.remove(organism)
        self.organisms = living

    def _resolve_and_mate_pairs(self) -> None:
        """Resolve collisions and try mating for nearby organism pairs."""
        current = list(self.organisms)
        current_set = set(current)
        mate_query_extra = config.MAX_ORGANISM_RADIUS + 4
        for a in current:
            if a.is_dead:
                continue
            query_radius = a.radius + mate_query_extra
            for b in self.spatial_grid.near(a.position, query_radius, exclude=(a,)):
                if b not in current_set:
                    continue
                # Handle each unordered pair once. Both are in the world, so
                # their uids are assigned.
                if a.uid >= b.uid:
                    continue
                self._resolve_collision(a, b)
                child = self._try_mating(a, b)
                if child:
                    if self.add_child(child):
                        self.record_birth(child)

    def _update_food(self, dt: float) -> None:
        for food in self.food:
            food.update(dt)
        # One rebuild per tick beats a list.remove() per decayed item.
        self.food = [f for f in self.food if not f.is_gone]

    def _spawn_food(self, dt: float) -> None:
        self._food_spawn_accum += dt
        if self._food_spawn_accum > 1.0:
            self._food_spawn_accum -= 1.0
            if len(self.food) < config.FOOD_MAX_ITEMS and random.random() < config.FOOD_SPAWN_CHANCE:
                self.spawn_food(energy=random.uniform(25.0, config.ENERGY_GAIN_FROM_FOOD))

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def record_birth(self, organism: Organism) -> None:
        """Register a birth for global and per-species statistics."""
        self.births += 1
        species = organism.name
        self.births_by_species[species] = self.births_by_species.get(species, 0) + 1

    def register_death(self, cause: str, species: str = "") -> None:
        self.deaths[cause] = self.deaths.get(cause, 0) + 1
        if species:
            self.deaths_by_species[species] = self.deaths_by_species.get(species, 0) + 1

    def stats(self) -> dict[str, Any]:
        organisms = [o for o in self.organisms if not o.is_dead]
        total = len(organisms)
        max_generation = max((o.generation for o in organisms), default=0)
        min_generation = min((o.generation for o in organisms), default=0)
        return {
            "organisms": total,
            "food": len(self.food),
            "births": self.births,
            "walls": sum(row.count(self.TILE_WALL) for row in self.tiles),
            "hazards": sum(row.count(self.TILE_RADIOACTIVE) + row.count(self.TILE_LAVA) for row in self.tiles),
            "tick": int(self.tick),
            "max_generation": max_generation,
            "min_generation": min_generation,
            # Nested rather than merged into the top level: death causes are
            # arbitrary strings and used to be flattened into this dict, where
            # a cause named e.g. "food" or "births" would overwrite a real stat.
            "deaths": dict(self.deaths),
            "deaths_total": sum(self.deaths.values()),
        }
