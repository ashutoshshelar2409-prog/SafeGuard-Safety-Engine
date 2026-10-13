"""
Unit and Integration Tests for RoutingService orchestrator (Member 2).
"""

import unittest
from src.models.route import Route
from src.models.route_request import Coordinate, RouteRequest
from src.providers.routing_provider import MockRoutingProvider
from src.services.safety_engine_adapter import SafetyEngineAdapter
from src.services.routing_service import RoutingService


class TestRoutingService(unittest.TestCase):

    def setUp(self):
        self.origin = Coordinate(12.9716, 77.5946)
        self.destination = Coordinate(12.9850, 77.6100)
        self.request = RouteRequest(origin=self.origin, destination=self.destination)

        # Define 2 test routes
        # Route 1: Faster (10 min), passes through higher crime area
        route1 = Route(
            route_id="route_1",
            distance_km=2.8,
            duration_minutes=10.0,
            coordinates=[
                {"latitude": 12.9716, "longitude": 77.5946},
                {"latitude": 12.9780, "longitude": 77.6010},
                {"latitude": 12.9850, "longitude": 77.6100}
            ]
        )
        # Route 2: Slower (16 min), avoids downtown
        route2 = Route(
            route_id="route_2",
            distance_km=3.9,
            duration_minutes=16.0,
            coordinates=[
                {"latitude": 12.9716, "longitude": 77.5946},
                {"latitude": 12.9700, "longitude": 77.5900},
                {"latitude": 12.9850, "longitude": 77.6100}
            ]
        )

        self.mock_provider = MockRoutingProvider(routes_to_return=[route1, route2])
        self.adapter = SafetyEngineAdapter(data_dir="data/raw")
        self.service = RoutingService(provider=self.mock_provider, adapter=self.adapter)

    def test_calculate_routes_end_to_end(self):
        result = self.service.calculate_routes(self.request, preferred_ranking="balanced")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_routes_found"], 2)
        self.assertIn("recommendations", result)
        self.assertIn("fastest_route_id", result["recommendations"])
        self.assertIn("safest_route_id", result["recommendations"])
        self.assertIn("balanced_route_id", result["recommendations"])

        routes = result["routes"]
        self.assertEqual(len(routes), 2)
        for r in routes:
            self.assertIn("route_id", r)
            self.assertIn("safety_score", r)
            self.assertIn("breakdown", r)
            self.assertIn("rankings", r)
            self.assertIn("coordinates", r)
            self.assertTrue(0.0 <= r["safety_score"] <= 100.0)

    def test_calculate_routes_fastest_preference(self):
        result = self.service.calculate_routes(self.request, preferred_ranking="fastest")
        # Route 1 should be first because it is 10 min vs 16 min
        self.assertEqual(result["routes"][0]["route_id"], "route_1")

    def test_compare_custom_routes(self):
        custom_routes = [
            {
                "route_id": "custom_1",
                "distance_km": 2.0,
                "duration_minutes": 7.0,
                "coordinates": [{"latitude": 12.9716, "longitude": 77.5946}]
            },
            {
                "route_id": "custom_2",
                "distance_km": 4.0,
                "duration_minutes": 14.0,
                "coordinates": [{"latitude": 12.9850, "longitude": 77.6100}]
            }
        ]

        result = self.service.compare_custom_routes(custom_routes)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_routes_evaluated"], 2)


if __name__ == "__main__":
    unittest.main()
