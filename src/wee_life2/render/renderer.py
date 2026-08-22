"""Pygame rendering for the simulation."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pygame

from ..core import config
from .actions import (
    Action,
    ClearAction,
    RandomizeAction,
    RemoveAction,
    ResetAction,
    SaveAction,
    SpawnAction,
    SpawnRandomAction,
)
from .body_drawing import BODY_DRAWERS, DrawContext, draw_generic
from .legend_drawing import draw_legend_icon
from .tile_drawing import (
    ANIMATED_TILES,
    draw_grid,
    draw_tile_highlight,
    draw_tiles,
    tile_color,
)

if TYPE_CHECKING:
    from ..core.world import World


class Renderer:
    """Draws the world using Pygame."""

    EDIT_TOOLS = {
        0: ("empty", config.TILE_EMPTY),
        1: ("wall", config.TILE_WALL),
        2: ("radioactive", config.TILE_RADIOACTIVE),
        3: ("lava", config.TILE_LAVA),
        4: ("water", config.TILE_WATER),
        5: ("heal", config.TILE_HEAL),
    }
    MAX_FRAME_DT = (
        1.0 / 20.0
    )  # hard cap on simulated seconds per frame; guards against lag-spike damage/movement bursts
    SPECIES_HIGHLIGHT_COLOR = (60, 220, 255)  # cyan; distinct from the yellow used for a single selected organism
    GENE_HIGHLIGHT_COLOR = (255, 140, 0)  # orange; distinct from species (cyan) and single-organism (yellow) highlights

    def __init__(
        self, width: int = config.WINDOW_WIDTH, height: int = config.WINDOW_HEIGHT, fps: int = config.FPS
    ) -> None:
        pygame.init()
        self.width = width
        self.height = height
        self.fps = fps
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Wee Life 2 - Artificial Life Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 14)
        self.small_font = pygame.font.SysFont("monospace", 12)
        self.running = True
        self.show_legend = False
        self.show_help = False
        self.show_species = True
        self.paused = False
        self.edit_mode = False
        self.edit_tool_index = 1
        self.drawing = False
        self.erasing = False
        self.hovered_species: str | None = None
        self.selected_organism: object | None = None
        self.selected_species: str | None = None
        self.selected_gene: str | None = None
        self._species_top5: list[tuple[str, int]] = []
        self._species_total: int = 0
        self._species_panel_rect: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._legend_panel_rect: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._eye_overlay: pygame.Surface | None = None
        self._eye_line_overlay: pygame.Surface | None = None
        self._map_surface: pygame.Surface | None = None
        self._animated_tile_rects: dict[int, list[pygame.Rect]] = {}
        self.confirming_reset = False

    def clear_map_cache(self) -> None:
        """Invalidate the cached static map background."""
        self._map_surface = None

    def clear_selections(self) -> None:
        """Clear selected organism, species and gene."""
        self.selected_organism = None
        self.selected_species = None
        self.selected_gene = None
        self.hovered_species = None

    def _select_tool(self, index: int) -> None:
        if index in self.EDIT_TOOLS:
            self.edit_tool_index = index

    def _edit_tool_tile(self) -> int:
        return self.EDIT_TOOLS[self.edit_tool_index][1]

    def _handle_key_event(self, event: pygame.event.Event, actions: list[Action]) -> None:
        """Handle a KEYDOWN event and optionally append an action."""
        if event.key == pygame.K_ESCAPE:
            if self.confirming_reset:
                self.confirming_reset = False
            elif self.edit_mode:
                self.edit_mode = False
                self.paused = False
                self.drawing = False
                self.erasing = False
            else:
                self.running = False
        elif event.key == pygame.K_l:
            if not self.edit_mode:
                self.show_legend = not self.show_legend
        elif event.key == pygame.K_h:
            self.show_help = not self.show_help
        elif event.key == pygame.K_g:
            config.GRAY_WITH_AGE = not config.GRAY_WITH_AGE
        elif event.key == pygame.K_t:
            self.show_species = not self.show_species
        elif event.key == pygame.K_SPACE:
            if not self.edit_mode:
                self.paused = not self.paused
        elif event.key == pygame.K_e:
            self.edit_mode = not self.edit_mode
            self.paused = self.edit_mode
            self.drawing = False
            self.erasing = False
            self.clear_map_cache()
            if self.edit_mode:
                self.show_legend = False
        elif self.edit_mode and event.key in (
            pygame.K_0,
            pygame.K_1,
            pygame.K_2,
            pygame.K_3,
            pygame.K_4,
            pygame.K_5,
        ):
            self._select_tool(event.key - pygame.K_0)
        elif self.edit_mode and event.key == pygame.K_s:
            actions.append(SaveAction())
        elif self.edit_mode and event.key == pygame.K_c:
            actions.append(ClearAction())
        elif self.edit_mode and event.key == pygame.K_r:
            actions.append(RandomizeAction())
        elif self.confirming_reset and event.key == pygame.K_y:
            actions.append(ResetAction())
            self.confirming_reset = False
        elif self.confirming_reset and event.key in (pygame.K_n, pygame.K_c):
            self.confirming_reset = False
        elif not self.edit_mode and event.key == pygame.K_r:
            actions.append(SpawnRandomAction())
        elif not self.edit_mode and event.key == pygame.K_c:
            self.confirming_reset = True
        elif event.key == pygame.K_p:
            self._save_screenshot()

    def _save_screenshot(self) -> None:
        """Save the current screen to a timestamped PNG in data/screenshots."""
        base = Path("data/screenshots")
        base.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"{datetime.now().microsecond:04x}"
        path = base / f"screenshot_{timestamp}_{suffix}.png"
        pygame.image.save(self.screen, str(path))
        print(f"Saved screenshot to {path}")

    def _handle_mouse_event(self, event: pygame.event.Event, world: World, actions: list[Action]) -> None:
        """Handle mouse button events for both edit and simulation modes."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.edit_mode:
                if event.button == 1:
                    self.drawing = True
                elif event.button == 3:
                    self.erasing = True
            else:
                clicked_gene = None
                if self.show_legend and event.button in (1, 3):
                    clicked_gene = self._legend_row_at(event.pos)
                clicked_species = None
                if clicked_gene is None and self.show_species and event.button in (1, 3):
                    clicked_species = self._species_row_at(event.pos)
                if clicked_gene is not None:
                    # Clicking a gene name in the legend selects it (and all
                    # organisms carrying it) until another click lands elsewhere.
                    if event.button == 1:
                        self.selected_gene = clicked_gene
                        self.selected_species = None
                    elif event.button == 3:
                        self.selected_gene = None
                elif clicked_species is not None:
                    # Clicking a species name selects it (and all its organisms)
                    # until another click lands elsewhere.
                    if event.button == 1:
                        self.selected_species = clicked_species
                        self.selected_gene = None
                elif self.paused:
                    # While paused, mouse buttons still spawn / remove organisms.
                    self.selected_species = None
                    self.selected_gene = None
                    if event.button == 1:
                        actions.append(SpawnAction(event.pos))
                    elif event.button == 3:
                        actions.append(RemoveAction(event.pos))
                else:
                    # During simulation, left-click selects an organism and shows
                    # its stats; right-click clears the selection and hides the panel.
                    self.selected_species = None
                    self.selected_gene = None
                    if event.button == 1:
                        self.selected_organism = self._find_organism_at(world, event.pos)
                    elif event.button == 3:
                        self.selected_organism = None
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.edit_mode:
                if event.button == 1:
                    self.drawing = False
                elif event.button == 3:
                    self.erasing = False

    def handle_events(self, world: World) -> list[Action]:
        actions: list[Action] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key_event(event, actions)
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                self._handle_mouse_event(event, world, actions)
        return actions

    def _screen_to_tile(self, world: World, pos: tuple[int, int]) -> tuple[int, int]:
        col = int(pos[0] / world.tile_size)
        row = int(pos[1] / world.tile_size)
        return col, row

    def apply_edits(self, world: World) -> None:
        """Apply the current edit tool to the tile under the mouse cursor."""
        if not self.edit_mode or not (self.drawing or self.erasing):
            return
        pos = pygame.mouse.get_pos()
        col, row = self._screen_to_tile(world, pos)
        if 0 <= col < world.cols and 0 <= row < world.rows:
            tile = config.TILE_EMPTY if self.erasing else self._edit_tool_tile()
            world.set_tile(col, row, tile)
            self.clear_map_cache()

    def _rebuild_animated_tile_rects(self, world: World) -> None:
        """Precompute screen rectangles for tiles that need per-frame animation.

        Runs of the same animated tile in a row are merged into one rectangle
        so each frame needs fewer fill calls.
        """
        rects_by_tile: dict[int, list[pygame.Rect]] = {tile: [] for tile in ANIMATED_TILES}
        tile_size = world.tile_size
        for row in range(world.rows):
            row_tiles = world.tiles[row]
            col = 0
            while col < world.cols:
                tile = row_tiles[col]
                start = col
                while col < world.cols and row_tiles[col] == tile:
                    col += 1
                if tile in rects_by_tile:
                    x = int(start * tile_size)
                    y = int(row * tile_size)
                    w = int(col * tile_size) - x
                    h = int((row + 1) * tile_size) - y
                    rects_by_tile[tile].append(pygame.Rect(x, y, w, h))
        self._animated_tile_rects = rects_by_tile

    def _draw_tiles(self, world: World) -> None:
        if self.edit_mode:
            self._map_surface = None
            draw_tiles(self.screen, world)
            return

        if self._map_surface is None:
            self._map_surface = pygame.Surface((self.width, self.height))
            self._map_surface.fill(config.COLOR_BACKGROUND)
            draw_tiles(self._map_surface, world)
            self._rebuild_animated_tile_rects(world)
        self.screen.blit(self._map_surface, (0, 0))

        # Animate pulsing tiles on top of the cached map.
        time_ms = pygame.time.get_ticks()
        for tile, rects in self._animated_tile_rects.items():
            if not rects:
                continue
            color = tile_color(tile, time_ms)
            for rect in rects:
                self.screen.fill(color, rect)

    def _draw_food(self, world: World) -> None:
        for food in world.food:
            color = config.COLOR_POISON if food.is_poison else config.COLOR_FOOD
            pos = (int(food.position[0]), int(food.position[1]))
            pygame.draw.circle(self.screen, color, pos, int(food.radius))
            pygame.draw.circle(self.screen, (0, 0, 0), pos, int(food.radius), 1)

    @staticmethod
    def _desaturate_color(color: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        if t <= 0.0:
            return color
        t = max(0.0, min(1.0, t))
        g = sum(color) // 3
        return tuple(int(g * t + c * (1 - t)) for c in color)

    class _OrganismProxy:
        """Lightweight stand-in used when drawing an organism on a non-world surface."""

        __slots__ = ("position", "toxin_resistance")

        def __init__(self, position: tuple[float, float], toxin_resistance: float) -> None:
            self.position = position
            self.toxin_resistance = toxin_resistance

    def _draw_organism_body(
        self,
        organism,
        surface: pygame.Surface,
        center: tuple[float, float],
        scale: float = 1.0,
        age_ratio: float = 0.0,
        overlays: dict[str, pygame.Surface] | None = None,
    ) -> None:
        """Draw an organism's body parts onto ``surface`` centered at ``center``."""
        ox0, oy0 = center
        cos_a = math.cos(organism.angle)
        sin_a = math.sin(organism.angle)
        proxy = self._OrganismProxy(center, organism.toxin_resistance)
        for part in organism.body_parts:
            offset_x, offset_y = part.blueprint.offset
            x = ox0 + (offset_x * cos_a - offset_y * sin_a) * scale
            y = oy0 + (offset_x * sin_a + offset_y * cos_a) * scale
            size = int(part.blueprint.size * scale)
            color = self._desaturate_color(part.blueprint.color, age_ratio)

            ctx = DrawContext(
                surface=surface,
                x=int(x),
                y=int(y),
                size=size,
                angle=organism.angle + part.blueprint.angle,
                color=color,
                organism=proxy,
                overlays=overlays,
                params=part.blueprint.params,
            )
            drawer = BODY_DRAWERS.get(part.blueprint.kind, draw_generic)
            drawer(ctx)

    def _draw_organism(self, organism) -> None:
        if organism.is_dead:
            return

        age_ratio = min(1.0, organism.age / max(1.0, organism.lifespan)) if config.GRAY_WITH_AGE else 0.0

        # Body parts are already sorted largest-first by Organism._build_body.
        overlays = None
        if self._eye_overlay and self._eye_line_overlay:
            overlays = {"fill": self._eye_overlay, "line": self._eye_line_overlay}

        self._draw_organism_body(
            organism,
            self.screen,
            organism.position,
            scale=organism.visual_scale,
            age_ratio=age_ratio,
            overlays=overlays,
        )

        cx, cy = int(organism.position[0]), int(organism.position[1])  # center x, center y

        # Highlight all organisms of the hovered species
        if self.hovered_species and organism.name == self.hovered_species:
            r = int(organism.radius)
            pygame.draw.circle(self.screen, (255, 220, 80), (cx, cy), r + 4, 2)

    def _draw_organisms(self, world: World) -> None:
        size = self.screen.get_size()
        if self._eye_overlay is None or self._eye_overlay.get_size() != size:
            self._eye_overlay = pygame.Surface(size, pygame.SRCALPHA)
        if self._eye_line_overlay is None or self._eye_line_overlay.get_size() != size:
            self._eye_line_overlay = pygame.Surface(size, pygame.SRCALPHA)
        self._eye_overlay.fill((0, 0, 0, 0))
        self._eye_line_overlay.fill((0, 0, 0, 0))
        for organism in world.organisms:
            self._draw_organism(organism)
        # Fill is blitted first, then lines, so no organism's fill obscures
        # another's outline.
        self.screen.blit(self._eye_overlay, (0, 0))
        self.screen.blit(self._eye_line_overlay, (0, 0))

    def _find_organism_at(self, world: World, pos: tuple[int, int]) -> object | None:
        """Return the organism whose body is under the given screen position, if any."""
        best = None
        best_dist = None
        for organism in world.organisms:
            if organism.is_dead:
                continue
            dx = organism.position[0] - pos[0]
            dy = organism.position[1] - pos[1]
            dist = math.hypot(dx, dy)
            if dist <= organism.radius and (best_dist is None or dist < best_dist):
                best = organism
                best_dist = dist
        return best

    def _draw_organism_highlight(self, organism, color: tuple[int, int, int] = (255, 255, 0)) -> None:
        cx, cy = int(organism.position[0]), int(organism.position[1])
        radius = int(organism.radius) + 4
        pulse = 2 + int(2 * math.sin(pygame.time.get_ticks() / 150))
        pygame.draw.circle(self.screen, color, (cx, cy), radius + pulse, 2)

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """Wrap a single text line into multiple lines that fit max_width."""
        words = text.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}" if current else word
            if self.small_font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _draw_organism_panel(self, organism) -> None:
        """Draw a panel with DNA / status stats for the hovered organism."""
        status_lines = [
            # "Selected organism",
            getattr(organism, "name", "unknown").upper(),
            f"energy: {organism.energy:.0f}/{organism.max_energy:.0f}",
            f"age: {organism.age:.0f}/{organism.lifespan:.0f}",
            f"generation: {organism.generation}",
            f"aggression: {organism.aggression:.2f}  armor: {organism.armor_value:.2f}",
            f"toxin res.: {organism.toxin_resistance:.2f}  glow: {organism.bioluminescence:.2f}",
            f"genes: {len(organism.dna.genes)}",
        ]
        if any(g.kind == "memory" for g in organism.dna.genes):
            status_lines.append(f"memory: {len(organism.memory)} points")
        status_lines.extend(
            [
                "-- DNA --",
            ]
        )

        margin = 12
        line_height = 16
        panel_width = 420
        thumb_size = 100
        x = margin
        # Top status text flows in the narrow column to the left of the thumbnail;
        # the rest of the panel (genes/DNA) can use the full width below it.
        thumb_x = x + panel_width - thumb_size - margin
        top_text_width = thumb_x - x - 2 * margin
        full_text_width = panel_width - 2 * margin

        header_color = (240, 240, 140)
        normal_color = (220, 220, 220)
        gene_color = (140, 220, 180)  # pale teal for the gene name
        # Each wrapped line is a list of (text, color, x_offset) segments.
        wrapped: list[list[tuple[str, tuple[int, int, int], int]]] = []

        for i, line in enumerate(status_lines):
            color = header_color if line == "-- DNA --" or i == 0 else normal_color
            for sub in self._wrap_text(line, top_text_width):
                wrapped.append([(sub, color, 0)])

        # Sort genes by how many copies the organism has (most common first)
        # to put the most impactful genes at the top of the panel.
        kind_counts: dict[str, int] = {}
        for g in organism.dna.genes:
            kind_counts[g.kind] = kind_counts.get(g.kind, 0) + 1
        sorted_genes = sorted(
            enumerate(organism.dna.genes),
            key=lambda item: (-kind_counts[item[1].kind], item[0]),
        )

        for _, gene in sorted_genes:
            kind_label = f"{gene.kind}: "
            kind_width = self.small_font.size(kind_label)[0]
            params_text = ", ".join(f"{k}={v:.2f}" for k, v in gene.params.items())
            params_width = max(0, full_text_width - kind_width)
            if params_text and params_width > 0:
                params_wrapped = self._wrap_text(params_text, params_width)
                wrapped.append([(kind_label, gene_color, 0), (params_wrapped[0], normal_color, kind_width)])
                for sub in params_wrapped[1:]:
                    wrapped.append([(sub, normal_color, kind_width)])
            else:
                wrapped.append([(kind_label, gene_color, 0)])

        panel_height = margin * 2 + len(wrapped) * line_height
        y = self.height - panel_height - margin

        panel = pygame.Surface((panel_width, panel_height))
        panel.fill((20, 20, 30))
        panel.set_alpha(220)
        self.screen.blit(panel, (x, y))
        pygame.draw.rect(self.screen, (100, 100, 110), (x, y, panel_width, panel_height), 1)

        # Thumbnail in the top-right corner of the stats panel, shifted left.
        thumb = pygame.Surface((thumb_size, thumb_size), pygame.SRCALPHA)
        thumb.fill((0, 0, 0, 0))
        target_radius = thumb_size / 2 - 8
        scale = min(2.0, target_radius / max(1.0, organism.radius))
        age_ratio = min(1.0, organism.age / max(1.0, organism.lifespan)) if config.GRAY_WITH_AGE else 0.0
        self._draw_organism_body(
            organism,
            thumb,
            (thumb_size / 2, thumb_size / 2),
            scale=scale,
            age_ratio=age_ratio,
        )
        self.screen.blit(thumb, (thumb_x, y + margin))

        for i, line_segments in enumerate(wrapped):
            line_y = y + margin + i * line_height
            for text, color, x_off in line_segments:
                surf = self.small_font.render(text, True, color)
                self.screen.blit(surf, (x + margin + x_off, line_y))

    LEGEND = [
        ("body", "main body / color gene", (180, 180, 180), "circle"),
        ("eye", "vision and steering", (240, 240, 240), "eye"),
        ("jaw", "eating and biting", (200, 120, 100), "pincer"),
        ("leg", "movement", (120, 120, 120), "limb"),
        ("spike", "contact damage", (220, 60, 60), "barb"),
        ("armor", "damage reduction", (160, 160, 170), "shield"),
        ("toxin_gland", "poison on death", (180, 60, 220), "hexagon"),
        ("scent", "smell (360° sensing)", (140, 120, 220), "antenna"),
        ("pheromone", "mating scent signal", (230, 120, 200), "diamond"),
        ("fat", "energy storage", (220, 200, 120), "ellipse"),
        ("regeneration", "healing when hurt", (80, 220, 120), "cross"),
        ("fear", "danger detection / escape", (240, 200, 80), "bolt"),
        ("touch", "wall / hazard avoidance whiskers", (230, 230, 150), "whiskers"),
        ("herd", "attraction toward same-species kin", (255, 215, 90), "flag"),
        ("amphibious", "safe, full-speed movement in water", (70, 190, 210), "tadpole"),
        ("venom", "poison bite (damage over time)", (100, 220, 100), "fangs"),
        ("asexual", "solitary cloning reproduction", (200, 220, 100), "bud"),
        ("cannibal", "will prey on same-species kin", (140, 20, 20), "maw"),
        ("memory", "remembers water, hazards and walls", (210, 120, 240), "memory"),
    ]

    TERRAIN = [
        ("empty", config.COLOR_BACKGROUND),
        ("wall", config.COLOR_WALL),
        ("radioactive", config.COLOR_RADIOACTIVE),
        ("lava", config.COLOR_LAVA),
        ("water", config.COLOR_WATER),
        ("heal", config.COLOR_HEAL),
    ]

    def _draw_legend_icon(self, x: int, y: int, size: int, color: tuple[int, int, int], shape: str) -> None:
        """Draw a legend icon for a body-part / gene kind using the legend drawers."""
        draw_legend_icon(self.screen, x, y, size, color, shape)

    def _draw_legend(self) -> None:
        """Draw the body-part / gene and terrain legend overlay."""
        margin = 12
        line_height = 24
        panel_width = 380
        terrain_rows = (len(self.TERRAIN) + 1) // 2
        terrain_offset = len(self.LEGEND) * line_height + 40
        panel_height = terrain_offset + terrain_rows * line_height + margin * 2

        panel = pygame.Surface((panel_width, panel_height))
        panel.fill((20, 20, 30))
        panel.set_alpha(220)
        x = self.width - panel_width - margin
        y = margin
        self._legend_panel_rect = (x, y, panel_width, panel_height)
        self.screen.blit(panel, (x, y))
        pygame.draw.rect(self.screen, (100, 100, 110), (x, y, panel_width, panel_height), 1)

        title = self.font.render("Body parts / genes (L to hide)", True, (240, 240, 240))
        self.screen.blit(title, (x + margin, y + margin))

        for i, (name, desc, color, shape) in enumerate(self.LEGEND):
            row_y = y + margin + 22 + i * line_height
            self._draw_legend_icon(x + margin + 4, row_y + 2, 18, color, shape)
            text = f"{name}: {desc}"
            text_color = self.GENE_HIGHLIGHT_COLOR if name == self.selected_gene else (220, 220, 220)
            surf = self.small_font.render(text, True, text_color)
            self.screen.blit(surf, (x + margin + 28, row_y + 4))

        terrain_title = self.font.render("Terrain", True, (240, 240, 240))
        self.screen.blit(terrain_title, (x + margin, y + terrain_offset - 6))

        column_width = (panel_width - margin * 2) // 2
        for i, (name, color) in enumerate(self.TERRAIN):
            col = i % 2
            row = i // 2
            tx = x + margin + col * column_width
            row_y = y + terrain_offset + 18 + row * line_height
            pygame.draw.rect(self.screen, color, (tx + 4, row_y + 2, 16, 16))
            pygame.draw.rect(self.screen, (100, 100, 110), (tx + 4, row_y + 2, 16, 16), 1)
            surf = self.small_font.render(f"{name}", True, (220, 220, 220))
            self.screen.blit(surf, (tx + 28, row_y + 4))

    def _legend_row_at(self, pos: tuple[int, int]) -> str | None:
        """Return the gene kind whose row in the legend panel contains `pos`, if any."""
        x, y, panel_width, panel_height = self._legend_panel_rect
        margin = 12
        line_height = 24
        mx, my = pos
        if x <= mx <= x + panel_width and y <= my <= y + panel_height:
            idx = (my - (y + margin + 22)) // line_height
            if 0 <= idx < len(self.LEGEND):
                return self.LEGEND[idx][0]
        return None

    def _draw_ui(self, stats: dict[str, Any]) -> None:
        lines = [
            f"tick: {stats.get('tick', 0)}",
            f"organisms: {stats['organisms']}",
            f"food: {stats['food']} births: {stats.get('births', 0)}",
            f"deaths: {stats.get('combat', 0) + stats.get('starvation', 0) + stats.get('age', 0) + stats.get('venom', 0)}",
            f"max gen: {stats.get('max_generation', 0)}  min gen: {stats.get('min_generation', 0)}",
            f"walls: {stats['walls']} hazards: {stats['hazards']}",
        ]
        if self.edit_mode:
            tool_name = self.EDIT_TOOLS[self.edit_tool_index][0]
            lines.extend(
                [
                    "EDIT MODE",
                    f"tool: {tool_name} (0 empty, 1 wall, 2 radioactive, 3 lava, 4 water, 5 heal)",
                    "LMB draw | RMB erase | S save | C clear | R random",
                    "E exit | ESC quit",
                ]
            )
        else:
            lines.append(f"fps: {int(self.clock.get_fps())}")

        y = 10
        for line in lines:
            surf = self.font.render(line, True, (220, 220, 220))
            self.screen.blit(surf, (10, y))
            y += 18

    def _update_species_hover(self, world: World) -> None:
        """Update hovered_species and cache top-5 species data for the panel."""
        counts: dict[str, int] = {}
        for o in world.organisms:
            if not o.is_dead:
                counts[o.name] = counts.get(o.name, 0) + 1

        if counts:
            total = sum(counts.values())
            top5 = [item for item in sorted(counts.items(), key=lambda x: -x[1]) if item[1] > 1][:5]
        else:
            total = 0
            top5 = []

        self._species_total = total
        self._species_top5 = top5

        margin = 12
        line_height = 18
        panel_width = 260
        panel_height = margin * 2 + (1 + len(top5)) * line_height
        x = self.width - panel_width - margin
        y = self.height - panel_height - margin
        self._species_panel_rect = (x, y, panel_width, panel_height)

        self.hovered_species = None
        mx, my = pygame.mouse.get_pos()
        if x <= mx <= x + panel_width and y <= my <= y + panel_height:
            idx = (my - (y + margin + line_height)) // line_height
            if 0 <= idx < len(top5):
                self.hovered_species = top5[idx][0]

    def _species_row_at(self, pos: tuple[int, int]) -> str | None:
        """Return the species name whose row in the panel contains `pos`, if any."""
        if not self._species_top5:
            return None
        x, y, panel_width, panel_height = self._species_panel_rect
        margin = 12
        line_height = 18
        mx, my = pos
        if x <= mx <= x + panel_width and y <= my <= y + panel_height:
            idx = (my - (y + margin + line_height)) // line_height
            if 0 <= idx < len(self._species_top5):
                return self._species_top5[idx][0]
        return None

    def _draw_species_stats(self) -> None:
        """Draw the separate top-5 species panel in the bottom-right corner."""
        if not self._species_top5:
            return

        x, y, panel_width, panel_height = self._species_panel_rect
        margin = 12
        line_height = 18
        total = self._species_total

        panel = pygame.Surface((panel_width, panel_height))
        panel.fill((20, 20, 30))
        panel.set_alpha(220)
        self.screen.blit(panel, (x, y))
        pygame.draw.rect(self.screen, (100, 100, 110), (x, y, panel_width, panel_height), 1)

        title = self.font.render("top 5 species", True, (240, 240, 140))
        self.screen.blit(title, (x + margin, y + margin))

        for i, (name, count) in enumerate(self._species_top5):
            row_y = y + margin + (i + 1) * line_height
            text = f"{name}: {count} ({count / total * 100:.1f}%)"
            if name == self.selected_species:
                color = self.SPECIES_HIGHLIGHT_COLOR
            elif name == self.hovered_species:
                color = (255, 220, 80)
            else:
                color = (220, 220, 220)
            surf = self.small_font.render(text, True, color)
            self.screen.blit(surf, (x + margin, row_y))

    def _draw_help(self) -> None:
        """Draw a centred help overlay listing all keyboard and mouse shortcuts."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        lines = [
            "Controls",
            "",
            "Simulation mode:",
            "  LMB      - spawn organism at cursor",
            "  RMB      - remove organism under cursor",
            "  R        - spawn a few random organisms",
            "  C        - reset simulation (Y/N)",
            "  SPACE    - pause / resume",
            "  L        - toggle legend",
            "  H        - toggle this help",
            "  G        - toggle age greying",
            "  T        - toggle top-5 species panel",
            "  P        - take screenshot",
            "  E        - toggle map edit mode",
            "  ESC      - quit",
            "",
            "Edit mode:",
            "  LMB      - draw selected tile",
            "  RMB      - erase tile",
            "  0-5      - select empty / wall / radioactive / lava / water / heal",
            "  S        - save map",
            "  C        - clear map",
            "  R        - randomize map",
            "  E / ESC  - exit edit mode",
        ]

        margin_x = 40
        margin_y = 40
        line_height = 20
        panel_width = max(self.font.size(line)[0] for line in lines) + margin_x * 2
        panel_height = len(lines) * line_height + margin_y * 2
        panel_x = (self.width - panel_width) // 2
        panel_y = (self.height - panel_height) // 2

        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill((30, 30, 35, 230))
        self.screen.blit(panel, (panel_x, panel_y))

        y = panel_y + margin_y
        for line in lines:
            surf = self.font.render(line, True, (240, 240, 240))
            self.screen.blit(surf, (panel_x + margin_x, y))
            y += line_height

    def _draw_reset_confirmation(self) -> None:
        """Show a centred prompt asking whether to reset the simulation."""
        lines = [
            "Reset simulation?",
            "Press Y to confirm, N or ESC to cancel",
        ]
        margin_x = 40
        margin_y = 30
        line_height = 24
        panel_width = max(self.font.size(line)[0] for line in lines) + margin_x * 2
        panel_height = len(lines) * line_height + margin_y * 2
        panel_x = (self.width - panel_width) // 2
        panel_y = (self.height - panel_height) // 2
        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill((60, 20, 20, 230))
        self.screen.blit(panel, (panel_x, panel_y))
        pygame.draw.rect(self.screen, (255, 80, 80), (panel_x, panel_y, panel_width, panel_height), 2)
        y = panel_y + margin_y
        for line in lines:
            surf = self.font.render(line, True, (240, 240, 240))
            self.screen.blit(surf, (panel_x + margin_x, y))
            y += line_height

    def _draw_edit_overlay(self, world: World) -> None:
        """Draw a tile grid and cursor highlight while in edit mode."""
        draw_grid(self.screen, world.tile_size, self.width, self.height)

        # Highlight tile under cursor
        mx, my = pygame.mouse.get_pos()
        col, row = self._screen_to_tile(world, (mx, my))
        if 0 <= col < world.cols and 0 <= row < world.rows:
            draw_tile_highlight(self.screen, col, row, world.tile_size)

    def render(self, world: World) -> None:
        self.screen.fill(config.COLOR_BACKGROUND)
        self._draw_tiles(world)
        self._draw_food(world)
        if not self.edit_mode and self.show_species:
            self._update_species_hover(world)
        else:
            self.hovered_species = None
        self._draw_organisms(world)
        self._draw_ui(world.stats())
        if not self.edit_mode and self.show_species:
            self._draw_species_stats()

        if not self.edit_mode and self.selected_species is not None:
            for organism in world.organisms:
                if not organism.is_dead and organism.name == self.selected_species:
                    self._draw_organism_highlight(organism, color=self.SPECIES_HIGHLIGHT_COLOR)

        if not self.edit_mode and self.selected_gene is not None:
            for organism in world.organisms:
                if not organism.is_dead and any(g.kind == self.selected_gene for g in organism.dna.genes):
                    self._draw_organism_highlight(organism, color=self.GENE_HIGHLIGHT_COLOR)

        if self.edit_mode:
            self._draw_edit_overlay(world)
        elif self.paused:
            # While paused, show stats for the organism under the cursor.
            hovered = self._find_organism_at(world, pygame.mouse.get_pos())
            if hovered is not None:
                self._draw_organism_highlight(hovered)
                self._draw_organism_panel(hovered)
        else:
            # During simulation, show stats for the selected organism (clicked with
            # the left mouse button) and clear the selection if it dies.
            if self.selected_organism is not None and self.selected_organism.is_dead:
                self.selected_organism = None
            if self.selected_organism is not None:
                self._draw_organism_highlight(self.selected_organism)
                self._draw_organism_panel(self.selected_organism)

        if self.show_legend:
            self._draw_legend()
        if self.show_help:
            self._draw_help()
        if self.confirming_reset:
            self._draw_reset_confirmation()
        pygame.display.flip()

    def tick(self) -> float:
        if self.fps > 0:
            raw_dt = self.clock.tick(self.fps) / 1000.0
        else:
            raw_dt = self.clock.tick() / 1000.0
        # Clamp so a stalled/slow frame (window drag, focus loss, GC pause, or
        # a heavy tick from O(n^2) collision/mating checks at high population)
        # can't be treated as many simulated ticks worth of time, which would
        # apply many ticks' worth of hazard damage/movement at once and can
        # wipe out large parts of the population in a single frame.
        return min(raw_dt, self.MAX_FRAME_DT)

    def close(self) -> None:
        pygame.quit()
