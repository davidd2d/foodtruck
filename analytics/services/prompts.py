"""
Versioned prompt builder for event AI analyses.

Keeping prompts in a dedicated module enables independent versioning, testing,
and future A/B comparison without touching service or task code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from analytics.models import Event


# Bump this constant whenever the prompt wording changes in a way that would
# produce materially different outputs, so old and new analyses can be compared.
CURRENT_PROMPT_VERSION: str = "1.0"


@dataclass(frozen=True)
class BuiltPrompt:
    """Container holding a versioned, ready-to-send prompt."""

    version: str
    system_message: str
    user_message: str


class PromptBuilder:
    """
    Constructs deterministic, version-tagged prompts for event evaluation.

    Usage::

        prompt = PromptBuilder().build(event)
        # prompt.system_message → system role content
        # prompt.user_message   → user role content
        # prompt.version        → "1.0"
    """

    VERSION: str = CURRENT_PROMPT_VERSION

    _SYSTEM_TEMPLATE: str = (
        "You are an expert evaluator of public events for food truck business potential. "
        "Your task is to analyse event data and extract structured signals relevant to "
        "food truck operators. "
        "Rules:\n"
        "- Respond with valid JSON only. No markdown. No text outside the JSON object.\n"
        "- Use only the information provided. Do not speculate or invent details.\n"
        "- If a field cannot be determined, choose the most conservative valid value.\n"
        "- Be concise: the 'reasoning' field must not exceed 3 sentences."
    )

    _USER_TEMPLATE: str = (
        "Evaluate the following event for food truck business potential.\n\n"
        "Event name: {name}\n"
        "Start date: {start_date}\n"
        "End date: {end_date}\n"
        "Duration (hours): {duration_hours}\n"
        "Expected attendance: {expected_attendance}\n"
        "Location: {city}\n\n"
        "Return a single JSON object with these exact keys: "
        "attendance_estimation, foodtruck_compatibility, audience_type, "
        "family_friendly, outdoor_event, weather_dependency, "
        "estimated_visit_duration, peak_meal_relevance, confidence, reasoning."
    )

    def build(self, event: Event) -> BuiltPrompt:
        """Build a versioned prompt from an ``Event`` instance."""
        duration_hours = self._compute_duration_hours(event)
        city = getattr(event, "city", None) or "unknown"
        expected_attendance = (
            str(event.expected_attendance)
            if event.expected_attendance is not None
            else "unknown"
        )

        user_message = self._USER_TEMPLATE.format(
            name=event.name,
            start_date=event.start_date.isoformat(),
            end_date=event.end_date.isoformat(),
            duration_hours=f"{duration_hours:.1f}",
            expected_attendance=expected_attendance,
            city=city,
        )

        return BuiltPrompt(
            version=self.VERSION,
            system_message=self._SYSTEM_TEMPLATE,
            user_message=user_message,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_duration_hours(event: Event) -> float:
        """Return the event duration in fractional hours."""
        from datetime import datetime, timezone as tz

        # Use full datetime if available (start_at / end_at), fall back to dates
        start_at = getattr(event, "start_at", None)
        end_at = getattr(event, "end_at", None)

        if start_at and end_at:
            delta = end_at - start_at
        else:
            from datetime import timedelta
            days = (event.end_date - event.start_date).days
            delta = __import__("datetime").timedelta(days=max(1, days))

        total_seconds = max(0, delta.total_seconds())
        return total_seconds / 3600


def get_prompt_version_info() -> dict[str, Any]:
    """Return metadata about all known prompt versions (useful for admin/audit)."""
    return {
        "current_version": CURRENT_PROMPT_VERSION,
        "versions": {
            "1.0": {
                "description": "Initial event evaluation prompt with 10 structured signals.",
                "fields": [
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
            }
        },
    }
