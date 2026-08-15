"""Tests for CLI helpers in main.py."""

import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

main_module = importlib.import_module("wee_life2.main")
from wee_life2.core import config


class TestMain(unittest.TestCase):
    def setUp(self):
        self._originals = {}

    def tearDown(self):
        for key, value in self._originals.items():
            setattr(config, key, value)

    def _save(self, *keys):
        for key in keys:
            self._originals[key] = getattr(config, key)

    def test_coerce_bool(self):
        self.assertTrue(main_module._coerce_config_value("true", True))
        self.assertTrue(main_module._coerce_config_value("1", True))
        self.assertTrue(main_module._coerce_config_value("yes", True))
        self.assertFalse(main_module._coerce_config_value("false", True))
        self.assertFalse(main_module._coerce_config_value("0", True))

    def test_coerce_int(self):
        self.assertEqual(main_module._coerce_config_value("42", 0), 42)

    def test_coerce_float(self):
        self.assertAlmostEqual(main_module._coerce_config_value("3.14", 0.0), 3.14)

    def test_coerce_str(self):
        self.assertEqual(main_module._coerce_config_value("hello", ""), "hello")

    def test_apply_config_overrides(self):
        self._save("MATING_RATE")
        main_module._apply_config_overrides(["MATING_RATE=0.123"])
        self.assertAlmostEqual(config.MATING_RATE, 0.123)

    def test_apply_multiple_overrides(self):
        self._save("MATING_RATE", "RADIATION_DAMAGE")
        main_module._apply_config_overrides(["MATING_RATE=0.5", "RADIATION_DAMAGE=0.9"])
        self.assertAlmostEqual(config.MATING_RATE, 0.5)
        self.assertAlmostEqual(config.RADIATION_DAMAGE, 0.9)

    def test_unknown_config_raises(self):
        with self.assertRaises(SystemExit):
            main_module._apply_config_overrides(["NOT_A_REAL_KEY=1"])

    def _make_config_file(self, data: dict) -> str:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, f)
        f.close()
        return f.name

    def test_config_file_flag_loads(self):
        self._save("MATING_RATE")
        path = self._make_config_file({"MATING_RATE": 0.123})
        try:
            argv = ["wee-life2", "--config-file", path, "--get", "MATING_RATE"]
            with patch.object(sys, "argv", argv):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    main_module.main()
                self.assertIn("MATING_RATE = 0.123", stdout.getvalue())
        finally:
            os.unlink(path)

    def test_config_file_then_set_override(self):
        self._save("MATING_RATE")
        path = self._make_config_file({"MATING_RATE": 0.1})
        try:
            argv = [
                "wee-life2",
                "--config-file",
                path,
                "--set",
                "MATING_RATE=0.5",
                "--get",
                "MATING_RATE",
            ]
            with patch.object(sys, "argv", argv):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    main_module.main()
                self.assertIn("MATING_RATE = 0.5", stdout.getvalue())
        finally:
            os.unlink(path)

    def test_missing_config_file_raises(self):
        argv = ["wee-life2", "--config-file", "does_not_exist.json"]
        with patch.object(sys, "argv", argv):
            with self.assertRaises(SystemExit):
                main_module.main()

    def test_edit_config_flag_opens_editor(self):
        with patch("wee_life2.config_editor.ConfigEditorApp") as mock_cls:
            instance = MagicMock()
            mock_cls.return_value = instance
            argv = ["wee-life2", "--edit-config"]
            with patch.object(sys, "argv", argv):
                main_module.main()
            mock_cls.assert_called_once_with(initial_path=None)
            instance.run.assert_called_once()

    def test_edit_config_with_config_file_path(self):
        self._save("MATING_RATE")
        path = self._make_config_file({"MATING_RATE": 0.123})
        try:
            with patch("wee_life2.config_editor.ConfigEditorApp") as mock_cls:
                instance = MagicMock()
                mock_cls.return_value = instance
                argv = ["wee-life2", "--config-file", path, "--edit-config"]
                with patch.object(sys, "argv", argv):
                    main_module.main()
                mock_cls.assert_called_once_with(initial_path=path)
                instance.run.assert_called_once()
        finally:
            os.unlink(path)

    def test_edit_config_rejects_set_and_get(self):
        with patch("wee_life2.config_editor.ConfigEditorApp"):
            argv = ["wee-life2", "--edit-config", "--set", "MATING_RATE=0.5"]
            with patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit):
                    main_module.main()


if __name__ == "__main__":
    unittest.main()
