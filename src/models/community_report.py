"""
Community Report Data Models (Member 4).
Defines structured schema, categories, review statuses, and serialization
with strict privacy and data protection safeguards.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List
import uuid


class ReviewStatus(str, Enum):
    """Review and verification lifecycle status for community reports."""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class IncidentCategory(str, Enum):
    """Standardized incident categories for community reporting."""
    POOR_LIGHTING = "poor_lighting"
    ROAD_HAZARD = "road_hazard"
    HARASSMENT = "harassment"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    INFRASTRUCTURE_PROBLEM = "infrastructure_problem"
    OTHER = "other"

    @classmethod
    def display_names(cls) -> Dict[str, str]:
        """Maps canonical category keys to user-friendly human-readable labels."""
        return {
            cls.POOR_LIGHTING.value: "Poor lighting",
            cls.ROAD_HAZARD.value: "Road hazard",
            cls.HARASSMENT.value: "Harassment",
            cls.SUSPICIOUS_ACTIVITY.value: "Suspicious activity",
            cls.INFRASTRUCTURE_PROBLEM.value: "Infrastructure problem",
            cls.OTHER.value: "Other or uncertain",
        }

    @property
    def display_name(self) -> str:
        """Returns the human-readable display name for this category."""
        return self.display_names().get(self.value, "Other or uncertain")


@dataclass
class ClassificationResult:
    """Explainable result returned by the lightweight NLP text classifier."""
    suggested_category: str
    confidence: float
    method: str
    keywords_matched: List[str] = field(default_factory=list)
    needs_review: bool = False
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggested_category": self.suggested_category,
            "confidence": round(float(self.confidence), 3),
            "method": self.method,
            "keywords_matched": self.keywords_matched,
            "needs_review": self.needs_review,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClassificationResult":
        return cls(
            suggested_category=str(data.get("suggested_category", IncidentCategory.OTHER.value)),
            confidence=float(data.get("confidence", 0.0)),
            method=str(data.get("method", "rule_based_lexical_nlp")),
            keywords_matched=list(data.get("keywords_matched", [])),
            needs_review=bool(data.get("needs_review", False)),
            explanation=str(data.get("explanation", ""))
        )


@dataclass
class CommunityReport:
    """
    Modular representation of a community-submitted safety incident report.
    Supports complete validation, classification metadata, and privacy masking.
    """
    report_id: str
    description: str
    category: str
    latitude: float
    longitude: float
    incident_time: Optional[str] = None
    submission_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    review_status: ReviewStatus = ReviewStatus.PENDING
    severity: int = 1
    classification_result: Optional[ClassificationResult] = None
    possible_duplicate_of: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def generate_id(cls) -> str:
        """Generates a safe, readable unique report identifier."""
        return f"rep_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        """Internal dictionary representation including all system metadata."""
        return {
            "report_id": self.report_id,
            "description": self.description,
            "category": self.category,
            "category_label": IncidentCategory.display_names().get(self.category, "Other or uncertain"),
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "incident_time": self.incident_time,
            "submission_timestamp": self.submission_timestamp,
            "review_status": self.review_status.value if isinstance(self.review_status, ReviewStatus) else str(self.review_status),
            "severity": int(self.severity),
            "classification_result": self.classification_result.to_dict() if self.classification_result else None,
            "possible_duplicate_of": self.possible_duplicate_of,
            "metadata": self.metadata,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """
        Public-facing dictionary representation.
        Ensures privacy:
        - Excludes any private submitter IP or device metadata.
        - Excludes internal review notes.
        - Clearly tags verified status for frontend map rendering.
        - Clearly marks community crowdsourced nature (NOT official police crime statistics).
        """
        status_val = self.review_status.value if isinstance(self.review_status, ReviewStatus) else str(self.review_status)
        return {
            "report_id": self.report_id,
            "description": self.description,
            "category": self.category,
            "category_label": IncidentCategory.display_names().get(self.category, "Other or uncertain"),
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "incident_time": self.incident_time,
            "submission_timestamp": self.submission_timestamp,
            "review_status": status_val,
            "is_verified": (status_val == ReviewStatus.VERIFIED.value),
            "severity": int(self.severity),
            "classification": {
                "suggested_category": self.classification_result.suggested_category,
                "confidence": self.classification_result.confidence,
                "needs_review": self.classification_result.needs_review,
            } if self.classification_result else None,
            "possible_duplicate_of": self.possible_duplicate_of,
            "source": "community_crowdsourced",
            "disclaimer": "Community reports are crowdsourced user observations and do not represent confirmed crime statistics."
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommunityReport":
        """Instantiates a CommunityReport from a dictionary."""
        report_id = data.get("report_id") or cls.generate_id()
        raw_status = data.get("review_status", ReviewStatus.PENDING.value)
        try:
            status = ReviewStatus(raw_status)
        except ValueError:
            status = ReviewStatus.PENDING

        clf_data = data.get("classification_result")
        classification_result = None
        if isinstance(clf_data, dict):
            classification_result = ClassificationResult.from_dict(clf_data)

        return cls(
            report_id=str(report_id),
            description=str(data.get("description", "")),
            category=str(data.get("category", data.get("report_type", IncidentCategory.OTHER.value))),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            incident_time=data.get("incident_time") or data.get("timestamp"),
            submission_timestamp=data.get("submission_timestamp") or data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            review_status=status,
            severity=int(data.get("severity", 1)),
            classification_result=classification_result,
            possible_duplicate_of=data.get("possible_duplicate_of"),
            metadata=dict(data.get("metadata", {}))
        )
