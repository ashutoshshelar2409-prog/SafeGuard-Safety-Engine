"""
Unit tests for Community Report Validation (Member 4).
"""

from datetime import datetime, timezone, timedelta
import unittest

from src.models.community_report import IncidentCategory, ReviewStatus
from src.processing.report_validation import (
    validate_report_dict,
    ReportValidationError,
    normalize_category,
    parse_iso_timestamp,
)


class TestReportValidation(unittest.TestCase):

    def test_valid_report_payload(self):
        payload = {
            "description": "Flickering street lamp makes the bus stop unsafe at night",
            "category": "poor_lighting",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "incident_time": "2026-10-14T20:30:00Z",
            "severity": 3,
        }
        sanitized, errors = validate_report_dict(payload)
        self.assertEqual(len(errors), 0)
        self.assertEqual(sanitized["latitude"], 12.9716)
        self.assertEqual(sanitized["longitude"], 77.5946)
        self.assertEqual(sanitized["category"], IncidentCategory.POOR_LIGHTING.value)
        self.assertEqual(sanitized["severity"], 3)
        self.assertIn("incident_time", sanitized)

    def test_missing_required_fields(self):
        payload = {"category": "road_hazard"}
        sanitized, errors = validate_report_dict(payload, require_all=True)
        self.assertIn("Missing required field: 'latitude'.", errors)
        self.assertIn("Missing required field: 'longitude'.", errors)
        self.assertIn("Missing required field: 'description'.", errors)

    def test_invalid_coordinates(self):
        # Latitude out of bounds
        sanitized, errors = validate_report_dict({
            "description": "Broken sidewalk obstacle",
            "latitude": 95.0,
            "longitude": 77.59,
        })
        self.assertTrue(any("Latitude 95.0 out of range" in e for e in errors))

        # Longitude out of bounds
        sanitized, errors = validate_report_dict({
            "description": "Broken sidewalk obstacle",
            "latitude": 12.97,
            "longitude": -190.0,
        })
        self.assertTrue(any("Longitude -190.0 out of range" in e for e in errors))

        # Non-numeric coordinate
        sanitized, errors = validate_report_dict({
            "description": "Broken sidewalk obstacle",
            "latitude": "invalid_lat",
            "longitude": 77.59,
        })
        self.assertTrue(any("Latitude must be a valid numeric" in e for e in errors))

    def test_description_length_validation(self):
        # Too short (< 5 chars)
        sanitized, errors = validate_report_dict({
            "description": "bad",
            "latitude": 12.97,
            "longitude": 77.59,
        })
        self.assertTrue(any("too short" in e for e in errors))

        # Too long (> 1000 chars)
        long_desc = "a" * 1005
        sanitized, errors = validate_report_dict({
            "description": long_desc,
            "latitude": 12.97,
            "longitude": 77.59,
        })
        self.assertTrue(any("too long" in e for e in errors))

        # Non-string description
        sanitized, errors = validate_report_dict({
            "description": 12345,
            "latitude": 12.97,
            "longitude": 77.59,
        })
        self.assertTrue(any("Description must be a string" in e for e in errors))

    def test_category_normalization_and_aliases(self):
        self.assertEqual(normalize_category("streetlight_failure"), IncidentCategory.POOR_LIGHTING.value)
        self.assertEqual(normalize_category("catcalling"), IncidentCategory.HARASSMENT.value)
        self.assertEqual(normalize_category("pothole"), IncidentCategory.ROAD_HAZARD.value)
        self.assertEqual(normalize_category("waterlogging"), IncidentCategory.INFRASTRUCTURE_PROBLEM.value)
        self.assertEqual(normalize_category("suspicious"), IncidentCategory.SUSPICIOUS_ACTIVITY.value)
        self.assertEqual(normalize_category("unknown_alien_category"), IncidentCategory.OTHER.value)
        self.assertEqual(normalize_category(None), IncidentCategory.OTHER.value)

    def test_timestamp_validation(self):
        # Valid ISO 8601 with Z
        dt = parse_iso_timestamp("2026-10-10T14:30:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)

        # Valid ISO 8601 with offset
        dt_offset = parse_iso_timestamp("2026-10-10T20:00:00+05:30")
        self.assertIsNotNone(dt_offset)

        # Invalid timestamp string
        with self.assertRaises(ValueError):
            parse_iso_timestamp("not-a-timestamp")

        # Future timestamp rejection
        future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        sanitized, errors = validate_report_dict({
            "description": "Incident in the future",
            "latitude": 12.97,
            "longitude": 77.59,
            "incident_time": future_time
        })
        self.assertTrue(any("cannot be in the future" in e for e in errors))

    def test_review_status_validation(self):
        # Valid status
        sanitized, errors = validate_report_dict({
            "description": "Validated street report",
            "latitude": 12.97,
            "longitude": 77.59,
            "review_status": "verified"
        })
        self.assertEqual(sanitized["review_status"], ReviewStatus.VERIFIED)

        # Invalid status
        sanitized, errors = validate_report_dict({
            "description": "Validated street report",
            "latitude": 12.97,
            "longitude": 77.59,
            "review_status": "super_verified"
        })
        self.assertTrue(any("Invalid review status" in e for e in errors))

    def test_severity_validation(self):
        # Valid severity 1-5
        sanitized, errors = validate_report_dict({
            "description": "Moderate hazard on walkway",
            "latitude": 12.97,
            "longitude": 77.59,
            "severity": 4
        })
        self.assertEqual(sanitized["severity"], 4)

        # Invalid severity > 5
        sanitized, errors = validate_report_dict({
            "description": "Extreme hazard on walkway",
            "latitude": 12.97,
            "longitude": 77.59,
            "severity": 10
        })
        self.assertTrue(any("Severity must be an integer between 1 and 5" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
