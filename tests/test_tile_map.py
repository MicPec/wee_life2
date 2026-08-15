"""Tests for the TileMap class."""

import unittest

from wee_life2.core import config
from wee_life2.core.tile_map import TileMap


class TestTileMap(unittest.TestCase):
    def setUp(self):
        self.tile_map = TileMap(200, 150, tile_size=20)
        self.tile_map.clear_map()

    def test_dimensions(self):
        self.assertEqual(self.tile_map.cols, 10)
        self.assertEqual(self.tile_map.rows, 7)
        self.assertEqual(self.tile_map.tile_size, 20)
        self.assertEqual(len(self.tile_map.tiles), 7)
        self.assertEqual(len(self.tile_map.tiles[0]), 10)

    def test_set_and_tile_at(self):
        self.tile_map.set_tile(2, 2, config.TILE_WALL)
        self.assertEqual(self.tile_map.tile_at((45, 45)), config.TILE_WALL)
        self.assertEqual(self.tile_map.tile_at((30, 30)), config.TILE_EMPTY)

    def test_out_of_bounds_is_wall(self):
        self.assertEqual(self.tile_map.tile_at((-20, 50)), config.TILE_WALL)
        self.assertEqual(self.tile_map.tile_at((250, 50)), config.TILE_WALL)

    def test_generate_map_has_border_walls(self):
        self.tile_map.generate_map()
        for col in range(self.tile_map.cols):
            self.assertEqual(self.tile_map.tiles[0][col], config.TILE_WALL)
            self.assertEqual(self.tile_map.tiles[-1][col], config.TILE_WALL)
        for row in range(self.tile_map.rows):
            self.assertEqual(self.tile_map.tiles[row][0], config.TILE_WALL)
            self.assertEqual(self.tile_map.tiles[row][-1], config.TILE_WALL)

    def test_clear_map_keeps_borders(self):
        self.tile_map.generate_map()
        self.tile_map.clear_map()
        for row in range(1, self.tile_map.rows - 1):
            for col in range(1, self.tile_map.cols - 1):
                self.assertEqual(self.tile_map.tiles[row][col], config.TILE_EMPTY)

    def test_is_wall_circle(self):
        self.tile_map.set_tile(1, 1, config.TILE_WALL)
        self.assertTrue(self.tile_map.is_wall_circle((25, 25), 5))
        self.assertFalse(self.tile_map.is_wall_circle((80, 80), 5))

    def test_is_empty_circle(self):
        pos = self.tile_map.random_empty_position(radius=5)
        self.assertTrue(self.tile_map.is_empty_circle(pos, 5))

    def test_line_intersects_wall(self):
        self.tile_map.set_tile(2, 2, config.TILE_WALL)
        # line from a non-wall tile to the wall tile
        self.assertTrue(self.tile_map._line_intersects_wall((30, 30), (45, 45)))
        # line entirely inside an empty tile
        self.assertFalse(self.tile_map._line_intersects_wall((30, 30), (35, 35)))

    def test_line_crosses_water(self):
        self.tile_map.set_tile(3, 3, config.TILE_WATER)
        self.assertTrue(self.tile_map.line_crosses_water((60, 60), (75, 75)))
        self.assertFalse(self.tile_map.line_crosses_water((30, 30), (35, 35)))

    def test_distance_to_obstacle_along_ray(self):
        self.tile_map.set_tile(2, 2, config.TILE_WALL)
        self.tile_map.set_tile(3, 3, config.TILE_WATER)
        # A wall is encountered first.
        result = self.tile_map.distance_to_obstacle_along_ray((30, 30), 0.785, 100)
        self.assertIsNotNone(result)
        _, is_hazard = result
        self.assertFalse(is_hazard)
        # A ray that only crosses water reports a hazard.
        result = self.tile_map.distance_to_obstacle_along_ray((65, 65), 0.785, 60, avoid_water=True)
        self.assertIsNotNone(result)
        _, is_hazard = result
        self.assertTrue(is_hazard)
        # A clear ray reports nothing.
        result = self.tile_map.distance_to_obstacle_along_ray((30, 30), 0.0, 100)
        self.assertIsNone(result)

    def test_push_out_of_walls(self):
        pos = self.tile_map.push_out_of_walls((35, 35), 8)
        self.assertFalse(self.tile_map.is_wall_circle(pos, 8))

    def test_nearest_empty_position(self):
        target = self.tile_map.nearest_empty_position((100, 100))
        self.assertEqual(self.tile_map.tile_at(target), config.TILE_EMPTY)

    def test_save_load_tiles_roundtrip(self):
        self.tile_map.generate_map()
        saved = self.tile_map.save_tiles()
        fresh = TileMap(200, 150, tile_size=20)
        fresh.load_tiles(saved)
        self.assertEqual(fresh.tiles, saved)

    def test_first_interesting_tile_along_ray(self):
        self.tile_map.set_tile(2, 2, config.TILE_WALL)
        self.tile_map.set_tile(3, 3, config.TILE_WATER)
        # Ray hits the wall first.
        result = self.tile_map.first_interesting_tile_along_ray((30, 30), 0.785, 100)
        self.assertIsNotNone(result)
        pos, tile_type = result
        self.assertEqual(tile_type, config.TILE_WALL)
        self.assertAlmostEqual(pos[0], 50.0, places=5)
        self.assertAlmostEqual(pos[1], 50.0, places=5)
        # Ray that only crosses water reports water.
        result = self.tile_map.first_interesting_tile_along_ray((65, 65), 0.785, 60)
        self.assertIsNotNone(result)
        pos, tile_type = result
        self.assertEqual(tile_type, config.TILE_WATER)
        # Clear ray reports nothing.
        result = self.tile_map.first_interesting_tile_along_ray((30, 30), 0.0, 100)
        self.assertIsNone(result)

    def test_is_heal(self):
        self.tile_map.set_tile(2, 2, config.TILE_HEAL)
        self.assertTrue(self.tile_map.is_heal((45, 45)))
        self.assertFalse(self.tile_map.is_heal((30, 30)))

    def test_nearest_heal(self):
        self.tile_map.set_tile(2, 2, config.TILE_HEAL)
        self.tile_map.set_tile(5, 5, config.TILE_HEAL)
        result = self.tile_map.nearest_heal((30, 30), 200)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 50.0, places=5)
        self.assertAlmostEqual(result[1], 50.0, places=5)

    def test_generate_map_includes_heal(self):
        self.tile_map.generate_map(heal_rate=0.5)
        heal_count = sum(row.count(config.TILE_HEAL) for row in self.tile_map.tiles)
        self.assertGreater(heal_count, 0)


if __name__ == "__main__":
    unittest.main()
