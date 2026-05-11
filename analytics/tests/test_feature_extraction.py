"""
Tests for deterministic feature extraction.
"""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from analytics.services.feature_extraction import EventFeatureExtractor


def _make_event(
    name: str = "Test Event",
    start_date: datetime.date = datetime.date(2025, 7, 5),  # Saturday
    end_date: datetime.date = datetime.date(2025, 7, 5),
    expected_attendance: int | None = 500,
    latitude: float = 48.85,
    longitude: float = 2.35,
) -> MagicMock:
    event = MagicMock()
    event.name = name
    event.start_date = start_date
    event.end_date = end_date
    event.expected_attendance = expected_attendance
    event.latitude = latitude
    event.longitude = longitude
    # No start_at / end_at by default (date-only mode)
    del event.start_at
    del event.end_at
    return event


def _make_event_with_datetimes(
    start_at: datetime.datetime,
    end_at: datetime.datetime,
) -> MagicMock:
    import pytz
    event = MagicMock()
    event.name = "Datetime Event"
    event.start_date = start_at.date()
    event.end_date = end_at.date()
    event.expected_attendance = 1000
    event.latitude = 48.85
    event.longitude = 2.35
    event.start_at = pytz.UTC.localize(start_at.replace(tzinfo=None))
    event.end_at = pytz.UTC.localize(end_at.replace(tzinfo=None))
    return event


class TestEventFeatureExtractor:
    def setup_method(self):
        self.extractor = EventFeatureExtractor()

    # --- Weekend detection ---------------------------------------------------

    def test_saturday_is_weekend(self):
        event = _make_event(start_date=datetime.date(2025, 7, 5))  # Saturday
        features = self.extractor.extract(event)
        assert features.is_weekend is True

    def test_sunday_is_weekend(self):
        event = _make_event(start_date=datetime.date(2025, 7, 6))  # Sunday
        features = self.extractor.extract(event)
        assert features.is_weekend is True

    def test_monday_is_not_weekend(self):
        event = _make_event(start_date=datetime.date(2025, 7, 7))  # Monday
        features = self.extractor.extract(event)
        assert features.is_weekend is False

    # --- Summer period -------------------------------------------------------

    def test_july_is_summer(self):
        event = _make_event(start_date=datetime.date(2025, 7, 15))
        assert self.extractor.extract(event).summer_period is True

    def test_december_is_not_summer(self):
        event = _make_event(start_date=datetime.date(2025, 12, 20))
        assert self.extractor.extract(event).summer_period is False

    def test_june_is_summer(self):
        event = _make_event(start_date=datetime.date(2025, 6, 1))
        assert self.extractor.extract(event).summer_period is True

    def test_august_is_summer(self):
        event = _make_event(start_date=datetime.date(2025, 8, 31))
        assert self.extractor.extract(event).summer_period is True

    def test_september_is_not_summer(self):
        event = _make_event(start_date=datetime.date(2025, 9, 1))
        assert self.extractor.extract(event).summer_period is False

    # --- Multi-day detection -------------------------------------------------

    def test_single_day_not_multi_day(self):
        event = _make_event(
            start_date=datetime.date(2025, 7, 5),
            end_date=datetime.date(2025, 7, 5),
        )
        assert self.extractor.extract(event).multi_day is False

    def test_two_day_event_is_multi_day(self):
        event = _make_event(
            start_date=datetime.date(2025, 7, 5),
            end_date=datetime.date(2025, 7, 6),
        )
        assert self.extractor.extract(event).multi_day is True

    def test_duration_days_single(self):
        event = _make_event(
            start_date=datetime.date(2025, 7, 5),
            end_date=datetime.date(2025, 7, 5),
        )
        assert self.extractor.extract(event).duration_days == 1

    def test_duration_days_three(self):
        event = _make_event(
            start_date=datetime.date(2025, 7, 5),
            end_date=datetime.date(2025, 7, 7),
        )
        assert self.extractor.extract(event).duration_days == 3

    # --- Meal overlap (datetime-precise) ------------------------------------

    def test_lunch_overlap_detected(self):
        # Event covers 12:00–13:00: squarely inside lunch window
        start = datetime.datetime(2025, 7, 5, 12, 0)
        end = datetime.datetime(2025, 7, 5, 13, 0)
        event = _make_event_with_datetimes(start, end)
        features = self.extractor.extract(event)
        assert features.lunch_time_overlap is True

    def test_dinner_overlap_detected(self):
        start = datetime.datetime(2025, 7, 5, 19, 0)
        end = datetime.datetime(2025, 7, 5, 21, 0)
        event = _make_event_with_datetimes(start, end)
        features = self.extractor.extract(event)
        assert features.dinner_time_overlap is True

    def test_no_overlap_early_morning(self):
        # Event 06:00–08:00 – before lunch and dinner
        start = datetime.datetime(2025, 7, 5, 6, 0)
        end = datetime.datetime(2025, 7, 5, 8, 0)
        event = _make_event_with_datetimes(start, end)
        features = self.extractor.extract(event)
        assert features.lunch_time_overlap is False
        assert features.dinner_time_overlap is False

    def test_full_day_event_overlaps_both_meals(self):
        # Date-only event is mapped to midnight–23:59 so covers both meal windows
        event = _make_event(
            start_date=datetime.date(2025, 7, 5),
            end_date=datetime.date(2025, 7, 5),
        )
        features = self.extractor.extract(event)
        assert features.lunch_time_overlap is True
        assert features.dinner_time_overlap is True

    # --- Distance placeholder -----------------------------------------------

    def test_distance_score_is_zero_placeholder(self):
        event = _make_event()
        assert self.extractor.extract(event).distance_score_placeholder == 0.0

    # --- Duration hours (datetime mode) -------------------------------------

    def test_duration_hours_two_hours(self):
        start = datetime.datetime(2025, 7, 5, 10, 0)
        end = datetime.datetime(2025, 7, 5, 12, 0)
        event = _make_event_with_datetimes(start, end)
        features = self.extractor.extract(event)
        assert features.duration_hours == pytest.approx(2.0, abs=0.01)

    def test_duration_hours_non_negative(self):
        # Inverted dates should yield 0
        start = datetime.datetime(2025, 7, 5, 12, 0)
        end = datetime.datetime(2025, 7, 5, 10, 0)
        event = _make_event_with_datetimes(start, end)
        features = self.extractor.extract(event)
        assert features.duration_hours >= 0.0
