"""
Deterministic feature extraction from an ``Event`` instance.

All computations are timezone-safe, pure functions with no side effects.
The extracted features feed directly into ``EventScoringService`` and can
also be stored alongside the AI signals for auditability.
"""
from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass
from typing import Any

import pytz

from analytics.models import Event


# Default timezone used when an event has no explicit timezone info.
_DEFAULT_TZ = pytz.UTC

# Summer months (Northern Hemisphere definition used across this platform).
_SUMMER_MONTHS: frozenset[int] = frozenset({6, 7, 8})

# Meal-time windows (inclusive, 24-hour clock, local time).
_LUNCH_START = datetime.time(11, 30)
_LUNCH_END = datetime.time(14, 30)
_DINNER_START = datetime.time(18, 0)
_DINNER_END = datetime.time(22, 0)


@dataclass(frozen=True)
class EventFeatures:
    """Typed, immutable feature vector extracted from an event."""

    is_weekend: bool
    """True when the event starts on Saturday or Sunday."""

    duration_hours: float
    """Total event duration in fractional hours (min 0)."""

    duration_days: int
    """Total calendar days spanned by the event (min 1)."""

    lunch_time_overlap: bool
    """True when the event overlaps the 11:30–14:30 window on any day."""

    dinner_time_overlap: bool
    """True when the event overlaps the 18:00–22:00 window on any day."""

    summer_period: bool
    """True when the event start month is June, July, or August."""

    multi_day: bool
    """True when the event spans more than one calendar day."""

    distance_score_placeholder: float
    """
    Placeholder for geospatial distance scoring (always 0.0 here).
    Must be filled externally before scoring if a reference location is known.
    """

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict (compatible with JSONField storage)."""
        return asdict(self)


class EventFeatureExtractor:
    """
    Extracts deterministic features from an ``Event``.

    Example::

        features = EventFeatureExtractor().extract(event)
        print(features.is_weekend)        # True / False
        print(features.lunch_time_overlap) # True / False
    """

    def extract(self, event: Event) -> EventFeatures:
        """Return an ``EventFeatures`` dataclass for *event*."""
        start_dt, end_dt = self._resolve_datetimes(event)

        duration_hours = self._duration_hours(start_dt, end_dt)
        duration_days = max(1, (event.end_date - event.start_date).days + 1)

        return EventFeatures(
            is_weekend=self._is_weekend(event.start_date),
            duration_hours=duration_hours,
            duration_days=duration_days,
            lunch_time_overlap=self._has_meal_overlap(start_dt, end_dt, _LUNCH_START, _LUNCH_END),
            dinner_time_overlap=self._has_meal_overlap(start_dt, end_dt, _DINNER_START, _DINNER_END),
            summer_period=event.start_date.month in _SUMMER_MONTHS,
            multi_day=duration_days > 1,
            distance_score_placeholder=0.0,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_datetimes(event: Event) -> tuple[datetime.datetime, datetime.datetime]:
        """
        Return (start_datetime, end_datetime) for the event.

        Uses ``start_at`` / ``end_at`` when present (timezone-aware),
        otherwise synthesises midnight datetimes from ``start_date`` /
        ``end_date`` to stay timezone-safe.
        """
        start_at = getattr(event, "start_at", None)
        end_at = getattr(event, "end_at", None)

        if start_at and end_at:
            # Normalise to UTC if tz-aware, or attach UTC if naive
            if start_at.tzinfo is None:
                start_at = _DEFAULT_TZ.localize(start_at)
            if end_at.tzinfo is None:
                end_at = _DEFAULT_TZ.localize(end_at)
            return start_at, end_at

        # Fall back to date-only: treat events as running midnight-to-midnight UTC
        start_dt = datetime.datetime.combine(event.start_date, datetime.time.min, tzinfo=_DEFAULT_TZ)
        end_dt = datetime.datetime.combine(event.end_date, datetime.time.max, tzinfo=_DEFAULT_TZ)
        return start_dt, end_dt

    @staticmethod
    def _duration_hours(start: datetime.datetime, end: datetime.datetime) -> float:
        delta = end - start
        return max(0.0, delta.total_seconds() / 3600.0)

    @staticmethod
    def _is_weekend(date: datetime.date) -> bool:
        # weekday(): Monday=0 … Sunday=6; weekend = 5 or 6
        return date.weekday() >= 5

    @staticmethod
    def _has_meal_overlap(
        start: datetime.datetime,
        end: datetime.datetime,
        window_start: datetime.time,
        window_end: datetime.time,
    ) -> bool:
        """
        Return True if any point within the event duration falls inside the
        given daily time window.

        The check iterates through each calendar day to handle multi-day events.
        """
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            # Build window boundaries on the current calendar day (UTC)
            day_window_start = datetime.datetime.combine(current_date, window_start, tzinfo=_DEFAULT_TZ)
            day_window_end = datetime.datetime.combine(current_date, window_end, tzinfo=_DEFAULT_TZ)

            # Overlap check: [start, end] ∩ [window_start, window_end] ≠ ∅
            if start < day_window_end and end > day_window_start:
                return True

            current_date += datetime.timedelta(days=1)

        return False

    @staticmethod
    def _is_duration(hours: float) -> str:
        """Classify duration to a human-readable label (helper, not stored in features)."""
        if hours < 2:
            return "short"
        if hours < 6:
            return "medium"
        if hours < 12:
            return "long"
        return "full_day"
