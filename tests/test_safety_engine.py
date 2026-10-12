"""
End-to-End Tests for SafetyEngine service.
"""

import os
import unittest
from src.services.safety_engine import SafetyEngine
from src.models.route import Route


class TestSafetyEngine(unittest.TestCase):

    def test_safety_engine_end_to_end(self):
        data_dir = "data/raw"
        sample_route_path = "examples/sample_route.json"

        self.assertTrue(os.path.exists(sample_route_path))

        engine = SafetyEngine(data_dir=data_dir)
        engine.load_data()

        result = engine.analyze_route(sample_route_path)

        self.assertEqual(result["status"], "success")
        self.assertIn("route_id", result)
        self.assertIn("safety_score", result)
        self.assertIn("breakdown", result)

        # Check breakdown components
        breakdown = result["breakdown"]
        for factor in ["lighting", "crime", "emergency_access", "infrastructure", "community"]:
            self.assertIn(factor, breakdown)
            self.assertTrue(0.0 <= breakdown[factor] <= 100.0)

        # Check final score bounds
        self.assertTrue(0.0 <= result["safety_score"] <= 100.0)

    def test_safety_engine_direct_route_object(self):
        engine = SafetyEngine(data_dir="data/raw")
        engine.load_data()

        route = Route(
            route_id="test_route_999",
            distance_km=2.5,
            duration_minutes=10,
            coordinates=[{"latitude": 12.9716, "longitude": 77.5946}]
        )

        result = engine.analyze_route(route)
        self.assertEqual(result["route_id"], "test_route_999")
        self.assertTrue(0.0 <= result["safety_score"] <= 100.0)


if __name__ == "__main__":
    unittest.main()
