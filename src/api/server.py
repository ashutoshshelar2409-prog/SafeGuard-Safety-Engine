"""
SafeGuard HTTP API Server (Member 2 & Member 4).
Provides lightweight REST endpoints with full CORS support for the React SafeRoute frontend:
- GET   /api/health               -> System health and provider status
- POST  /api/routes/calculate     -> Calculate real routes, compute safety score, and rank
- POST  /api/routes/compare       -> Compare and rank pre-computed or custom routes
- POST  /api/reports              -> Submit community incident report with AI classification
- GET   /api/reports              -> List public community reports with spatial/status filters
- GET   /api/reports/summary      -> Get aggregate report stats, category counts, and verified status
- GET   /api/reports/{id}         -> View individual public report by ID
- POST  /api/reports/{id}/review  -> Update report review status (verified, rejected, duplicate)
- PATCH /api/reports/{id}/review  -> Update report review status (verified, rejected, duplicate)
"""

import json
import logging
import os
import re
import tempfile
try:
    from http.server import ThreadingHTTPServer as DefaultHTTPServer
except ImportError:
    from http.server import HTTPServer as DefaultHTTPServer
from http.server import BaseHTTPRequestHandler
import sys
import urllib.parse
from typing import Dict, Any, Optional, List

# Ensure project root is in sys.path when running script directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.services.routing_service import RoutingService
from src.providers.routing_provider import RoutingError, RoutingConnectionError, NoRouteFoundError
from src.services.safety_engine_adapter import SafetyEngineIntegrationError
from src.services.community_service import CommunityReportService
from src.processing.report_validation import ReportValidationError

logger = logging.getLogger(__name__)

# Canonical endpoint definitions
HEALTH_PATHS = {"/health", "/api/health"}
CALCULATE_PATHS = {"/routes/calculate", "/api/routes/calculate"}
COMPARE_PATHS = {"/routes/compare", "/api/routes/compare"}
REPORTS_PATHS = {"/reports", "/api/reports"}
REPORTS_SUMMARY_PATHS = {"/reports/summary", "/api/reports/summary"}

REPORT_ITEM_PATTERN = re.compile(r"^/(?:api/)?reports/([a-zA-Z0-9_\-]+)$")
REPORT_REVIEW_PATTERN = re.compile(r"^/(?:api/)?reports/([a-zA-Z0-9_\-]+)/review$")


class SafeGuardRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler serving SafeGuard navigation and community incident API requests.
    """

    routing_service: Optional[RoutingService] = None
    report_service: Optional[CommunityReportService] = None

    def _normalize_path(self) -> str:
        """Parses and normalizes the request URL path (stripping trailing slash)."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.strip()
        if len(path) > 1:
            path = path.rstrip("/")
        return path

    def _get_query_params(self) -> Dict[str, str]:
        """Parses URL query parameters into a flat dictionary."""
        parsed_url = urllib.parse.urlparse(self.path)
        raw_params = urllib.parse.parse_qs(parsed_url.query)
        return {k: v[0] for k, v in raw_params.items() if v}

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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Key")
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Key")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # Bug 4 fix: maximum allowed request body size (100 KB)
    _MAX_BODY_BYTES: int = 100 * 1024  # 100 KB

    def _read_json_body(self) -> Optional[Dict[str, Any]]:
        """Reads and parses JSON request body, sending 400 response on failure.

        Bug 4 fix: Enforces a 100 KB cap on Content-Length before reading any
        bytes, preventing large bodies from being fully buffered into memory.
        """
        try:
            content_length_header = self.headers.get("Content-Length")
            if not content_length_header:
                self._send_error_response(400, "Missing Content-Length header or empty request body.")
                return None
            content_length = int(content_length_header)
            if content_length <= 0:
                self._send_error_response(400, "Request body cannot be empty. JSON payload required.")
                return None
            # Bug 4 fix: reject bodies that exceed the size cap before reading
            if content_length > self._MAX_BODY_BYTES:
                self._send_error_response(
                    400,
                    f"Request body too large ({content_length} bytes). "
                    f"Maximum allowed size is {self._MAX_BODY_BYTES} bytes (100 KB)."
                )
                return None
            body_bytes = self.rfile.read(content_length)
            if not body_bytes:
                self._send_error_response(400, "Request body is empty. JSON payload required.")
                return None
            body = json.loads(body_bytes.decode("utf-8"))
            if not isinstance(body, dict):
                self._send_error_response(400, "JSON request body must be an object.")
                return None
            return body
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_error_response(400, f"Malformed JSON request body: {exc}")
            return None
        except Exception as exc:
            self._send_error_response(400, f"Error reading request body: {exc}")
            return None

    def do_GET(self):
        """Handles GET requests."""
        path = self._normalize_path()
        params = self._get_query_params()
        report_svc = self.report_service or CommunityReportService()

        # 1. Health check
        if path in HEALTH_PATHS:
            payload = {
                "status": "healthy",
                "service": "safeguard-routing-engine",
                "version": "1.0.0",
                "routing_provider": "OSRM",
                "modules": {
                    "routing": "active",
                    "safety_scoring": "active",
                    "community_reports": "active"
                }
            }
            self._send_json_response(200, payload)
            return

        # 2. Method-not-allowed checks for POST-only route endpoints
        if path in CALCULATE_PATHS:
            self._send_error_response(
                405,
                f"Method 'GET' not allowed for '{path}'. Use POST to calculate routes.",
                extra_headers={"Allow": "POST, OPTIONS"}
            )
            return

        if path in COMPARE_PATHS:
            self._send_error_response(
                405,
                f"Method 'GET' not allowed for '{path}'. Use POST to compare routes.",
                extra_headers={"Allow": "POST, OPTIONS"}
            )
            return

        # 3. Community report summary
        # Bug 1 fix: wrap float parsing so invalid query params return 400
        if path in REPORTS_SUMMARY_PATHS:
            try:
                lat = float(params["lat"]) if "lat" in params else None
                lon = float(params["lon"]) if "lon" in params else None
                radius_km = float(params["radius_km"]) if "radius_km" in params else None
            except (ValueError, TypeError) as exc:
                self._send_error_response(400, f"Invalid query parameter value: {exc}")
                return
            summary = report_svc.get_summary(lat=lat, lon=lon, radius_km=radius_km)
            self._send_json_response(200, {"status": "success", "summary": summary})
            return

        # 4. Community reports list
        # Bug 1 fix: wrap float parsing so invalid query params return 400
        if path in REPORTS_PATHS:
            status = params.get("status")
            category = params.get("category")
            try:
                lat = float(params["lat"]) if "lat" in params else None
                lon = float(params["lon"]) if "lon" in params else None
                radius_km = float(params["radius_km"]) if "radius_km" in params else None
            except (ValueError, TypeError) as exc:
                self._send_error_response(400, f"Invalid query parameter value: {exc}")
                return
            time_window = params.get("time_window")
            since_iso = params.get("since")

            reports = report_svc.get_public_reports(
                status=status,
                category=category,
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                time_window=time_window,
                since_iso=since_iso
            )
            self._send_json_response(200, {
                "status": "success",
                "count": len(reports),
                "reports": reports,
                "disclaimer": "Community reports are crowdsourced user observations and do not represent confirmed crime statistics."
            })
            return

        # 5. Report review endpoint rejects GET with 405
        review_match = REPORT_REVIEW_PATTERN.match(path)
        if review_match:
            self._send_error_response(
                405,
                f"Method 'GET' not allowed for '{path}'. Use POST or PATCH to update review status.",
                extra_headers={"Allow": "POST, PATCH, OPTIONS"}
            )
            return

        # 6. Single report lookup by ID
        item_match = REPORT_ITEM_PATTERN.match(path)
        if item_match:
            report_id = item_match.group(1)
            report = report_svc.get_report(report_id)
            if not report:
                self._send_error_response(404, f"Report '{report_id}' not found.")
                return
            self._send_json_response(200, {"status": "success", "report": report})
            return

        self._send_error_response(404, f"Endpoint '{path}' not found.")

    def do_POST(self):
        """Handles POST requests."""
        path = self._normalize_path()

        # Disallow POST on GET-only endpoints
        if path in HEALTH_PATHS:
            self._send_error_response(
                405,
                f"Method 'POST' not allowed for '{path}'. Use GET for health check.",
                extra_headers={"Allow": "GET, OPTIONS"}
            )
            return

        if path in REPORTS_SUMMARY_PATHS:
            self._send_error_response(
                405,
                f"Method 'POST' not allowed for '{path}'. Use GET for report summary.",
                extra_headers={"Allow": "GET, OPTIONS"}
            )
            return

        # Check if route is a recognized POST endpoint
        is_calc = path in CALCULATE_PATHS
        is_compare = path in COMPARE_PATHS
        is_reports = path in REPORTS_PATHS
        review_match = REPORT_REVIEW_PATTERN.match(path)

        if not (is_calc or is_compare or is_reports or review_match):
            # Check if this was a GET on single report item
            if REPORT_ITEM_PATTERN.match(path):
                self._send_error_response(
                    405,
                    f"Method 'POST' not allowed for '{path}'. Use GET to retrieve report details.",
                    extra_headers={"Allow": "GET, OPTIONS"}
                )
                return
            self._send_error_response(404, f"Endpoint '{path}' not found.")
            return

        # Read JSON body
        body = self._read_json_body()
        if body is None:
            return

        # 1. Route calculation
        if is_calc:
            service = self.routing_service or RoutingService()
            try:
                preferred_ranking = body.get("preferred_ranking", "balanced")
                result = service.calculate_routes(body, preferred_ranking=preferred_ranking)
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
                logger.exception("Safety Engine integration error")
                self._send_error_response(500, "Safety Engine integration error. Check server logs.")
            except Exception as exc:
                logger.exception("Unexpected server error")
                self._send_error_response(500, "Internal server error. Check server logs.")
            return

        # 2. Route comparison
        if is_compare:
            service = self.routing_service or RoutingService()
            try:
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
                logger.exception("Safety Engine integration error")
                self._send_error_response(500, "Safety Engine integration error. Check server logs.")
            except Exception as exc:
                logger.exception("Unexpected server error")
                self._send_error_response(500, "Internal server error. Check server logs.")
            return

        # 3. Community report submission
        if is_reports:
            report_svc = self.report_service or CommunityReportService()
            try:
                report, meta = report_svc.submit_report(body)
                response_payload = {
                    "status": "success",
                    "message": "Community incident report submitted successfully.",
                    "report": report.to_public_dict(),
                    "metadata": meta
                }
                self._send_json_response(201, response_payload)
            except ReportValidationError as exc:
                self._send_error_response(400, str(exc), errors=exc.errors)
            except Exception as exc:
                logger.exception("Unexpected error in report submission")
                self._send_error_response(500, "Internal server error. Check server logs.")
            return

        # 4. Review status update
        # Bug 3 fix: require X-Admin-Key header to protect review integrity
        if review_match:
            if not self._check_admin_key():
                return
            report_svc = self.report_service or CommunityReportService()
            report_id = review_match.group(1)
            new_status = body.get("status") or body.get("review_status")
            if not new_status:
                self._send_error_response(400, "Missing required 'status' field in review payload.")
                return
            try:
                updated = report_svc.update_review_status(report_id, str(new_status))
                if not updated:
                    self._send_error_response(404, f"Report '{report_id}' not found.")
                    return
                self._send_json_response(200, {
                    "status": "success",
                    "message": f"Report '{report_id}' review status updated to '{new_status}'.",
                    "report": updated
                })
            except ReportValidationError as exc:
                self._send_error_response(400, str(exc), errors=exc.errors)
            except Exception as exc:
                logger.exception("Unexpected error updating report review")
                self._send_error_response(500, "Internal server error. Check server logs.")
            return

    def do_PATCH(self):
        """Handles PATCH requests (e.g. for /api/reports/{id}/review)."""
        path = self._normalize_path()
        review_match = REPORT_REVIEW_PATTERN.match(path)

        if not review_match:
            self._handle_unsupported_method("PATCH")
            return

        # Bug 3 fix: require X-Admin-Key header before reading body
        if not self._check_admin_key():
            return

        body = self._read_json_body()
        if body is None:
            return

        report_svc = self.report_service or CommunityReportService()
        report_id = review_match.group(1)
        new_status = body.get("status") or body.get("review_status")
        if not new_status:
            self._send_error_response(400, "Missing required 'status' field in review payload.")
            return

        try:
            updated = report_svc.update_review_status(report_id, str(new_status))
            if not updated:
                self._send_error_response(404, f"Report '{report_id}' not found.")
                return
            self._send_json_response(200, {
                "status": "success",
                "message": f"Report '{report_id}' review status updated to '{new_status}'.",
                "report": updated
            })
        except ReportValidationError as exc:
            self._send_error_response(400, str(exc), errors=exc.errors)
        except Exception as exc:
            logger.exception("Unexpected error updating report review")
            self._send_error_response(500, "Internal server error. Check server logs.")

    def do_PUT(self):
        """Rejects PUT with proper 405 or 404."""
        self._handle_unsupported_method("PUT")

    def do_DELETE(self):
        """Rejects DELETE with proper 405 or 404."""
        self._handle_unsupported_method("DELETE")

    def _handle_unsupported_method(self, method: str):
        path = self._normalize_path()
        if path in HEALTH_PATHS or path in REPORTS_SUMMARY_PATHS:
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
        elif path in REPORTS_PATHS:
            self._send_error_response(
                405,
                f"Method '{method}' not allowed for '{path}'.",
                extra_headers={"Allow": "GET, POST, OPTIONS"}
            )
        elif REPORT_REVIEW_PATTERN.match(path):
            self._send_error_response(
                405,
                f"Method '{method}' not allowed for '{path}'.",
                extra_headers={"Allow": "POST, PATCH, OPTIONS"}
            )
        elif REPORT_ITEM_PATTERN.match(path):
            self._send_error_response(
                405,
                f"Method '{method}' not allowed for '{path}'.",
                extra_headers={"Allow": "GET, OPTIONS"}
            )
        else:
            self._send_error_response(404, f"Endpoint '{path}' not found.")

    def _check_admin_key(self) -> bool:
        """Bug 3 fix: validates X-Admin-Key header against SAFEGUARD_ADMIN_KEY env var.

        Returns True if the key is valid (or no key is configured, for local dev).
        Sends a 401 response and returns False when the key is missing or wrong.
        """
        required_key = os.environ.get("SAFEGUARD_ADMIN_KEY", "").strip()
        if not required_key:
            # No key configured — allow (useful for local dev without .env)
            logger.warning(
                "SAFEGUARD_ADMIN_KEY is not set. Admin endpoints are unprotected. "
                "Set this env var before deploying."
            )
            return True
        provided_key = self.headers.get("X-Admin-Key", "").strip()
        if provided_key != required_key:
            self._send_error_response(
                401,
                "Unauthorized. A valid 'X-Admin-Key' header is required for this endpoint."
            )
            return False
        return True

    def _send_error_response(
        self,
        status_code: int,
        message: str,
        extra_headers: Optional[Dict[str, str]] = None,
        errors: Optional[List[str]] = None
    ):
        """Sends uniform JSON error response."""
        error_payload = {
            "status": "error",
            "code": status_code,
            "message": message
        }
        if errors:
            error_payload["errors"] = errors
        self._send_json_response(status_code, error_payload, extra_headers=extra_headers)

    def log_message(self, format, *args):
        """Silences default noisy stderr logging in favor of python logging."""
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    routing_service: Optional[RoutingService] = None,
    report_service: Optional[CommunityReportService] = None
) -> DefaultHTTPServer:
    """Factory creating an instance of HTTPServer configured with SafeGuardRequestHandler."""
    SafeGuardRequestHandler.routing_service = routing_service or RoutingService()
    SafeGuardRequestHandler.report_service = report_service or CommunityReportService()
    DefaultHTTPServer.allow_reuse_address = True
    return DefaultHTTPServer((host, port), SafeGuardRequestHandler)


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Runs the API server until interrupted."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    server = create_server(host=host, port=port)
    print(f"==================================================", flush=True)
    print(f" SafeGuard Routing & Safety API Server (Members 2 & 4)", flush=True)
    print(f" Running on http://{host}:{port}", flush=True)
    print(f" Health check:  GET   http://{host}:{port}/api/health", flush=True)
    print(f" Calculate:     POST  http://{host}:{port}/api/routes/calculate", flush=True)
    print(f" Compare:       POST  http://{host}:{port}/api/routes/compare", flush=True)
    print(f" Submit Report: POST  http://{host}:{port}/api/reports", flush=True)
    print(f" List Reports:  GET   http://{host}:{port}/api/reports", flush=True)
    print(f" Summary:       GET   http://{host}:{port}/api/reports/summary", flush=True)
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
