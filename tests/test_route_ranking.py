"""
Unit Tests for RouteRankingService (Member 2).
Tests Fastest, Safest, Balanced ranking, composite normalized scoring, and badge tags.
"""

import unittest
from src.models.route import Route
from src.models.route_request import EvaluatedRoute
from src.services.route_ranking import RouteRankingService


class TestRouteRanking(unittest.TestCase):

    def setUp(self):
        self.ranking_service = RouteRankingService(
            balanced_safety_weight=0.5,
            balanced_time_weight=0.5
        )

        # Route A: Very Fast (10 mins), Moderate Safety (70)
        route_a = Route("route_a", distance_km=3.0, duration_minutes=10.0, coordinates=[{"latitude": 12.0, "longitude": 77.0}])
        self.eval_a = EvaluatedRoute(
            route=route_a,
            safety_score=70.0,
            breakdown={},
            weights={}
        )

        # Route B: Moderate Time (15 mins), High Safety (90)
        route_b = Route("route_b", distance_km=3.5, duration_minutes=15.0, coordinates=[{"latitude": 12.0, "longitude": 77.0}])
        self.eval_b = EvaluatedRoute(
            route=route_b,
            safety_score=90.0,
            breakdown={},
            weights={}
        )

        # Route C: Slow (20 mins), Low Safety (50)
        route_c = Route("route_c", distance_km=4.0, duration_minutes=20.0, coordinates=[{"latitude": 12.0, "longitude": 77.0}])
        self.eval_c = EvaluatedRoute(
            route=route_c,
            safety_score=50.0,
            breakdown={},
            weights={}
        )

    def test_ranking_fastest_order(self):
        routes = [self.eval_b, self.eval_a, self.eval_c]
        ranked = self.ranking_service.rank_routes(routes)

        fastest_sorted = self.ranking_service.get_ranked_by_criterion(ranked, criterion="fastest")
        # Route A should be #1 fastest (10 mins)
        self.assertEqual(fastest_sorted[0].route.route_id, "route_a")
        self.assertEqual(fastest_sorted[0].rank_fastest, 1)

        # Route B should be #2 fastest (15 mins)
        self.assertEqual(fastest_sorted[1].route.route_id, "route_b")
        self.assertEqual(fastest_sorted[1].rank_fastest, 2)

        # Route C should be #3 fastest (20 mins)
        self.assertEqual(fastest_sorted[2].route.route_id, "route_c")
        self.assertEqual(fastest_sorted[2].rank_fastest, 3)

    def test_ranking_safest_order(self):
        routes = [self.eval_a, self.eval_b, self.eval_c]
        ranked = self.ranking_service.rank_routes(routes)

        safest_sorted = self.ranking_service.get_ranked_by_criterion(ranked, criterion="safest")
        # Route B should be #1 safest (score 90)
        self.assertEqual(safest_sorted[0].route.route_id, "route_b")
        self.assertEqual(safest_sorted[0].rank_safest, 1)

        # Route A should be #2 safest (score 70)
        self.assertEqual(safest_sorted[1].route.route_id, "route_a")

        # Route C should be #3 safest (score 50)
        self.assertEqual(safest_sorted[2].route.route_id, "route_c")

    def test_balanced_scoring_calculation(self):
        """
        Durations: A=10 min, B=15 min, C=20 min
        Normalized Time Scores (0-100):
          A: (1 - (10-10)/10) * 100 = 100.0
          B: (1 - (15-10)/10) * 100 = 50.0
          C: (1 - (20-10)/10) * 100 = 0.0

        Safety Scores:
          A: 70.0
          B: 90.0
          C: 50.0

        Balanced Scores (50% safety, 50% time):
          A: 0.5*70 + 0.5*100 = 35 + 50 = 85.0
          B: 0.5*90 + 0.5*50  = 45 + 25 = 70.0
          C: 0.5*50 + 0.5*0   = 25 + 0  = 25.0
        """
        routes = [self.eval_a, self.eval_b, self.eval_c]
        ranked = self.ranking_service.rank_routes(routes)

        self.assertEqual(self.eval_a.balanced_score, 85.0)
        self.assertEqual(self.eval_b.balanced_score, 70.0)
        self.assertEqual(self.eval_c.balanced_score, 25.0)

        balanced_sorted = self.ranking_service.get_ranked_by_criterion(ranked, criterion="balanced")
        self.assertEqual(balanced_sorted[0].route.route_id, "route_a")

    def test_tags_assignment(self):
        routes = [self.eval_a, self.eval_b, self.eval_c]
        ranked = self.ranking_service.rank_routes(routes)

        # Route A is fastest and balanced
        self.assertIn("fastest", self.eval_a.tags)
        self.assertIn("balanced", self.eval_a.tags)

        # Route B is safest
        self.assertIn("safest", self.eval_b.tags)

        # Route C has no winning tags
        self.assertEqual(self.eval_c.tags, [])

    def test_single_route_ranking(self):
        routes = [self.eval_a]
        ranked = self.ranking_service.rank_routes(routes)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].rank_fastest, 1)
        self.assertEqual(ranked[0].rank_safest, 1)
        self.assertEqual(ranked[0].rank_balanced, 1)
        self.assertIn("fastest", ranked[0].tags)
        self.assertIn("safest", ranked[0].tags)
        self.assertIn("balanced", ranked[0].tags)


if __name__ == "__main__":
    unittest.main()
