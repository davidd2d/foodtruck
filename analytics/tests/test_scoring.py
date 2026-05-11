"""
Tests for the deterministic event scoring service.
"""
from __future__ import annotations

import pytest

from analytics.services.feature_extraction import EventFeatures
from analytics.services.schemas import NormalizedAISignals
from analytics.services.scoring import EventScoringService


def _make_features(**overrides) -> EventFeatures:
    defaults = dict(
        is_weekend=True,
        duration_hours=6.0,
        duration_days=1,
        lunch_time_overlap=True,
        dinner_time_overlap=True,
        summer_period=True,
        multi_day=False,
        distance_score_placeholder=0.0,
    )
    defaults.update(overrides)
    return EventFeatures(**defaults)


def _make_signals(**overrides) -> NormalizedAISignals:
    defaults = dict(
        attendance_estimation="high",
        foodtruck_compatibility="good",
        audience_type="mixed",
        family_friendly=True,
        outdoor_event=True,
        weather_dependency=False,
        estimated_visit_duration="medium",
        peak_meal_relevance="high",
        confidence=0.85,
        reasoning="Fine event.",
    )
    defaults.update(overrides)
    return NormalizedAISignals(**defaults)


class TestEventScoringService:
    def setup_method(self):
        self.service = EventScoringService()

    def test_score_is_in_range(self):
        result = self.service.score(_make_features(), _make_signals())
        assert 0 <= result.final_score <= 100

    def test_score_is_deterministic(self):
        features = _make_features()
        signals = _make_signals()
        r1 = self.service.score(features, signals)
        r2 = self.service.score(features, signals)
        assert r1.final_score == r2.final_score
        assert r1.raw_score == r2.raw_score

    def test_excellent_event_scores_higher_than_poor_event(self):
        good_features = _make_features(
            is_weekend=True,
            lunch_time_overlap=True,
            dinner_time_overlap=True,
            summer_period=True,
            duration_hours=8.0,
        )
        good_signals = _make_signals(
            attendance_estimation="very_high",
            foodtruck_compatibility="excellent",
            outdoor_event=True,
        )

        bad_features = _make_features(
            is_weekend=False,
            lunch_time_overlap=False,
            dinner_time_overlap=False,
            summer_period=False,
            duration_hours=0.5,
        )
        bad_signals = _make_signals(
            attendance_estimation="very_low",
            foodtruck_compatibility="poor",
            outdoor_event=False,
        )

        good = self.service.score(good_features, good_signals)
        bad = self.service.score(bad_features, bad_signals)
        assert good.final_score > bad.final_score

    def test_breakdown_contributions_sum_to_raw_score(self):
        result = self.service.score(_make_features(), _make_signals())
        bd = result.breakdown
        total = (
            bd.attendance_contribution
            + bd.compatibility_contribution
            + bd.weekend_contribution
            + bd.duration_contribution
            + bd.meal_overlap_contribution
            + bd.outdoor_contribution
            + bd.summer_contribution
        )
        assert abs(total - result.raw_score) < 0.001

    def test_weekend_bonus_applied(self):
        weekend = self.service.score(_make_features(is_weekend=True), _make_signals())
        weekday = self.service.score(_make_features(is_weekend=False), _make_signals())
        assert weekend.breakdown.weekend_score > weekday.breakdown.weekend_score

    def test_no_meal_overlap_lowers_score(self):
        overlap = self.service.score(
            _make_features(lunch_time_overlap=True, dinner_time_overlap=True),
            _make_signals(),
        )
        no_overlap = self.service.score(
            _make_features(lunch_time_overlap=False, dinner_time_overlap=False),
            _make_signals(),
        )
        assert overlap.final_score > no_overlap.final_score

    def test_to_dict_is_json_serialisable(self):
        import json
        result = self.service.score(_make_features(), _make_signals())
        serialised = json.dumps(result.to_dict())
        parsed = json.loads(serialised)
        assert parsed["final_score"] == result.final_score

    def test_very_short_duration_score(self):
        result = self.service.score(_make_features(duration_hours=0.5), _make_signals())
        assert result.breakdown.duration_score == 20.0

    def test_full_day_duration_score(self):
        result = self.service.score(_make_features(duration_hours=15.0), _make_signals())
        assert result.breakdown.duration_score == 100.0

    def test_outdoor_event_bonus(self):
        outdoor = self.service.score(_make_features(), _make_signals(outdoor_event=True))
        indoor = self.service.score(_make_features(), _make_signals(outdoor_event=False))
        assert outdoor.breakdown.outdoor_score > indoor.breakdown.outdoor_score

    def test_summer_period_bonus(self):
        summer = self.service.score(_make_features(summer_period=True), _make_signals())
        off_season = self.service.score(_make_features(summer_period=False), _make_signals())
        assert summer.breakdown.summer_score > off_season.breakdown.summer_score
