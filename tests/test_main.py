"""Tests for CLI helpers in main.py."""

import importlib
import unittest

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


if __name__ == "__main__":
    unittest.main()
