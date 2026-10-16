"""
Unit Tests for SafeGuard API Server and Request Handler (Member 2).
"""

import io
import json
import os
import threading
import unittest
from unittest.mock import MagicMock
import urllib.request
import urllib.error

from src.api.server import SafeGuardRequestHandler, create_server
from src.models.route import Route
from src.providers.routing_provider import (
    MockRoutingProvider,
    NoRouteFoundError,
    RoutingConnectionError,
    RoutingAPIError
)
from src.services.safety_engine_adapter import SafetyEngineAdapter, SafetyEngineIntegrationError
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

    def test_health_check_alias_get(self):
        handler = self._create_handler("GET", "/health")
        handler.do_GET()

        handler.send_response.assert_called_with(200)
        output_bytes = handler.wfile.getvalue()
        payload = json.loads(output_bytes.decode("utf-8"))
        self.assertEqual(payload["status"], "healthy")

    def test_health_check_post_method_not_allowed(self):
        handler = self._create_handler("POST", "/api/health", body={"data": "test"})
        handler.do_POST()

        handler.send_response.assert_called_with(405)
        handler.send_header.assert_any_call("Allow", "GET, OPTIONS")
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["code"], 405)
        self.assertIn("Method 'POST' not allowed", payload["message"])

    def test_calculate_get_method_not_allowed(self):
        """Visiting calculate endpoint via browser/GET must return 405, not 404."""
        handler = self._create_handler("GET", "/api/routes/calculate")
        handler.do_GET()

        handler.send_response.assert_called_with(405)
        handler.send_header.assert_any_call("Allow", "POST, OPTIONS")
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["code"], 405)
        self.assertIn("Method 'GET' not allowed", payload["message"])
        self.assertIn("Use POST", payload["message"])

    def test_compare_get_method_not_allowed(self):
        """Visiting compare endpoint via GET must return 405, not 404."""
        handler = self._create_handler("GET", "/api/routes/compare")
        handler.do_GET()

        handler.send_response.assert_called_with(405)
        handler.send_header.assert_any_call("Allow", "POST, OPTIONS")
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["code"], 405)

    def test_cors_options(self):
        handler = self._create_handler("OPTIONS", "/api/routes/calculate")
        handler.do_OPTIONS()

        handler.send_response.assert_called_with(204)
        handler.send_header.assert_any_call("Access-Control-Allow-Origin", "*")
        handler.send_header.assert_any_call("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")

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
        self.assertIn("disclaimer", payload)

    def test_calculate_routes_post_trailing_slash(self):
        req_body = {
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100},
            "profile": "driving"
        }
        handler = self._create_handler("POST", "/api/routes/calculate/", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(200)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "success")

    def test_calculate_routes_post_without_api_prefix(self):
        req_body = {
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100},
            "profile": "driving"
        }
        handler = self._create_handler("POST", "/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(200)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "success")

    def test_compare_routes_post(self):
        req_body = {
            "routes": [
                {
                    "route_id": "test_r1",
                    "distance_km": 3.0,
                    "duration_minutes": 10.0,
                    "coordinates": [{"latitude": 12.9716, "longitude": 77.5946}]
                }
            ],
            "preferred_ranking": "balanced"
        }
        handler = self._create_handler("POST", "/api/routes/compare", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(200)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["total_routes_evaluated"], 1)
        self.assertIn("disclaimer", payload)

    def test_compare_routes_invalid_empty_routes(self):
        req_body = {"routes": []}
        handler = self._create_handler("POST", "/api/routes/compare", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(400)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")

    def test_calculate_routes_invalid_body_missing_destination(self):
        req_body = {"origin": {"latitude": 12.9716, "longitude": 77.5946}}
        handler = self._create_handler("POST", "/api/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(400)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")

    def test_calculate_routes_invalid_coordinates(self):
        req_body = {
            "origin": {"latitude": 999.0, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100}
        }
        handler = self._create_handler("POST", "/api/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(400)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")
        self.assertIn("out of bounds", payload["message"].lower())

    def test_calculate_routes_empty_payload(self):
        handler = self._create_handler("POST", "/api/routes/calculate", body=None)
        handler.do_POST()

        handler.send_response.assert_called_with(400)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")

    def test_calculate_routes_malformed_json(self):
        handler = SafeGuardRequestHandler.__new__(SafeGuardRequestHandler)
        handler.command = "POST"
        handler.path = "/api/routes/calculate"
        bad_bytes = b"{ not a valid json"
        handler.headers = {"Content-Length": str(len(bad_bytes)), "Content-Type": "application/json"}
        handler.rfile = io.BytesIO(bad_bytes)
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        handler.do_POST()
        handler.send_response.assert_called_with(400)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")
        self.assertIn("Malformed JSON", payload["message"])

    def test_not_found_endpoint_get(self):
        handler = self._create_handler("GET", "/api/unknown_path")
        handler.do_GET()
        handler.send_response.assert_called_with(404)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")

    def test_not_found_endpoint_post(self):
        handler = self._create_handler("POST", "/api/unknown_path", body={"foo": "bar"})
        handler.do_POST()
        handler.send_response.assert_called_with(404)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["status"], "error")

    def test_unsupported_methods_put_delete(self):
        # PUT on known POST endpoint -> 405
        handler_put = self._create_handler("PUT", "/api/routes/calculate")
        handler_put.do_PUT()
        handler_put.send_response.assert_called_with(405)

        # DELETE on health endpoint -> 405
        handler_del = self._create_handler("DELETE", "/api/health")
        handler_del.do_DELETE()
        handler_del.send_response.assert_called_with(405)

        # PUT on unknown endpoint -> 404
        handler_unknown = self._create_handler("PUT", "/api/nonexistent")
        handler_unknown.do_PUT()
        handler_unknown.send_response.assert_called_with(404)

    def test_provider_no_route_error_returns_404(self):
        mock_service = MagicMock()
        mock_service.calculate_routes.side_effect = NoRouteFoundError("No road path found.")
        SafeGuardRequestHandler.routing_service = mock_service

        req_body = {
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100}
        }
        handler = self._create_handler("POST", "/api/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(404)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["code"], 404)
        self.assertIn("No road path found", payload["message"])

    def test_provider_connection_error_returns_503(self):
        mock_service = MagicMock()
        mock_service.calculate_routes.side_effect = RoutingConnectionError("Connection timed out.")
        SafeGuardRequestHandler.routing_service = mock_service

        req_body = {
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100}
        }
        handler = self._create_handler("POST", "/api/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(503)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["code"], 503)
        self.assertIn("Routing provider unreachable", payload["message"])

    def test_provider_api_error_returns_502(self):
        mock_service = MagicMock()
        mock_service.calculate_routes.side_effect = RoutingAPIError("500 Internal error from OSRM.")
        SafeGuardRequestHandler.routing_service = mock_service

        req_body = {
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100}
        }
        handler = self._create_handler("POST", "/api/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(502)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["code"], 502)
        self.assertIn("Routing provider failure", payload["message"])

    def test_safety_adapter_error_returns_500(self):
        mock_service = MagicMock()
        mock_service.calculate_routes.side_effect = SafetyEngineIntegrationError("Data loading error.")
        SafeGuardRequestHandler.routing_service = mock_service

        req_body = {
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100}
        }
        handler = self._create_handler("POST", "/api/routes/calculate", body=req_body)
        handler.do_POST()

        handler.send_response.assert_called_with(500)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["code"], 500)
        self.assertIn("Safety Engine integration error", payload["message"])


