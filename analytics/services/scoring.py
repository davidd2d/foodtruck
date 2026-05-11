"""
Deterministic event scoring service.

The final score is computed from a weighted combination of:
  - Deterministic features (weekend, duration, meal overlaps, etc.)
  - Normalised AI signals (attendance, compatibility, etc.)

The AI **never** decides the final score; it contributes calibrated weights
that are combined with rule-based factors.  Every factor is named, logged,
and stored for full explainability.

Score range: 0–100 (integer, clamped).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from analytics.services.feature_extraction import EventFeatures
from analytics.services.schemas import NormalizedAISignals


# ---------------------------------------------------------------------------
# Weight configuration – all weights must sum to 1.0
# ---------------------------------------------------------------------------

_W_ATTENDANCE: float = 0.25
_W_COMPATIBILITY: float = 0.25
_W_WEEKEND: float = 0.10
_W_DURATION: float = 0.10
_W_MEAL_OVERLAP: float = 0.15
_W_OUTDOOR: float = 0.08
_W_SUMMER: float = 0.07

_WEIGHT_SUM: float = (
    _W_ATTENDANCE
    + _W_COMPATIBILITY
    + _W_WEEKEND
    + _W_DURATION
    + _W_MEAL_OVERLAP
    + _W_OUTDOOR
    + _W_SUMMER
)
assert abs(_WEIGHT_SUM - 1.0) < 1e-9, f"Weights must sum to 1.0, got {_WEIGHT_SUM}"


# ---------------------------------------------------------------------------
# Multilingual translations for scoring explanations
# ---------------------------------------------------------------------------

_TRANSLATIONS = {
    "en": {
        "factor_labels": {
            "attendance": "Expected Attendance",
            "compatibility": "Food Truck Compatibility",
            "outdoor": "Outdoor Event",
            "weekend": "Weekend",
            "meal_overlap": "Meal Time Overlap",
            "duration": "Event Duration",
            "summer": "Summer Period",
        },
        "attendance_explanations": {
            "very_low": "Very low expected attendance",
            "low": "Low expected attendance",
            "medium": "Medium expected attendance",
            "high": "High expected attendance",
            "very_high": "Very high expected attendance",
        },
        "compatibility_explanations": {
            "poor": "Poor fit for food trucks",
            "fair": "Fair fit for food trucks",
            "good": "Good fit for food trucks",
            "excellent": "Excellent fit for food trucks",
        },
        "outdoor_explanations": {
            "true": "Outdoor events are ideal for food trucks",
            "false": "Indoor events have lower demand",
        },
        "weekend_explanations": {
            "true": "Weekend events attract more visitors",
            "false": "Weekday events have lower foot traffic",
        },
        "meal_overlap_explanations": {
            "both": "Covers both lunch and dinner peaks",
            "lunch": "Covers lunch time peak",
            "dinner": "Covers dinner time peak",
            "none": "No overlap with meal times",
        },
        "duration_explanations": {
            "very_short": "Very short event (< 2h)",
            "short": "Short event (2-6h)",
            "medium": "Medium duration (6-12h)",
            "long": "Full day or multi-day event",
        },
        "summer_explanations": {
            "true": "Summer events have higher demand",
            "false": "Off-season events have lower footfall",
        },
        "quality_levels": {
            "excellent": "excellent",
            "good": "good",
            "moderate": "moderate",
            "low": "low",
        },
        "summary_template": "This is an {quality} opportunity ({score}/100 score). The main strengths are: {factors}.",
        "factors_joiner": "and",
    },
    "fr": {
        "factor_labels": {
            "attendance": "Affluence Attendue",
            "compatibility": "Compatibilité Food Truck",
            "outdoor": "Événement en Plein Air",
            "weekend": "Week-End",
            "meal_overlap": "Chevauchement Heures de Repas",
            "duration": "Durée de l'Événement",
            "summer": "Période Estivale",
        },
        "attendance_explanations": {
            "very_low": "Affluence attendue très faible",
            "low": "Affluence attendue faible",
            "medium": "Affluence attendue moyenne",
            "high": "Affluence attendue élevée",
            "very_high": "Affluence attendue très élevée",
        },
        "compatibility_explanations": {
            "poor": "Mauvais ajustement pour les food trucks",
            "fair": "Ajustement correct pour les food trucks",
            "good": "Bon ajustement pour les food trucks",
            "excellent": "Excellent ajustement pour les food trucks",
        },
        "outdoor_explanations": {
            "true": "Les événements en plein air sont idéaux pour les food trucks",
            "false": "Les événements en intérieur ont une demande plus faible",
        },
        "weekend_explanations": {
            "true": "Les événements en week-end attirent plus de visiteurs",
            "false": "Les événements en semaine ont un trafic moins important",
        },
        "meal_overlap_explanations": {
            "both": "Couvre les pics du midi et du soir",
            "lunch": "Couvre le pic du midi",
            "dinner": "Couvre le pic du soir",
            "none": "Aucun chevauchement avec les heures de repas",
        },
        "duration_explanations": {
            "very_short": "Événement très court (< 2h)",
            "short": "Événement court (2-6h)",
            "medium": "Durée moyenne (6-12h)",
            "long": "Événement sur une journée entière ou multi-jours",
        },
        "summer_explanations": {
            "true": "Les événements estivaux ont une forte demande",
            "false": "Les événements hors-saison ont un trafic réduit",
        },
        "quality_levels": {
            "excellent": "excellente",
            "good": "bonne",
            "moderate": "modérée",
            "low": "faible",
        },
        "summary_template": "Ceci est une opportunité {quality} ({score}/100). Les points forts principaux sont : {factors}.",
        "factors_joiner": "et",
    },
}


def _get_text(key: str, lang: str = "en", subkey: str | None = None) -> str:
    """Get translated text. Falls back to English if translation missing."""
    if lang not in _TRANSLATIONS:
        lang = "en"
    
    text_dict = _TRANSLATIONS[lang].get(key, {})
    if isinstance(text_dict, dict) and subkey:
        return text_dict.get(subkey, _TRANSLATIONS["en"][key].get(subkey, "Unknown"))
    elif isinstance(text_dict, str):
        return text_dict
    return ""


# ---------------------------------------------------------------------------
# Enum-to-numeric mappings (calibrated, not hardcoded everywhere)
# ---------------------------------------------------------------------------

_ATTENDANCE_MAP: dict[str, float] = {
    "very_low": 10.0,
    "low": 30.0,
    "medium": 55.0,
    "high": 80.0,
    "very_high": 100.0,
}

_COMPATIBILITY_MAP: dict[str, float] = {
    "poor": 10.0,
    "fair": 40.0,
    "good": 75.0,
    "excellent": 100.0,
}

_MEAL_RELEVANCE_MAP: dict[str, float] = {
    "none": 0.0,
    "low": 33.0,
    "medium": 66.0,
    "high": 100.0,
}

_DURATION_THRESHOLDS: list[tuple[float, float]] = [
    # (max_hours, score)
    (1.0, 20.0),
    (3.0, 50.0),
    (6.0, 75.0),
    (12.0, 90.0),
    (float("inf"), 100.0),
]


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreBreakdown:
    """Per-factor scores and their contributions to the final result."""

    attendance_score: float
    compatibility_score: float
    weekend_score: float
    duration_score: float
    meal_overlap_score: float
    outdoor_score: float
    summer_score: float

    attendance_contribution: float
    compatibility_contribution: float
    weekend_contribution: float
    duration_contribution: float
    meal_overlap_contribution: float
    outdoor_contribution: float
    summer_contribution: float

    def to_dict(self) -> dict[str, Any]:
        """Plain dict – safe for JSONField storage."""
        return {
            "factors": {
                "attendance": {
                    "score": self.attendance_score,
                    "weight": _W_ATTENDANCE,
                    "contribution": self.attendance_contribution,
                },
                "compatibility": {
                    "score": self.compatibility_score,
                    "weight": _W_COMPATIBILITY,
                    "contribution": self.compatibility_contribution,
                },
                "weekend": {
                    "score": self.weekend_score,
                    "weight": _W_WEEKEND,
                    "contribution": self.weekend_contribution,
                },
                "duration": {
                    "score": self.duration_score,
                    "weight": _W_DURATION,
                    "contribution": self.duration_contribution,
                },
                "meal_overlap": {
                    "score": self.meal_overlap_score,
                    "weight": _W_MEAL_OVERLAP,
                    "contribution": self.meal_overlap_contribution,
                },
                "outdoor": {
                    "score": self.outdoor_score,
                    "weight": _W_OUTDOOR,
                    "contribution": self.outdoor_contribution,
                },
                "summer": {
                    "score": self.summer_score,
                    "weight": _W_SUMMER,
                    "contribution": self.summer_contribution,
                },
            },
        }


@dataclass(frozen=True)
class ScoringResult:
    """Final scoring output: a deterministic score with full breakdown."""

    final_score: int
    """Final bounded score in [0, 100]."""

    raw_score: float
    """Unbounded weighted sum before clamping (useful for debugging)."""

    breakdown: ScoreBreakdown

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_score": self.final_score,
            "raw_score": round(self.raw_score, 4),
            "breakdown": self.breakdown.to_dict(),
        }


# ---------------------------------------------------------------------------
# Scoring service
# ---------------------------------------------------------------------------

class EventScoringService:
    """
    Computes a deterministic, explainable business opportunity score for
    an event by combining AI-extracted signals with rule-based features.

    The AI output influences the score through calibrated numeric mappings
    but never controls the result unilaterally.

    Usage::

        result = EventScoringService().score(features, signals)
        print(result.final_score)          # e.g. 72
        print(result.breakdown.to_dict())  # full factor breakdown
    """

    def score(
        self,
        features: EventFeatures,
        signals: NormalizedAISignals,
    ) -> ScoringResult:
        """
        Compute and return a ``ScoringResult`` for the given feature vector
        and AI signals.

        This method is pure: same inputs always produce the same output.
        """
        attendance_score = _ATTENDANCE_MAP[signals.attendance_estimation]
        compatibility_score = _COMPATIBILITY_MAP[signals.foodtruck_compatibility]
        weekend_score = 100.0 if features.is_weekend else 40.0
        duration_score = self._duration_score(features.duration_hours)
        meal_overlap_score = self._meal_overlap_score(features)
        outdoor_score = 80.0 if signals.outdoor_event else 50.0
        summer_score = 85.0 if features.summer_period else 50.0

        attendance_c = attendance_score * _W_ATTENDANCE
        compatibility_c = compatibility_score * _W_COMPATIBILITY
        weekend_c = weekend_score * _W_WEEKEND
        duration_c = duration_score * _W_DURATION
        meal_overlap_c = meal_overlap_score * _W_MEAL_OVERLAP
        outdoor_c = outdoor_score * _W_OUTDOOR
        summer_c = summer_score * _W_SUMMER

        raw_score = (
            attendance_c
            + compatibility_c
            + weekend_c
            + duration_c
            + meal_overlap_c
            + outdoor_c
            + summer_c
        )
        final_score = max(0, min(100, round(raw_score)))

        breakdown = ScoreBreakdown(
            attendance_score=attendance_score,
            compatibility_score=compatibility_score,
            weekend_score=weekend_score,
            duration_score=duration_score,
            meal_overlap_score=meal_overlap_score,
            outdoor_score=outdoor_score,
            summer_score=summer_score,
            attendance_contribution=round(attendance_c, 4),
            compatibility_contribution=round(compatibility_c, 4),
            weekend_contribution=round(weekend_c, 4),
            duration_contribution=round(duration_c, 4),
            meal_overlap_contribution=round(meal_overlap_c, 4),
            outdoor_contribution=round(outdoor_c, 4),
            summer_contribution=round(summer_c, 4),
        )

        return ScoringResult(
            final_score=final_score,
            raw_score=raw_score,
            breakdown=breakdown,
        )

    # ------------------------------------------------------------------
    # Private factor helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _duration_score(duration_hours: float) -> float:
        """Map event duration to a score using calibrated thresholds."""
        for max_hours, score in _DURATION_THRESHOLDS:
            if duration_hours <= max_hours:
                return score
        return 100.0  # unreachable but satisfies type checker

    @staticmethod
    def _meal_overlap_score(features: EventFeatures) -> float:
        """Return higher score when both meal windows are covered."""
        if features.lunch_time_overlap and features.dinner_time_overlap:
            return 100.0
        if features.lunch_time_overlap or features.dinner_time_overlap:
            return 60.0
        return 10.0


def explain_score(
    result: ScoringResult,
    signals: NormalizedAISignals,
    features: EventFeatures,
    language: str = "en",
) -> dict[str, Any]:
    """
    Generate a human-readable explanation of why the score is what it is.
    
    Args:
        result: ScoringResult from scoring
        signals: Normalized AI signals
        features: Extracted event features
        language: Language code (en, fr, etc.). Defaults to 'en'
    
    Returns a dict with:
    - summary: 1-2 sentence explanation in plain language
    - factors: list of {name, score, weight, label, explanation}
    """
    bd = result.breakdown

    factor_explanations = [
        {
            "name": "attendance",
            "label": _get_text("factor_labels", language, "attendance"),
            "score": bd.attendance_score,
            "weight": _W_ATTENDANCE,
            "explanation": _explain_attendance(signals.attendance_estimation, language),
        },
        {
            "name": "compatibility",
            "label": _get_text("factor_labels", language, "compatibility"),
            "score": bd.compatibility_score,
            "weight": _W_COMPATIBILITY,
            "explanation": _explain_compatibility(signals.foodtruck_compatibility, language),
        },
        {
            "name": "outdoor",
            "label": _get_text("factor_labels", language, "outdoor"),
            "score": bd.outdoor_score,
            "weight": _W_OUTDOOR,
            "explanation": _explain_outdoor(signals.outdoor_event, language),
        },
        {
            "name": "weekend",
            "label": _get_text("factor_labels", language, "weekend"),
            "score": bd.weekend_score,
            "weight": _W_WEEKEND,
            "explanation": _explain_weekend(features.is_weekend, language),
        },
        {
            "name": "meal_overlap",
            "label": _get_text("factor_labels", language, "meal_overlap"),
            "score": bd.meal_overlap_score,
            "weight": _W_MEAL_OVERLAP,
            "explanation": _explain_meal_overlap(features, language),
        },
        {
            "name": "duration",
            "label": _get_text("factor_labels", language, "duration"),
            "score": bd.duration_score,
            "weight": _W_DURATION,
            "explanation": _explain_duration(features.duration_hours, language),
        },
        {
            "name": "summer",
            "label": _get_text("factor_labels", language, "summer"),
            "score": bd.summer_score,
            "weight": _W_SUMMER,
            "explanation": _explain_summer(features.summer_period, language),
        },
    ]

    summary = _generate_score_summary(result.final_score, factor_explanations, language)

    return {
        "summary": summary,
        "final_score": result.final_score,
        "raw_score": round(result.raw_score, 2),
        "factors": factor_explanations,
        "ai_confidence": f"{int(signals.confidence * 100)}%",
    }


def _explain_attendance(est: str, language: str = "en") -> str:
    """Translate attendance estimation to readable explanation."""
    return _get_text("attendance_explanations", language, est)


def _explain_compatibility(comp: str, language: str = "en") -> str:
    """Translate compatibility to readable explanation."""
    return _get_text("compatibility_explanations", language, comp)


def _explain_outdoor(is_outdoor: bool, language: str = "en") -> str:
    """Explain outdoor event status."""
    key = "true" if is_outdoor else "false"
    return _get_text("outdoor_explanations", language, key)


def _explain_weekend(is_weekend: bool, language: str = "en") -> str:
    """Explain weekend status."""
    key = "true" if is_weekend else "false"
    return _get_text("weekend_explanations", language, key)


def _explain_meal_overlap(features: EventFeatures, language: str = "en") -> str:
    """Explain meal overlap."""
    if features.lunch_time_overlap and features.dinner_time_overlap:
        key = "both"
    elif features.lunch_time_overlap:
        key = "lunch"
    elif features.dinner_time_overlap:
        key = "dinner"
    else:
        key = "none"
    return _get_text("meal_overlap_explanations", language, key)


def _explain_duration(hours: float, language: str = "en") -> str:
    """Explain event duration."""
    if hours < 2:
        key = "very_short"
    elif hours < 6:
        key = "short"
    elif hours < 12:
        key = "medium"
    else:
        key = "long"
    return _get_text("duration_explanations", language, key)


def _explain_summer(is_summer: bool, language: str = "en") -> str:
    """Explain summer period status."""
    key = "true" if is_summer else "false"
    return _get_text("summer_explanations", language, key)


def _generate_score_summary(score: int, factors: list[dict[str, Any]], language: str = "en") -> str:
    """Generate a human-readable score summary."""
    # Determine quality level
    if score >= 80:
        quality_key = "excellent"
    elif score >= 60:
        quality_key = "good"
    elif score >= 40:
        quality_key = "moderate"
    else:
        quality_key = "low"
    
    quality = _get_text("quality_levels", language, quality_key)
    
    # Find top 2 positive factors
    top_factors = sorted(factors, key=lambda f: f["score"], reverse=True)[:2]
    top_labels = [f["label"] for f in top_factors]
    joiner = _get_text("factors_joiner", language)
    factors_text = f" {joiner} ".join(top_labels) if len(top_labels) > 1 else (top_labels[0] if top_labels else "")
    
    template = _get_text("summary_template", language)
    summary = template.format(quality=quality, score=score, factors=factors_text)
    
    return summary

