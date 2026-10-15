"""
Report Analysis and Aggregation Service (Member 4).

Provides:
- Spatio-temporal and textual duplicate detection for community incident reports.
- Aggregation by geographic area (radius or bounding box), category, and time window.
- Frontend-ready summaries separating verified and unverified reports.
- Clear disclaimer maintaining separation from official crime statistics.
"""

from datetime import datetime, timezone, timedelta
import math
import re
from typing import List, Dict, Any, Optional, Tuple, Set

from src.models.community_report import CommunityReport, ReviewStatus, IncidentCategory
from src.processing.report_validation import parse_iso_timestamp


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two geographic coordinates in meters.
    """
    r_earth = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r_earth * c


def tokenize_text(text: str) -> Set[str]:
    """Extracts lowercase alphabetic words of length >= 3 for similarity comparison."""
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return {w for w in cleaned.split() if len(w) >= 3}


def jaccard_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    """Computes Jaccard index between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union) if union else 0.0


class DuplicateDetector:
    """
    Detects potential duplicate incident reports using a hybrid spatio-temporal
    and description similarity heuristic.
    """

    def __init__(
        self,
        max_distance_meters: float = 200.0,
        max_time_diff_hours: float = 12.0,
        min_text_similarity: float = 0.35,
        very_close_distance_meters: float = 60.0
    ):
        self.max_distance_meters = max_distance_meters
        self.max_time_diff_hours = max_time_diff_hours
        self.min_text_similarity = min_text_similarity
        self.very_close_distance_meters = very_close_distance_meters

    def find_duplicate(
        self,
        candidate: CommunityReport,
        existing_reports: List[CommunityReport]
    ) -> Tuple[Optional[str], float, str]:
        """
        Checks whether a candidate report is likely a duplicate of an existing report.

        Returns:
            Tuple of (matched_report_id, confidence, rationale).
            If no duplicate found, returns (None, 0.0, "").
        """
        cand_tokens = tokenize_text(candidate.description)
        cand_time = parse_iso_timestamp(candidate.incident_time or candidate.submission_timestamp)

        for existing in existing_reports:
            # Skip comparing against self or rejected reports
            if existing.report_id == candidate.report_id or existing.review_status == ReviewStatus.REJECTED:
                continue

            # 1. Geographic proximity check
            dist_meters = haversine_distance_meters(
                candidate.latitude, candidate.longitude,
                existing.latitude, existing.longitude
            )
            if dist_meters > self.max_distance_meters:
                continue

            # 2. Time proximity check
            exist_time = parse_iso_timestamp(existing.incident_time or existing.submission_timestamp)
            time_diff_hours = None
            if cand_time and exist_time:
                time_diff_hours = abs((cand_time - exist_time).total_seconds()) / 3600.0
                if time_diff_hours > self.max_time_diff_hours:
                    continue

            # 3. Description & category similarity check
            exist_tokens = tokenize_text(existing.description)
            text_sim = jaccard_similarity(cand_tokens, exist_tokens)
            same_category = (candidate.category == existing.category and candidate.category != IncidentCategory.OTHER.value)

            # High confidence duplicate conditions:
            # Case A: Very close (< 60m), same category, within time window
            if dist_meters <= self.very_close_distance_meters and same_category:
                confidence = 0.85 + (0.15 * text_sim)
                reason = (
                    f"Report is within {dist_meters:.1f}m of {existing.report_id} with identical category "
                    f"'{candidate.category}' within {time_diff_hours:.1f}h window."
                )
                return existing.report_id, round(confidence, 2), reason

            # Case B: Close (< 200m), notable text similarity
            if text_sim >= self.min_text_similarity:
                confidence = 0.70 + (0.30 * text_sim)
                reason = (
                    f"Report is within {dist_meters:.1f}m of {existing.report_id} with "
                    f"{text_sim:.0%} description vocabulary overlap."
                )
                return existing.report_id, round(confidence, 2), reason

        return None, 0.0, ""


