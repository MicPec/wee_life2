"""Organism and body part classes."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import config
from .dna import DNA
from .food import Food
from .geometry import angle_diff

if TYPE_CHECKING:
    from ..genes.base import BodyPartBlueprint
    from .world import World


@dataclass
class PerceptionEvent:
    """A short-lived sensory observation produced by one or more genes.

    `MemoryGene` consumes these events at the end of the perception pipeline
    each tick and turns them into longer-lived `MemoryEntry` records.
    """

    position: tuple[float, float]
    tile_type: int
    source: str
    tick: float


@dataclass
class MemoryEntry:
    """A remembered world location and the kind of tile that was observed there."""

    position: tuple[float, float]
    tile_type: int
    created_tick: float


@dataclass
class BodyPart:
    """One rendered / functional segment of an organism."""

    blueprint: BodyPartBlueprint
    parent: "Organism"

    @property
    def world_position(self) -> tuple[float, float]:
        ox, oy = self.blueprint.offset
        x = ox * math.cos(self.parent.angle) - oy * math.sin(self.parent.angle)
        y = ox * math.sin(self.parent.angle) + oy * math.cos(self.parent.angle)
        return (self.parent.position[0] + x, self.parent.position[1] + y)

    @property
    def world_angle(self) -> float:
        return self.parent.angle + self.blueprint.angle


class Organism:
    """A living unit on the board."""

    def __init__(self, dna: DNA, position: tuple[float, float] | None = None) -> None:
        self.dna = dna
        self.position: tuple[float, float] = position or (0.0, 0.0)
        self.velocity: tuple[float, float] = (0.0, 0.0)
        self.angle: float = random.uniform(-math.pi, math.pi)
        self.energy: float = config.BASE_ENERGY
        self.max_energy: float = config.BASE_ENERGY * 1.5
        self.age: float = 0.0
        self.base_lifespan: float = config.LIFESPAN_BASE
        self.lifespan: float = config.LIFESPAN_BASE
        self.is_dead: bool = False
        self.energy_to_mate: float = config.ENERGY_TO_MATE

        # Aggregate behaviour state; genes write into these each tick
        self.aggression: float = 0.0
        self.armor_value: float = 0.0
        self.toxin_resistance: float = 0.0
        self.radiation_resistance: float = 0.0
        self.amphibious: bool = False
        self.has_metabolism: bool = False
        self.bioluminescence: float = 0.0
        self.pheromone_strength: float = 0.0
        self.alarm_level: float = 0.0
        self.seen_target: str | None = None
        self.wander_angle: float = self.angle
        self.wander_timer: float = 0.0
        self.drives: list[tuple[float, float]] = []  # (angle_delta, weight)
        self.venom_stacks: list[dict] = []  # active DoT effects from venom genes

        # Perception / memory state
        self.perception_events: list[PerceptionEvent] = []
        self.memory: list[MemoryEntry] = []

        self.body_parts: list[BodyPart] = []
        self._stuck_timer: float = 0.0
        self._last_position: tuple[float, float] = self.position
        self._nearby_organisms: list[Organism] | None = None
        self._nearby_range: float = 0.0
        self._build_body()
        self._compute_base_traits()
        self.name = self.dna.name()

    def _compute_base_traits(self) -> None:
        """Set baseline traits derived from the genome before gene updates."""
        hunger = 1.0 - min(1.0, self.energy / self.max_energy)

        self.aggression = min(1.0, 0.02 * self._jaw_count + 0.03 * self._spike_count + 0.2 * hunger)
        self.amphibious = self._has_amphibious
        self.has_metabolism = self._has_metabolism

    def _build_body(self) -> None:
        """Assemble body parts from the genome, using color genes as base colour."""
        from ..genes.base import random_color

        base_color = random_color()
        color_gene = next((g for g in self.dna.genes if g.kind == "color"), None)
        if color_gene:
            from ..genes.base import hsv_to_rgb

            base_color = hsv_to_rgb(
                color_gene.params["hue"],
                color_gene.params["saturation"],
                color_gene.params["value"],
            )

        self.body_parts.clear()
        for gene in self.dna.genes:
            for bp in gene.body_parts(base_color):
                self.body_parts.append(BodyPart(bp, self))

        if not any(bp.blueprint.kind == "body" for bp in self.body_parts):
            # Fallback body disc if no color gene produced one.
            from ..genes.base import BodyPartBlueprint

            self.body_parts.append(BodyPart(BodyPartBlueprint(kind="body", size=5.0, color=base_color), self))

        # Make sure the body is always visible, even after heavy scaling.
        for bp in self.body_parts:
            if bp.blueprint.kind == "body":
                bp.blueprint.size = max(bp.blueprint.size, 5.0)

        natural_radius = max(
            math.hypot(bp.blueprint.offset[0], bp.blueprint.offset[1]) + bp.blueprint.size for bp in self.body_parts
        )

        # Sort body parts by size so that larger parts are drawn first.
        self.body_parts.sort(key=lambda p: p.blueprint.size, reverse=True)

        # Cache immutable genome-derived traits used every tick.
        self._jaw_count = sum(1 for g in self.dna.genes if g.kind == "jaw")
        self._spike_count = sum(1 for g in self.dna.genes if g.kind == "spike")
        self._has_amphibious = any(g.kind == "amphibious" for g in self.dna.genes)
        self._has_metabolism = any(g.kind == "metabolism" for g in self.dna.genes)

        # Genome length (and thus body part count/offsets) can grow unbounded
        # over many generations via structural mutation. Uniformly shrink
        # oversized organisms so they never exceed MAX_ORGANISM_RADIUS.
        # A MAX_ORGANISM_RADIUS of 0 or less disables the limit.
        if config.MAX_ORGANISM_RADIUS > 0 and natural_radius > config.MAX_ORGANISM_RADIUS:
            scale = config.MAX_ORGANISM_RADIUS / natural_radius
            for bp in self.body_parts:
                ox, oy = bp.blueprint.offset
                bp.blueprint.offset = (ox * scale, oy * scale)
                bp.blueprint.size *= scale
            self.radius = config.MAX_ORGANISM_RADIUS
        else:
            self.radius = natural_radius

    def add_drive(self, angle_delta: float, weight: float, target_kind: str | None = None) -> None:
        """Add a steering intention. Positive weight turns toward, negative turns away."""
        self.drives.append((angle_delta, weight))
        if target_kind is not None and self.seen_target is None:
            self.seen_target = target_kind

    def add_perception(self, position: tuple[float, float], tile_type: int, source: str, tick: float) -> None:
        """Record a sensory observation for `MemoryGene` to consume this tick."""
        self.perception_events.append(PerceptionEvent(position, tile_type, source, tick))

    def remember(self, position: tuple[float, float], tile_type: int, current_tick: float, merge_radius: float) -> None:
        """Add a new memory entry or refresh an existing one near the same position."""
        px, py = position
        for entry in self.memory:
            if entry.tile_type != tile_type:
                continue
            ex, ey = entry.position
            if (px - ex) * (px - ex) + (py - ey) * (py - ey) <= merge_radius * merge_radius:
                entry.created_tick = current_tick
                return
        self.memory.append(MemoryEntry(position, tile_type, current_tick))

    def prune_memory(self, current_tick: float, retention: float, capacity: int) -> None:
        """Forget old entries and trim to capacity, keeping the most recent ones."""
        self.memory = [e for e in self.memory if current_tick - e.created_tick < retention]
        if len(self.memory) > capacity:
            self.memory.sort(key=lambda e: e.created_tick)
            self.memory = self.memory[-capacity:]

    def combined_drive(self) -> float:
        """Merge all drives into a single steering delta."""
        if not self.drives:
            return 0.0
        x = y = 0.0
        for angle, weight in self.drives:
            x += math.cos(self.angle + angle) * weight
            y += math.sin(self.angle + angle) * weight
        if x == 0 and y == 0:
            return 0.0
        desired = math.atan2(y, x)
        return angle_diff(desired, self.angle)

    def accelerate(self, ax: float, ay: float) -> None:
        vx, vy = self.velocity
        self.velocity = (vx + ax, vy + ay)

    def steer(self, delta: float) -> None:
        self.angle += delta * config.TURN_RATE

    # ------------------------------------------------------------------
    # Main update pipeline
    # ------------------------------------------------------------------
    def update(self, world: World, dt: float) -> None:
        if self.is_dead:
            return

        self._reset_tick_state()
        self._run_genes(world, dt)
        self._clamp_aggregate_traits()
        if self.is_dead:
            return

        self._process_venom(world, dt)
        if self.is_dead:
            return

        self._apply_physics_and_movement(world, dt)
        self._apply_hazards_and_water(world, dt)
        self._handle_contact_food(world)
        self._check_vitals(world)

    def _reset_tick_state(self) -> None:
        """Reset per-tick aggregate traits and recompute base traits."""
        self.seen_target = None
        self.drives.clear()
        self.perception_events.clear()
        self.pheromone_strength = 0.0
        self.radiation_resistance = 0.0
        self.armor_value = 0.0
        self.toxin_resistance = 0.0
        self.alarm_level = 0.0
        self.amphibious = False
        self.has_metabolism = False
        self.bioluminescence = 0.0
        self.lifespan = self.base_lifespan
        self._compute_base_traits()
        self._nearby_organisms = None
        self._nearby_range = 0.0

    def nearby_organisms(self, world: World, radius: float) -> list[Organism]:
        """Return nearby organisms for the current tick, caching the result."""
        if self._nearby_organisms is None or radius > self._nearby_range:
            self._nearby_organisms = world.organisms_near(self.position, radius, exclude=(self,))
            self._nearby_range = radius
        return self._nearby_organisms

    def _run_genes(self, world: World, dt: float) -> None:
        """Run each gene. Locomotion (leg) is last so it can see all drives."""
        other_genes = [g for g in self.dna.genes if g.kind != "leg"]
        leg_genes = [g for g in self.dna.genes if g.kind == "leg"]
        for gene in other_genes:
            gene.apply(self, world, dt)
        for gene in leg_genes:
            gene.apply(self, world, dt)

    def _clamp_aggregate_traits(self) -> None:
        self.aggression = max(0.0, min(1.0, self.aggression))
        self.armor_value = max(0.0, self.armor_value)
        self.toxin_resistance = max(0.0, min(1.0, self.toxin_resistance))
        self.radiation_resistance = max(0.0, min(1.0, self.radiation_resistance))
        self.alarm_level = max(0.0, min(1.0, self.alarm_level))
        self.pheromone_strength = max(0.0, min(1.0, self.pheromone_strength))
        self.bioluminescence = max(0.0, min(1.0, self.bioluminescence))

    def _process_venom(self, world: World, dt: float) -> None:
        """Process active venom stacks (damage over time from venom genes)."""
        for stack in list(self.venom_stacks):
            stack["remaining"] -= dt * 60.0
            if stack["remaining"] <= 0:
                self.venom_stacks.remove(stack)
                continue
            self.energy -= stack["damage_per_tick"]
            if self.energy <= 0 and not self.is_dead:
                self.die(world, cause="venom")
                return

    def _apply_physics_and_movement(self, world: World, dt: float) -> None:
        """Clamp speed, apply friction, move, handle bounds and wall bounce."""
        vx, vy = self.velocity
        speed = math.hypot(vx, vy)

        # Water is the home of amphibious organisms; on land they move slowly.
        # Non-amphibious organisms are slow in water. This has to clamp velocity
        # directly, otherwise the leg gene's full-strength thrust re-added next
        # tick would immediately undo the penalty.
        max_speed = config.MAX_SPEED

        # Older organisms slow down so they don't block younger, faster ones.
        age_fraction = self.age / self.lifespan
        if age_fraction > config.AGE_SLOWDOWN_START:
            span = 1.0 - config.AGE_SLOWDOWN_START
            t = (age_fraction - config.AGE_SLOWDOWN_START) / span if span > 0 else 1.0
            max_speed *= 1.0 - (1.0 - config.AGE_SLOWDOWN_END_SPEED) * t

        tile = world.tile_at(self.position)
        if (self.amphibious and tile != world.TILE_WATER) or (not self.amphibious and tile == world.TILE_WATER):
            max_speed *= config.WATER_SPEED_PENALTY

        if speed > max_speed:
            scale = max_speed / speed
            vx *= scale
            vy *= scale

        # Friction
        vx *= config.FRICTION
        vy *= config.FRICTION
        self.velocity = (vx, vy)

        # Move
        x = self.position[0] + vx * dt * 60.0
        y = self.position[1] + vy * dt * 60.0

        # World bounds
        if x < self.radius:
            x = self.radius
            vx = -vx * 0.5
        if x > world.width - self.radius:
            x = world.width - self.radius
            vx = -vx * 0.5
        if y < self.radius:
            y = self.radius
            vy = -vy * 0.5
        if y > world.height - self.radius:
            y = world.height - self.radius
            vy = -vy * 0.5

        # Wall collision: simple bounce with a random turn
        if world.is_wall_circle((x, y), self.radius) or world._line_intersects_wall(self.position, (x, y)):
            x, y = self.position
            vx = -vx * 0.4
            vy = -vy * 0.4
            # Turn away from the wall
            self.angle += random.choice([-1, 1]) * random.uniform(0.4, 1.2)
            self.wander_angle = self.angle

        self.position = (x, y)
        self.velocity = (vx, vy)

        # If somehow inside a wall, push out
        if world.is_wall_circle(self.position, self.radius):
            self.position = world.push_out_of_walls(self.position, self.radius)
            self._stuck_timer = 0.0
            self._last_position = self.position

        # Detect total stop (dead-end / congestion)
        moved = math.hypot(
            self.position[0] - self._last_position[0],
            self.position[1] - self._last_position[1],
        )
        if moved < 0.5:
            self._stuck_timer += dt * 60.0
        else:
            self._stuck_timer = 0.0
        self._last_position = self.position

        if self._stuck_timer > 60.0:
            self.position = world.push_out_of_walls(self.position, self.radius)
            self.angle = random.uniform(-math.pi, math.pi)
            self.wander_angle = self.angle
            self.velocity = (
                math.cos(self.angle) * config.MAX_SPEED * 0.5,
                math.sin(self.angle) * config.MAX_SPEED * 0.5,
            )
            self._stuck_timer = 0.0

    def _apply_hazards_and_water(self, world: World, dt: float) -> None:
        """Base metabolism / ageing and environmental hazard tiles."""
        self.energy -= config.ENERGY_COST_STAY * dt * 60.0
        self.age += dt * 60.0

        tile = world.tile_at(self.position)
        if tile == world.TILE_RADIOACTIVE:
            self.energy -= config.RADIATION_DAMAGE * (1.0 - self.radiation_resistance) * dt * 60.0
        elif tile == world.TILE_LAVA:
            self.energy -= config.LAVA_DAMAGE * (1.0 - self.radiation_resistance) * dt * 60.0
        elif tile == world.TILE_WATER and not self.amphibious:
            self.energy -= config.WATER_DROWN_DAMAGE * dt * 60.0
        elif tile != world.TILE_WATER and self.amphibious:
            self.energy -= config.AMPHIBIOUS_LAND_DRAIN * dt * 60.0
        elif tile == world.TILE_HEAL:
            self.energy = min(self.energy + config.HEAL_ENERGY * dt * 60.0, self.max_energy)

    def _handle_contact_food(self, world: World) -> None:
        """Default contact eating for organisms without a jaw."""
        if any(g.kind == "jaw" for g in self.dna.genes):
            return

        for food in list(world.food):
            dx = food.position[0] - self.position[0]
            dy = food.position[1] - self.position[1]
            if math.hypot(dx, dy) < self.radius + food.radius:
                gain = food.energy * 0.5
                if food.is_poison:
                    damage = gain * (1.0 - self.toxin_resistance)
                    self.energy -= damage
                else:
                    self.energy += gain
                world.remove_food(food)
                self.energy = min(self.energy, self.max_energy)
                break

    def _check_vitals(self, world: World) -> None:
        """Lifespan and starvation checks."""
        if self.age > self.lifespan:
            self.die(world, cause="age")
            return

        if self.energy <= 0 and not self.is_dead:
            self.die(world, cause="starvation")

    def die(self, world: World, cause: str = "unknown") -> None:
        if self.is_dead:
            return
        self.is_dead = True
        world.register_death(cause, self.name)

        if random.random() < config.FOOD_ON_DEATH_CHANCE:
            food_pos = world.push_out_of_walls(self.position, self.radius * 0.6)
            world.add_food(
                Food(
                    position=food_pos,
                    energy=max(10.0, self.energy * 0.5 + 20.0),
                    radius=self.radius * 0.6,
                    is_poison=self.toxin_resistance < 0.2 and any(g.kind == "toxin_gland" for g in self.dna.genes),
                )
            )

    @property
    def maturity_min_age(self) -> float:
        return self.lifespan * config.MATURITY_MIN_FRACTION

    @property
    def maturity_max_age(self) -> float:
        return self.lifespan * config.MATURITY_MAX_FRACTION

    @property
    def visual_scale(self) -> float:
        """Rendering-only scale: grows linearly from BABY_SIZE_FRACTION to 1.0.

        Growth is anchored to base_lifespan so changes to lifespan later in
        life (e.g. from metabolism genes) do not shrink an already-mature
        organism.
        """
        target_age = self.base_lifespan * config.MATURITY_MIN_FRACTION
        if target_age <= 0 or self.age >= target_age:
            return 1.0
        fraction = self.age / target_age
        return config.BABY_SIZE_FRACTION + (1.0 - config.BABY_SIZE_FRACTION) * fraction

    def is_of_mating_age(self) -> bool:
        return self.maturity_min_age < self.age < self.maturity_max_age

    def can_mate(self) -> bool:
        return self.is_of_mating_age() and self.energy > self.energy_to_mate

    def mate(self, partner: "Organism") -> "Organism" | None:
        if not (self.can_mate() and partner.can_mate()):
            return None
        child_dna = self.dna.crossover(partner.dna)
        child_dna.mutate(config.MUTATION_RATE, config.MUTATION_STRENGTH)

        # Position near parents
        x = (self.position[0] + partner.position[0]) / 2
        y = (self.position[1] + partner.position[1]) / 2
        child = Organism(child_dna, (x, y))

        # Reproduction costs
        self.energy -= config.ENERGY_COST_MATE
        partner.energy -= config.ENERGY_COST_MATE

        return child

    def __repr__(self) -> str:
        return f"Organism(age={self.age:.0f}, energy={self.energy:.1f}, dna={self.dna})"
