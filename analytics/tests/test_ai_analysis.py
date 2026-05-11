"""
Tests for JSON schema validation and AI response normalisation.
"""
from __future__ import annotations

import pytest

from analytics.services.schemas import (
    AIResponseValidationError,
    validate_and_normalize,
)


def _valid_raw() -> dict:
    return {
        "attendance_estimation": "high",
        "foodtruck_compatibility": "good",
        "audience_type": "mixed",
        "family_friendly": True,
        "outdoor_event": True,
        "weather_dependency": False,
        "estimated_visit_duration": "medium",
        "peak_meal_relevance": "high",
        "confidence": 0.85,
        "reasoning": "Large outdoor festival with diverse audience and full-day schedule.",
    }


class TestValidateAndNormalize:
    def test_valid_response_returns_signals(self):
        signals = validate_and_normalize(_valid_raw())
        assert signals.attendance_estimation == "high"
        assert signals.foodtruck_compatibility == "good"
        assert signals.outdoor_event is True
        assert signals.confidence == pytest.approx(0.85)

    def test_all_attendance_values_accepted(self):
        for value in ("very_low", "low", "medium", "high", "very_high"):
            raw = {**_valid_raw(), "attendance_estimation": value}
            assert validate_and_normalize(raw).attendance_estimation == value

    def test_all_compatibility_values_accepted(self):
        for value in ("poor", "fair", "good", "excellent"):
            raw = {**_valid_raw(), "foodtruck_compatibility": value}
            assert validate_and_normalize(raw).foodtruck_compatibility == value

    def test_invalid_attendance_raises(self):
        raw = {**_valid_raw(), "attendance_estimation": "enormous"}
        with pytest.raises(AIResponseValidationError, match="attendance_estimation"):
            validate_and_normalize(raw)

    def test_missing_field_raises(self):
        raw = _valid_raw()
        raw.pop("confidence")
        with pytest.raises(AIResponseValidationError, match="confidence"):
            validate_and_normalize(raw)

    def test_confidence_below_zero_raises(self):
        raw = {**_valid_raw(), "confidence": -0.1}
        with pytest.raises(AIResponseValidationError, match="confidence"):
            validate_and_normalize(raw)

    def test_confidence_above_one_raises(self):
        raw = {**_valid_raw(), "confidence": 1.1}
        with pytest.raises(AIResponseValidationError, match="confidence"):
            validate_and_normalize(raw)

    def test_confidence_boundary_zero(self):
        raw = {**_valid_raw(), "confidence": 0.0}
        signals = validate_and_normalize(raw)
        assert signals.confidence == 0.0

    def test_confidence_boundary_one(self):
        raw = {**_valid_raw(), "confidence": 1.0}
        signals = validate_and_normalize(raw)
        assert signals.confidence == 1.0

    def test_family_friendly_must_be_bool(self):
        raw = {**_valid_raw(), "family_friendly": 1}  # int, not bool
        with pytest.raises(AIResponseValidationError, match="family_friendly"):
            validate_and_normalize(raw)

    def test_empty_reasoning_raises(self):
        raw = {**_valid_raw(), "reasoning": "   "}
        with pytest.raises(AIResponseValidationError, match="reasoning"):
            validate_and_normalize(raw)

    def test_signals_are_immutable(self):
        signals = validate_and_normalize(_valid_raw())
        with pytest.raises(Exception):  # frozen dataclass
            signals.confidence = 0.5  # type: ignore[misc]

    def test_normalized_data_matches_input(self):
        raw = _valid_raw()
        signals = validate_and_normalize(raw)
        assert signals.audience_type == raw["audience_type"]
        assert signals.peak_meal_relevance == raw["peak_meal_relevance"]
        assert signals.estimated_visit_duration == raw["estimated_visit_duration"]
