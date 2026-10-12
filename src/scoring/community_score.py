"""
Community Reports Safety Score Calculation.
Computes a 0–100 safety factor score based on user community reports along a route.
Higher report density / severity -> lower safety score (100 = no reports, 0 = severe reports).
"""

from typing import List, Dict, Any
from src.processing.normalization import min_max_scale

# Max severity load benchmark for normalization scaling
MAX_COMMUNITY_SEVERITY_BENCHMARK = 15.0


def calculate_community_score(reports: List[Dict[str, Any]]) -> float:
    """
    Calculates community factor safety score based on user community reports near the route.

    Args:
        reports (List[Dict]): List of report objects near the route.

    Returns:
        float: Community safety score between 0.0 and 100.0.
    """
    if not reports:
        # No adverse community reports along route -> maximum safety score
        return 100.0

    # Accumulate total severity score of reports along the route
    total_severity = sum(float(r.get("severity", 1)) for r in reports)

    # Inverted scaling: higher total report severity -> lower safety score
    score = min_max_scale(
        value=total_severity,
        min_val=0.0,
        max_val=MAX_COMMUNITY_SEVERITY_BENCHMARK,
        invert=True
    )

    return float(round(score, 2))
