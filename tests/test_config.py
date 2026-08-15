"""Tests for JSON config loading/saving."""

import json
import os
import tempfile
import unittest

from wee_life2.core import config
from wee_life2.core import config_json


class TestConfigJson(unittest.TestCase):
    def setUp(self):
        self._originals = {}

    def tearDown(self):
        for key, value in self._originals.items():
            setattr(config, key, value)

    def _save(self, *keys):
        for key in keys:
            self._originals[key] = getattr(config, key)

    def test_config_to_dict_includes_public_constants(self):
        data = config_json.config_to_dict()
        self.assertIn("MATING_RATE", data)
        self.assertIn("COLOR_BACKGROUND", data)
        self.assertIn("GENE_SPAWN_WEIGHTS", data)
        self.assertNotIn("__name__", data)
        self.assertNotIn("__doc__", data)
        self.assertIsInstance(data["COLOR_BACKGROUND"], tuple)

    def test_coerce_value_bool_from_string(self):
        self.assertTrue(config_json.coerce_value("true", True))
        self.assertTrue(config_json.coerce_value("1", True))
        self.assertTrue(config_json.coerce_value("yes", True))
        self.assertFalse(config_json.coerce_value("false", True))

    def test_coerce_value_int(self):
        self.assertEqual(config_json.coerce_value("42", 0), 42)
        self.assertEqual(config_json.coerce_value(42, 0), 42)
        with self.assertRaises(TypeError):
            config_json.coerce_value(3.14, 0)

    def test_coerce_value_float(self):
        self.assertAlmostEqual(config_json.coerce_value("3.14", 0.0), 3.14)
        self.assertAlmostEqual(config_json.coerce_value(3, 0.0), 3.0)
        with self.assertRaises(TypeError):
            config_json.coerce_value(True, 0.0)

    def test_coerce_value_tuple(self):
        result = config_json.coerce_value([10, 20, 30], (0, 0, 0))
        self.assertEqual(result, (10, 20, 30))
        self.assertIsInstance(result, tuple)

    def test_coerce_value_dict(self):
        current = {"a": 0.5, "b": 1.0}
        result = config_json.coerce_value({"a": 1, "b": "2.5"}, current)
        self.assertAlmostEqual(result["a"], 1.0)
        self.assertAlmostEqual(result["b"], 2.5)

    def test_load_config_file_overrides(self):
        self._save("MATING_RATE")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"MATING_RATE": 0.123}, f)
            path = f.name
        try:
            config_json.load_config_file(path)
            self.assertAlmostEqual(config.MATING_RATE, 0.123)
        finally:
            os.unlink(path)

    def test_load_config_file_unknown_key_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"NOT_A_REAL_KEY": 1}, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                config_json.load_config_file(path)
        finally:
            os.unlink(path)

    def test_load_config_file_type_mismatch(self):
        self._save("MATING_RATE")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"MATING_RATE": "abc"}, f)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                config_json.load_config_file(path)
        finally:
            os.unlink(path)

    def test_load_config_file_tuple_conversion(self):
        self._save("COLOR_BACKGROUND")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"COLOR_BACKGROUND": [10, 20, 30]}, f)
            path = f.name
        try:
            config_json.load_config_file(path)
            self.assertEqual(config.COLOR_BACKGROUND, (10, 20, 30))
            self.assertIsInstance(config.COLOR_BACKGROUND, tuple)
        finally:
            os.unlink(path)

    def test_load_config_file_gene_spawn_weights(self):
        self._save("GENE_SPAWN_WEIGHTS")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"GENE_SPAWN_WEIGHTS": {"asexual": 1, "spike": 2}}, f)
            path = f.name
        try:
            config_json.load_config_file(path)
            self.assertAlmostEqual(config.GENE_SPAWN_WEIGHTS["asexual"], 1.0)
            self.assertAlmostEqual(config.GENE_SPAWN_WEIGHTS["spike"], 2.0)
        finally:
            os.unlink(path)

    def test_save_and_load_roundtrip(self):
        self._save("MATING_RATE", "COLOR_BACKGROUND", "GENE_SPAWN_WEIGHTS")
        config.MATING_RATE = 0.999
        config.COLOR_BACKGROUND = (1, 2, 3)
        config.GENE_SPAWN_WEIGHTS = {"asexual": 0.1}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            config_json.save_config_file(path)
            # reset to different values
            config.MATING_RATE = 0.3
            config.COLOR_BACKGROUND = (20, 20, 30)
            config.GENE_SPAWN_WEIGHTS = {"asexual": 0.4}
            config_json.load_config_file(path)
            self.assertAlmostEqual(config.MATING_RATE, 0.999)
            self.assertEqual(config.COLOR_BACKGROUND, (1, 2, 3))
            self.assertAlmostEqual(config.GENE_SPAWN_WEIGHTS["asexual"], 0.1)
        finally:
            os.unlink(path)

    def test_config_from_dict_ignores_private_keys(self):
        self._save("MATING_RATE")
        config_json.config_from_dict({"_PRIVATE": 1, "MATING_RATE": 0.5})
        self.assertAlmostEqual(config.MATING_RATE, 0.5)

    def test_config_from_dict_rejects_unknown_keys(self):
        with self.assertRaises(ValueError):
            config_json.config_from_dict({"UNKNOWN_KEY": 123})


if __name__ == "__main__":
    unittest.main()
