"""
Tests for Individual Factor Scoring and Final Weighted Scoring.
Includes tests verifying scoring directions (Higher crime -> lower score; Better lighting -> higher score).
"""

import unittest
from src.processing.route_processing import route_length_km
from src.scoring.crime_score import calculate_crime_score, MAX_CRIMES_PER_KM
from src.scoring.lighting_score import calculate_lighting_score
from src.scoring.emergency_score import calculate_emergency_score
from src.scoring.infrastructure_score import calculate_infrastructure_score
from src.scoring.community_score import calculate_community_score, MAX_COMMUNITY_SEVERITY_PER_KM
from src.scoring.final_score import calculate_final_safety_score


class TestScoring(unittest.TestCase):

    def test_route_length_km(self):
        """Verify haversine sum calculation across route coordinates."""
        self.assertEqual(route_length_km([]), 0.0)
        self.assertEqual(route_length_km([{"latitude": 12.9716, "longitude": 77.5946}]), 0.0)

        # Two points in Bangalore approx 1.6 km apart
        coords = [
            {"latitude": 12.9716, "longitude": 77.5946},
            {"latitude": 12.9850, "longitude": 77.6000}
        ]
        length = route_length_km(coords)
        self.assertGreater(length, 1.0)
        self.assertLess(length, 2.5)

    def test_crime_score_directionality(self):
        """Verify that higher crime count leads to a LOWER crime safety score."""
        low_crime_data = [{"crime_count": 2}]
        high_crime_data = [{"crime_count": 25}]

        low_crime_score = calculate_crime_score(low_crime_data)
        high_crime_score = calculate_crime_score(high_crime_data)

        self.assertGreater(low_crime_score, high_crime_score)
        self.assertTrue(0.0 <= low_crime_score <= 100.0)
        self.assertTrue(0.0 <= high_crime_score <= 100.0)

    def test_crime_length_bias_fix(self):
        """
        Verify that a 10 km route with 10 crimes and a 1 km route with 1 crime
        (identical 1.0 crime/km density) yield the exact same safety score.
        """
        crime_10km = [{"crime_count": 10}]
        crime_1km = [{"crime_count": 1}]

        score_10km = calculate_crime_score(crime_10km, route_km=10.0)
        score_1km = calculate_crime_score(crime_1km, route_km=1.0)

        self.assertEqual(score_10km, score_1km)
        self.assertEqual(score_10km, 90.0)  # 1.0 crime/km with MAX 10.0 -> 90.0

    def test_community_length_bias_fix(self):
        """
        Verify that a 10 km route with severity 10 and a 1 km route with severity 1
        (identical 1.0 severity/km density) yield the exact same safety score.
        """
        reports_10km = [{"severity": 10}]
        reports_1km = [{"severity": 1}]

        score_10km = calculate_community_score(reports_10km, route_km=10.0)
        score_1km = calculate_community_score(reports_1km, route_km=1.0)

        self.assertEqual(score_10km, score_1km)
        self.assertEqual(score_10km, 80.0)  # 1.0 severity/km with MAX 5.0 -> 80.0

    def test_lighting_score_directionality(self):
        """Verify that better lighting quality leads to a HIGHER lighting safety score."""
        poor_lighting_data = [{"lighting_quality": 20}]
        good_lighting_data = [{"lighting_quality": 90}]

        poor_score = calculate_lighting_score(poor_lighting_data)
        good_score = calculate_lighting_score(good_lighting_data)

        self.assertGreater(good_score, poor_score)
        self.assertTrue(0.0 <= poor_score <= 100.0)
        self.assertTrue(0.0 <= good_score <= 100.0)

    def test_emergency_score(self):
        route_coords = [{"latitude": 12.9716, "longitude": 77.5946}]
        emergency_data = [
            {"name": "Police A", "type": "police", "latitude": 12.9720, "longitude": 77.5950},
            {"name": "Hospital B", "type": "hospital", "latitude": 12.9750, "longitude": 77.5950}
        ]

        score = calculate_emergency_score(route_coords, emergency_data)
        self.assertTrue(0.0 <= score <= 100.0)

    def test_infrastructure_score(self):
        infra_data = [
            {"road_condition": 80, "pedestrian_access": 85},
            {"road_condition": 90, "pedestrian_access": 95}
        ]
        score = calculate_infrastructure_score(infra_data)
        self.assertTrue(0.0 <= score <= 100.0)
        self.assertGreaterEqual(score, 80.0)

    def test_community_score(self):
        few_reports = [{"severity": 1}]
        many_reports = [{"severity": 5}, {"severity": 4}, {"severity": 5}]

        high_score = calculate_community_score(few_reports)
        low_score = calculate_community_score(many_reports)

        self.assertGreater(high_score, low_score)
        self.assertTrue(0.0 <= high_score <= 100.0)
        self.assertTrue(0.0 <= low_score <= 100.0)

    def test_final_weighted_score_bounds_and_calculation(self):
        scores = {
            "lighting": 90.0,           # weight 0.25 -> 22.5
            "crime": 70.0,              # weight 0.25 -> 17.5
            "emergency_access": 85.0,   # weight 0.15 -> 12.75
            "infrastructure": 80.0,     # weight 0.15 -> 12.0
            "community": 75.0           # weight 0.20 -> 15.0
        }
        # Expected sum = 22.5 + 17.5 + 12.75 + 12.0 + 15.0 = 79.75

        final_score = calculate_final_safety_score(scores)
        self.assertEqual(final_score, 79.75)
        self.assertTrue(0.0 <= final_score <= 100.0)


if __name__ == "__main__":
    unittest.main()
