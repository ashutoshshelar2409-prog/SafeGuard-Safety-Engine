"""
Emergency Access Safety Score Calculation.
Computes a 0–100 safety factor score based on proximity to emergency services (police, hospital).
Shorter distance to emergency services -> higher safety score (100 = closest/safest, 0 = isolated).
"""

from typing import List, Dict, Any, Union
from src.processing.route_processing import find_minimum_distance_to_route
from src.processing.normalization import min_max_scale

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

MAX_DISTANCE_BENCHMARK_KM = 5.0
MIN_DISTANCE_BENCHMARK_KM = 0.2


def calculate_emergency_score(
    route_coords: List[Dict[str, float]],
    emergency_data: Union[Any, List[Dict[str, Any]]]
) -> float:
    """
    Calculates emergency access score based on proximity to nearest police station and hospital.
    """
    if not route_coords:
        return 50.0

    if HAS_PANDAS and isinstance(emergency_data, pd.DataFrame):
        if emergency_data.empty:
            return 50.0
        police_items = emergency_data[emergency_data["type"].str.lower() == "police"].to_dict("records")
        hospital_items = emergency_data[emergency_data["type"].str.lower() == "hospital"].to_dict("records")
    elif isinstance(emergency_data, list):
        if not emergency_data:
            return 50.0
        police_items = [item for item in emergency_data if str(item.get("type", "")).lower() == "police"]
        hospital_items = [item for item in emergency_data if str(item.get("type", "")).lower() == "hospital"]
    else:
        return 50.0

    min_police_dist = float("inf")
    for item in police_items:
        d = find_minimum_distance_to_route(route_coords, float(item["latitude"]), float(item["longitude"]))
        if d < min_police_dist:
            min_police_dist = d

    min_hospital_dist = float("inf")
    for item in hospital_items:
        d = find_minimum_distance_to_route(route_coords, float(item["latitude"]), float(item["longitude"]))
        if d < min_hospital_dist:
            min_hospital_dist = d

    if min_police_dist == float("inf"):
        min_police_dist = MAX_DISTANCE_BENCHMARK_KM
    if min_hospital_dist == float("inf"):
        min_hospital_dist = MAX_DISTANCE_BENCHMARK_KM

    avg_emergency_dist = (min_police_dist + min_hospital_dist) / 2.0

    score = min_max_scale(
        value=avg_emergency_dist,
        min_val=MIN_DISTANCE_BENCHMARK_KM,
        max_val=MAX_DISTANCE_BENCHMARK_KM,
        invert=True
    )

    return float(round(score, 2))
