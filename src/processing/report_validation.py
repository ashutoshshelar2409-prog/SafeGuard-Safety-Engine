"""
Community Report Validation Module (Member 4).
Performs strict schema validation, coordinate boundary checks, text length validation,
timestamp verification, and review status integrity checks with clear error messages.
"""

from datetime import datetime, timezone, timedelta
import re
from typing import Dict, Any, List, Optional, Tuple

from src.models.community_report import IncidentCategory, ReviewStatus


CATEGORY_ALIASES = {
    # Poor lighting
    "poor_lighting": IncidentCategory.POOR_LIGHTING.value,
    "poor lighting": IncidentCategory.POOR_LIGHTING.value,
    "lighting": IncidentCategory.POOR_LIGHTING.value,
    "streetlight_failure": IncidentCategory.POOR_LIGHTING.value,
    "dark": IncidentCategory.POOR_LIGHTING.value,
    "broken_light": IncidentCategory.POOR_LIGHTING.value,

    # Road hazard
    "road_hazard": IncidentCategory.ROAD_HAZARD.value,
    "road hazard": IncidentCategory.ROAD_HAZARD.value,
    "hazard": IncidentCategory.ROAD_HAZARD.value,
    "unsafe_road": IncidentCategory.ROAD_HAZARD.value,
    "pothole": IncidentCategory.ROAD_HAZARD.value,
    "road_damage": IncidentCategory.ROAD_HAZARD.value,

    # Harassment
    "harassment": IncidentCategory.HARASSMENT.value,
    "catcalling": IncidentCategory.HARASSMENT.value,
    "stalking": IncidentCategory.HARASSMENT.value,
    "verbal_abuse": IncidentCategory.HARASSMENT.value,

    # Suspicious activity
    "suspicious_activity": IncidentCategory.SUSPICIOUS_ACTIVITY.value,
    "suspicious activity": IncidentCategory.SUSPICIOUS_ACTIVITY.value,
    "suspicious": IncidentCategory.SUSPICIOUS_ACTIVITY.value,
    "loitering": IncidentCategory.SUSPICIOUS_ACTIVITY.value,

    # Infrastructure problem
    "infrastructure_problem": IncidentCategory.INFRASTRUCTURE_PROBLEM.value,
    "infrastructure problem": IncidentCategory.INFRASTRUCTURE_PROBLEM.value,
    "infrastructure": IncidentCategory.INFRASTRUCTURE_PROBLEM.value,
    "broken_sidewalk": IncidentCategory.INFRASTRUCTURE_PROBLEM.value,
    "waterlogging": IncidentCategory.INFRASTRUCTURE_PROBLEM.value,
    "traffic_light": IncidentCategory.INFRASTRUCTURE_PROBLEM.value,

    # Other
    "other": IncidentCategory.OTHER.value,
    "uncertain": IncidentCategory.OTHER.value,
}

VALID_STATUSES = {s.value for s in ReviewStatus}
VALID_CATEGORIES = {c.value for c in IncidentCategory}

MIN_DESCRIPTION_LENGTH = 5
MAX_DESCRIPTION_LENGTH = 1000


