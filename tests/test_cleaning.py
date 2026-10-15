"""
Tests for Data Cleaning and Data Validation.
"""

import unittest
from src.processing.cleaning import clean_dataframe, clean_community_reports, clean_dataset
from src.processing.validation import validate_coordinates

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class TestCleaning(unittest.TestCase):

    def test_validate_coordinates(self):
        self.assertTrue(validate_coordinates(12.9716, 77.5946))
        self.assertFalse(validate_coordinates(95.0, 77.5946))  # Invalid lat > 90
        self.assertFalse(validate_coordinates("invalid", 77.5946))

    def test_clean_community_reports(self):
        reports = [
            {
                "report_id": "rep_1",
                "latitude": 12.9,
                "longitude": 77.5,
                "severity": 3
            },
            {
                "report_id": "rep_1",  # Duplicate report_id
                "latitude": 12.9,
                "longitude": 77.5,
                "severity": 3
            },
            {
                "report_id": "rep_2",
                "latitude": 100.0,  # Invalid latitude
                "longitude": 77.5,
                "severity": 5
            }
        ]

        cleaned = clean_community_reports(reports)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["report_id"], "rep_1")

    def test_clean_dataset_list(self):
        raw_data = [
            {"area": "A", "latitude": 12.9, "longitude": 77.5, "crime_count": 10},
            {"area": "A", "latitude": 12.9, "longitude": 77.5, "crime_count": 10},  # Duplicate
            {"area": "B", "latitude": 13.0, "longitude": 77.6, "crime_count": None}, # Default
            {"area": None, "latitude": 13.1, "longitude": 77.7, "crime_count": 5}   # Missing required
        ]

        cleaned = clean_dataset(
            raw_data,
            required_columns=["area", "latitude", "longitude", "crime_count"],
            numeric_columns=["latitude", "longitude", "crime_count"],
            defaults={"crime_count": 0}
        )

        self.assertEqual(len(cleaned), 2)

    def test_clean_dataframe_pandas(self):
        if not HAS_PANDAS:
            return
        raw_data = {
            "area": ["A", "A", "B", None],
            "latitude": [12.9, 12.9, 13.0, 13.1],
            "longitude": [77.5, 77.5, 77.6, 77.7],
            "crime_count": [10, 10, None, 5]
        }
        df = pd.DataFrame(raw_data)

        cleaned = clean_dataframe(
            df,
            required_columns=["area", "latitude", "longitude", "crime_count"],
            numeric_columns=["latitude", "longitude", "crime_count"],
            defaults={"crime_count": 0}
        )

        self.assertEqual(len(cleaned), 2)
        self.assertEqual(int(cleaned.loc[cleaned["area"] == "B", "crime_count"].values[0]), 0)

    def test_clean_dataset_range_checks(self):
        """Verify negative crime_count and out-of-range lighting/road_condition are dropped."""
        raw_data = [
            {"latitude": 12.9, "longitude": 77.5, "crime_count": -5, "lighting_quality": 50, "road_condition": 50},
            {"latitude": 12.9, "longitude": 77.5, "crime_count": 5, "lighting_quality": 120, "road_condition": 50},
            {"latitude": 12.9, "longitude": 77.5, "crime_count": 5, "lighting_quality": -10, "road_condition": 50},
            {"latitude": 12.9, "longitude": 77.5, "crime_count": 5, "lighting_quality": 50, "road_condition": 105},
            {"latitude": 12.9, "longitude": 77.5, "crime_count": 5, "lighting_quality": 50, "road_condition": -20},
            {"latitude": 12.9, "longitude": 77.5, "crime_count": 5, "lighting_quality": 80, "road_condition": 90}  # Valid
        ]
        cleaned = clean_dataset(
            raw_data,
            required_columns=["latitude", "longitude"],
            numeric_columns=["latitude", "longitude", "crime_count", "lighting_quality", "road_condition"]
        )
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["crime_count"], 5.0)
        self.assertEqual(cleaned[0]["lighting_quality"], 80.0)
        self.assertEqual(cleaned[0]["road_condition"], 90.0)

    def test_route_clean_coordinates_raises_value_error(self):
        """Verify Route._clean_coordinates raises ValueError on missing/invalid lat/lng."""
        from src.models.route import Route

        # Missing latitude
        with self.assertRaises(ValueError):
            Route("r1", 1.0, 5.0, [{"longitude": 77.59}])

        # Missing longitude
        with self.assertRaises(ValueError):
            Route("r2", 1.0, 5.0, [{"latitude": 12.97}])

        # None values
        with self.assertRaises(ValueError):
            Route("r3", 1.0, 5.0, [{"latitude": None, "longitude": 77.59}])

        # Out-of-bounds latitude > 90
        with self.assertRaises(ValueError):
            Route("r4", 1.0, 5.0, [{"latitude": 95.0, "longitude": 77.59}])

        # Empty coordinate list
        with self.assertRaises(ValueError):
            Route("r5", 1.0, 5.0, [])


if __name__ == "__main__":
    unittest.main()
