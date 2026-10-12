"""
Data Normalization Module.
Provides reusable functions to convert raw safety parameters into a uniform 0–100 scale.
In all score functions: 100 = safer, 0 = less safe.
"""

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _clip_0_100(val: float) -> float:
    """Clips value strictly between 0.0 and 100.0."""
    if HAS_NUMPY:
        return float(np.clip(val, 0.0, 100.0))
    return float(max(0.0, min(100.0, val)))


def min_max_scale(
    value: float,
    min_val: float,
    max_val: float,
    invert: bool = False
) -> float:
    """
    Scales a raw numeric value to a 0–100 range using Min-Max scaling.

    Args:
        value (float): The raw value to normalize.
        min_val (float): Expected minimum possible raw value.
        max_val (float): Expected maximum possible raw value.
        invert (bool): If True, higher raw values produce LOWER safety scores (e.g. crime).

    Returns:
        float: Normalized score bounded strictly between 0 and 100.
    """
    if max_val == min_val:
        # Avoid division by zero. Return neutral score of 50.0.
        score = 50.0
    else:
        # Standard min-max ratio [0, 1]
        normalized = (value - min_val) / (max_val - min_val)
        
        if invert:
            # Higher raw value = lower safety score
            score = (1.0 - normalized) * 100.0
        else:
            # Higher raw value = higher safety score
            score = normalized * 100.0

    return _clip_0_100(score)


def scale_rating_to_100(
    rating: float,
    min_rating: float = 1.0,
    max_rating: float = 5.0,
    invert: bool = False
) -> float:
    """
    Utility wrapper to convert discrete ratings (e.g., 1–5 or 1–10) to 0–100 score.
    """
    return min_max_scale(rating, min_rating, max_rating, invert=invert)
