"""
Lighting Safety Score Calculation.
Computes a 0–100 safety factor score based on lighting quality data along a route.
Better lighting quality -> higher safety score (100 = safest, 0 = less safe).
"""

from typing import Union, List, Dict, Any
from src.processing.normalization import min_max_scale

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def calculate_lighting_score(lighting_data: Union[Any, List[Dict[str, Any]]]) -> float:
    """
    Calculates lighting factor safety score from lighting data along the route.
    """
    if HAS_PANDAS and isinstance(lighting_data, pd.DataFrame):
        if lighting_data.empty:
            return 50.0
        avg_lighting = float(lighting_data["lighting_quality"].mean())
    elif isinstance(lighting_data, list):
        if not lighting_data:
            return 50.0
        avg_lighting = sum(float(item.get("lighting_quality", 50)) for item in lighting_data) / len(lighting_data)
    else:
        return 50.0

    score = min_max_scale(
        value=avg_lighting,
        min_val=0.0,
        max_val=100.0,
        invert=False
    )

    return float(round(score, 2))
