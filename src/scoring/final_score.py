"""
Final Weighted Safety Score Calculation.
Aggregates individual factor safety scores into a transparent, single overall Safety Score (0–100).
"""

from typing import Dict
from src.config.weights import FACTOR_WEIGHTS, validate_weights
from src.processing.normalization import _clip_0_100


def calculate_final_safety_score(
    scores: Dict[str, float],
    weights: Dict[str, float] = None
) -> float:
    """
    Computes the final weighted Safety Score (0–100).

    Formula:
        Final Score = Σ (Factor_Score_i * Weight_i)

    Args:
        scores (Dict[str, float]): Dictionary containing factor scores (0–100).
            Keys: 'lighting', 'crime', 'emergency_access', 'infrastructure', 'community'
        weights (Dict[str, float], optional): Custom weights dictionary. Defaults to FACTOR_WEIGHTS.

    Returns:
        float: Overall safety score bounded strictly between 0 and 100.
    """
    if weights is None:
        weights = FACTOR_WEIGHTS

    validate_weights(weights)

    final_score = 0.0
    for factor, weight in weights.items():
        factor_score = scores.get(factor, 50.0)  # Default neutral 50 if missing factor
        final_score += factor_score * weight

    # Guarantee final score is strictly bounded between 0 and 100
    bounded_score = _clip_0_100(final_score)
    return float(round(bounded_score, 2))
