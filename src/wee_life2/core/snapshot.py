"""Restorable world snapshots: the single schema for saving and loading a run.

`world_to_dict` serialises the complete state of a `World` (tiles, counters,
food and every living organism) into a plain dict for `json.dump`;
`world_from_dict` restores it in place into a same-geometry world. The schema
is versioned so the loader can reject snapshots it does not understand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .dna import DNA
from .food import Food
from .organism import MemoryEntry, Organism, VenomStack

if TYPE_CHECKING:
    from .world import World

SNAPSHOT_VERSION = 1


def _r(value: float) -> float:
    return round(value, 4)


def world_to_dict(world: World) -> dict[str, Any]:
    """Serialise the full restorable state of ``world``."""
    return {
        "version": SNAPSHOT_VERSION,
        "tick": _r(world.tick),
        "world": {
            "width": _r(world.width),
            "height": _r(world.height),
            "tile_size": _r(world.tile_size),
            "tiles": world.save_tiles(),
            "births": world.births,
            "deaths": dict(world.deaths),
            "births_by_species": dict(world.births_by_species),
            "deaths_by_species": dict(world.deaths_by_species),
            "next_organism_uid": world._next_organism_uid,
            "food_spawn_accum": _r(world._food_spawn_accum),
        },
        "food": [
            {
                "x": _r(f.position[0]),
                "y": _r(f.position[1]),
                "energy": _r(f.energy),
                "radius": _r(f.radius),
                "is_poison": f.is_poison,
                "age": _r(f.age),
                "decay_time": _r(f.decay_time),
            }
            for f in world.food
        ],
        "organisms": [_organism_to_dict(o) for o in world.organisms if not o.is_dead],
    }


def _organism_to_dict(o: Organism) -> dict[str, Any]:
    # `name` and `radius` are derived from the DNA by `Organism._build_body`;
    # they are written for offline analysis and ignored on load.
    return {
        "uid": o.uid,
        "name": o.name,
        "generation": o.generation,
        "parents": list(o.parent_uids),
        "dna": o.dna.to_dict(),
        "x": _r(o.position[0]),
        "y": _r(o.position[1]),
        "vx": _r(o.velocity[0]),
        "vy": _r(o.velocity[1]),
        "angle": _r(o.angle),
        "wander_angle": _r(o.wander_angle),
        "wander_timer": _r(o.wander_timer),
        "energy": _r(o.energy),
        "max_energy": _r(o.max_energy),
        "fat_reserve": _r(o.fat_reserve),
        "fat_capacity": _r(o.fat_capacity),
        "age": _r(o.age),
        "base_lifespan": _r(o.base_lifespan),
        "energy_to_mate": _r(o.energy_to_mate),
        "stuck_timer": _r(o._stuck_timer),
        "radius": _r(o.radius),
        "venom": [
            {"damage_per_tick": _r(s.damage_per_tick), "remaining": _r(s.remaining)} for s in o.venom_stacks
        ],
        "memory": [
            {"x": _r(m.position[0]), "y": _r(m.position[1]), "tile_type": m.tile_type, "created_tick": _r(m.created_tick)}
            for m in o.memory
        ],
    }


def world_from_dict(world: World, data: dict[str, Any]) -> None:
    """Restore snapshot ``data`` into ``world`` in place.

    Raises ``ValueError`` on an unknown schema version or a world-geometry
    mismatch -- restoring into a differently-sized board would corrupt
    positions.
    """
    if data.get("version") != SNAPSHOT_VERSION:
        raise ValueError(f"unsupported snapshot version {data.get('version')!r} (expected {SNAPSHOT_VERSION})")
    w = data["world"]
    if (w["width"], w["height"], w["tile_size"]) != (world.width, world.height, world.tile_size):
        raise ValueError(
            f"snapshot world geometry {w['width']}x{w['height']} tile {w['tile_size']} "
            f"does not match this world {world.width}x{world.height} tile {world.tile_size}"
        )

    world.clear_population()
    world.load_tiles(w["tiles"])
    world.tick = data["tick"]
    world.births = w["births"]
    world.deaths = dict(w["deaths"])
    world.births_by_species = dict(w["births_by_species"])
    world.deaths_by_species = dict(w["deaths_by_species"])
    world._next_organism_uid = w["next_organism_uid"]
    world._food_spawn_accum = w["food_spawn_accum"]

    for rec in data["food"]:
        world.food.append(
            Food(
                position=(rec["x"], rec["y"]),
                energy=rec["energy"],
                radius=rec["radius"],
                is_poison=rec["is_poison"],
                age=rec["age"],
                decay_time=rec["decay_time"],
            )
        )

    for rec in data["organisms"]:
        # Deliberately not World.add_organism: it enforces population/species
        # caps, assigns a fresh uid and would write a phantom `log_organism`
        # record for a restored creature.
        organism = Organism(DNA.from_dict(rec["dna"]), (rec["x"], rec["y"]), generation=rec["generation"])
        organism.uid = rec["uid"]
        organism.parent_uids = tuple(rec["parents"])
        organism.velocity = (rec["vx"], rec["vy"])
        organism.angle = rec["angle"]
        organism.wander_angle = rec["wander_angle"]
        organism.wander_timer = rec["wander_timer"]
        organism.energy = rec["energy"]
        organism.max_energy = rec["max_energy"]
        organism.fat_reserve = rec["fat_reserve"]
        organism.fat_capacity = rec["fat_capacity"]
        organism.age = rec["age"]
        organism.base_lifespan = rec["base_lifespan"]
        organism.energy_to_mate = rec["energy_to_mate"]
        organism._stuck_timer = rec["stuck_timer"]
        organism._last_position = organism.position
        organism.venom_stacks = [
            VenomStack(damage_per_tick=s["damage_per_tick"], remaining=s["remaining"]) for s in rec["venom"]
        ]
        organism.memory = [
            MemoryEntry(position=(m["x"], m["y"]), tile_type=m["tile_type"], created_tick=m["created_tick"])
            for m in rec["memory"]
        ]
        world.organisms.append(organism)

    world._rebuild_spatial_grid()
