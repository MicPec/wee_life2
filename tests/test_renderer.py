"""Tests for renderer wiring that is easy to break silently.

These cover lookups that fall back to a generic default when a key is missing:
a typo there is invisible on screen rather than raising, so it needs asserting.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from wee_life2.render.legend_drawing import LEGEND_DRAWERS, _draw_legend_generic, draw_legend_icon
from wee_life2.render.renderer import MAX_OUTLINE_THICKNESS, Renderer
from wee_life2.render.tile_drawing import EDIT_TOOLS


class TestLegendWiring(unittest.TestCase):
    def test_every_legend_row_has_a_dedicated_drawer(self):
        """`draw_legend_icon` silently falls back to a generic icon.

        The `body` row used shape "circle", which is not a registered drawer,
        so `_draw_legend_body` was dead code and the icon rendered generically.
        """
        missing = sorted({shape for *_rest, shape in Renderer.LEGEND if shape not in LEGEND_DRAWERS})
        self.assertEqual(missing, [], f"legend shapes without a drawer: {missing}")

    def test_legend_rows_are_well_formed(self):
        for row in Renderer.LEGEND:
            self.assertEqual(len(row), 4, f"malformed legend row: {row}")
            _kind, label, color, shape = row
            self.assertIsInstance(label, str)
            self.assertEqual(len(color), 3)
            self.assertIsInstance(shape, str)

    def test_unknown_shape_uses_generic_drawer(self):
        self.assertIs(LEGEND_DRAWERS.get("definitely-not-a-shape", _draw_legend_generic), _draw_legend_generic)

    def test_all_drawers_paint_without_error(self):
        pygame.init()
        surface = pygame.Surface((32, 32))
        try:
            for shape in LEGEND_DRAWERS:
                draw_legend_icon(surface, 4, 4, 16, (200, 200, 200), shape)
        finally:
            pygame.quit()


class TestEditTools(unittest.TestCase):
    def test_renderer_and_map_editor_share_one_tool_table(self):
        from wee_life2.render.map_editor import MapEditor

        self.assertIs(Renderer.EDIT_TOOLS, EDIT_TOOLS)
        self.assertIs(MapEditor.TOOLS, EDIT_TOOLS)

    def test_tool_indices_are_contiguous_digit_keys(self):
        self.assertEqual(sorted(EDIT_TOOLS), list(range(len(EDIT_TOOLS))))


class TestResetConfirmationIsModal(unittest.TestCase):
    """While "really reset?" is up, other keys must not act behind the dialog."""

    def setUp(self):
        self.renderer = Renderer(width=200, height=150, fps=60)

    def tearDown(self):
        self.renderer.close()

    def _press(self, key):
        actions = []
        event = pygame.event.Event(pygame.KEYDOWN, key=key)
        self.renderer._handle_key_event(event, actions)
        return actions

    def test_unrelated_keys_are_swallowed(self):
        for key in (pygame.K_e, pygame.K_SPACE, pygame.K_r, pygame.K_h, pygame.K_l, pygame.K_g, pygame.K_t):
            self.renderer.confirming_reset = True
            before = (self.renderer.edit_mode, self.renderer.paused, self.renderer.show_help, self.renderer.running)
            actions = self._press(key)
            after = (self.renderer.edit_mode, self.renderer.paused, self.renderer.show_help, self.renderer.running)
            self.assertEqual(before, after, f"key {key} leaked through the modal dialog")
            self.assertEqual(actions, [], f"key {key} emitted an action through the modal dialog")
            self.assertTrue(self.renderer.confirming_reset, "dialog should stay open for unrelated keys")

    def test_escape_does_not_quit_while_confirming(self):
        self.renderer.confirming_reset = True
        self._press(pygame.K_ESCAPE)
        self.assertTrue(self.renderer.running, "ESC should dismiss the dialog, not quit the app")
        self.assertFalse(self.renderer.confirming_reset)

    def test_yes_emits_reset_and_closes(self):
        from wee_life2.render.actions import ResetAction

        self.renderer.confirming_reset = True
        actions = self._press(pygame.K_y)
        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], ResetAction)
        self.assertFalse(self.renderer.confirming_reset)

    def test_no_closes_without_reset(self):
        for key in (pygame.K_n, pygame.K_c):
            self.renderer.confirming_reset = True
            self.assertEqual(self._press(key), [])
            self.assertFalse(self.renderer.confirming_reset)


class TestOutlineThickness(unittest.TestCase):
    def test_thickness_is_clamped(self):
        """A mutated armor thickness must not produce an absurd outline width."""
        self.assertGreater(MAX_OUTLINE_THICKNESS, 0)
        for raw, expected in [(-5.0, 0), (0.0, 0), (2.0, 2), (999.0, MAX_OUTLINE_THICKNESS)]:
            clamped = int(min(MAX_OUTLINE_THICKNESS, max(0.0, raw)))
            self.assertEqual(clamped, expected)


if __name__ == "__main__":
    unittest.main()
