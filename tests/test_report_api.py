"""
Integration tests for SafeGuard Community Reporting API Endpoints (Member 4).
"""

import io
import json
import os
import unittest
from unittest.mock import MagicMock

from src.api.server import SafeGuardRequestHandler
from src.models.community_report import IncidentCategory, ReviewStatus
from src.services.community_service import CommunityReportService
from src.storage.report_store import ReportStore


class TestReportAPI(unittest.TestCase):

    def setUp(self):
        # Configure isolated clean in-memory report store for testing
        self.store = ReportStore(persistence_file=None, seed_file=None)
        self.service = CommunityReportService(store=self.store)
        SafeGuardRequestHandler.report_service = self.service
        # Review endpoints require an admin key (Bug 5). Use dev bypass for tests.
        self._orig_allow_insecure = os.environ.get("SAFEGUARD_ALLOW_INSECURE_ADMIN")
        os.environ["SAFEGUARD_ALLOW_INSECURE_ADMIN"] = "1"

    def tearDown(self):
        # Restore env var to its original state
        if self._orig_allow_insecure is None:
            os.environ.pop("SAFEGUARD_ALLOW_INSECURE_ADMIN", None)
        else:
            os.environ["SAFEGUARD_ALLOW_INSECURE_ADMIN"] = self._orig_allow_insecure

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

    def test_submit_report_success_201(self):
        payload = {
            "description": "Pitch dark alley with broken streetlights near metro station",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "severity": 2
        }
        handler = self._create_handler("POST", "/api/reports", body=payload)
        handler.do_POST()

        handler.send_response.assert_called_with(201)
        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["report"]["category"], IncidentCategory.POOR_LIGHTING.value)
        self.assertEqual(res["report"]["review_status"], ReviewStatus.PENDING.value)
        self.assertFalse(res["report"]["is_verified"])
        self.assertIn("disclaimer", res["report"])

    def test_submit_report_validation_failure_400(self):
        # Invalid coordinate (lat = 95)
        payload = {
            "description": "Broken road barrier",
            "latitude": 95.0,
            "longitude": 77.5946
        }
        handler = self._create_handler("POST", "/api/reports", body=payload)
        handler.do_POST()

        handler.send_response.assert_called_with(400)
        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["code"], 400)
        self.assertTrue(any("out of range" in err for err in res["errors"]))

    def test_submit_report_malformed_json_400(self):
        handler = self._create_handler("POST", "/api/reports")
        handler.rfile = io.BytesIO(b"{bad json:")
        handler.headers = {"Content-Length": "10"}
        handler.do_POST()

        handler.send_response.assert_called_with(400)
        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res["status"], "error")
        self.assertIn("Malformed JSON", res["message"])

    def test_list_reports_get_200(self):
        # Seed 1 report
        self.service.submit_report({
            "description": "Open manhole on pedestrian path",
            "category": "infrastructure_problem",
            "latitude": 12.9716,
            "longitude": 77.5946
        })

        handler = self._create_handler("GET", "/api/reports")
        handler.do_GET()

        handler.send_response.assert_called_with(200)
        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["reports"][0]["category"], IncidentCategory.INFRASTRUCTURE_PROBLEM.value)

    def test_reports_summary_get_200(self):
        self.service.submit_report({
            "description": "Harassment near park entrance",
            "category": "harassment",
            "latitude": 12.9716,
            "longitude": 77.5946
        })

        handler = self._create_handler("GET", "/api/reports/summary")
        handler.do_GET()

        handler.send_response.assert_called_with(200)
        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res["status"], "success")
        summary = res["summary"]
        self.assertEqual(summary["total_reports"], 1)
        self.assertEqual(summary["verification_summary"]["unverified_count"], 1)
        self.assertIn("disclaimer", summary)

    def test_single_report_get_200_and_404(self):
        rep, _ = self.service.submit_report({
            "description": "Deep pothole causing accidents",
            "category": "road_hazard",
            "latitude": 12.9716,
            "longitude": 77.5946
        })

        # Exists
        handler = self._create_handler("GET", f"/api/reports/{rep.report_id}")
        handler.do_GET()
        handler.send_response.assert_called_with(200)

        # Not found
        handler404 = self._create_handler("GET", "/api/reports/rep_nonexistent_99")
        handler404.do_GET()
        handler404.send_response.assert_called_with(404)

    def test_update_review_status_post_and_patch(self):
        rep, _ = self.service.submit_report({
            "description": "Suspicious group casing cars",
            "category": "suspicious_activity",
            "latitude": 12.9716,
            "longitude": 77.5946
        })

        # POST review update
        handler_post = self._create_handler(
            "POST",
            f"/api/reports/{rep.report_id}/review",
            body={"status": "verified"}
        )
        handler_post.do_POST()
        handler_post.send_response.assert_called_with(200)
        res_post = json.loads(handler_post.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res_post["report"]["review_status"], "verified")
        self.assertTrue(res_post["report"]["is_verified"])

        # PATCH review update
        handler_patch = self._create_handler(
            "PATCH",
            f"/api/reports/{rep.report_id}/review",
            body={"status": "duplicate"}
        )
        handler_patch.do_PATCH()
        handler_patch.send_response.assert_called_with(200)
        res_patch = json.loads(handler_patch.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res_patch["report"]["review_status"], "duplicate")

    def test_method_not_allowed_405(self):
        # GET on report review path
        handler = self._create_handler("GET", "/api/reports/rep_01/review")
        handler.do_GET()
        handler.send_response.assert_called_with(405)

        # POST on reports summary path
        handler_summary = self._create_handler("POST", "/api/reports/summary", body={"dummy": 1})
        handler_summary.do_POST()
        handler_summary.send_response.assert_called_with(405)


if __name__ == "__main__":
    unittest.main()
