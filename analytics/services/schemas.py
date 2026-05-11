"""
JSON schema definitions and dataclass types for AI event analysis responses.

All validation is done here, keeping AI calls decoupled from persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Enum-style type aliases (used for documentation and validation contracts)
# ---------------------------------------------------------------------------

AttendanceEstimation = Literal["very_low", "low", "medium", "high", "very_high"]
FoodtruckCompatibility = Literal["poor", "fair", "good", "excellent"]
AudienceType = Literal["families", "young_adults", "professionals", "general", "mixed"]
EstimatedVisitDuration = Literal["short", "medium", "long", "full_day"]
PeakMealRelevance = Literal["none", "low", "medium", "high"]


# ---------------------------------------------------------------------------
# OpenAI response_format JSON schema (used with response_format="json_schema")
# ---------------------------------------------------------------------------

EVENT_ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "name": "event_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "attendance_estimation": {
                "type": "string",
                "enum": ["very_low", "low", "medium", "high", "very_high"],
                "description": "Estimated attendance level based on available event information.",
            },
            "foodtruck_compatibility": {
                "type": "string",
                "enum": ["poor", "fair", "good", "excellent"],
                "description": "How well the event context suits a food truck business.",
            },
            "audience_type": {
                "type": "string",
                "enum": ["families", "young_adults", "professionals", "general", "mixed"],
                "description": "Primary audience profile inferred from the event.",
            },
            "family_friendly": {
                "type": "boolean",
                "description": "Whether the event is likely suitable for families with children.",
            },
            "outdoor_event": {
                "type": "boolean",
                "description": "Whether the event takes place outdoors.",
            },
            "weather_dependency": {
                "type": "boolean",
                "description": "Whether attendance/success strongly depends on weather conditions.",
            },
            "estimated_visit_duration": {
                "type": "string",
                "enum": ["short", "medium", "long", "full_day"],
                "description": "Typical duration of a visitor's stay (short < 1h, medium 1-3h, long 3-6h, full_day > 6h).",
            },
            "peak_meal_relevance": {
                "type": "string",
                "enum": ["none", "low", "medium", "high"],
                "description": "How much the event schedule overlaps with traditional meal times.",
            },
            "confidence": {
                "type": "number",
                "description": "AI confidence in the analysis from 0.0 to 1.0.",
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "reasoning": {
                "type": "string",
                "description": "Concise explanation (max 3 sentences) justifying the evaluation.",
            },
        },
        "required": [
            "attendance_estimation",
            "foodtruck_compatibility",
            "audience_type",
            "family_friendly",
            "outdoor_event",
            "weather_dependency",
            "estimated_visit_duration",
            "peak_meal_relevance",
            "confidence",
            "reasoning",
        ],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------
# Normalised dataclass – the contract between AI service and scoring service
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizedAISignals:
    """Validated, typed representation of what the AI extracted from an event."""

    attendance_estimation: AttendanceEstimation
    foodtruck_compatibility: FoodtruckCompatibility
    audience_type: AudienceType
    family_friendly: bool
    outdoor_event: bool
    weather_dependency: bool
    estimated_visit_duration: EstimatedVisitDuration
    peak_meal_relevance: PeakMealRelevance
    confidence: float
    reasoning: str


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_VALID_ATTENDANCE: frozenset[str] = frozenset({"very_low", "low", "medium", "high", "very_high"})
_VALID_COMPATIBILITY: frozenset[str] = frozenset({"poor", "fair", "good", "excellent"})
_VALID_AUDIENCE: frozenset[str] = frozenset({"families", "young_adults", "professionals", "general", "mixed"})
_VALID_DURATION: frozenset[str] = frozenset({"short", "medium", "long", "full_day"})
_VALID_MEAL_RELEVANCE: frozenset[str] = frozenset({"none", "low", "medium", "high"})


class AIResponseValidationError(ValueError):
    """Raised when the AI response does not conform to the expected schema."""


def validate_and_normalize(raw: dict[str, Any]) -> NormalizedAISignals:
    """
    Validate a raw AI response dict against expected types and enum ranges,
    then return a strongly-typed ``NormalizedAISignals`` instance.

    Raises ``AIResponseValidationError`` on any constraint violation.
    """
    _assert_string_enum("attendance_estimation", raw.get("attendance_estimation"), _VALID_ATTENDANCE)
    _assert_string_enum("foodtruck_compatibility", raw.get("foodtruck_compatibility"), _VALID_COMPATIBILITY)
    _assert_string_enum("audience_type", raw.get("audience_type"), _VALID_AUDIENCE)
    _assert_string_enum("estimated_visit_duration", raw.get("estimated_visit_duration"), _VALID_DURATION)
    _assert_string_enum("peak_meal_relevance", raw.get("peak_meal_relevance"), _VALID_MEAL_RELEVANCE)
    _assert_bool("family_friendly", raw.get("family_friendly"))
    _assert_bool("outdoor_event", raw.get("outdoor_event"))
    _assert_bool("weather_dependency", raw.get("weather_dependency"))
    _assert_float_range("confidence", raw.get("confidence"), 0.0, 1.0)
    _assert_non_empty_string("reasoning", raw.get("reasoning"))

    return NormalizedAISignals(
        attendance_estimation=raw["attendance_estimation"],
        foodtruck_compatibility=raw["foodtruck_compatibility"],
        audience_type=raw["audience_type"],
        family_friendly=bool(raw["family_friendly"]),
        outdoor_event=bool(raw["outdoor_event"]),
        weather_dependency=bool(raw["weather_dependency"]),
        estimated_visit_duration=raw["estimated_visit_duration"],
        peak_meal_relevance=raw["peak_meal_relevance"],
        confidence=float(raw["confidence"]),
        reasoning=str(raw["reasoning"]),
    )


# ---------------------------------------------------------------------------
# Private assertion helpers
# ---------------------------------------------------------------------------

def _assert_string_enum(field: str, value: Any, valid: frozenset[str]) -> None:
    if not isinstance(value, str) or value not in valid:
        raise AIResponseValidationError(
            f"Field '{field}' must be one of {sorted(valid)!r}, got {value!r}."
        )


def _assert_bool(field: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise AIResponseValidationError(
            f"Field '{field}' must be a boolean, got {type(value).__name__!r}."
        )


def _assert_float_range(field: str, value: Any, lo: float, hi: float) -> None:
    if not isinstance(value, (int, float)) or not (lo <= float(value) <= hi):
        raise AIResponseValidationError(
            f"Field '{field}' must be a float in [{lo}, {hi}], got {value!r}."
        )


def _assert_non_empty_string(field: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AIResponseValidationError(
            f"Field '{field}' must be a non-empty string, got {value!r}."
        )
