"""
Safety Engine Service.
Main entry point for Member 1 safety processing pipeline.
Receives route object/dict and datasets, executes cleaning & normalization, calculates factor scores,
and generates transparent weighted final safety score output.
"""

import csv
import json
import os
from typing import Dict, Any, Optional, Union, List

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from src.models.route import Route
from src.processing.validation import (
    validate_crime_data,
    validate_lighting_data,
    validate_emergency_data,
    validate_infrastructure_data,
    validate_community_reports
)
from src.processing.cleaning import clean_dataset, clean_community_reports
from src.processing.route_processing import (
    filter_data_near_route,
    filter_reports_near_route
)
from src.scoring.crime_score import calculate_crime_score
from src.scoring.lighting_score import calculate_lighting_score
from src.scoring.emergency_score import calculate_emergency_score
from src.scoring.infrastructure_score import calculate_infrastructure_score
from src.scoring.community_score import calculate_community_score
from src.scoring.final_score import calculate_final_safety_score
from src.config.weights import FACTOR_WEIGHTS


def load_csv_file(path: str) -> Any:
    """Helper to load CSV as DataFrame or List of Dicts depending on Pandas availability."""
    if not os.path.exists(path):
        return pd.DataFrame() if HAS_PANDAS else []

    if HAS_PANDAS:
        return pd.read_csv(path)

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


class SafetyEngine:
    """
    Main Safety Score and Data Processing Engine for SafeGuard.
    """

    def __init__(self, data_dir: str = "data/raw"):
        """
        Initialize SafetyEngine with default data directory path.

        Args:
            data_dir (str): Directory containing raw safety data files.
        """
        self.data_dir = data_dir
        self.crime_df = pd.DataFrame() if HAS_PANDAS else []
        self.lighting_df = pd.DataFrame() if HAS_PANDAS else []
        self.emergency_df = pd.DataFrame() if HAS_PANDAS else []
        self.infrastructure_df = pd.DataFrame() if HAS_PANDAS else []
        self.community_reports = []

    def load_data(self) -> None:
        """Loads and validates default raw data files from the data directory."""
        crime_path = os.path.join(self.data_dir, "crime.csv")
        lighting_path = os.path.join(self.data_dir, "lighting.csv")
        emergency_path = os.path.join(self.data_dir, "emergency_services.csv")
        infra_path = os.path.join(self.data_dir, "infrastructure.csv")
        community_path = os.path.join(self.data_dir, "community_reports.json")

        if os.path.exists(crime_path):
            raw_crime = load_csv_file(crime_path)
            validate_crime_data(raw_crime)
            self.crime_df = clean_dataset(
                raw_crime,
                required_columns=["latitude", "longitude", "crime_count"],
                numeric_columns=["latitude", "longitude", "crime_count"],
                defaults={"crime_count": 0}
            )

        if os.path.exists(lighting_path):
            raw_lighting = load_csv_file(lighting_path)
            validate_lighting_data(raw_lighting)
            self.lighting_df = clean_dataset(
                raw_lighting,
                required_columns=["latitude", "longitude", "lighting_quality"],
                numeric_columns=["latitude", "longitude", "lighting_quality"],
                defaults={"lighting_quality": 50}
            )

        if os.path.exists(emergency_path):
            raw_emergency = load_csv_file(emergency_path)
            validate_emergency_data(raw_emergency)
            self.emergency_df = clean_dataset(
                raw_emergency,
                required_columns=["latitude", "longitude", "type"],
                numeric_columns=["latitude", "longitude"]
            )

        if os.path.exists(infra_path):
            raw_infra = load_csv_file(infra_path)
            validate_infrastructure_data(raw_infra)
            self.infrastructure_df = clean_dataset(
                raw_infra,
                required_columns=["latitude", "longitude", "road_condition", "pedestrian_access"],
                numeric_columns=["latitude", "longitude", "road_condition", "pedestrian_access"],
                defaults={"road_condition": 50, "pedestrian_access": 50}
            )

        if os.path.exists(community_path):
            with open(community_path, "r", encoding="utf-8") as f:
                reports = json.load(f)
            validate_community_reports(reports)
            self.community_reports = clean_community_reports(reports)

    def analyze_route(self, route_input: Union[Route, Dict[str, Any], str]) -> Dict[str, Any]:
        """
        Analyzes route safety and returns structured JSON output.

        Args:
            route_input (Route | dict | str): Route object, route dict, or path to route JSON file.

        Returns:
            Dict[str, Any]: Structured output dictionary containing route_id, safety_score, and factor breakdown.
        """
        # Parse route input into Route model
        if isinstance(route_input, Route):
            route = route_input
        elif isinstance(route_input, str):
            route = Route.from_json_file(route_input)
        elif isinstance(route_input, dict):
            route = Route.from_dict(route_input)
        else:
            raise ValueError("Invalid route_input provided. Expected Route object, dict, or JSON file path.")

        # Ensure safety data is loaded
        is_empty = (self.crime_df.empty if HAS_PANDAS else len(self.crime_df) == 0)
        if is_empty and os.path.exists(os.path.join(self.data_dir, "crime.csv")):
            self.load_data()

        # Step 1: Filter safety data near the route buffer
        nearby_crime = filter_data_near_route(route.coordinates, self.crime_df, radius_km=1.0)
        nearby_lighting = filter_data_near_route(route.coordinates, self.lighting_df, radius_km=1.0)
        nearby_infra = filter_data_near_route(route.coordinates, self.infrastructure_df, radius_km=1.0)
        nearby_community = filter_reports_near_route(route.coordinates, self.community_reports, radius_km=1.0)

        # Step 2: Calculate individual 0–100 factor scores
        breakdown = {
            "lighting": calculate_lighting_score(nearby_lighting),
            "crime": calculate_crime_score(nearby_crime),
            "emergency_access": calculate_emergency_score(route.coordinates, self.emergency_df),
            "infrastructure": calculate_infrastructure_score(nearby_infra),
            "community": calculate_community_score(nearby_community)
        }

        # Step 3: Compute final weighted safety score
        final_score = calculate_final_safety_score(breakdown, FACTOR_WEIGHTS)

        # Step 4: Return structured output format for Member 2 / Member 3 / Member 4 / Frontend
        return {
            "route_id": route.route_id,
            "safety_score": final_score,
            "breakdown": breakdown,
            "weights": FACTOR_WEIGHTS,
            "status": "success",
            "message": "Safety score calculated contextually based on available route safety parameters."
        }
