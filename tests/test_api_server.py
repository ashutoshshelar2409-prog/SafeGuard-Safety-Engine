"""
Unit Tests for SafeGuard API Server and Request Handler (Member 2).
"""

import io
import json
import unittest
from unittest.mock import MagicMock

from src.api.server import SafeGuardRequestHandler
from src.models.route import Route
from src.providers.routing_provider import MockRoutingProvider
from src.services.safety_engine_adapter import SafetyEngineAdapter
from src.services.routing_service import RoutingService


class DummyRequest:
    """Mock socket request object."""
    def makefile(self, *args, **kwargs):
        return io.BytesIO()


class TestAPIServer(unittest.TestCase):

    def setUp(self):
        # Configure RoutingService with mock provider
        route = Route(
            route_id="route_api_1",
            distance_km=2.5,
            duration_minutes=8.0,
            coordinates=[{"latitude": 12.9716, "longitude": 77.5946}]
        )
        provider = MockRoutingProvider(routes_to_return=[route])
        adapter = SafetyEngineAdapter(data_dir="data/raw")
        self.service = RoutingService(provider=provider, adapter=adapter)
        SafeGuardRequestHandler.routing_service = self.service

    def _create_handler(self, method: str, path: str, body: dict = None, headers: dict = None):
        """Helper to create and initialize a SafeGuardRequestHandler."""
        handler = SafeGuardRequestHandler.__new__(SafeGuardRequestHandler)
        handler.command = method
        handler.path = path
        handler.request_version = "HTTP/1.1"
        handler.close_connection = False

        headers = headers or {}
        body_bytes = b""
        if body is not None:
            body_bytes = json.dumps(body).encode("utf-8")
            headers["Content-Length"] = str(len(body_bytes))
            headers["Content-Type"] = "application/json"

        handler.headers = headers
        handler.rfile = io.BytesIO(body_bytes)
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        return handler

    def test_health_check_get(self):
        handler = self._create_handler("GET", "/api/health")
        handler.do_GET()

        handler.send_response.assert_called_with(200)
        output_bytes = handler.wfile.getvalue()
        payload = json.loads(output_bytes.decode("utf-8"))
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["service"], "safeguard-routing-engine")

    def test_cors_options(self):
        handler = self._create_handler("OPTIONS", "/api/routes/calculate")
        handler.do_OPTIONS()

        handler.send_response.assert_called_with(204)
        handler.send_header.assert_any_call("Access-Control-Allow-Origin", "*")
        handler.send_header.assert_any_call("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def test_calculate_routes_post(self):
        req_body = {
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100},
            "profile": "driving",
            "alternatives": True
        }
        handler = self._create_handler("POST", "/api/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(200)
        output_bytes = handler.wfile.getvalue()
        payload = json.loads(output_bytes.decode("utf-8"))
        self.assertEqual(payload["status"], "success")
        self.assertIn("recommendations", payload)
        self.assertIn("routes", payload)

    def test_calculate_routes_invalid_body(self):
        # Missing destination
        req_body = {"origin": {"latitude": 12.9716, "longitude": 77.5946}}
        handler = self._create_handler("POST", "/api/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(400)
        output_bytes = handler.wfile.getvalue()
        payload = json.loads(output_bytes.decode("utf-8"))
        self.assertEqual(payload["status"], "error")

    def test_not_found_endpoint(self):
        handler = self._create_handler("GET", "/api/unknown_path")
        handler.do_GET()
        handler.send_response.assert_called_with(404)


if __name__ == "__main__":
    unittest.main()
