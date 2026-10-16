"""
Community Report Storage & Persistence Module (Member 4).

Storage Architecture & Limitations:
-----------------------------------
This module provides thread-safe in-memory and local JSON file persistence for
community incident reports.

Limitations:
- Designed for lightweight local development, prototype testing, and frontend pairing.
- Does not offer distributed ACID transaction locking or spatial indexing.
- For production enterprise deployment, replace this layer with PostgreSQL + PostGIS
  or an equivalent spatial database.

Privacy Safeguards:
-------------------
- No unnecessary PII (reporter email, phone number, name, device identifiers) is collected.
- Public query endpoints exclusively export sanitized dictionaries via `to_public_dict()`.
"""

import json
import logging
import os
import threading
from typing import Dict, List, Optional, Any

from src.models.community_report import CommunityReport, ReviewStatus, IncidentCategory
from src.services.report_analysis import ReportAggregator

logger = logging.getLogger(__name__)


class DuplicateReportIdError(ValueError):
    """Raised when attempting to add a report whose ID already exists in the store."""
    def __init__(self, report_id: str):
        super().__init__(f"Report ID already exists: '{report_id}'.")
        self.report_id = report_id



class ReportStore:
    """
    Thread-safe repository for community reports with optional JSON file backup.
    """

    def __init__(self, persistence_file: Optional[str] = None, seed_file: Optional[str] = "data/raw/community_reports.json"):
        self._lock = threading.RLock()
        self._reports: Dict[str, CommunityReport] = {}
        self.persistence_file = persistence_file
        self.seed_file = seed_file

        # Load seed data or existing persisted data
        self._initialize()

    def _initialize(self):
        """Loads existing persisted data or initial seed data if available."""
        with self._lock:
            # 1. Attempt to load from persistence file first
            if self.persistence_file and os.path.exists(self.persistence_file):
                try:
                    with open(self.persistence_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                report = CommunityReport.from_dict(item)
                                self._reports[report.report_id] = report
                        logger.info("Loaded %d reports from persistence file %s", len(self._reports), self.persistence_file)
                        return
                except Exception as exc:
                    logger.warning("Failed to load persistence file '%s': %s", self.persistence_file, exc)

            # 2. Fall back to loading seed data if persistence file did not populate
            if self.seed_file and os.path.exists(self.seed_file):
                try:
                    with open(self.seed_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                report = CommunityReport.from_dict(item)
                                # Mark seed data as verified for baseline visualization if not specified
                                if "review_status" not in item:
                                    report.review_status = ReviewStatus.VERIFIED
                                self._reports[report.report_id] = report
                        logger.info("Loaded %d seed reports from %s", len(self._reports), self.seed_file)
                except Exception as exc:
                    logger.warning("Failed to load seed reports '%s': %s", self.seed_file, exc)

    def _persist_unlocked(self):
        """Writes current reports to persistence file if configured. Must be called with lock held."""
        if not self.persistence_file:
            return
        try:
            parent_dir = os.path.dirname(self.persistence_file)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            serializable = [r.to_dict() for r in self._reports.values()]
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception as exc:
            logger.error("Failed to persist reports to '%s': %s", self.persistence_file, exc)

    def add_report(self, report: CommunityReport) -> CommunityReport:
        """Adds a new community report to the store and persists if enabled.

        Raises:
            DuplicateReportIdError: If a report with the same ID already exists.
        """
        with self._lock:
            if report.report_id in self._reports:
                raise DuplicateReportIdError(report.report_id)
            self._reports[report.report_id] = report
            self._persist_unlocked()
            return report

    def get_report(self, report_id: str) -> Optional[CommunityReport]:
        """Retrieves a single report by unique report_id."""
        with self._lock:
            return self._reports.get(report_id)

    def list_reports(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[float] = None,
        time_window: Optional[str] = None,
        since_iso: Optional[str] = None
    ) -> List[CommunityReport]:
        """Lists reports matching optional filters."""
        with self._lock:
            all_reports = list(self._reports.values())
            return ReportAggregator.filter_reports(
                all_reports,
                status=status,
                category=category,
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                time_window=time_window,
                since_iso=since_iso
            )

    def list_public_reports(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[float] = None,
        time_window: Optional[str] = None,
        since_iso: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists public-sanitized reports ensuring reporter privacy."""
        reports = self.list_reports(
            status=status,
            category=category,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            time_window=time_window,
            since_iso=since_iso
        )
        return [r.to_public_dict() for r in reports]

    def update_review_status(self, report_id: str, new_status: ReviewStatus) -> Optional[CommunityReport]:
        """Updates the review status of an existing report."""
        with self._lock:
            report = self._reports.get(report_id)
            if not report:
                return None
            report.review_status = new_status
            self._persist_unlocked()
            return report

    def get_summary(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[float] = None
    ) -> Dict[str, Any]:
        """Generates aggregate summary statistics over stored reports."""
        with self._lock:
            all_reports = list(self._reports.values())
            return ReportAggregator.generate_summary(all_reports, lat=lat, lon=lon, radius_km=radius_km)

    def count(self) -> int:
        """Returns total count of stored reports."""
        with self._lock:
            return len(self._reports)

    def clear(self):
        """Clears all stored reports (primarily for unit tests)."""
        with self._lock:
            self._reports.clear()
            self._persist_unlocked()