class TestAPIServerLiveSocketIntegration(unittest.TestCase):
    """
    Tests live TCP socket integration using create_server on ephemeral port.
    Ensures complete end-to-end HTTP request/response pipeline functions without external network dependencies.
    """

    @classmethod
    def setUpClass(cls):
        route1 = Route("r_sock_1", distance_km=2.0, duration_minutes=7.0, coordinates=[{"latitude": 12.97, "longitude": 77.59}])
        route2 = Route("r_sock_2", distance_km=2.5, duration_minutes=9.0, coordinates=[{"latitude": 12.97, "longitude": 77.59}])
        provider = MockRoutingProvider(routes_to_return=[route1, route2])
        adapter = SafetyEngineAdapter(data_dir="data/raw")
        service = RoutingService(provider=provider, adapter=adapter)

        # Port 0 selects an available ephemeral port
        cls.server = create_server(host="127.0.0.1", port=0, routing_service=service)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_live_socket_health_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            self.assertEqual(resp.getcode(), 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "healthy")

    def test_live_socket_get_on_calculate_returns_405(self):
        """Simulates opening http://127.0.0.1:8000/api/routes/calculate in browser -> must return 405."""
        url = f"http://127.0.0.1:{self.port}/api/routes/calculate"
        req = urllib.request.Request(url, method="GET")
        try:
            urllib.request.urlopen(req, timeout=3.0)
            self.fail("Expected HTTP 405 error")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 405)
            data = json.loads(exc.read().decode("utf-8"))
            self.assertEqual(data["code"], 405)
            self.assertIn("Method 'GET' not allowed", data["message"])

    def test_live_socket_post_calculate_returns_200(self):
        url = f"http://127.0.0.1:{self.port}/api/routes/calculate"
        body = json.dumps({
            "origin": {"latitude": 12.9716, "longitude": 77.5946},
            "destination": {"latitude": 12.9850, "longitude": 77.6100},
            "profile": "driving",
            "alternatives": True
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            self.assertEqual(resp.getcode(), 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["total_routes_found"], 2)
            self.assertIn("disclaimer", data)


class TestAdminKey(unittest.TestCase):
    """Tests for Bug 5: _check_admin_key decision matrix."""

    REVIEW_PATH = "/api/reports/rep_test/review"
    REAL_KEY = "super-secret-test-key-abc123"

    def _create_review_handler(self, provided_key=None, body=None):
        """Helper: builds a PATCH handler for the review endpoint."""
        handler = SafeGuardRequestHandler.__new__(SafeGuardRequestHandler)
        handler.command = "PATCH"
        handler.path = self.REVIEW_PATH
        handler.request_version = "HTTP/1.1"
        handler.close_connection = False

        body_bytes = b""
        raw_headers = {"Content-Type": "application/json"}
        if body is not None:
            body_bytes = json.dumps(body).encode("utf-8")
            raw_headers["Content-Length"] = str(len(body_bytes))
        if provided_key is not None:
            raw_headers["X-Admin-Key"] = provided_key

        handler.headers = raw_headers
        handler.rfile = io.BytesIO(body_bytes)
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        return handler

    def setUp(self):
        # Capture and clean relevant env vars before each test
        self._orig_key = os.environ.pop("SAFEGUARD_ADMIN_KEY", None)
        self._orig_dev = os.environ.pop("SAFEGUARD_ALLOW_INSECURE_ADMIN", None)

    def tearDown(self):
        # Restore env state after each test
        if self._orig_key is not None:
            os.environ["SAFEGUARD_ADMIN_KEY"] = self._orig_key
        else:
            os.environ.pop("SAFEGUARD_ADMIN_KEY", None)
        if self._orig_dev is not None:
            os.environ["SAFEGUARD_ALLOW_INSECURE_ADMIN"] = self._orig_dev
        else:
            os.environ.pop("SAFEGUARD_ALLOW_INSECURE_ADMIN", None)

    def test_no_key_set_returns_503(self):
        """Admin endpoint is disabled (503) when SAFEGUARD_ADMIN_KEY is unset."""
        # Env already cleared in setUp
        handler = self._create_review_handler()
        result = handler._check_admin_key()

        self.assertFalse(result)
        handler.send_response.assert_called_with(503)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["code"], 503)
        self.assertIn("disabled", payload["message"])

    def test_placeholder_key_returns_503(self):
        """Placeholder value 'change-me-before-deploying' is treated like no key → 503."""
        os.environ["SAFEGUARD_ADMIN_KEY"] = "change-me-before-deploying"
        handler = self._create_review_handler()
        result = handler._check_admin_key()

        self.assertFalse(result)
        handler.send_response.assert_called_with(503)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["code"], 503)

    def test_wrong_key_returns_401(self):
        """A real key is configured but the client sends the wrong value → 401."""
        os.environ["SAFEGUARD_ADMIN_KEY"] = self.REAL_KEY
        handler = self._create_review_handler(provided_key="completely-wrong-key")
        result = handler._check_admin_key()

        self.assertFalse(result)
        handler.send_response.assert_called_with(401)
        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(payload["code"], 401)
        self.assertIn("Unauthorized", payload["message"])

    def test_correct_key_returns_true(self):
        """Matching key passes through without sending any error response."""
        os.environ["SAFEGUARD_ADMIN_KEY"] = self.REAL_KEY
        handler = self._create_review_handler(provided_key=self.REAL_KEY)
        result = handler._check_admin_key()

        self.assertTrue(result)
        # No error response must have been written
        self.assertEqual(handler.wfile.getvalue(), b"")

    def test_dev_flag_allows_access_with_no_key(self):
        """SAFEGUARD_ALLOW_INSECURE_ADMIN=1 grants access even when no key is set."""
        # No SAFEGUARD_ADMIN_KEY set
        os.environ["SAFEGUARD_ALLOW_INSECURE_ADMIN"] = "1"
        handler = self._create_review_handler()
        result = handler._check_admin_key()

        self.assertTrue(result)
        # No error response must have been written
        self.assertEqual(handler.wfile.getvalue(), b"")


if __name__ == "__main__":
    unittest.main()
