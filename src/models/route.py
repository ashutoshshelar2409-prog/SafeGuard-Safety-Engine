"""
Route Data Model.
Represents a geographical route provided by Member 2 or external routing APIs.
"""

import json
from typing import List, Dict, Any, Union, Tuple


class Route:
    """
    Data model representing a route with geographical coordinates.
    """

    def __init__(
        self,
        route_id: str,
        distance_km: float,
        duration_minutes: float,
        coordinates: List[Union[Dict[str, float], Tuple[float, float], List[float]]]
    ):
        """
        Initialize a Route object.

        Args:
            route_id (str): Unique identifier for the route.
            distance_km (float): Total route distance in kilometers.
            duration_minutes (float): Estimated travel duration in minutes.
            coordinates (List): List of lat/lng coordinates along the route.
        """
        self.route_id = str(route_id)
        self.distance_km = float(distance_km)
        self.duration_minutes = float(duration_minutes)
        self.coordinates = self._clean_coordinates(coordinates)

    def _clean_coordinates(self, coords: List[Any]) -> List[Dict[str, float]]:
        """Normalizes various coordinate formats to [{'latitude': lat, 'longitude': lng}]."""
        cleaned = []
        for point in coords:
            if isinstance(point, dict):
                lat = float(point.get("latitude", point.get("lat", 0.0)))
                lng = float(point.get("longitude", point.get("lng", point.get("lon", 0.0))))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                lat = float(point[0])
                lng = float(point[1])
            else:
                continue
            cleaned.append({"latitude": lat, "longitude": lng})
        
        if not cleaned:
            raise ValueError("Route must contain at least one valid coordinate point.")
        return cleaned

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Route":
        """Factory method to construct Route from a dictionary."""
        return cls(
            route_id=data.get("route_id", "unknown_route"),
            distance_km=data.get("distance_km", 0.0),
            duration_minutes=data.get("duration_minutes", 0.0),
            coordinates=data.get("coordinates", [])
        )

    @classmethod
    def from_json_file(cls, filepath: str) -> "Route":
        """Factory method to load Route from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Converts Route instance back to a standard dictionary."""
        return {
            "route_id": self.route_id,
            "distance_km": self.distance_km,  
            "duration_minutes": self.duration_minutes,
            "coordinates": self.coordinates
        }

    def __repr__(self) -> str:
        return f"<Route {self.route_id} ({self.distance_km} km, {len(self.coordinates)} points)>"
