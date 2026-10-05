"""Tests for the SpatialGrid class."""

import unittest

from wee_life2.core.spatial_grid import SpatialGrid


class FakeOrganism:
    def __init__(self, pos, is_dead=False, uid=0):
        self.position = pos
        self.is_dead = is_dead
        self.uid = uid


class TestSpatialGrid(unittest.TestCase):
    def setUp(self):
        self.grid = SpatialGrid(cell_size=50.0, width=200, height=150)

    def test_add_and_near(self):
        a = FakeOrganism((10, 10))
        b = FakeOrganism((20, 20))
        c = FakeOrganism((150, 120))
        self.grid.add(a)
        self.grid.add(b)
        self.grid.add(c)

        near = list(self.grid.near((15, 15), 30))
        self.assertIn(a, near)
        self.assertIn(b, near)
        self.assertNotIn(c, near)

    def test_dead_organisms_not_returned(self):
        a = FakeOrganism((10, 10))
        a.is_dead = True
        self.grid.add(a)
        self.assertEqual(list(self.grid.near((10, 10), 20)), [])

    def test_exclude(self):
        a = FakeOrganism((10, 10))
        b = FakeOrganism((15, 15))
        self.grid.add(a)
        self.grid.add(b)
        near = list(self.grid.near((12, 12), 30, exclude=(a,)))
        self.assertNotIn(a, near)
        self.assertIn(b, near)

    def test_remove(self):
        a = FakeOrganism((10, 10))
        self.grid.add(a)
        self.grid.remove(a)
        self.assertEqual(list(self.grid.near((10, 10), 20)), [])

    def test_rebuild(self):
        a = FakeOrganism((10, 10))
        b = FakeOrganism((20, 20))
        c = FakeOrganism((15, 15), is_dead=True)
        self.grid.add(a)
        self.grid.add(b)
        # Simulate b moving far away
        b.position = (150, 150)
        self.grid.rebuild([a, b, c])
        near = list(self.grid.near((10, 10), 30))
        self.assertIn(a, near)
        self.assertNotIn(b, near)

    def test_local_density(self):
        a = FakeOrganism((10, 10))
        b = FakeOrganism((20, 20))
        c = FakeOrganism((150, 120))
        self.grid.add(a)
        self.grid.add(b)
        self.grid.add(c)
        self.assertEqual(self.grid.local_density((15, 15), 30), 2)


if __name__ == "__main__":
    unittest.main()
