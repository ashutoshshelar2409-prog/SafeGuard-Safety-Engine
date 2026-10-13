"""
Unit Tests for Route Request, Coordinate Validation, and EvaluatedRoute Models (Member 2).
"""

import unittest
from src.models.route_request import Coordinate, RouteRequest, EvaluatedRoute
from src.models.route import Route


class TestRouteRequest(unittest.TestCase):

    def test_coordinate_valid(self):
        coord = Coordinate(latitude=12.9716, longitude=77.5946)
        self.assertEqual(coord.latitude, 12.9716)
        self.assertEqual(coord.longitude, 77.5946)
        self.assertEqual(coord.to_dict(), {"latitude": 12.9716, "longitude": 77.5946})
        self.assertEqual(coord.to_lat_lng_tuple(), (12.9716, 77.5946))
        self.assertEqual(coord.to_lng_lat_tuple(), (77.5946, 12.9716))

    def test_coordinate_invalid_bounds(self):
        # Latitude out of bounds
        with self.assertRaises(ValueError):
            Coordinate(latitude=95.0, longitude=77.5946)
        with self.assertRaises(ValueError):
            Coordinate(latitude=-91.0, longitude=77.5946)

        # Longitude out of bounds
        with self.assertRaises(ValueError):
            Coordinate(latitude=12.9716, longitude=185.0)
        with self.assertRaises(ValueError):
            Coordinate(latitude=12.9716, longitude=-181.0)

    def test_coordinate_from_any(self):
        c1 = Coordinate.from_any({"latitude": 12.5, "longitude": 77.5})
        self.assertEqual(c1.latitude, 12.5)

        c2 = Coordinate.from_any({"lat": 12.5, "lon": 77.5})
        self.assertEqual(c2.longitude, 77.5)

        c3 = Coordinate.from_any([12.5, 77.5])
        self.assertEqual(c3.latitude, 12.5)
        self.assertEqual(c3.longitude, 77.5)

        c4 = Coordinate.from_any(c1)
        self.assertEqual(c4, c1)

    def test_route_request_creation(self):
        req = RouteRequest(
            origin=Coordinate(12.9716, 77.5946),
            destination=Coordinate(12.9850, 77.6100),
            alternatives=True,
            profile="driving"
        )
        self.assertEqual(req.origin.latitude, 12.9716)
        self.assertEqual(req.profile, "driving")

    def test_route_request_from_dict(self):
        payload = {
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100},
            "profile": "walking",
            "alternatives": False
        }
        req = RouteRequest.from_dict(payload)
        self.assertEqual(req.profile, "walking")
        self.assertFalse(req.alternatives)

    def test_route_request_unsupported_profile(self):
        with self.assertRaises(ValueError):
            RouteRequest(
                origin=Coordinate(12.0, 77.0),
                destination=Coordinate(12.1, 77.1),
                profile="airplane"
            )

    def test_evaluated_route_to_dict(self):
        base_route = Route(
            route_id="r1",
            distance_km=2.5,
            duration_minutes=8.0,
            coordinates=[{"latitude": 12.0, "longitude": 77.0}]
        )
        evaluated = EvaluatedRoute(
            route=base_route,
            safety_score=85.5,
            breakdown={"lighting": 80.0, "crime": 90.0},
            weights={"lighting": 0.5, "crime": 0.5},
            rank_fastest=1,
            rank_safest=2,
            rank_balanced=1,
            balanced_score=88.2,
            tags=["fastest", "balanced"]
        )
        d = evaluated.to_dict()
        self.assertEqual(d["route_id"], "r1")
        self.assertEqual(d["safety_score"], 85.5)
        self.assertEqual(d["rankings"]["fastest"], 1)
        self.assertIn("fastest", d["tags"])


if __name__ == "__main__":
    unittest.main()
