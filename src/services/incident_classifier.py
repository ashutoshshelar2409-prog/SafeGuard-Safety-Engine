"""
Lightweight Explainable Incident Text Classifier (Member 4).

Methodology & Evaluation Disclaimer:
------------------------------------
This module implements a transparent, explainable rule- and lexical-assisted NLP classifier.
It relies on curated domain lexicons, phrase n-grams, and weighted token density rather than
an uninterpretable 'black box' model.

Important:
This rule-based NLP classifier does NOT claim unverified machine learning benchmark accuracy.
In real-world deployment, this lightweight classifier serves as a fast first-stage triage layer.
Uncertain, low-confidence, or ambiguous incident reports are explicitly flagged for human moderator review.
"""

import math
import re
from typing import Dict, List, Tuple, Optional, Any

from src.models.community_report import IncidentCategory, ClassificationResult


class IncidentClassifier:
    """
    Lightweight, explainable NLP text classifier for urban safety reports.
    Categorizes free-text incident descriptions into standard categories and
    flags uncertain reports for human review.
    """

    # Multi-word phrase patterns (checked first with higher weight)
    PHRASE_PATTERNS: Dict[str, List[Tuple[str, float]]] = {
        IncidentCategory.POOR_LIGHTING.value: [
            ("broken street lamp", 3.0),
            ("broken streetlight", 3.0),
            ("broken street light", 3.0),
            ("broken lamp", 2.5),
            ("street lamp near", 2.5),
            ("street light near", 2.5),
            ("no streetlights", 3.0),
            ("no street lights", 3.0),
            ("streetlights out", 3.0),
            ("pitch dark", 3.0),
            ("dark alley", 2.8),
            ("dark street", 2.5),
            ("poorly lit", 2.8),
            ("dimly lit", 2.8),
            ("no lighting", 3.0),
            ("total blackout", 2.8),
            ("bulb broken", 2.5),
            ("flickering light", 2.2),
        ],
        IncidentCategory.ROAD_HAZARD.value: [
            ("deep pothole", 3.0),
            ("huge pothole", 3.0),
            ("road cave-in", 3.0),
            ("collapsed road", 3.0),
            ("oil spill", 3.0),
            ("open trench", 3.0),
            ("debris on road", 2.8),
            ("fallen branch", 2.5),
            ("fallen tree", 2.5),
            ("slippery surface", 2.5),
            ("sharp turn without sign", 2.2),
            ("pothole on sidewalk", 2.5),
            ("deep hole", 2.5),
        ],
        IncidentCategory.HARASSMENT.value: [
            ("catcalling", 3.0),
            ("catcalling reported", 3.0),
            ("cat called", 3.0),
            ("verbal abuse", 3.0),
            ("inappropriate comment", 2.8),
            ("stalking", 3.0),
            ("followed by", 3.0),
            ("stalked by", 3.0),
            ("inappropriate touching", 3.5),
            ("physical harassment", 3.5),
            ("sexual harassment", 3.5),
            ("threatened me", 3.0),
            ("shouting threats", 3.0),
            ("flashing", 2.8),
            ("indecent exposure", 3.5),
            ("leering and whistling", 2.8),
            ("blocked my path", 2.5),
        ],
        IncidentCategory.SUSPICIOUS_ACTIVITY.value: [
            ("casing cars", 3.5),
            ("casing houses", 3.5),
            ("trying door handles", 3.5),
            ("trying car handles", 3.5),
            ("lurking in the dark", 3.0),
            ("lurking near", 2.8),
            ("loitering near", 2.8),
            ("loitering in alley", 3.0),
            ("peeping into", 3.0),
            ("suspicious group", 2.8),
            ("acting suspicious", 2.5),
            ("drug dealing", 3.0),
            ("prowling around", 3.0),
        ],
        IncidentCategory.INFRASTRUCTURE_PROBLEM.value: [
            ("broken sidewalk", 3.0),
            ("open manhole", 3.5),
            ("missing drain cover", 3.5),
            ("missing manhole cover", 3.5),
            ("water main leak", 3.0),
            ("water main break", 3.0),
            ("flooded underpass", 3.0),
            ("severe waterlogging", 3.0),
            ("fallen power line", 3.5),
            ("exposed electric wire", 3.5),
            ("traffic light broken", 3.0),
            ("traffic signal malfunctioning", 3.0),
            ("damaged guardrail", 2.8),
            ("pedestrian bridge damaged", 3.0),
        ],
    }

    # Individual single tokens (checked with moderate weight)
    TOKEN_LEXICON: Dict[str, Dict[str, float]] = {
        IncidentCategory.POOR_LIGHTING.value: {
            "streetlight": 2.0,
            "streetlamp": 2.0,
            "lighting": 1.5,
            "dark": 1.2,
            "darkness": 1.5,
            "unlit": 2.0,
            "blackout": 2.0,
            "lamp": 1.2,
            "shadowy": 1.2,
            "blindspot": 1.2,
        },
        IncidentCategory.ROAD_HAZARD.value: {
            "pothole": 2.2,
            "potholes": 2.2,
            "trench": 1.8,
            "spill": 1.5,
            "crater": 1.8,
            "hazard": 1.2,
            "obstacle": 1.2,
            "debris": 1.5,
            "barrier": 1.0,
        },
        IncidentCategory.HARASSMENT.value: {
            "catcall": 2.5,
            "catcalled": 2.5,
            "catcalling": 2.5,
            "harassment": 2.5,
            "harass": 2.0,
            "stalking": 2.5,
            "stalker": 2.5,
            "followed": 1.8,
            "threatened": 2.0,
            "threat": 1.5,
            "groped": 3.0,
            "intimidating": 1.8,
            "whistling": 1.5,
        },
        IncidentCategory.SUSPICIOUS_ACTIVITY.value: {
            "loitering": 2.2,
            "loiter": 2.0,
            "lurking": 2.2,
            "suspicious": 1.8,
            "prowler": 2.5,
            "prowling": 2.2,
            "peeping": 2.2,
            "shady": 1.2,
            "casing": 2.5,
        },
        IncidentCategory.INFRASTRUCTURE_PROBLEM.value: {
            "manhole": 2.5,
            "sidewalk": 1.8,
            "pavement": 1.5,
            "curb": 1.2,
            "waterlogging": 2.2,
            "waterlogged": 2.2,
            "flooding": 1.8,
            "powerline": 2.5,
            "wire": 1.5,
            "leak": 1.5,
            "signal": 1.5,
            "drain": 1.8,
        },
    }

    # Minimum threshold to avoid assigning a specific category to non-matching text
    CONFIDENCE_THRESHOLD = 0.40
    # Minimum margin between top 2 categories to avoid ambiguous classifications
    AMBIGUITY_MARGIN = 0.12

    def __init__(self):
        # Precompile phrase regexes for rapid explainable matching
        self._compiled_phrases: Dict[str, List[Tuple[re.Pattern, str, float]]] = {}
        for cat, phrases in self.PHRASE_PATTERNS.items():
            compiled_list = []
            for phrase, weight in phrases:
                pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
                compiled_list.append((pattern, phrase, weight))
            self._compiled_phrases[cat] = compiled_list

    def _tokenize(self, text: str) -> List[str]:
        """Low-overhead word tokenization and lowercase normalization."""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return [w for w in cleaned.split() if len(w) > 2]

    def classify(self, description: str) -> ClassificationResult:
        """
        Classifies incident description text into a category with confidence score and explanation.

        Args:
            description: The raw text description submitted by the user.

        Returns:
            ClassificationResult containing suggested category, confidence, matched keywords,
            flag for manual review, and transparent explanation.
        """
        if not description or not description.strip():
            return ClassificationResult(
                suggested_category=IncidentCategory.OTHER.value,
                confidence=0.0,
                method="rule_based_lexical_nlp",
                keywords_matched=[],
                needs_review=True,
                explanation="Empty description provided; unable to classify."
            )

        text_lower = description.lower()
        tokens = set(self._tokenize(description))

        scores: Dict[str, float] = {cat: 0.0 for cat in self.PHRASE_PATTERNS.keys()}
        matched_keywords: Dict[str, List[str]] = {cat: [] for cat in self.PHRASE_PATTERNS.keys()}

        # 1. Match multi-word phrases (higher weight)
        for cat, patterns in self._compiled_phrases.items():
            for pattern, phrase, weight in patterns:
                if pattern.search(text_lower):
                    scores[cat] += weight
                    matched_keywords[cat].append(phrase)

        # 2. Match single tokens (medium weight)
        for cat, token_weights in self.TOKEN_LEXICON.items():
            for token, weight in token_weights.items():
                if token in tokens:
                    # Avoid double-counting if part of a matched phrase
                    already_in_phrase = any(token in kw for kw in matched_keywords[cat])
                    if not already_in_phrase:
                        scores[cat] += weight
                        matched_keywords[cat].append(token)

        # 3. Score evaluation and confidence scaling
        sorted_cats = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_cat, top_score = sorted_cats[0]
        second_cat, second_score = sorted_cats[1] if len(sorted_cats) > 1 else ("", 0.0)

        # No keywords matched at all
        if top_score <= 0.0:
            return ClassificationResult(
                suggested_category=IncidentCategory.OTHER.value,
                confidence=0.10,
                method="rule_based_lexical_nlp",
                keywords_matched=[],
                needs_review=True,
                explanation="No recognized safety category keywords matched; marked as uncertain for review."
            )

        # Non-linear confidence scaling: S / (S + 2.5) mapping positive scores to (0, 1]
        confidence = round(top_score / (top_score + 2.2), 3)

        # Check for ambiguity between top 2 categories
        is_ambiguous = bool(
            second_score > 0
            and (
                (top_score - second_score) <= 1.5
                or (second_score / (top_score + 1e-6)) >= 0.50
            )
        )
        is_low_confidence = confidence < self.CONFIDENCE_THRESHOLD

        if is_low_confidence:
            return ClassificationResult(
                suggested_category=IncidentCategory.OTHER.value,
                confidence=confidence,
                method="rule_based_lexical_nlp",
                keywords_matched=matched_keywords[top_cat],
                needs_review=True,
                explanation=(
                    f"Low match confidence ({confidence:.2f}) for category '{top_cat}'. "
                    f"Flagged for manual review."
                )
            )

        if is_ambiguous:
            return ClassificationResult(
                suggested_category=top_cat,
                confidence=confidence,
                method="rule_based_lexical_nlp",
                keywords_matched=matched_keywords[top_cat] + matched_keywords[second_cat],
                needs_review=True,
                explanation=(
                    f"Ambiguous report matching both '{top_cat}' and '{second_cat}'. "
                    f"Assigned top candidate '{top_cat}' but flagged for manual review."
                )
            )

        # Clear confident match
        display_name = IncidentCategory.display_names().get(top_cat, top_cat)
        matched_str = ", ".join(f"'{k}'" for k in matched_keywords[top_cat][:4])
        return ClassificationResult(
            suggested_category=top_cat,
            confidence=confidence,
            method="rule_based_lexical_nlp",
            keywords_matched=matched_keywords[top_cat],
            needs_review=False,
            explanation=f"Matched {display_name} based on keywords: {matched_str}."
        )
