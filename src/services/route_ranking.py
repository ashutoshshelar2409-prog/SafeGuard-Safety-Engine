"""
Route Ranking Service (Member 2).
Provides transparent, multi-criteria route comparison and ranking:
- Fastest: prioritizes lowest travel duration.
- Safest-scoring: prioritizes highest valid SafetyEngine safety score.
- Balanced: normalized composite comparison between travel time and safety.
"""

from typing import List, Optional
from src.models.route_request import EvaluatedRoute


class RouteRankingService:
    """
    Ranks evaluated routes according to Fastest, Safest, and Balanced criteria.
    Maintains complete separation from Member 1's factor scoring logic.
    """

    def __init__(
        self,
        balanced_safety_weight: float = 0.5,
        balanced_time_weight: float = 0.5
    ):
        """
        Initialize RouteRankingService.

        Args:
            balanced_safety_weight (float): Relative weight of safety score in balanced ranking (0.0 to 1.0).
            balanced_time_weight (float): Relative weight of normalized time score in balanced ranking.
        """
        if abs((balanced_safety_weight + balanced_time_weight) - 1.0) > 1e-5:
            raise ValueError("Balanced weights must sum to 1.0.")
        self.w_safety = balanced_safety_weight
        self.w_time = balanced_time_weight

    def rank_routes(
        self,
        evaluated_routes: List[EvaluatedRoute]
    ) -> List[EvaluatedRoute]:
        """
        Computes and assigns Fastest, Safest, and Balanced rankings across candidate routes.
        Mutates the rank fields and tags of each EvaluatedRoute, and returns the list.
        """
        if not evaluated_routes:
            return []

        if len(evaluated_routes) == 1:
            single = evaluated_routes[0]
            single.rank_fastest = 1
            single.rank_safest = 1
            single.rank_balanced = 1
            single.balanced_score = round(float(single.safety_score), 2)
            single.tags = ["fastest", "safest", "balanced"]
            return evaluated_routes

        # 1. Compute Normalized Balanced Score
        durations = [r.duration_minutes for r in evaluated_routes]
        min_dur = min(durations)
        max_dur = max(durations)

        for route in evaluated_routes:
            if max_dur > min_dur:
                # 100 = fastest among alternatives, 0 = slowest among alternatives
                time_score = 100.0 * (1.0 - (route.duration_minutes - min_dur) / (max_dur - min_dur))
            else:
                time_score = 100.0

            balanced = (self.w_safety * route.safety_score) + (self.w_time * time_score)
            route.balanced_score = round(float(balanced), 2)

        # 2. Assign Fastest Ranks (duration ascending, then distance ascending, then safety descending)
        sorted_by_fastest = sorted(
            evaluated_routes,
            key=lambda r: (r.duration_minutes, r.distance_km, -r.safety_score)
        )
        for rank_idx, r in enumerate(sorted_by_fastest, start=1):
            r.rank_fastest = rank_idx

        # 3. Assign Safest Ranks (safety score descending, then duration ascending)
        sorted_by_safest = sorted(
            evaluated_routes,
            key=lambda r: (-r.safety_score, r.duration_minutes, r.distance_km)
        )
        for rank_idx, r in enumerate(sorted_by_safest, start=1):
            r.rank_safest = rank_idx

        # 4. Assign Balanced Ranks (balanced score descending, then safety descending, then duration ascending)
        sorted_by_balanced = sorted(
            evaluated_routes,
            key=lambda r: (-r.balanced_score, -r.safety_score, r.duration_minutes)
        )
        for rank_idx, r in enumerate(sorted_by_balanced, start=1):
            r.rank_balanced = rank_idx

        # 5. Assign Recommendation Badges / Tags
        fastest_winner = sorted_by_fastest[0]
        safest_winner = sorted_by_safest[0]
        balanced_winner = sorted_by_balanced[0]

        for r in evaluated_routes:
            tags = []
            if r.route.route_id == fastest_winner.route.route_id:
                tags.append("fastest")
            if r.route.route_id == safest_winner.route.route_id:
                tags.append("safest")
            if r.route.route_id == balanced_winner.route.route_id:
                tags.append("balanced")
            r.tags = tags

        return evaluated_routes

    def get_ranked_by_criterion(
        self,
        evaluated_routes: List[EvaluatedRoute],
        criterion: str = "balanced"
    ) -> List[EvaluatedRoute]:
        """
        Returns routes ordered according to the chosen ranking criterion.

        Args:
            evaluated_routes: List of already-ranked routes.
            criterion: 'fastest', 'safest', or 'balanced' (default).
        """
        criterion_lower = criterion.lower()
        if criterion_lower == "fastest":
            return sorted(evaluated_routes, key=lambda r: r.rank_fastest)
        if criterion_lower == "safest":
            return sorted(evaluated_routes, key=lambda r: r.rank_safest)
        if criterion_lower == "balanced":
            return sorted(evaluated_routes, key=lambda r: r.rank_balanced)
        raise ValueError(f"Unknown ranking criterion: '{criterion}'. Choose 'fastest', 'safest', or 'balanced'.")
