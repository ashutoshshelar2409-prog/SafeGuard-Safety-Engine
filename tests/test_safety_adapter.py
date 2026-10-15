"""
Unit Tests for SafetyEngineAdapter (Member 2).
Verifies safe integration with Member 1's SafetyEngine, data loading,
coordinate validation, and explicit error handling.
"""

import os
import unittest
from src.models.route import Route
from src.services.safety_engine import SafetyEngine
from src.services.safety_engine_adapter import SafetyEngineAdapter, SafetyEngineIntegrationError


class TestSafetyEngineAdapter(unittest.TestCase):

    def setUp(self):
        self.data_dir = "data/raw"
        self.adapter = SafetyEngineAdapter(data_dir=self.data_dir)

    def test_adapter_loads_data(self):
        self.adapter.ensure_data_loaded()
        self.assertTrue(self.adapter._data_loaded)

    def test_adapter_analyzes_valid_route(self):
        route = Route(
            route_id="route_adapter_test",
            distance_km=3.2,
            duration_minutes=12.0,
            coordinates=[
                {"latitude": 12.9716, "longitude": 77.5946},
                {"latitude": 12.9750, "longitude": 77.5980},
                {"latitude": 12.9850, "longitude": 77.6100}
            ]
        )
        result = self.adapter.analyze_route(route)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["route_id"], "route_adapter_test")
        self.assertIn("safety_score", result)
        self.assertTrue(0.0 <= result["safety_score"] <= 100.0)

        breakdown = result["breakdown"]
        for factor in ["lighting", "crime", "emergency_access", "infrastructure", "community"]:
            self.assertIn(factor, breakdown)
            self.assertTrue(0.0 <= breakdown[factor] <= 100.0)

    def test_adapter_rejects_empty_coordinates(self):
        # Construct raw invalid route with empty coords bypass
        class FakeRoute:
            route_id = "fake_invalid"
            coordinates = []

        with self.assertRaises(SafetyEngineIntegrationError):
            self.adapter.validate_route_for_engine(FakeRoute())

    def test_adapter_rejects_out_of_bounds_coords(self):
        class FakeRoute:
            route_id = "fake_coords"
            coordinates = [{"latitude": 150.0, "longitude": 77.5946}]

        with self.assertRaises(SafetyEngineIntegrationError):
            self.adapter.validate_route_for_engine(FakeRoute())

    def test_adapter_invalid_data_dir(self):
        bad_adapter = SafetyEngineAdapter(data_dir="non_existent_dir_99999")
        with self.assertRaises(SafetyEngineIntegrationError):
            bad_adapter.ensure_data_loaded()

    def test_adapter_reports_sparse_coverage_transparently(self):
        """Routes far outside safety data coverage must report sparse coverage transparently."""
        remote_route = Route(
            route_id="remote_route_delhi",
            distance_km=5.0,
            duration_minutes=20.0,
            coordinates=[
                {"latitude": 28.6139, "longitude": 77.2090},
                {"latitude": 28.6200, "longitude": 77.2150}
            ]
        )
        result = self.adapter.analyze_route(remote_route)
        self.assertEqual(result["data_coverage"], "sparse")
        self.assertIn("fallback", result["message"].lower())
        self.assertIn("disclaimer", result)


if __name__ == "__main__":
    unittest.main()
