"""
Routing Service Orchestrator (Member 2).
Coordinates external route generation, coordinate normalization,
safety score analysis via Member 1's SafetyEngine, and multi-criteria route ranking.
"""

import logging
from typing import Dict, Any, List, Optional, Union

from src.models.route import Route
from src.models.route_request import Coordinate, RouteRequest, EvaluatedRoute
from src.providers.routing_provider import RoutingProvider, OSRMProvider
from src.services.safety_engine_adapter import SafetyEngineAdapter
from src.services.route_ranking import RouteRankingService

logger = logging.getLogger(__name__)


class RoutingService:
    """
    High-level facade orchestrating Member 2 routing operations:
    1. Fetches candidate routes from real routing provider (OSRM).
    2. Sends routes through Member 1's SafetyEngine via adapter.
    3. Ranks routes by Fastest, Safest, and Balanced criteria.
    4. Formats clean, transparent output for API and React SafeRoute frontend.
    """

    def __init__(
        self,
        provider: Optional[RoutingProvider] = None,
        adapter: Optional[SafetyEngineAdapter] = None,
        ranking_service: Optional[RouteRankingService] = None,
        data_dir: str = "data/raw"
    ):
        """
        Initialize RoutingService with dependencies (supporting dependency injection).

        Args:
            provider (RoutingProvider, optional): Routing provider instance. Defaults to OSRMProvider.
            adapter (SafetyEngineAdapter, optional): Adapter for SafetyEngine.
            ranking_service (RouteRankingService, optional): Ranking service.
            data_dir (str): Data directory for SafetyEngine if adapter not provided.
        """
        self.provider = provider or OSRMProvider()
        self.adapter = adapter or SafetyEngineAdapter(data_dir=data_dir)
        self.ranking_service = ranking_service or RouteRankingService()

    def calculate_routes(
        self,
        request_input: Union[RouteRequest, Dict[str, Any]],
        preferred_ranking: str = "balanced"
    ) -> Dict[str, Any]:
        """
        End-to-end route calculation, safety analysis, and ranking.

        Args:
            request_input: RouteRequest instance or raw dictionary payload.
            preferred_ranking: 'balanced' (default), 'fastest', or 'safest'.

        Returns:
            Dict[str, Any]: Structured output dictionary for API / frontend consumers.
        """
        # Step 1: Parse and validate request
        if isinstance(request_input, RouteRequest):
            request = request_input
        elif isinstance(request_input, dict):
            request = RouteRequest.from_dict(request_input)
        else:
            raise TypeError(f"Expected RouteRequest or dict, got {type(request_input)}")

        # Step 2: Fetch real routes from provider
        routes = self.provider.get_routes(request)
        if not routes:
            raise ValueError("No routes returned by provider.")

        # Step 3: Analyze each route through SafetyEngineAdapter
        evaluated_routes: List[EvaluatedRoute] = []
        for route in routes:
            safety_output = self.adapter.analyze_route(route)
            evaluated = EvaluatedRoute(
                route=route,
                safety_score=safety_output.get("safety_score", 0.0),
                breakdown=safety_output.get("breakdown", {}),
                weights=safety_output.get("weights", {}),
                status=safety_output.get("status", "success"),
                message=safety_output.get("message", ""),
                data_coverage=safety_output.get("data_coverage", "supported")
            )
            evaluated_routes.append(evaluated)

        # Step 4: Multi-criteria ranking (Fastest, Safest, Balanced)
        ranked_routes = self.ranking_service.rank_routes(evaluated_routes)

        # Step 5: Sort routes by the preferred ranking criterion
        ordered_routes = self.ranking_service.get_ranked_by_criterion(
            ranked_routes,
            criterion=preferred_ranking
        )

        # Step 6: Identify designated winners for frontend badges
        fastest_winner = min(ranked_routes, key=lambda r: r.rank_fastest)
        safest_winner = min(ranked_routes, key=lambda r: r.rank_safest)
        balanced_winner = min(ranked_routes, key=lambda r: r.rank_balanced)

        return {
            "status": "success",
            "query": {
                "origin": request.origin.to_dict(),
                "destination": request.destination.to_dict(),
                "profile": request.profile,
                "alternatives_requested": request.alternatives,
                "preferred_ranking": preferred_ranking
            },
            "total_routes_found": len(ranked_routes),
            "recommendations": {
                "fastest_route_id": fastest_winner.route.route_id,
                "safest_route_id": safest_winner.route.route_id,
                "balanced_route_id": balanced_winner.route.route_id
            },
            "disclaimer": (
                "SafeGuard safety scores are contextual analytical estimates based on available historical "
                "and environmental datasets and do not guarantee personal safety."
            ),
            "routes": [r.to_dict() for r in ordered_routes]
        }

    def compare_custom_routes(
        self,
        routes: List[Union[Route, Dict[str, Any]]],
        preferred_ranking: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Takes already generated or custom routes, runs them through the SafetyEngine,
        and provides comparative ranking.
        """
        if not routes:
            raise ValueError("Route list cannot be empty.")

        parsed_routes: List[Route] = []
        for r in routes:
            if isinstance(r, Route):
                parsed_routes.append(r)
            elif isinstance(r, dict):
                parsed_routes.append(Route.from_dict(r))
            else:
                raise TypeError(f"Invalid route type: {type(r)}")

        evaluated_routes: List[EvaluatedRoute] = []
        for route in parsed_routes:
            safety_output = self.adapter.analyze_route(route)
            evaluated = EvaluatedRoute(
                route=route,
                safety_score=safety_output.get("safety_score", 0.0),
                breakdown=safety_output.get("breakdown", {}),
                weights=safety_output.get("weights", {}),
                status=safety_output.get("status", "success"),
                message=safety_output.get("message", ""),
                data_coverage=safety_output.get("data_coverage", "supported")
            )
            evaluated_routes.append(evaluated)

        ranked_routes = self.ranking_service.rank_routes(evaluated_routes)
        ordered_routes = self.ranking_service.get_ranked_by_criterion(
            ranked_routes,
            criterion=preferred_ranking
        )

        fastest_winner = min(ranked_routes, key=lambda r: r.rank_fastest)
        safest_winner = min(ranked_routes, key=lambda r: r.rank_safest)
        balanced_winner = min(ranked_routes, key=lambda r: r.rank_balanced)

        return {
            "status": "success",
            "total_routes_evaluated": len(ranked_routes),
            "recommendations": {
                "fastest_route_id": fastest_winner.route.route_id,
                "safest_route_id": safest_winner.route.route_id,
                "balanced_route_id": balanced_winner.route.route_id
            },
            "disclaimer": (
                "SafeGuard safety scores are contextual analytical estimates based on available historical "
                "and environmental datasets and do not guarantee personal safety."
            ),
            "routes": [r.to_dict() for r in ordered_routes]
        }