class ReportValidationError(ValueError):
    """Raised when a community report fails validation checks."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        message = "; ".join(errors)
        super().__init__(message)


def parse_iso_timestamp(ts_str: Any) -> Optional[datetime]:
    """
    Parses an ISO 8601 timestamp string into a timezone-aware UTC datetime.
    Supports standard 'Z' suffix and numeric offsets (+05:30).
    """
    if not ts_str:
        return None
    if isinstance(ts_str, datetime):
        if ts_str.tzinfo is None:
            return ts_str.replace(tzinfo=timezone.utc)
        return ts_str.astimezone(timezone.utc)

    if not isinstance(ts_str, str):
        raise ValueError("Timestamp must be an ISO 8601 string or datetime object.")

    clean_str = ts_str.strip()
    # Normalize 'Z' to '+00:00' for fromisoformat compatibility
    if clean_str.endswith("Z"):
        clean_str = clean_str[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception as exc:
        raise ValueError(f"Invalid ISO 8601 timestamp format: '{ts_str}'.") from exc


def normalize_category(category: Optional[str]) -> str:
    """Normalizes raw category strings to canonical IncidentCategory values."""
    if not category:
        return IncidentCategory.OTHER.value
    cleaned = category.strip().lower()
    return CATEGORY_ALIASES.get(cleaned, IncidentCategory.OTHER.value)


def validate_report_dict(
    payload: Dict[str, Any],
    require_all: bool = True,
    allow_future_minutes: int = 10
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validates a raw report dictionary against all Member 4 requirements.

    Args:
        payload: Dict containing incoming report fields.
        require_all: Whether required fields (description, latitude, longitude) must be present.
        allow_future_minutes: Margin allowed for incident timestamps (clock drift tolerance).

    Returns:
        Tuple of (sanitized_data_dict, list_of_error_strings).
    """
    errors: List[str] = []
    sanitized: Dict[str, Any] = {}

    if not isinstance(payload, dict):
        return {}, ["Report payload must be a JSON object."]

    # 1. Latitude validation
    if "latitude" in payload:
        try:
            lat = float(payload["latitude"])
            if not (-90.0 <= lat <= 90.0):
                errors.append(f"Latitude {lat} out of range. Must be between -90.0 and 90.0.")
            else:
                sanitized["latitude"] = lat
        except (ValueError, TypeError):
            errors.append("Latitude must be a valid numeric coordinate.")
    elif require_all:
        errors.append("Missing required field: 'latitude'.")

    # 2. Longitude validation
    if "longitude" in payload:
        try:
            lon = float(payload["longitude"])
            if not (-180.0 <= lon <= 180.0):
                errors.append(f"Longitude {lon} out of range. Must be between -180.0 and 180.0.")
            else:
                sanitized["longitude"] = lon
        except (ValueError, TypeError):
            errors.append("Longitude must be a valid numeric coordinate.")
    elif require_all:
        errors.append("Missing required field: 'longitude'.")

    # 3. Description validation
    if "description" in payload:
        desc = payload["description"]
        if not isinstance(desc, str):
            errors.append("Description must be a string.")
        else:
            stripped = desc.strip()
            if len(stripped) < MIN_DESCRIPTION_LENGTH:
                errors.append(
                    f"Description is too short ({len(stripped)} chars). "
                    f"Minimum {MIN_DESCRIPTION_LENGTH} characters required."
                )
            elif len(stripped) > MAX_DESCRIPTION_LENGTH:
                errors.append(
                    f"Description is too long ({len(stripped)} chars). "
                    f"Maximum {MAX_DESCRIPTION_LENGTH} characters allowed."
                )
            else:
                sanitized["description"] = stripped
    elif require_all:
        errors.append("Missing required field: 'description'.")

    # 4. Category validation / normalization
    raw_category = payload.get("category") or payload.get("report_type")
    if raw_category is not None:
        if not isinstance(raw_category, str):
            errors.append("Category must be a string.")
        else:
            normalized = normalize_category(raw_category)
            sanitized["category"] = normalized
    else:
        sanitized["category"] = IncidentCategory.OTHER.value

    # 5. Timestamp validation
    now = datetime.now(timezone.utc)
    max_allowed = now + timedelta(minutes=allow_future_minutes)

    # 5a. Incident time (optional)
    raw_incident_time = payload.get("incident_time") or payload.get("timestamp")
    if raw_incident_time:
        try:
            dt = parse_iso_timestamp(raw_incident_time)
            if dt > max_allowed:
                errors.append(f"Incident time cannot be in the future: '{raw_incident_time}'.")
            else:
                sanitized["incident_time"] = dt.isoformat()
        except ValueError as exc:
            errors.append(str(exc))
    else:
        sanitized["incident_time"] = None

    # 5b. Submission timestamp (optional override, defaults to now)
    raw_sub_ts = payload.get("submission_timestamp")
    if raw_sub_ts:
        try:
            sub_dt = parse_iso_timestamp(raw_sub_ts)
            sanitized["submission_timestamp"] = sub_dt.isoformat()
        except ValueError as exc:
            errors.append(str(exc))
    else:
        sanitized["submission_timestamp"] = now.isoformat()

    # 6. Review status validation
    raw_status = payload.get("review_status", ReviewStatus.PENDING.value)
    if raw_status:
        status_str = str(raw_status).lower()
        if status_str not in VALID_STATUSES:
            errors.append(
                f"Invalid review status: '{raw_status}'. "
                f"Must be one of: {sorted(list(VALID_STATUSES))}."
            )
        else:
            sanitized["review_status"] = ReviewStatus(status_str)
    else:
        sanitized["review_status"] = ReviewStatus.PENDING

    # 7. Severity validation (optional integer 1-5)
    if "severity" in payload:
        try:
            sev = int(payload["severity"])
            if not (1 <= sev <= 5):
                errors.append("Severity must be an integer between 1 and 5.")
            else:
                sanitized["severity"] = sev
        except (ValueError, TypeError):
            errors.append("Severity must be a valid integer between 1 and 5.")
    else:
        sanitized["severity"] = 1

    # Optional report_id if specified (e.g. for updates/seeding)
    if "report_id" in payload and payload["report_id"]:
        sanitized["report_id"] = str(payload["report_id"]).strip()

    return sanitized, errors
