"""
Data Validation Module.
Validates schemas, data types, coordinate ranges, and required columns for input data.
"""

from typing import List, Dict, Any, Union

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def validate_coordinates(lat: float, lon: float) -> bool:
    """Validates if latitude and longitude are within standard geographical limits."""
    try:
        lat, lon = float(lat), float(lon)
        return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
    except (TypeError, ValueError):
        return False


def validate_columns(data: Union[Any, List[Dict[str, Any]]], required_columns: List[str], dataset_name: str) -> bool:
    """Checks if a dataset contains all required columns."""
    if HAS_PANDAS and isinstance(data, pd.DataFrame):
        missing = [col for col in required_columns if col not in data.columns]
    elif isinstance(data, list):
        if not data:
            return True
        first_row = data[0] if isinstance(data[0], dict) else {}
        missing = [col for col in required_columns if col not in first_row]
    else:
        missing = required_columns

    if missing:
        raise ValueError(f"Dataset '{dataset_name}' is missing required columns: {missing}")
    return True


def validate_crime_data(data: Any) -> bool:
    """Validates raw crime data."""
    required = ["area", "latitude", "longitude", "crime_type", "crime_count"]
    return validate_columns(data, required, "crime")


def validate_lighting_data(data: Any) -> bool:
    """Validates raw lighting data."""
    required = ["area", "latitude", "longitude", "lighting_quality"]
    return validate_columns(data, required, "lighting")


def validate_emergency_data(data: Any) -> bool:
    """Validates raw emergency services data."""
    required = ["name", "type", "latitude", "longitude"]
    return validate_columns(data, required, "emergency_services")


def validate_infrastructure_data(data: Any) -> bool:
    """Validates raw infrastructure data."""
    required = ["area", "latitude", "longitude", "road_condition", "pedestrian_access"]
    return validate_columns(data, required, "infrastructure")


def validate_community_reports(reports: List[Dict[str, Any]]) -> bool:
    """Validates raw community reports JSON structure."""
    if not isinstance(reports, list):
        raise ValueError("Community reports must be a JSON list of objects.")
    
    required = ["report_id", "latitude", "longitude", "severity"]
    for idx, report in enumerate(reports):
        if not isinstance(report, dict):
            raise ValueError(f"Report at index {idx} is not a valid JSON object.")
        missing = [f for f in required if f not in report]
        if missing:
            raise ValueError(f"Report {report.get('report_id', idx)} missing fields: {missing}")
    return True
