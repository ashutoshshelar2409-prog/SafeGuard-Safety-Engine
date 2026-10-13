"""
Unit Tests for Routing Providers (Member 2).
Tests OSRM URL construction, coordinate normalization, error handling, and mock provider.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

from src.models.route_request import Coordinate, RouteRequest
from src.providers.routing_provider import (
    OSRMProvider,
    MockRoutingProvider,
    RoutingAPIError,
    RoutingConnectionError,
    NoRouteFoundError
)


class TestRoutingProvider(unittest.TestCase):

    def setUp(self):
        self.origin = Coordinate(12.9716, 77.5946)
        self.destination = Coordinate(12.9850, 77.6100)
        self.request = RouteRequest(origin=self.origin, destination=self.destination, profile="driving")

    def test_osrm_url_construction(self):
        provider = OSRMProvider(base_url="https://router.project-osrm.org")
        url = provider._build_url(self.request)

        # Coordinate syntax must be: {lon1},{lat1};{lon2},{lat2}
        expected_coords = f"{self.origin.longitude:.6f},{self.origin.latitude:.6f};{self.destination.longitude:.6f},{self.destination.latitude:.6f}"
        self.assertIn(expected_coords, url)
        self.assertIn("/route/v1/driving/", url)
        self.assertIn("overview=full", url)
        self.assertIn("geometries=geojson", url)

    def test_osrm_profile_mapping(self):
        provider = OSRMProvider()
        self.assertEqual(provider._resolve_profile("walking"), "foot")
        self.assertEqual(provider._resolve_profile("foot"), "foot")
        self.assertEqual(provider._resolve_profile("cycling"), "bike")
        self.assertEqual(provider._resolve_profile("driving"), "driving")

    @patch("urllib.request.urlopen")
    def test_osrm_coordinate_normalization(self, mock_urlopen):
        """
        Verify that OSRM GeoJSON [lon, lat] coordinates are correctly mapped to
        {'latitude': lat, 'longitude': lon} for Member 1's Route model.
        """
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 3500.0,  # meters
                    "duration": 480.0,   # seconds (8 mins)
                    "geometry": {
                        "coordinates": [
                            [77.5946, 12.9716],
                            [77.6000, 12.9780],
                            [77.6100, 12.9850]
                        ]
                    }
                }
            ]
        }
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = OSRMProvider()
        routes = provider.get_routes(self.request)

        self.assertEqual(len(routes), 1)
        route = routes[0]
        self.assertEqual(route.distance_km, 3.5)
        self.assertEqual(route.duration_minutes, 8.0)
        self.assertEqual(len(route.coordinates), 3)

        # Verify latitude and longitude are NOT swapped
        first_pt = route.coordinates[0]
        self.assertEqual(first_pt["latitude"], 12.9716)
        self.assertEqual(first_pt["longitude"], 77.5946)

    @patch("urllib.request.urlopen")
    def test_osrm_no_route_error(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps({"code": "NoRoute"}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = OSRMProvider()
        with self.assertRaises(NoRouteFoundError):
            provider.get_routes(self.request)

    @patch("urllib.request.urlopen")
    def test_osrm_network_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        provider = OSRMProvider()
        with self.assertRaises(RoutingConnectionError):
            provider.get_routes(self.request)

    @patch("urllib.request.urlopen")
    def test_osrm_http_api_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://router.project-osrm.org",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )

        provider = OSRMProvider()
        with self.assertRaises(RoutingAPIError):
            provider.get_routes(self.request)

    def test_mock_routing_provider(self):
        provider = MockRoutingProvider()
        routes = provider.get_routes(self.request)
        self.assertEqual(len(routes), 2)
        self.assertGreater(len(routes[0].coordinates), 0)
        self.assertGreater(len(routes[1].coordinates), 0)


if __name__ == "__main__":
    unittest.main()
