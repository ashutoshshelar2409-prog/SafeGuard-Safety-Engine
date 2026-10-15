"""
Community Reports Safety Score Calculation.
Computes a 0–100 safety factor score based on user community reports along a route.
Calculated per-kilometre to eliminate route length bias.
Higher report severity density (severity/km) -> lower safety score (100 = no reports, 0 = severe reports).
"""

from typing import List, Dict, Any, Optional, Union
from src.processing.normalization import min_max_scale
from src.processing.route_processing import route_length_km

# Recalibrated benchmark: 5.0 severity load per km (recalibrated from 15 severity over ~3 km route)
MAX_COMMUNITY_SEVERITY_PER_KM = 5.0
MAX_COMMUNITY_SEVERITY_BENCHMARK = MAX_COMMUNITY_SEVERITY_PER_KM  # Backwards compatibility alias


def calculate_community_score(
    reports: List[Dict[str, Any]],
    route_km_or_coords: Optional[Union[float, int, List[Any]]] = None,
    *,
    route_km: Optional[float] = None,
    coordinates: Optional[List[Any]] = None,
    max_severity_per_km: float = MAX_COMMUNITY_SEVERITY_PER_KM,
    empty_default: float = 50.0
) -> float:
    """
    Calculates community factor safety score based on user community reports near the route,
    normalized per kilometre. Missing/empty reports default to a neutral score (50.0)
    rather than treating lack of data as evidence of complete safety (100.0).

    Args:
        reports (List[Dict]): List of report objects near the route.
        route_km_or_coords: Optional route distance in km, or list of coordinates.
        route_km: Optional keyword-only route distance in km.
        coordinates: Optional keyword-only list of coordinate points.
        max_severity_per_km: Maximum benchmark severity density for 0-score normalization.
        empty_default: Fallback score when community data is unavailable (default: 50.0).

    Returns:
        float: Community safety score between 0.0 and 100.0.
    """
    if not reports:
        # Missing / unavailable community reports along route -> neutral default (not 100)
        return empty_default

    # Accumulate total severity score of reports along the route
    total_severity = sum(float(r.get("severity", 1)) for r in reports)

    # Resolve effective route length in km
    eff_km: Optional[float] = None
    if route_km is not None:
        eff_km = float(route_km)
    elif coordinates is not None:
        eff_km = route_length_km(coordinates)
    elif isinstance(route_km_or_coords, (int, float)):
        eff_km = float(route_km_or_coords)
    elif isinstance(route_km_or_coords, list):
        eff_km = route_length_km(route_km_or_coords)

    # Apply minimum floor of 0.5 km
    effective_km = max(eff_km if eff_km is not None else 1.0, 0.5)

    severity_per_km = total_severity / effective_km

    # Inverted scaling: higher report severity per km -> lower safety score
    score = min_max_scale(
        value=severity_per_km,
        min_val=0.0,
        max_val=max_severity_per_km,
        invert=True
    )

    return float(round(score, 2))
