"""
Crime Safety Score Calculation.
Computes a 0–100 safety factor score based on historical crime data near a route.

Calculated per-kilometre to eliminate route length bias.
Higher crime density (crimes/km) -> lower safety score (100 = safer, 0 = less safe).
"""

from typing import Union, List, Dict, Any, Optional
from src.processing.normalization import min_max_scale
from src.processing.route_processing import route_length_km

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# Recalibrated benchmark: 10 crimes per km (recalibrated from 30 crimes over ~3 km route)
MAX_CRIMES_PER_KM = 10.0
MAX_BENCHMARK_CRIME_COUNT = MAX_CRIMES_PER_KM  # Backwards compatibility alias


def calculate_crime_score(
    crime_data: Union[Any, List[Dict[str, Any]]],
    route_km_or_coords: Optional[Union[float, int, List[Any]]] = None,
    *,
    route_km: Optional[float] = None,
    coordinates: Optional[List[Any]] = None,
    max_crimes_per_km: float = MAX_CRIMES_PER_KM,
    empty_default: float = 50.0
) -> float:
    """
    Calculates crime factor safety score from filtered crime data near the route,
    normalized per kilometre. Missing/empty data defaults to a neutral score (50.0)
    rather than treating lack of data as evidence of complete safety (100.0).

    Args:
        crime_data: Filtered crime records near the route (DataFrame or list of dicts).
        route_km_or_coords: Optional route distance in km, or list of coordinates.
        route_km: Optional keyword-only route distance in km.
        coordinates: Optional keyword-only list of coordinate points.
        max_crimes_per_km: Maximum benchmark crime density for 0-score normalization.
        empty_default: Fallback score when crime data is unavailable (default: 50.0).

    Returns:
        float: Safety score between 0.0 and 100.0.
    """
    if HAS_PANDAS and isinstance(crime_data, pd.DataFrame):
        if crime_data.empty:
            return empty_default
        total_crime_count = float(crime_data["crime_count"].sum())
    elif isinstance(crime_data, list):
        if not crime_data:
            return empty_default
        total_crime_count = sum(float(item.get("crime_count", 0)) for item in crime_data)
    else:
        return empty_default

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

    # Floor at 0.5 km to prevent extreme scaling on tiny routes and avoid zero division
    effective_km = max(eff_km if eff_km is not None else 1.0, 0.5)

    crime_per_km = total_crime_count / effective_km

    score = min_max_scale(
        value=crime_per_km,
        min_val=0.0,
        max_val=max_crimes_per_km,
        invert=True
    )

    return float(round(score, 2))
