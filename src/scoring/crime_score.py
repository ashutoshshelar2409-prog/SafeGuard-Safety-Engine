"""
Crime Safety Score Calculation.
Computes a 0–100 safety factor score based on historical crime data near a route.
Higher crime count -> lower safety score (100 = safer, 0 = less safe).
"""

from typing import Union, List, Dict, Any
from src.processing.normalization import min_max_scale

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

MAX_BENCHMARK_CRIME_COUNT = 30.0


def calculate_crime_score(crime_data: Union[Any, List[Dict[str, Any]]]) -> float:
    """
    Calculates crime factor safety score from filtered crime data near the route.
    """
    if HAS_PANDAS and isinstance(crime_data, pd.DataFrame):
        if crime_data.empty:
            return 100.0
        total_crime_count = float(crime_data["crime_count"].sum())
    elif isinstance(crime_data, list):
        if not crime_data:
            return 100.0
        total_crime_count = sum(float(item.get("crime_count", 0)) for item in crime_data)
    else:
        return 100.0

    score = min_max_scale(
        value=total_crime_count,
        min_val=0.0,
        max_val=MAX_BENCHMARK_CRIME_COUNT,
        invert=True
    )

    return float(round(score, 2))
