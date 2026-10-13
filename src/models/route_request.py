"""
Route Request and Ranking Data Models (Member 2).
Provides validated coordinate representations, request configurations,
and enriched ranked route models for SafeGuard navigation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union
from src.processing.validation import validate_coordinates
from src.models.route import Route


@dataclass
class Coordinate:
    """
    Geographical coordinate representation with strict validation.
    """
    latitude: float
    longitude: float

    def __post_init__(self):
        try:
            self.latitude = float(self.latitude)
            self.longitude = float(self.longitude)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Coordinates must be numeric: {exc}") from exc

        if not validate_coordinates(self.latitude, self.longitude):
            raise ValueError(
                f"Coordinates out of bounds: lat={self.latitude}, lon={self.longitude}. "
                "Latitude must be between -90 and 90, Longitude between -180 and 180."
            )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary with explicit latitude and longitude keys."""
        return {"latitude": self.latitude, "longitude": self.longitude}

    def to_lat_lng_tuple(self) -> Tuple[float, float]:
        """Return (latitude, longitude) tuple."""
        return (self.latitude, self.longitude)

    def to_lng_lat_tuple(self) -> Tuple[float, float]:
        """Return (longitude, latitude) tuple, standard for GeoJSON / OSRM."""
        return (self.longitude, self.latitude)

    @classmethod
    def from_any(cls, value: Union["Coordinate", Dict[str, Any], Tuple[float, float], List[float]]) -> "Coordinate":
        """
        Parses coordinates from various formats:
        - Coordinate instance
        - dict with 'latitude'/'lat' and 'longitude'/'lng'/'lon'
        - (lat, lng) tuple or list
        """
        if isinstance(value, Coordinate):
            return value
        if isinstance(value, dict):
            lat = value.get("latitude", value.get("lat"))
            lng = value.get("longitude", value.get("lng", value.get("lon")))
            if lat is None or lng is None:
                raise ValueError(f"Dictionary must contain latitude/longitude: {value}")
            return cls(latitude=float(lat), longitude=float(lng))
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return cls(latitude=float(value[0]), longitude=float(value[1]))
        raise TypeError(f"Cannot parse Coordinate from {type(value)}: {value}")


@dataclass
class RouteRequest:
    """
    Encapsulates route calculation parameters from user or frontend.
    """
    origin: Coordinate
    destination: Coordinate
    alternatives: bool = True
    profile: str = "driving"  # e.g., 'driving', 'walking', 'foot'
    max_alternatives: int = 3

    def __post_init__(self):
        self.origin = Coordinate.from_any(self.origin)
        self.destination = Coordinate.from_any(self.destination)
        if self.profile not in ("driving", "walking", "foot", "bike", "cycling"):
            raise ValueError(f"Unsupported routing profile: '{self.profile}'")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouteRequest":
        """Factory method to construct RouteRequest from dict payload."""
        origin_raw = data.get("origin")
        dest_raw = data.get("destination")
        if not origin_raw or not dest_raw:
            raise ValueError("RouteRequest requires 'origin' and 'destination'.")
        return cls(
            origin=Coordinate.from_any(origin_raw),
            destination=Coordinate.from_any(dest_raw),
            alternatives=bool(data.get("alternatives", True)),
            profile=str(data.get("profile", "driving")),
            max_alternatives=int(data.get("max_alternatives", 3))
        )


@dataclass
class EvaluatedRoute:
    """
    Enriched route object containing Member 1's Route model,
    calculated safety score, detailed factor breakdown, and ranking badges.
    """
    route: Route
    safety_score: float
    breakdown: Dict[str, float]
    weights: Dict[str, float]
    status: str = "success"
    message: str = ""
    data_coverage: str = "supported"
    # Ranking metrics
    duration_minutes: float = 0.0
    distance_km: float = 0.0
    rank_fastest: int = 0
    rank_safest: int = 0
    rank_balanced: int = 0
    balanced_score: float = 0.0
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.duration_minutes = float(self.route.duration_minutes)
        self.distance_km = float(self.route.distance_km)

    def to_dict(self) -> Dict[str, Any]:
        """Convert evaluated route to clean JSON serializable dictionary for frontend."""
        return {
            "route_id": self.route.route_id,
            "distance_km": self.distance_km,
            "duration_minutes": self.duration_minutes,
            "safety_score": self.safety_score,
            "breakdown": self.breakdown,
            "weights": self.weights,
            "data_coverage": self.data_coverage,
            "coordinates": self.route.coordinates,
            "rankings": {
                "fastest": self.rank_fastest,
                "safest": self.rank_safest,
                "balanced": self.rank_balanced,
                "balanced_score": self.balanced_score
            },
            "tags": self.tags,
            "status": self.status,
            "message": self.message
        }
