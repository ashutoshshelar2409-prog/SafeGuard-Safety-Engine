"""
Route Processing Module.
Calculates spatial proximity between route coordinates and safety data points using Haversine distance.
"""

import math
from typing import List, Dict, Any, Union, Tuple

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points on the Earth's surface in kilometers.

    Args:
        lat1, lon1: Coordinates of point 1 in degrees.
        lat2, lon2: Coordinates of point 2 in degrees.

    Returns:
        float: Distance in kilometers.
    """
    R = 6371.0  # Earth's radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def route_length_km(
    coordinates: List[Union[Dict[str, float], Tuple[float, float], List[float]]]
) -> float:
    """
    Computes total route distance in kilometers as the sum of Haversine distances
    between consecutive coordinate points.

    Args:
        coordinates: List of geographical coordinate points.

    Returns:
        float: Total length of the route in kilometers.
    """
    if not coordinates or len(coordinates) < 2:
        return 0.0

    total_km = 0.0
    for i in range(len(coordinates) - 1):
        p1 = coordinates[i]
        p2 = coordinates[i + 1]

        # Extract lat/lon for point 1
        if isinstance(p1, dict):
            lat1 = float(p1.get("latitude", p1.get("lat", 0.0)))
            lon1 = float(p1.get("longitude", p1.get("lng", p1.get("lon", 0.0))))
        elif isinstance(p1, (list, tuple)) and len(p1) >= 2:
            lat1, lon1 = float(p1[0]), float(p1[1])
        else:
            continue

        # Extract lat/lon for point 2
        if isinstance(p2, dict):
            lat2 = float(p2.get("latitude", p2.get("lat", 0.0)))
            lon2 = float(p2.get("longitude", p2.get("lng", p2.get("lon", 0.0))))
        elif isinstance(p2, (list, tuple)) and len(p2) >= 2:
            lat2, lon2 = float(p2[0]), float(p2[1])
        else:
            continue

        total_km += haversine_distance(lat1, lon1, lat2, lon2)

    return float(round(total_km, 4))


def find_minimum_distance_to_route(
    route_coords: List[Dict[str, float]],
    target_lat: float,
    target_lon: float
) -> float:
    """
    Finds the minimum distance in km from a target coordinate to any point on the route.
    """
    min_dist = float("inf")
    for pt in route_coords:
        dist = haversine_distance(pt["latitude"], pt["longitude"], target_lat, target_lon)
        if dist < min_dist:
            min_dist = dist
    return min_dist


def filter_data_near_route(
    route_coords: List[Dict[str, float]],
    data: Union[Any, List[Dict[str, Any]]],
    radius_km: float = 1.0,
    lat_col: str = "latitude",
    lon_col: str = "longitude"
) -> Union[Any, List[Dict[str, Any]]]:
    """
    Filters rows/items that are within `radius_km` of any point along the route.
    """
    if HAS_PANDAS and isinstance(data, pd.DataFrame):
        if data.empty:
            return data.copy()

        nearby_indices = []
        for idx, row in data.iterrows():
            min_dist = find_minimum_distance_to_route(route_coords, row[lat_col], row[lon_col])
            if min_dist <= radius_km:
                nearby_indices.append(idx)

        return data.loc[nearby_indices].reset_index(drop=True)

    # Pure Python list of dicts fallback
    if isinstance(data, list):
        nearby_items = []
        for item in data:
            lat = item[lat_col]
            lon = item[lon_col]
            min_dist = find_minimum_distance_to_route(route_coords, lat, lon)
            if min_dist <= radius_km:
                nearby_items.append(item)
        return nearby_items

    return data


def filter_reports_near_route(
    route_coords: List[Dict[str, float]],
    reports: List[Dict[str, Any]],
    radius_km: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Filters community report JSON objects that fall within `radius_km` of the route.
    """
    return filter_data_near_route(route_coords, reports, radius_km=radius_km)
