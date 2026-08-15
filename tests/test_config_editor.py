"""Tests for the Textual configuration editor."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest import TestCase

from textual.widgets import Input, TabbedContent, TabPane
from textual_slider import Slider

from wee_life2.config_editor import ConfigEditorApp, _load_sections
from wee_life2.core import config, config_json


class TestConfigEditorApp(TestCase):
    """Smoke tests for the Textual configuration editor app."""

    def setUp(self) -> None:
        self._tmp_files: list[Path] = []

    def tearDown(self) -> None:
        for path in self._tmp_files:
            if path.exists():
                path.unlink()

    def _run_pilot(self, coro):
        return asyncio.run(coro)

    def test_sections_loaded(self) -> None:
        """Public config keys are grouped into at least one section."""
        sections = _load_sections()
        public = set(config_json.config_to_dict().keys())
        found = {k for keys in sections.values() for k in keys}
        self.assertEqual(found, public)

    def test_app_mounts_tabs(self) -> None:
        """The editor mounts a TabbedContent with panes for each section."""

        async def run():
            app = ConfigEditorApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                tabs = pilot.app.query_one(TabbedContent)
                panes = list(tabs.query(TabPane))
                self.assertGreaterEqual(len(panes), 1)
                self.assertEqual(len(panes), len(_load_sections()))

        self._run_pilot(run())

    def test_numeric_field_slider_and_input_sync(self) -> None:
        """Moving a slider updates the corresponding text input."""

        async def run():
            app = ConfigEditorApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                field = pilot.app.query_one("#field-MATING_RATE")
                self.assertIsNotNone(field._slider)
                self.assertIsNotNone(field._input)
                original = float(field._input.value)
                field._slider.value = 500
                await pilot.pause()
                self.assertNotEqual(float(field._input.value), original)

        self._run_pilot(run())

    def test_save_writes_json(self) -> None:
        """Clicking Save writes the current values to the specified path."""

        async def run():
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                path = Path(f.name)
            self._tmp_files.append(path)

            app = ConfigEditorApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                pilot.app.query_one("#path-input", Input).value = str(path)
                await pilot.click("#save")
                await pilot.pause()

            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("MATING_RATE", data)
            self.assertAlmostEqual(float(data["MATING_RATE"]), config.MATING_RATE, places=3)

        self._run_pilot(run())

    def test_load_initial_path(self) -> None:
        """Loading the editor with a config file applies its values."""

        async def run():
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                path = Path(f.name)
                f.write(json.dumps({"MATING_RATE": 0.123, "MAX_SPEED": 5.5}))
            self._tmp_files.append(path)

            original_mating = config.MATING_RATE
            original_speed = config.MAX_SPEED
            try:
                app = ConfigEditorApp(initial_path=path)
                async with app.run_test() as pilot:
                    await pilot.pause()
                    self.assertAlmostEqual(config.MATING_RATE, 0.123, places=5)
                    self.assertAlmostEqual(config.MAX_SPEED, 5.5, places=5)
            finally:
                config.MATING_RATE = original_mating
                config.MAX_SPEED = original_speed

        self._run_pilot(run())

    def test_revert_restores_defaults(self) -> None:
        """Revert reloads the original config module values."""

        async def run():
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                path = Path(f.name)
                f.write(json.dumps({"MATING_RATE": 0.999}))
            self._tmp_files.append(path)

            original = config.MATING_RATE
            try:
                app = ConfigEditorApp(initial_path=path)
                async with app.run_test() as pilot:
                    await pilot.pause()
                    self.assertAlmostEqual(config.MATING_RATE, 0.999, places=5)
                    await pilot.app.action_revert()
                    await pilot.pause()
                    self.assertAlmostEqual(config.MATING_RATE, original, places=5)
            finally:
                config.MATING_RATE = original

        self._run_pilot(run())