class ReportAggregator:
    """
    Performs multi-criteria spatial and temporal aggregation over community reports.
    Produces clear frontend summaries with explicit separation of verified vs unverified data.
    """

    CROWDSOURCE_DISCLAIMER = (
        "Community reports are crowdsourced user observations and do not represent "
        "confirmed crime statistics or verified municipal records."
    )

    @classmethod
    def filter_reports(
        cls,
        reports: List[CommunityReport],
        status: Optional[str] = None,
        category: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[float] = None,
        time_window: Optional[str] = None,
        since_iso: Optional[str] = None
    ) -> List[CommunityReport]:
        """
        Filters reports by status, category, geographic radius, or time window.
        """
        filtered = reports

        # Status filter
        if status:
            status_clean = status.strip().lower()
            if status_clean != "all":
                filtered = [
                    r for r in filtered
                    if (r.review_status.value if isinstance(r.review_status, ReviewStatus) else str(r.review_status)).lower() == status_clean
                ]

        # Category filter
        if category:
            cat_clean = category.strip().lower()
            filtered = [r for r in filtered if r.category.lower() == cat_clean]

        # Spatial radius filter
        if lat is not None and lon is not None and radius_km is not None and radius_km > 0:
            filtered = [
                r for r in filtered
                if (haversine_distance_meters(lat, lon, r.latitude, r.longitude) / 1000.0) <= radius_km
            ]

        # Time window filter (e.g., '24h', '7d', '30d')
        now = datetime.now(timezone.utc)
        cutoff_dt = None
        if time_window:
            tw = time_window.strip().lower()
            if tw == "24h":
                cutoff_dt = now - timedelta(hours=24)
            elif tw == "7d":
                cutoff_dt = now - timedelta(days=7)
            elif tw == "30d":
                cutoff_dt = now - timedelta(days=30)
            elif tw != "all":
                # Try parsing as hours or days if numeric
                try:
                    cutoff_dt = now - timedelta(hours=float(tw))
                except ValueError:
                    pass
        elif since_iso:
            try:
                cutoff_dt = parse_iso_timestamp(since_iso)
            except ValueError:
                pass

        if cutoff_dt:
            result = []
            for r in filtered:
                report_dt = parse_iso_timestamp(r.incident_time or r.submission_timestamp)
                if report_dt and report_dt >= cutoff_dt:
                    result.append(r)
            filtered = result

        return filtered

    @classmethod
    def generate_summary(
        cls,
        reports: List[CommunityReport],
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_km: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculates report totals, category breakdown, review status breakdown,
        and separation between verified vs unverified reports.
        """
        target_reports = reports
        if lat is not None and lon is not None and radius_km is not None:
            target_reports = cls.filter_reports(reports, lat=lat, lon=lon, radius_km=radius_km)

        total_count = len(target_reports)

        status_counts = {s.value: 0 for s in ReviewStatus}
        category_counts = {c.value: 0 for c in IncidentCategory}
        verified_category_counts = {c.value: 0 for c in IncidentCategory}
        unverified_category_counts = {c.value: 0 for c in IncidentCategory}

        recent_24h = 0
        recent_7d = 0
        now = datetime.now(timezone.utc)
        t_24h = now - timedelta(hours=24)
        t_7d = now - timedelta(days=7)

        for r in target_reports:
            status_val = r.review_status.value if isinstance(r.review_status, ReviewStatus) else str(r.review_status)
            status_counts[status_val] = status_counts.get(status_val, 0) + 1

            cat_val = r.category
            category_counts[cat_val] = category_counts.get(cat_val, 0) + 1

            is_verified = (status_val == ReviewStatus.VERIFIED.value)
            if is_verified:
                verified_category_counts[cat_val] = verified_category_counts.get(cat_val, 0) + 1
            else:
                unverified_category_counts[cat_val] = unverified_category_counts.get(cat_val, 0) + 1

            # Recency checks
            rdt = parse_iso_timestamp(r.incident_time or r.submission_timestamp)
            if rdt:
                if rdt >= t_24h:
                    recent_24h += 1
                if rdt >= t_7d:
                    recent_7d += 1

        verified_count = status_counts.get(ReviewStatus.VERIFIED.value, 0)
        pending_count = status_counts.get(ReviewStatus.PENDING.value, 0)
        rejected_count = status_counts.get(ReviewStatus.REJECTED.value, 0)
        duplicate_count = status_counts.get(ReviewStatus.DUPLICATE.value, 0)
        unverified_count = pending_count  # Pending community reports are unverified

        # Human-readable category labels
        display_names = IncidentCategory.display_names()
        categories_breakdown = [
            {
                "category": cat,
                "label": display_names.get(cat, cat),
                "total_count": count,
                "verified_count": verified_category_counts.get(cat, 0),
                "unverified_count": unverified_category_counts.get(cat, 0),
            }
            for cat, count in category_counts.items()
        ]

        summary: Dict[str, Any] = {
            "total_reports": total_count,
            "verification_summary": {
                "verified_count": verified_count,
                "unverified_count": unverified_count,
                "rejected_count": rejected_count,
                "duplicate_count": duplicate_count,
                "verified_percentage": round((verified_count / total_count * 100), 1) if total_count > 0 else 0.0,
            },
            "status_breakdown": status_counts,
            "time_window_breakdown": {
                "past_24_hours": recent_24h,
                "past_7_days": recent_7d,
                "all_time": total_count,
            },
            "categories": categories_breakdown,
            "area_filter": {
                "latitude": lat,
                "longitude": lon,
                "radius_km": radius_km
            } if lat is not None and lon is not None and radius_km is not None else None,
            "source_type": "community_crowdsourced",
            "disclaimer": cls.CROWDSOURCE_DISCLAIMER,
        }

        return summary
