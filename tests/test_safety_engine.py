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

    def test_data_quality_indicator_sufficient_data(self):
        """Routes with comprehensive data coverage should be marked as sufficient_data."""
        engine = SafetyEngine(data_dir="data/raw")
        engine.load_data()

        result = engine.analyze_route("examples/sample_route.json")
        self.assertEqual(result["data_quality"], "sufficient_data")
        self.assertIn("data_availability", result)
        self.assertTrue(result["data_availability"]["crime"])

    def test_missing_data_not_treated_as_evidence_of_safety(self):
        """
        Routes outside data coverage must be marked as insufficient_data or limited_data,
        and missing crime/community factors must default to neutral 50.0 (NOT 100.0).
        """
        engine = SafetyEngine(data_dir="data/raw")
        engine.load_data()

        # Route far in New Delhi with no coverage in Bangalore datasets
        remote_route = Route(
            route_id="remote_uncovered_route",
            distance_km=4.0,
            duration_minutes=15.0,
            coordinates=[
                {"latitude": 28.6139, "longitude": 77.2090},
                {"latitude": 28.6200, "longitude": 77.2150}
            ]
        )

        result = engine.analyze_route(remote_route)

        # Must flag insufficient/limited data
        self.assertIn(result["data_quality"], ["insufficient_data", "limited_data"])
        self.assertFalse(result["data_availability"]["crime"])
        self.assertFalse(result["data_availability"]["community"])

        # Crucial: missing crime/community data must NOT score 100.0 (which would falsely imply perfect safety)
        self.assertEqual(result["breakdown"]["crime"], 50.0)
        self.assertEqual(result["breakdown"]["community"], 50.0)


if __name__ == "__main__":
    unittest.main()
