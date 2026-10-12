"""
Tests for Data Normalization functions.
"""

import unittest
from src.processing.normalization import min_max_scale, scale_rating_to_100


class TestNormalization(unittest.TestCase):

    def test_min_max_scale_direct(self):
        # Direct scale: 0 raw -> 0 score, 50 raw -> 50 score, 100 raw -> 100 score
        self.assertEqual(min_max_scale(50, 0, 100, invert=False), 50.0)
        self.assertEqual(min_max_scale(100, 0, 100, invert=False), 100.0)
        self.assertEqual(min_max_scale(0, 0, 100, invert=False), 0.0)

    def test_min_max_scale_inverted(self):
        # Inverted scale: 0 raw -> 100 score, 100 raw -> 0 score
        self.assertEqual(min_max_scale(0, 0, 100, invert=True), 100.0)
        self.assertEqual(min_max_scale(100, 0, 100, invert=True), 0.0)
        self.assertEqual(min_max_scale(25, 0, 100, invert=True), 75.0)

    def test_min_max_scale_clamping(self):
        # Out of bounds values must clamp strictly between 0 and 100
        self.assertEqual(min_max_scale(-10, 0, 100, invert=False), 0.0)
        self.assertEqual(min_max_scale(150, 0, 100, invert=False), 100.0)
        self.assertEqual(min_max_scale(-10, 0, 100, invert=True), 100.0)
        self.assertEqual(min_max_scale(150, 0, 100, invert=True), 0.0)

    def test_scale_rating_to_100(self):
        self.assertEqual(scale_rating_to_100(5, 1, 5, invert=False), 100.0)
        self.assertEqual(scale_rating_to_100(1, 1, 5, invert=False), 0.0)


if __name__ == "__main__":
    unittest.main()
