"""Memory gene: records interesting tile locations and steers toward/away from them."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..core import config
from .base import BodyPartBlueprint, Gene, hsv_to_rgb
from .geometry import angle_diff, angle_to
from .sensing import fan_ray_angles

if TYPE_CHECKING:
    from ..core.organism import Organism
    from ..core.world import World


class MemoryGene(Gene):
    """A memory core that turns sensory observations into long-term navigation hints.

    It consumes short-lived ``PerceptionEvent`` objects produced by ``eye``,
    ``scent`` and ``touch``, remembers tile positions for a limited time, and
    emits steering drives toward or away from those locations.
    """

    kind = "memory"
    default_params = {
        "capacity": 5.0,
        "retention": 600.0,
        "perception_range": 120.0,
        "recall_range": 140.0,
        "ray_count": 3.0,
        "water_weight": 0.25,
        "hazard_weight": -0.7,
        "wall_weight": -0.4,
        "heal_weight": 0.5,
        "heal_threshold": 0.7,
        "size": 4.0,
        "side": 0.5,  # 0-1, body side the organ sits on (thresholded at 0.5)
    }
    param_bounds = {
        "side": (0.0, 1.0),
    }

    def body_parts(self, base_color):
        size = self.params["size"]
        return [
            BodyPartBlueprint(
                kind="memory",
                offset=(self.side * 5, -6),
                size=size,
                color=hsv_to_rgb(0.8, 0.5, 0.95),
                params={},
            )
        ]

    def apply(self, organism: Organism, world: World, dt: float) -> None:
        # Memory is a shared system.  If an organism has multiple memory genes,
        # only the first one runs the logic, but it aggregates parameters from
        # all of them so that more memory genes mean a stronger memory.
        memory_genes = [g for g in organism.dna.genes if isinstance(g, MemoryGene)]
        if not memory_genes or memory_genes[0] is not self:
            return

        pos = organism.position
        current_tick = world.tick
        tile_size = world.tile_size
        merge_radius = tile_size * 0.6

        interesting = {world.TILE_WATER, world.TILE_RADIOACTIVE, world.TILE_LAVA, world.TILE_WALL}
        heal_tile = getattr(config, "TILE_HEAL", None)
        if heal_tile is not None:
            interesting.add(heal_tile)

        # Aggregate parameters across all memory genes on this organism.
        capacity = int(sum(g.params["capacity"] for g in memory_genes))
        retention = max(g.params["retention"] for g in memory_genes)
        perception_range = max(g.params["perception_range"] for g in memory_genes)
        recall_range = max(g.params["recall_range"] for g in memory_genes)
        ray_count = int(sum(g.params["ray_count"] for g in memory_genes))

        # 1. Consume perception events from other senses.
        # Only remember events within the organism's perception range; events
        # from eye/scent can be much farther away and would fill memory with
        # distant, irrelevant borders.
        for event in organism.perception_events:
            if event.tile_type not in interesting:
                continue
            dx = event.position[0] - pos[0]
            dy = event.position[1] - pos[1]
            if math.hypot(dx, dy) <= perception_range:
                organism.remember(event.position, event.tile_type, current_tick, merge_radius)

        # 2. Remember the tile currently under our feet.
        tile_here = world.tile_at(pos)
        if tile_here in interesting:
            col = int(pos[0] / tile_size)
            row = int(pos[1] / tile_size)
            centre = ((col + 0.5) * tile_size, (row + 0.5) * tile_size)
            organism.remember(centre, tile_here, current_tick, merge_radius)

        # 3. Fallback self-scan if no sensory events were produced this tick.
        # Scan a forward fan rather than 360° so memory does not keep filling up
        # with walls already behind the organism.
        if ray_count > 0 and not organism.perception_events:
            fov = math.pi * 0.8  # ~144°
            for angle in fan_ray_angles(organism.angle, fov, ray_count):
                hit = world.tile_map.first_interesting_tile_along_ray(pos, angle, perception_range)
                if hit is not None:
                    hit_pos, tile_type = hit
                    if tile_type in interesting:
                        organism.remember(hit_pos, tile_type, current_tick, merge_radius)

        # 4. Validate, decay and enforce capacity limits.
        organism.prune_memory(current_tick, retention, capacity)

        # Optionally drop entries whose tile has changed since we memorised it.
        # This is done every few ticks to keep the cost low.
        if int(current_tick) % 10 == 0:
            organism.memory = [e for e in organism.memory if world.tile_at(e.position) == e.tile_type]

        # 5. Recall remembered locations and emit steering drives.
        # Aggregate all remembered tiles into a single vector, just like eye/scent
        # do for terrain.  Multiple remembered walls/hazards on different sides
        # otherwise fight each other and make the organism spin in place.
        recall_range_inv = 1.0 / recall_range if recall_range > 0 else 0.0
        water_weight = sum(g.params["water_weight"] for g in memory_genes)
        hazard_weight = sum(g.params["hazard_weight"] for g in memory_genes)
        wall_weight = sum(g.params["wall_weight"] for g in memory_genes)
        heal_weight = sum(g.params["heal_weight"] for g in memory_genes)
        heal_threshold = sum(g.params["heal_threshold"] for g in memory_genes) / len(memory_genes)
        health_fraction = organism.energy / organism.max_energy
        angle = organism.angle
        is_amphibious = organism.amphibious

        total_x = 0.0
        total_y = 0.0
        for entry in organism.memory:
            dx = entry.position[0] - pos[0]
            dy = entry.position[1] - pos[1]
            dist = math.hypot(dx, dy)
            if dist > recall_range or dist < 1.0:
                continue
            strength = (1.0 - dist * recall_range_inv) ** 2

            # Ignore memories that are far behind the organism; they would
            # otherwise keep pulling it backwards and create chaotic turns.
            to_angle = angle_to(pos, entry.position)
            rel_angle = angle_diff(to_angle, angle)
            if abs(rel_angle) > math.pi * 0.7:
                continue

            tile_type = entry.tile_type
            if tile_type == world.TILE_WATER:
                # Don't steer toward remembered water that is now behind a wall;
                # that just pins the organism against the obstacle.
                if world.line_crosses_wall(pos, entry.position):
                    continue
                weight = water_weight * (1.0 if is_amphibious else -1.0) * strength
                target_angle = to_angle
            elif tile_type in (world.TILE_RADIOACTIVE, world.TILE_LAVA):
                if world.line_crosses_wall(pos, entry.position):
                    continue
                # Close hazards are handled by touch; memory steers from a distance.
                if dist < organism.radius * 3.0:
                    continue
                # `hazard_weight` is negative, which already reverses the
                # vector; reversing `to_angle` as well would steer *into*
                # the hazard (same convention as the water branch above).
                weight = hazard_weight * strength
                target_angle = to_angle
            elif tile_type == world.TILE_WALL:
                # Walls that are already within whisker range are handled by touch/eye/scent.
                # Memory handles walls that were seen earlier and may now be out of direct sense.
                if dist < organism.radius * 3.0:
                    continue
                # Negative `wall_weight` reverses the vector; see above.
                weight = wall_weight * strength
                target_angle = to_angle
            elif heal_tile is not None and tile_type == heal_tile:
                if health_fraction >= heal_threshold:
                    continue
                if world.line_crosses_wall(pos, entry.position):
                    continue
                weight = heal_weight * strength
                target_angle = to_angle
            else:
                continue

            total_x += math.cos(target_angle) * weight
            total_y += math.sin(target_angle) * weight

        if total_x != 0.0 or total_y != 0.0:
            target_angle = math.atan2(total_y, total_x)
            drive = angle_diff(target_angle, angle)
            # Keep memory as a hint rather than the dominant drive.
            weight = min(0.6, math.hypot(total_x, total_y))
            organism.add_drive(drive, weight, "memory")
