"""
Unit tests for Lightweight Explainable Incident Classifier (Member 4).
"""

import unittest

from src.models.community_report import IncidentCategory
from src.services.incident_classifier import IncidentClassifier


class TestIncidentClassifier(unittest.TestCase):

    def setUp(self):
        self.classifier = IncidentClassifier()

    def test_classify_poor_lighting(self):
        desc = "Broken street lamp near bus stand, area is pitch dark and unlit"
        res = self.classifier.classify(desc)
        self.assertEqual(res.suggested_category, IncidentCategory.POOR_LIGHTING.value)
        self.assertGreater(res.confidence, 0.5)
        self.assertFalse(res.needs_review)
        self.assertIn("broken street lamp", [k.lower() for k in res.keywords_matched])
        self.assertEqual(res.method, "rule_based_lexical_nlp")

    def test_classify_road_hazard(self):
        desc = "Deep pothole in middle of lane causing bike skidding"
        res = self.classifier.classify(desc)
        self.assertEqual(res.suggested_category, IncidentCategory.ROAD_HAZARD.value)
        self.assertGreater(res.confidence, 0.45)
        self.assertFalse(res.needs_review)
        self.assertTrue(any("pothole" in k for k in res.keywords_matched))

    def test_classify_harassment(self):
        desc = "Group of men catcalling and shouting verbal abuse at pedestrians"
        res = self.classifier.classify(desc)
        self.assertEqual(res.suggested_category, IncidentCategory.HARASSMENT.value)
        self.assertGreater(res.confidence, 0.5)
        self.assertFalse(res.needs_review)
        self.assertTrue(any("catcalling" in k or "verbal abuse" in k for k in res.keywords_matched))

    def test_classify_suspicious_activity(self):
        desc = "Suspicious person prowling around and casing cars trying door handles"
        res = self.classifier.classify(desc)
        self.assertEqual(res.suggested_category, IncidentCategory.SUSPICIOUS_ACTIVITY.value)
        self.assertGreater(res.confidence, 0.5)
        self.assertFalse(res.needs_review)
        self.assertTrue(any("casing cars" in k or "prowling" in k for k in res.keywords_matched))

    def test_classify_infrastructure_problem(self):
        desc = "Severe waterlogging and open manhole missing drain cover after rain"
        res = self.classifier.classify(desc)
        self.assertEqual(res.suggested_category, IncidentCategory.INFRASTRUCTURE_PROBLEM.value)
        self.assertGreater(res.confidence, 0.5)
        self.assertFalse(res.needs_review)
        self.assertTrue(any("open manhole" in k or "waterlogging" in k for k in res.keywords_matched))

    def test_classify_uncertain_and_needs_review(self):
        # Text with no domain safety keywords
        desc = "I was walking to the grocery store to buy some bread and milk"
        res = self.classifier.classify(desc)
        self.assertEqual(res.suggested_category, IncidentCategory.OTHER.value)
        self.assertTrue(res.needs_review)
        self.assertLess(res.confidence, 0.40)
        self.assertIn("marked as uncertain", res.explanation.lower())

    def test_classify_ambiguous_flags_manual_review(self):
        # Description containing conflicting signals from two categories
        desc = "Broken streetlight and deep pothole on road"
        res = self.classifier.classify(desc)
        # Should flag for manual review due to ambiguity
        self.assertTrue(res.needs_review)
        self.assertIn("Ambiguous", res.explanation)

    def test_classify_empty_string(self):
        res = self.classifier.classify("")
        self.assertEqual(res.suggested_category, IncidentCategory.OTHER.value)
        self.assertTrue(res.needs_review)
        self.assertEqual(res.confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
