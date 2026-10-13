"""
SafeGuard HTTP API Server (Member 2).
Provides lightweight REST endpoints with full CORS support for the React SafeRoute frontend:
- GET  /api/health            -> System health and provider status
- POST /api/routes/calculate  -> Calculate real routes, compute safety score, and rank
- POST /api/routes/compare    -> Compare and rank pre-computed or custom routes
"""

import json
import logging
import os
try:
    from http.server import ThreadingHTTPServer as DefaultHTTPServer
except ImportError:
    from http.server import HTTPServer as DefaultHTTPServer
from http.server import BaseHTTPRequestHandler
import sys
import urllib.parse
from typing import Dict, Any, Optional

# Ensure project root is in sys.path when running script directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.services.routing_service import RoutingService
from src.providers.routing_provider import RoutingError, RoutingConnectionError, NoRouteFoundError
from src.services.safety_engine_adapter import SafetyEngineIntegrationError

logger = logging.getLogger(__name__)

# Canonical endpoint definitions
HEALTH_PATHS = {"/health", "/api/health"}
CALCULATE_PATHS = {"/routes/calculate", "/api/routes/calculate"}
COMPARE_PATHS = {"/routes/compare", "/api/routes/compare"}


class SafeGuardRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler serving SafeGuard navigation API requests.
    """

    routing_service: Optional[RoutingService] = None

    def _normalize_path(self) -> str:
        """Parses and normalizes the request URL path (stripping trailing slash)."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.strip()
        if len(path) > 1:
            path = path.rstrip("/")
        return path

    def _set_headers(
        self,
        status_code: int = 200,
        content_type: str = "application/json",
        extra_headers: Optional[Dict[str, str]] = None
    ):
        """Sets HTTP response headers including essential CORS headers for React frontend."""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if extra_headers:
            for key, val in extra_headers.items():
                self.send_header(key, val)
        self.end_headers()

    def _send_json_response(
        self,
        status_code: int,
        payload: Any,
        extra_headers: Optional[Dict[str, str]] = None
    ):
        """Sends a JSON response with explicit Content-Length and CORS headers."""
        response_bytes = json.dumps(payload, indent=2).encode("utf-8")
        headers = {
            "Content-Length": str(len(response_bytes))
        }
        if extra_headers:
            headers.update(extra_headers)
        self._set_headers(status_code, content_type="application/json", extra_headers=headers)
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        """Handles CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        """Handles GET requests (e.g., /api/health)."""
        path = self._normalize_path()

        if path in HEALTH_PATHS:
            payload = {
                "status": "healthy",
                "service": "safeguard-routing-engine",
                "version": "1.0.0",
                "routing_provider": "OSRM"
            }
            self._send_json_response(200, payload)
        elif path in CALCULATE_PATHS:
            self._send_error_response(
                405,
                f"Method 'GET' not allowed for '{path}'. Use POST to calculate routes.",
                extra_headers={"Allow": "POST, OPTIONS"}
            )
        elif path in COMPARE_PATHS:
            self._send_error_response(
                405,
                f"Method 'GET' not allowed for '{path}'. Use POST to compare routes.",
                extra_headers={"Allow": "POST, OPTIONS"}
            )
        else:
            self._send_error_response(404, f"Endpoint '{path}' not found.")

    def do_POST(self):
        """Handles POST requests (/api/routes/calculate and /api/routes/compare)."""
        path = self._normalize_path()

        if path in HEALTH_PATHS:
            self._send_error_response(
                405,
                f"Method 'POST' not allowed for '{path}'. Use GET for health check.",
                extra_headers={"Allow": "GET, OPTIONS"}
            )
            return

        if path not in CALCULATE_PATHS and path not in COMPARE_PATHS:
            self._send_error_response(404, f"Endpoint '{path}' not found.")
            return

        # Read and validate request body
        try:
            content_length_header = self.headers.get("Content-Length")
            if not content_length_header:
                self._send_error_response(400, "Missing Content-Length header or empty request body.")
                return
            content_length = int(content_length_header)
            if content_length <= 0:
                self._send_error_response(400, "Request body cannot be empty. JSON payload required.")
                return
            body_bytes = self.rfile.read(content_length)
            if not body_bytes:
                self._send_error_response(400, "Request body is empty. JSON payload required.")
                return
            body = json.loads(body_bytes.decode("utf-8"))
            if not isinstance(body, dict):
                self._send_error_response(400, "JSON request body must be an object.")
                return
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error_response(400, f"Malformed JSON request body: {exc}")
            return
        except Exception as exc:
            self._send_error_response(400, f"Error reading request body: {exc}")
            return

        service = self.routing_service or RoutingService()

        try:
            if path in CALCULATE_PATHS:
                preferred_ranking = body.get("preferred_ranking", "balanced")
                result = service.calculate_routes(body, preferred_ranking=preferred_ranking)
                self._send_json_response(200, result)

            elif path in COMPARE_PATHS:
                routes_data = body.get("routes", [])
                if not routes_data or not isinstance(routes_data, list):
                    self._send_error_response(
                        400,
                        "Payload for /api/routes/compare requires a non-empty 'routes' array."
                    )
                    return
                preferred_ranking = body.get("preferred_ranking", "balanced")
                result = service.compare_custom_routes(routes_data, preferred_ranking=preferred_ranking)
                self._send_json_response(200, result)

        except (ValueError, TypeError) as exc:
            self._send_error_response(400, str(exc))
        except NoRouteFoundError as exc:
            self._send_error_response(404, str(exc))
        except RoutingConnectionError as exc:
            self._send_error_response(503, f"Routing provider unreachable: {exc}")
        except RoutingError as exc:
            self._send_error_response(502, f"Routing provider failure: {exc}")
        except SafetyEngineIntegrationError as exc:
            self._send_error_response(500, f"Safety Engine integration error: {exc}")
        except Exception as exc:
            logger.exception("Unexpected server error")
            self._send_error_response(500, f"Internal server error: {exc}")

    def do_PUT(self):
        """Rejects PUT with proper 405 or 404."""
        self._handle_unsupported_method("PUT")

    def do_DELETE(self):
        """Rejects DELETE with proper 405 or 404."""
        self._handle_unsupported_method("DELETE")

    def _handle_unsupported_method(self, method: str):
        path = self._normalize_path()
        if path in HEALTH_PATHS:
            self._send_error_response(
                405,
                f"Method '{method}' not allowed for '{path}'.",
                extra_headers={"Allow": "GET, OPTIONS"}
            )
        elif path in CALCULATE_PATHS or path in COMPARE_PATHS:
            self._send_error_response(
                405,
                f"Method '{method}' not allowed for '{path}'.",
                extra_headers={"Allow": "POST, OPTIONS"}
            )
        else:
            self._send_error_response(404, f"Endpoint '{path}' not found.")

    def _send_error_response(
        self,
        status_code: int,
        message: str,
        extra_headers: Optional[Dict[str, str]] = None
    ):
        """Sends uniform JSON error response."""
        error_payload = {
            "status": "error",
            "code": status_code,
            "message": message
        }
        self._send_json_response(status_code, error_payload, extra_headers=extra_headers)

    def log_message(self, format, *args):
        """Silences default noisy stderr logging in favor of python logging."""
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)


def create_server(host: str = "127.0.0.1", port: int = 8000, routing_service: Optional[RoutingService] = None) -> DefaultHTTPServer:
    """Factory creating an instance of HTTPServer configured with SafeGuardRequestHandler."""
    SafeGuardRequestHandler.routing_service = routing_service or RoutingService()
    DefaultHTTPServer.allow_reuse_address = True
    return DefaultHTTPServer((host, port), SafeGuardRequestHandler)


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Runs the API server until interrupted."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    server = create_server(host=host, port=port)
    print(f"==================================================", flush=True)
    print(f" SafeGuard Routing & Safety API Server (Member 2)", flush=True)
    print(f" Running on http://{host}:{port}", flush=True)
    print(f" Health check:  GET  http://{host}:{port}/api/health", flush=True)
    print(f" Calculate:     POST http://{host}:{port}/api/routes/calculate", flush=True)
    print(f" Compare:       POST http://{host}:{port}/api/routes/compare", flush=True)
    print(f" CORS enabled for React SafeRoute frontend", flush=True)
    print(f" Press Ctrl+C to terminate.", flush=True)
    print(f"==================================================", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...", flush=True)
        server.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port=port)
