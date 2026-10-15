"""
Unit tests for Report Analysis, Duplicate Detection, and Aggregation (Member 4).
"""

from datetime import datetime, timezone, timedelta
import unittest

from src.models.community_report import CommunityReport, ReviewStatus, IncidentCategory
from src.services.report_analysis import (
    DuplicateDetector,
    ReportAggregator,
    haversine_distance_meters,
    jaccard_similarity,
    tokenize_text
)


class TestReportAnalysis(unittest.TestCase):

    def setUp(self):
        self.detector = DuplicateDetector(
            max_distance_meters=200.0,
            max_time_diff_hours=12.0,
            min_text_similarity=0.35,
            very_close_distance_meters=60.0
        )
        self.base_time = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_haversine_distance_calculation(self):
        # Two identical points distance = 0
        d = haversine_distance_meters(12.9716, 77.5946, 12.9716, 77.5946)
        self.assertAlmostEqual(d, 0.0, places=2)

        # Roughly ~111 meters per 0.001 degree of latitude
        d2 = haversine_distance_meters(12.9716, 77.5946, 12.9726, 77.5946)
        self.assertGreater(d2, 100.0)
        self.assertLess(d2, 120.0)

    def test_text_similarity(self):
        tok1 = tokenize_text("Broken streetlight near bus stop")
        tok2 = tokenize_text("Broken street light close to bus stop")
        sim = jaccard_similarity(tok1, tok2)
        self.assertGreaterEqual(sim, 0.35)

        tok3 = tokenize_text("Completely unrelated pothole problem")
        sim_unrelated = jaccard_similarity(tok1, tok3)
        self.assertLess(sim_unrelated, 0.2)

    def test_duplicate_detection_close_location_and_same_category(self):
        existing = CommunityReport(
            report_id="rep_original",
            description="Broken streetlight near bus stop entrance",
            category=IncidentCategory.POOR_LIGHTING.value,
            latitude=12.9716,
            longitude=77.5946,
            submission_timestamp=self.base_time.isoformat(),
            review_status=ReviewStatus.PENDING
        )

        # Candidate report 30m away, submitted 1 hour later, same category
        candidate = CommunityReport(
            report_id="rep_candidate",
            description="Street lamp broken by the bus stop",
            category=IncidentCategory.POOR_LIGHTING.value,
            latitude=12.9718,
            longitude=77.5947,
            submission_timestamp=(self.base_time + timedelta(hours=1)).isoformat(),
            review_status=ReviewStatus.PENDING
        )

        dup_id, conf, reason = self.detector.find_duplicate(candidate, [existing])
        self.assertEqual(dup_id, "rep_original")
        self.assertGreater(conf, 0.8)
        self.assertIn("identical category", reason)

    def test_non_duplicate_far_distance(self):
        existing = CommunityReport(
            report_id="rep_original",
            description="Broken streetlight near bus stop entrance",
            category=IncidentCategory.POOR_LIGHTING.value,
            latitude=12.9716,
            longitude=77.5946,
            submission_timestamp=self.base_time.isoformat()
        )

        # Candidate 2 km away -> NOT a duplicate
        candidate = CommunityReport(
            report_id="rep_candidate",
            description="Broken streetlight near bus stop entrance",
            category=IncidentCategory.POOR_LIGHTING.value,
            latitude=12.9900,
            longitude=77.6100,
            submission_timestamp=self.base_time.isoformat()
        )

        dup_id, conf, reason = self.detector.find_duplicate(candidate, [existing])
        self.assertIsNone(dup_id)
        self.assertEqual(conf, 0.0)

    def test_non_duplicate_distant_time(self):
        existing = CommunityReport(
            report_id="rep_original",
            description="Pothole in middle of lane",
            category=IncidentCategory.ROAD_HAZARD.value,
            latitude=12.9716,
            longitude=77.5946,
            submission_timestamp=self.base_time.isoformat()
        )

        # Candidate submitted 5 days later
        candidate = CommunityReport(
            report_id="rep_candidate",
            description="Pothole in middle of lane",
            category=IncidentCategory.ROAD_HAZARD.value,
            latitude=12.97165,
            longitude=77.59465,
            submission_timestamp=(self.base_time + timedelta(days=5)).isoformat()
        )

        dup_id, conf, reason = self.detector.find_duplicate(candidate, [existing])
        self.assertIsNone(dup_id)

    def test_aggregation_and_summary_generation(self):
        now = datetime.now(timezone.utc)
        reports = [
            CommunityReport(
                report_id="r1",
                description="Verified streetlight problem",
                category=IncidentCategory.POOR_LIGHTING.value,
                latitude=12.9716,
                longitude=77.5946,
                submission_timestamp=now.isoformat(),
                review_status=ReviewStatus.VERIFIED
            ),
            CommunityReport(
                report_id="r2",
                description="Pending harassment observation",
                category=IncidentCategory.HARASSMENT.value,
                latitude=12.9720,
                longitude=77.5950,
                submission_timestamp=now.isoformat(),
                review_status=ReviewStatus.PENDING
            ),
            CommunityReport(
                report_id="r3",
                description="Rejected duplicate road complaint",
                category=IncidentCategory.ROAD_HAZARD.value,
                latitude=12.9730,
                longitude=77.5960,
                submission_timestamp=(now - timedelta(days=10)).isoformat(),
                review_status=ReviewStatus.REJECTED
            ),
        ]

        summary = ReportAggregator.generate_summary(reports)

        self.assertEqual(summary["total_reports"], 3)
        self.assertEqual(summary["verification_summary"]["verified_count"], 1)
        self.assertEqual(summary["verification_summary"]["unverified_count"], 1)
        self.assertEqual(summary["verification_summary"]["rejected_count"], 1)
        self.assertAlmostEqual(summary["verification_summary"]["verified_percentage"], 33.3, places=1)
        self.assertIn("Community reports are crowdsourced user observations", summary["disclaimer"])

        # Spatial filter aggregation
        summary_filtered = ReportAggregator.generate_summary(reports, lat=12.9716, lon=77.5946, radius_km=0.1)
        self.assertEqual(summary_filtered["total_reports"], 2)


if __name__ == "__main__":
    unittest.main()
