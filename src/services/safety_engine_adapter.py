"""
Safety Engine Adapter Service (Member 2).
Provides a resilient, transparent integration adapter between Member 2's routing subsystem
and Member 1's SafetyEngine.
"""

import logging
import os
from typing import Dict, Any, List, Optional

from src.models.route import Route
from src.processing.validation import validate_coordinates
from src.services.safety_engine import SafetyEngine

logger = logging.getLogger(__name__)


class SafetyEngineIntegrationError(Exception):
    """Raised when integration with Member 1's SafetyEngine fails."""
    pass


class SafetyEngineAdapter:
    """
    Adapter encapsulating Member 1's SafetyEngine.
    Guarantees coordinate validation, explicit error reporting, and prevents
    any duplication of Member 1's internal scoring formulas.
    """

    def __init__(self, engine: Optional[SafetyEngine] = None, data_dir: str = "data/raw"):
        """
        Initialize SafetyEngineAdapter.

        Args:
            engine (SafetyEngine, optional): Pre-existing SafetyEngine instance.
            data_dir (str): Path to data directory for SafetyEngine initialization.
        """
        self.data_dir = data_dir
        self.engine = engine if engine is not None else SafetyEngine(data_dir=data_dir)
        self._data_loaded = False

    def ensure_data_loaded(self) -> None:
        """
        Calls Member 1's real `load_data()` method and verifies data availability.
        Reports missing datasets explicitly without guessing or fabricating data.
        """
        if self._data_loaded:
            return

        if not os.path.isdir(self.data_dir):
            raise SafetyEngineIntegrationError(
                f"Safety data directory '{self.data_dir}' does not exist. Cannot load safety datasets."
            )

        try:
            self.engine.load_data()
            self._data_loaded = True
            logger.info("SafetyEngine data successfully loaded via adapter.")
        except Exception as exc:
            raise SafetyEngineIntegrationError(
                f"Member 1's SafetyEngine failed during load_data(): {exc}"
            ) from exc

    def validate_route_for_engine(self, route: Route) -> None:
        """
        Pre-flight validation ensuring coordinates strictly conform to geographical
        bounds before passing to the SafetyEngine.
        """
        if not route.coordinates:
            raise SafetyEngineIntegrationError(
                f"Route '{route.route_id}' has no coordinates for safety analysis."
            )

        for idx, pt in enumerate(route.coordinates):
            lat = pt.get("latitude")
            lon = pt.get("longitude")
            if lat is None or lon is None or not validate_coordinates(lat, lon):
                raise SafetyEngineIntegrationError(
                    f"Route '{route.route_id}' has invalid coordinate at index {idx}: {pt}"
                )

    def analyze_route(self, route: Route) -> Dict[str, Any]:
        """
        Calls Member 1's real `analyze_route(...)` method and validates the output.

        Args:
            route (Route): Validated Route model instance.

        Returns:
            Dict[str, Any]: Structured result dictionary containing:
                - route_id (str)
                - safety_score (float)
                - breakdown (Dict[str, float])
                - weights (Dict[str, float])
                - status (str)

        Raises:
            SafetyEngineIntegrationError: If analysis fails or output schema is invalid.
        """
        self.ensure_data_loaded()
        self.validate_route_for_engine(route)

        try:
            raw_result = self.engine.analyze_route(route)
        except Exception as exc:
            raise SafetyEngineIntegrationError(
                f"Member 1's analyze_route() failed for route '{route.route_id}': {exc}"
            ) from exc

        # Strict validation of Member 1's returned schema
        if not isinstance(raw_result, dict):
            raise SafetyEngineIntegrationError(
                f"Expected dict from analyze_route(), got {type(raw_result)}"
            )

        if "safety_score" not in raw_result or "breakdown" not in raw_result:
            raise SafetyEngineIntegrationError(
                f"Member 1's output missing required keys ('safety_score', 'breakdown'): {raw_result.keys()}"
            )

        score = raw_result.get("safety_score")
        if not isinstance(score, (int, float)) or score < 0.0 or score > 100.0:
            raise SafetyEngineIntegrationError(
                f"Invalid safety_score returned by engine: {score}. Expected float between 0 and 100."
            )

        breakdown = raw_result.get("breakdown", {})
        expected_factors = ["lighting", "crime", "emergency_access", "infrastructure", "community"]
        for factor in expected_factors:
            if factor not in breakdown:
                logger.warning("Factor '%s' missing from Member 1 breakdown.", factor)

        return raw_result

    def analyze_routes(self, routes: List[Route]) -> List[Dict[str, Any]]:
        """
        Analyzes a list of routes sequentially through the SafetyEngine.
        """
        results = []
        for route in routes:
            results.append(self.analyze_route(route))
        return results
