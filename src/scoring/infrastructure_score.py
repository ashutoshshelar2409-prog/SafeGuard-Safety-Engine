"""
Infrastructure Safety Score Calculation.
Computes a 0–100 safety factor score based on road condition and pedestrian access.
Better infrastructure -> higher safety score (100 = best condition, 0 = poor/dangerous).
"""

from typing import Union, List, Dict, Any
from src.processing.normalization import min_max_scale

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def calculate_infrastructure_score(infrastructure_data: Union[Any, List[Dict[str, Any]]]) -> float:
    """
    Calculates infrastructure factor safety score from road condition and pedestrian access.
    """
    if HAS_PANDAS and isinstance(infrastructure_data, pd.DataFrame):
        if infrastructure_data.empty:
            return 50.0
        avg_road = float(infrastructure_data["road_condition"].mean())
        avg_pedestrian = float(infrastructure_data["pedestrian_access"].mean())
    elif isinstance(infrastructure_data, list):
        if not infrastructure_data:
            return 50.0
        avg_road = sum(float(item.get("road_condition", 50)) for item in infrastructure_data) / len(infrastructure_data)
        avg_pedestrian = sum(float(item.get("pedestrian_access", 50)) for item in infrastructure_data) / len(infrastructure_data)
    else:
        return 50.0

    avg_quality = (avg_road + avg_pedestrian) / 2.0

    score = min_max_scale(
        value=avg_quality,
        min_val=0.0,
        max_val=100.0,
        invert=False
    )

    return float(round(score, 2))
