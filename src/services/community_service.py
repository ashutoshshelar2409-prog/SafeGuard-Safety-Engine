"""
Community Report Service (Member 4).
Orchestrates validation, AI classification, duplicate detection, persistence,
and summary aggregation for community incident reporting.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from src.models.community_report import (
    CommunityReport,
    ReviewStatus,
    IncidentCategory,
    ClassificationResult
)
from src.processing.report_validation import (
    validate_report_dict,
    ReportValidationError,
    normalize_category
)
from src.services.incident_classifier import IncidentClassifier
from src.services.report_analysis import DuplicateDetector, ReportAggregator
from src.storage.report_store import ReportStore, DuplicateReportIdError

logger = logging.getLogger(__name__)


class CommunityReportService:
    """
    Core service coordinating the community reporting pipeline for Member 4.
    """

    def __init__(
        self,
        store: Optional[ReportStore] = None,
        classifier: Optional[IncidentClassifier] = None,
        duplicate_detector: Optional[DuplicateDetector] = None
    ):
        self.store = store or ReportStore()
        self.classifier = classifier or IncidentClassifier()
        self.duplicate_detector = duplicate_detector or DuplicateDetector()

    def submit_report(self, payload: Dict[str, Any]) -> Tuple[CommunityReport, Dict[str, Any]]:
        """
        Validates, classifies, checks duplicates, and stores a new community incident report.

        Args:
            payload: Incoming JSON request body.

        Returns:
            Tuple of (stored CommunityReport, submission_metadata_dict).

        Raises:
            ReportValidationError: When inputs fail coordinate, text, or schema validation.
        """
        # Step 1: Validate payload schema, coordinates, text length, timestamps
        sanitized_data, validation_errors = validate_report_dict(payload, require_all=True)
        if validation_errors:
            raise ReportValidationError(validation_errors)

        description = sanitized_data["description"]
        provided_category = sanitized_data.get("category", IncidentCategory.OTHER.value)

        # Step 2: Run lightweight NLP text classification
        clf_result = self.classifier.classify(description)

        # Step 3: Resolve category
        # If user left category as default/other, use AI suggestion if confident
        effective_category = provided_category
        if (
            provided_category == IncidentCategory.OTHER.value
            and clf_result.suggested_category != IncidentCategory.OTHER.value
            and not clf_result.needs_review
        ):
            effective_category = clf_result.suggested_category

        # Step 4: Construct candidate report object
        report = CommunityReport(
            report_id=CommunityReport.generate_id(),
            description=description,
            category=effective_category,
            latitude=sanitized_data["latitude"],
            longitude=sanitized_data["longitude"],
            incident_time=sanitized_data.get("incident_time"),
            submission_timestamp=sanitized_data["submission_timestamp"],
            review_status=ReviewStatus.PENDING,
            severity=sanitized_data.get("severity", 1),
            classification_result=clf_result,
        )

        # Step 5: Duplicate detection against existing reports
        existing_reports = self.store.list_reports()
        dup_id, dup_confidence, dup_reason = self.duplicate_detector.find_duplicate(report, existing_reports)

        duplicate_detected = bool(dup_id)
        if duplicate_detected:
            report.possible_duplicate_of = dup_id
            # Flag review status as duplicate if high-confidence match
            if dup_confidence >= 0.85:
                report.review_status = ReviewStatus.DUPLICATE
            logger.info("Report %s flagged as possible duplicate of %s: %s", report.report_id, dup_id, dup_reason)

        # Step 6: Store report
        stored_report = self.store.add_report(report)

        submission_meta = {
            "duplicate_detected": duplicate_detected,
            "possible_duplicate_of": dup_id,
            "duplicate_confidence": dup_confidence,
            "duplicate_reason": dup_reason,
            "classification": clf_result.to_dict(),
        }

        return stored_report, submission_meta

    def get_public_reports(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[float] = None,
        time_window: Optional[str] = None,
        since_iso: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves public-facing sanitized reports."""
        return self.store.list_public_reports(
            status=status,
            category=category,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            time_window=time_window,
            since_iso=since_iso
        )

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single public-sanitized report by ID."""
        rep = self.store.get_report(report_id)
        return rep.to_public_dict() if rep else None

    def get_summary(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculates aggregate counts, categories, and review statuses."""
        return self.store.get_summary(lat=lat, lon=lon, radius_km=radius_km)

    def update_review_status(self, report_id: str, new_status_str: str) -> Optional[Dict[str, Any]]:
        """
        Updates review status (e.g., 'verified', 'rejected', 'duplicate').
        """
        try:
            status_enum = ReviewStatus(new_status_str.lower().strip())
        except ValueError:
            valid = sorted([s.value for s in ReviewStatus])
            raise ReportValidationError([f"Invalid review status: '{new_status_str}'. Must be one of {valid}."])

        updated = self.store.update_review_status(report_id, status_enum)
        return updated.to_public_dict() if updated else None

    def export_verified_reports_for_safety_engine(self) -> List[Dict[str, Any]]:
        """
        Export helper designed for Member 1 integration.
        Returns only human-verified reports in the schema expected by SafetyEngine.
        """
        verified_reports = self.store.list_reports(status=ReviewStatus.VERIFIED.value)
        return [
            {
                "report_id": r.report_id,
                "report_type": r.category,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "severity": r.severity,
                "timestamp": r.incident_time or r.submission_timestamp,
                "description": r.description,
            }
            for r in verified_reports
        ]
