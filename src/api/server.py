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
from http.server import HTTPServer, BaseHTTPRequestHandler
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


class SafeGuardRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler serving SafeGuard navigation API requests.
    """

    routing_service: Optional[RoutingService] = None

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json"):
        """Sets HTTP response headers including essential CORS headers for React frontend."""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        """Handles CORS preflight requests."""
        self._set_headers(204)

    def do_GET(self):
        """Handles GET requests (e.g., /api/health)."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/health", "/api/health"):
            payload = {
                "status": "healthy",
                "service": "safeguard-routing-engine",
                "version": "1.0.0",
                "routing_provider": "OSRM"
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        else:
            self._send_error_response(404, f"Endpoint '{path}' not found.")

    def do_POST(self):
        """Handles POST requests (/api/routes/calculate and /api/routes/compare)."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Read request body
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except json.JSONDecodeError as exc:
            self._send_error_response(400, f"Malformed JSON request body: {exc}")
            return
        except Exception as exc:
            self._send_error_response(400, f"Error reading request body: {exc}")
            return

        service = self.routing_service or RoutingService()

        try:
            if path == "/api/routes/calculate":
                preferred_ranking = body.get("preferred_ranking", "balanced")
                result = service.calculate_routes(body, preferred_ranking=preferred_ranking)
                self._set_headers(200)
                self.wfile.write(json.dumps(result, indent=2).encode("utf-8"))

            elif path == "/api/routes/compare":
                routes_data = body.get("routes", [])
                preferred_ranking = body.get("preferred_ranking", "balanced")
                result = service.compare_custom_routes(routes_data, preferred_ranking=preferred_ranking)
                self._set_headers(200)
                self.wfile.write(json.dumps(result, indent=2).encode("utf-8"))

            else:
                self._send_error_response(404, f"Endpoint '{path}' not found.")

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

    def _send_error_response(self, status_code: int, message: str):
        """Sends uniform JSON error response."""
        self._set_headers(status_code)
        error_payload = {
            "status": "error",
            "code": status_code,
            "message": message
        }
        self.wfile.write(json.dumps(error_payload).encode("utf-8"))

    def log_message(self, format, *args):
        """Silences default noisy stderr logging in favor of python logging."""
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)


def create_server(host: str = "127.0.0.1", port: int = 8000, routing_service: Optional[RoutingService] = None) -> HTTPServer:
    """Factory creating an instance of HTTPServer configured with SafeGuardRequestHandler."""
    SafeGuardRequestHandler.routing_service = routing_service or RoutingService()
    return HTTPServer((host, port), SafeGuardRequestHandler)


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Runs the API server until interrupted."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    server = create_server(host=host, port=port)
    print(f"==================================================", flush=True)
    print(f" SafeGuard Routing & Safety API Server (Member 2)", flush=True)
    print(f" Running on http://{host}:{port}", flush=True)
    print(f" Health check: http://{host}:{port}/api/health", flush=True)
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
