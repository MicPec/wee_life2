"""Interactive tile map editor."""

from __future__ import annotations

import pygame

from ..core import config
from ..core.map_storage import MapStorage
from ..core.world import World
from .tile_drawing import EDIT_TOOLS, draw_tile_highlight, draw_tiles


class MapEditor:
    """Pygame-based editor for drawing walls, hazards and empty tiles."""

    TOOLS = EDIT_TOOLS

    def __init__(
        self,
        width: int = config.WINDOW_WIDTH,
        height: int = config.WINDOW_HEIGHT,
        tile_size: int = config.TILE_SIZE,
        storage: MapStorage | None = None,
    ) -> None:
        pygame.init()
        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.storage = storage or MapStorage()

        self.world = World(float(width), float(height), float(tile_size))

        # Try to load saved map, otherwise generate a fresh random one
        saved = self.storage.load()
        if saved:
            self.world.load_tiles(saved)
        else:
            self.world.generate_map()

        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Wee Life 2 — Map Editor")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 14)

        self.tool_index = 1  # start with wall
        self.drawing = False
        self.erasing = False
        self.running = True

    @property
    def tool_name(self) -> str:
        return self.TOOLS[self.tool_index][0]

    @property
    def tool_tile(self) -> int:
        return self.TOOLS[self.tool_index][1]

    def _screen_to_tile(self, pos: tuple[int, int]) -> tuple[int, int]:
        col = pos[0] // self.tile_size
        row = pos[1] // self.tile_size
        return col, row

    def _apply_tool_at(self, screen_pos: tuple[int, int], tile: int) -> None:
        col, row = self._screen_to_tile(screen_pos)
        if 0 <= col < self.world.cols and 0 <= row < self.world.rows:
            self.world.set_tile(col, row, tile)

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key == pygame.K_s:
            self.save()
        elif event.key == pygame.K_c:
            self.clear_map()
        elif event.key == pygame.K_r:
            self.randomize()
        else:
            # Digit keys select a tool; derived from TOOLS so adding a tile
            # type does not need a new branch here.
            index = event.key - pygame.K_0
            if index in self.TOOLS:
                self.tool_index = index

    def _handle_mouse(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.drawing = True
            elif event.button == 3:
                self.erasing = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.drawing = False
            elif event.button == 3:
                self.erasing = False

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                self._handle_mouse(event)

        if self.drawing:
            self._apply_tool_at(pygame.mouse.get_pos(), self.tool_tile)
        if self.erasing:
            self._apply_tool_at(pygame.mouse.get_pos(), config.TILE_EMPTY)

    def clear_map(self) -> None:
        """Fill the whole board with empty tiles, keeping the border walls."""
        self.world.clear_map()

    def randomize(self) -> None:
        """Generate a fresh random map."""
        self.world.generate_map()

    def save(self) -> None:
        self.storage.save(self.world.save_tiles())
        print(f"Map saved to {self.storage.path}")

    def _draw(self) -> None:
        self.screen.fill(config.COLOR_BACKGROUND)
        draw_tiles(self.screen, self.world, border=True)

        # Highlight tile under the cursor
        col, row = self._screen_to_tile(pygame.mouse.get_pos())
        if 0 <= col < self.world.cols and 0 <= row < self.world.rows:
            draw_tile_highlight(self.screen, col, row, self.tile_size)

        self._draw_ui()
        pygame.display.flip()

    def _draw_ui(self) -> None:
        lines = [
            "Wee Life 2 Map Editor",
            f"Tool: {self.tool_name} (0 empty, 1 wall, 2 radioactive, 3 lava, 4 water, 5 heal)",
            "LMB draw | RMB erase | R random | C clear | S save | ESC exit",
            f"Saved: {self.storage.exists()}",
        ]
        y = 10
        for line in lines:
            # Dark background for readability
            surf = self.font.render(line, True, (240, 240, 240))
            self.screen.blit(surf, (10, y))
            y += 20

    def run(self) -> None:
        while self.running:
            self.clock.tick(config.FPS)
            self._handle_events()
            self._draw()
        pygame.quit()
