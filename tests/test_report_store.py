"""
Unit tests for ReportStore and CommunityReportService (Member 4).
"""

import os
import tempfile
import unittest

from src.models.community_report import CommunityReport, ReviewStatus, IncidentCategory
from src.services.community_service import CommunityReportService
from src.storage.report_store import ReportStore


class TestReportStoreAndService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.persistence_path = os.path.join(self.temp_dir.name, "test_reports.json")
        self.store = ReportStore(persistence_file=self.persistence_path, seed_file=None)
        self.service = CommunityReportService(store=self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_retrieve_report(self):
        report = CommunityReport(
            report_id="rep_test_01",
            description="Dark corner with broken street lamp",
            category=IncidentCategory.POOR_LIGHTING.value,
            latitude=12.9716,
            longitude=77.5946,
            review_status=ReviewStatus.PENDING
        )
        self.store.add_report(report)

        retrieved = self.store.get_report("rep_test_01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.description, "Dark corner with broken street lamp")
        self.assertEqual(self.store.count(), 1)

    def test_persistence_reload(self):
        report = CommunityReport(
            report_id="rep_test_persist",
            description="Severe pothole on crossroad",
            category=IncidentCategory.ROAD_HAZARD.value,
            latitude=12.9750,
            longitude=77.5980,
            review_status=ReviewStatus.VERIFIED
        )
        self.store.add_report(report)
        self.assertTrue(os.path.exists(self.persistence_path))

        # Reopen with new store instance pointing to same file
        reloaded_store = ReportStore(persistence_file=self.persistence_path, seed_file=None)
        self.assertEqual(reloaded_store.count(), 1)
        reloaded_report = reloaded_store.get_report("rep_test_persist")
        self.assertIsNotNone(reloaded_report)
        self.assertEqual(reloaded_report.review_status, ReviewStatus.VERIFIED)

    def test_service_submit_report_with_classification(self):
        payload = {
            "description": "Pitch dark alley with broken streetlights",
            "latitude": 12.9716,
            "longitude": 77.5946
        }
        report, meta = self.service.submit_report(payload)
        self.assertEqual(report.category, IncidentCategory.POOR_LIGHTING.value)
        self.assertEqual(report.review_status, ReviewStatus.PENDING)
        self.assertFalse(meta["duplicate_detected"])
        self.assertIsNotNone(report.classification_result)
        self.assertFalse(report.classification_result.needs_review)

    def test_service_submit_duplicate_detection(self):
        payload1 = {
            "description": "Broken streetlight near bus stop",
            "category": "poor_lighting",
            "latitude": 12.9716,
            "longitude": 77.5946
        }
        r1, meta1 = self.service.submit_report(payload1)
        self.assertFalse(meta1["duplicate_detected"])

        # Submit nearly identical report 20m away immediately
        payload2 = {
            "description": "Broken streetlight near bus stop",
            "category": "poor_lighting",
            "latitude": 12.9717,
            "longitude": 77.5946
        }
        r2, meta2 = self.service.submit_report(payload2)
        self.assertTrue(meta2["duplicate_detected"])
        self.assertEqual(r2.possible_duplicate_of, r1.report_id)

    def test_update_review_status(self):
        payload = {
            "description": "Suspicious person loitering in parking lot",
            "category": "suspicious_activity",
            "latitude": 12.9716,
            "longitude": 77.5946
        }
        r, _ = self.service.submit_report(payload)
        self.assertEqual(r.review_status, ReviewStatus.PENDING)

        updated = self.service.update_review_status(r.report_id, "verified")
        self.assertIsNotNone(updated)
        self.assertEqual(updated["review_status"], "verified")
        self.assertTrue(updated["is_verified"])

    def test_export_for_safety_engine_member1(self):
        # 1 verified report, 1 pending report
        r1, _ = self.service.submit_report({
            "description": "Pothole verified by city council",
            "category": "road_hazard",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "severity": 3
        })
        self.service.update_review_status(r1.report_id, "verified")

        r2, _ = self.service.submit_report({
            "description": "Unverified report waiting for review",
            "category": "poor_lighting",
            "latitude": 12.9800,
            "longitude": 77.6000
        })

        exported = self.service.export_verified_reports_for_safety_engine()
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["report_id"], r1.report_id)
        self.assertEqual(exported[0]["severity"], 3)


if __name__ == "__main__":
    unittest.main()
