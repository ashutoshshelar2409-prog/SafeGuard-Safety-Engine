"""
Routing Provider Layer (Member 2).
Interacts with real external routing engines (OSRM) to calculate alternative routes,
extract geometries, distances, and travel times, and normalizes coordinates
for SafeGuard's Safety Engine.
"""

from abc import ABC, abstractmethod
import json
import logging
import os
import urllib.error
import urllib.request
from typing import List, Optional

from src.models.route import Route
from src.models.route_request import Coordinate, RouteRequest

logger = logging.getLogger(__name__)


class RoutingError(Exception):
    """Base exception for routing failures."""
    pass


class RoutingConnectionError(RoutingError):
    """Raised when the routing provider cannot be reached (network/timeout)."""
    pass


class RoutingAPIError(RoutingError):
    """Raised when routing provider returns an HTTP error or error code."""
    pass


class NoRouteFoundError(RoutingError):
    """Raised when no viable route exists between origin and destination."""
    pass


class RoutingProvider(ABC):
    """Abstract interface for routing engines."""

    @abstractmethod
    def get_routes(self, request: RouteRequest) -> List[Route]:
        """
        Calculate one or more route alternatives for the given request.

        Args:
            request (RouteRequest): Validated origin, destination, profile, and options.

        Returns:
            List[Route]: List of Member 1 Route instances.

        Raises:
            RoutingError: If calculation or network fails.
        """
        pass


