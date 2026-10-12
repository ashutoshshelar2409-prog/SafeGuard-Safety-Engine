"""
Safety Engine Weights Configuration.
Defines the relative importance (weight) of each safety factor in the final score calculation.
All weights must be between 0.0 and 1.0 and sum to 1.0 (100%).
"""

FACTOR_WEIGHTS = {
    "lighting": 0.25,          # 25%
    "crime": 0.25,             # 25%
    "emergency_access": 0.15,   # 15%
    "infrastructure": 0.15,     # 15%
    "community": 0.20          # 20%
}

def validate_weights(weights: dict = None) -> bool:
    """
    Validates that all factor weights sum up to 1.0 (100%).

    Args:
        weights (dict, optional): Dictionary of weights. Defaults to FACTOR_WEIGHTS.

    Returns:
        bool: True if weights are valid.

    Raises:
        ValueError: If weights do not sum to 1.0 or contain invalid values.
    """
    if weights is None:
        weights = FACTOR_WEIGHTS
    
    for factor, weight in weights.items():
        if not isinstance(weight, (int, float)) or weight < 0 or weight > 1:
            raise ValueError(f"Weight for '{factor}' must be between 0 and 1, got {weight}")

    total = sum(weights.values())
    if not abs(total - 1.0) < 1e-5:
        raise ValueError(f"Weights must sum to 1.0 (100%), but got total: {total}")
    
    return True

# Validate on import
validate_weights()