class OSRMProvider(RoutingProvider):
    """
    Real routing provider integrating with Open Source Routing Machine (OSRM).
    Fetches real road network routes, alternative paths, geometry, distance, and duration.
    """

    DEFAULT_BASE_URL = "https://router.project-osrm.org"
    PROFILE_MAP = {
        "driving": "driving",
        "walking": "foot",
        "foot": "foot",
        "cycling": "bike",
        "bike": "bike",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: float = 8.0,
        user_agent: str = "SafeGuard-Safety-Engine/1.0"
    ):
        """
        Initialize OSRM routing provider.

        Args:
            base_url (str, optional): OSRM server URL. Defaults to env OSRM_BASE_URL or public demo.
            timeout_seconds (float): Network request timeout.
            user_agent (str): Request User-Agent header.
        """
        self.base_url = (
            base_url
            or os.environ.get("OSRM_BASE_URL")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def _resolve_profile(self, profile: str) -> str:
        """Map generic profile names to OSRM mode profiles."""
        return self.PROFILE_MAP.get(profile.lower(), "driving")

    def _build_url(self, request: RouteRequest) -> str:
        """Build OSRM route request URL with proper coordinate order (lon,lat)."""
        mode = self._resolve_profile(request.profile)
        # OSRM coordinate syntax: {lon1},{lat1};{lon2},{lat2}
        coords_str = (
            f"{request.origin.longitude:.6f},{request.origin.latitude:.6f};"
            f"{request.destination.longitude:.6f},{request.destination.latitude:.6f}"
        )
        alt_param = "true" if request.alternatives else "false"
        # Request full GeoJSON geometries so coordinates are exact
        return (
            f"{self.base_url}/route/v1/{mode}/{coords_str}"
            f"?overview=full&geometries=geojson&alternatives={alt_param}&steps=false"
        )

    def get_routes(self, request: RouteRequest) -> List[Route]:
        """
        Fetches route alternatives from the live OSRM service.
        Extracts distance (converted to km), duration (converted to minutes),
        and normalizes GeoJSON coordinates ([lon, lat] -> {'latitude': lat, 'longitude': lon}).
        """
        url = self._build_url(request)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json"
        }

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                status_code = response.getcode()
                if status_code != 200:
                    raise RoutingAPIError(f"OSRM returned HTTP status {status_code}")
                raw_bytes = response.read()
                data = json.loads(raw_bytes.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RoutingAPIError(f"OSRM HTTP error {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RoutingConnectionError(
                f"Failed to connect to OSRM routing provider at {self.base_url}: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RoutingAPIError(f"Invalid JSON response received from OSRM: {exc}") from exc

        code = data.get("code")
        if code == "NoRoute":
            raise NoRouteFoundError("No road route could be found between origin and destination.")
        if code != "Ok":
            message = data.get("message", code)
            raise RoutingAPIError(f"OSRM service error: {message}")

        raw_routes = data.get("routes", [])
        if not raw_routes:
            raise NoRouteFoundError("OSRM response contained no routes.")

        routes: List[Route] = []
        for idx, r in enumerate(raw_routes[:request.max_alternatives]):
            # Distance in OSRM is meters -> convert to kilometers
            dist_km = round(float(r.get("distance", 0.0)) / 1000.0, 3)
            # Duration in OSRM is seconds -> convert to minutes
            dur_mins = round(float(r.get("duration", 0.0)) / 60.0, 2)

            geometry = r.get("geometry", {})
            geo_coords = geometry.get("coordinates", [])

            # CRITICAL COORDINATE NORMALIZATION:
            # GeoJSON geometry coordinates are [longitude, latitude].
            # Member 1's Route model requires {'latitude': lat, 'longitude': lon}.
            # We explicitly map longitude to lon and latitude to lat here.
            normalized_coords = []
            for point in geo_coords:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    lon = float(point[0])
                    lat = float(point[1])
                    normalized_coords.append({"latitude": lat, "longitude": lon})

            if not normalized_coords:
                # Fallback to origin and destination if geometry is unexpectedly empty
                normalized_coords = [
                    {"latitude": request.origin.latitude, "longitude": request.origin.longitude},
                    {"latitude": request.destination.latitude, "longitude": request.destination.longitude}
                ]

            route_id = f"route_{idx + 1}"
            route = Route(
                route_id=route_id,
                distance_km=dist_km,
                duration_minutes=dur_mins,
                coordinates=normalized_coords
            )
            routes.append(route)

        return routes


class MockRoutingProvider(RoutingProvider):
    """
    Deterministic routing provider for testing and offline scenarios.
    Returns pre-configured realistic route alternatives without network access.
    """

    def __init__(self, routes_to_return: Optional[List[Route]] = None):
        self.routes_to_return = routes_to_return or []

    def set_routes(self, routes: List[Route]) -> None:
        """Inject routes to return."""
        self.routes_to_return = routes

    def get_routes(self, request: RouteRequest) -> List[Route]:
        """Returns pre-configured routes or generates deterministic alternatives between endpoints."""
        if self.routes_to_return:
            return self.routes_to_return

        # Generate 2 deterministic distinct alternative routes connecting origin & destination
        lat1, lon1 = request.origin.latitude, request.origin.longitude
        lat2, lon2 = request.destination.latitude, request.destination.longitude

        # Alternative 1: Direct path
        coords_alt1 = [
            {"latitude": lat1, "longitude": lon1},
            {"latitude": round((lat1 * 2 + lat2) / 3, 6), "longitude": round((lon1 * 2 + lon2) / 3, 6)},
            {"latitude": round((lat1 + lat2 * 2) / 3, 6), "longitude": round((lon1 + lon2 * 2) / 3, 6)},
            {"latitude": lat2, "longitude": lon2},
        ]
        # Alternative 2: Curved detour path (e.g. via main road)
        mid_lat = (lat1 + lat2) / 2 + 0.003
        mid_lon = (lon1 + lon2) / 2 + 0.003
        coords_alt2 = [
            {"latitude": lat1, "longitude": lon1},
            {"latitude": round(mid_lat, 6), "longitude": round(mid_lon, 6)},
            {"latitude": lat2, "longitude": lon2},
        ]

        route1 = Route(
            route_id="route_1",
            distance_km=3.2,
            duration_minutes=12.0,
            coordinates=coords_alt1
        )
        route2 = Route(
            route_id="route_2",
            distance_km=3.8,
            duration_minutes=16.0,
            coordinates=coords_alt2
        )

        return [route1, route2] if request.alternatives else [route1]
