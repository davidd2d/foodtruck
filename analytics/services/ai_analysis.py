"""
AI analysis service for event evaluation.

Responsibilities:
- Send structured prompts to OpenAI
- Validate and normalise the JSON response
- Persist the result as an ``EventAIAnalysis`` record
- Remain decoupled from scoring logic

This service intentionally does NOT compute the final business score.
It only extracts structured signals from the AI and stores them durably.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from django.utils import timezone
from openai import OpenAI

from analytics.models import Event, EventAIAnalysis
from analytics.services.prompts import PromptBuilder
from analytics.services.schemas import (
    AIResponseValidationError,
    EVENT_ANALYSIS_JSON_SCHEMA,
    NormalizedAISignals,
    validate_and_normalize,
)

logger = logging.getLogger(__name__)

# Default model used for event evaluations.
DEFAULT_MODEL: str = "gpt-4o-mini"


class EventAIAnalysisService:
    """
    Orchestrates the full lifecycle of one AI event analysis:

    1. Build a versioned prompt.
    2. Call OpenAI with structured output enforcement.
    3. Validate and normalise the response.
    4. Persist an ``EventAIAnalysis`` record (create or update).
    5. Return the normalised signals to the caller.

    The service is **stateless** and can be instantiated per-request or
    shared as a singleton.

    Example::

        service = EventAIAnalysisService()
        signals, analysis = service.analyse(event)
        print(signals.foodtruck_compatibility)   # "good"
        print(analysis.processing_time_ms)       # 843
    """

    def __init__(self, client: OpenAI | None = None, model: str = DEFAULT_MODEL) -> None:
        import os
        self._client: OpenAI = client or OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        self._model: str = model
        self._prompt_builder: PromptBuilder = PromptBuilder()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(self, event: Event) -> tuple[NormalizedAISignals, EventAIAnalysis]:
        """
        Perform AI analysis for *event* and persist the result.

        If an ``EventAIAnalysis`` already exists for the event and has the
        current prompt version, returns the cached record without a new API
        call.  Pass ``force=True`` to bypass this guard.

        Returns ``(NormalizedAISignals, EventAIAnalysis)``.
        Raises ``AIResponseValidationError`` on invalid AI output.
        Raises ``openai.OpenAIError`` on API failure (caller should handle).
        """
        existing = self._load_existing(event)
        if existing is not None:
            signals = validate_and_normalize(existing.normalized_data)
            return signals, existing

        return self._run_analysis(event)

    def analyse_force(self, event: Event) -> tuple[NormalizedAISignals, EventAIAnalysis]:
        """
        Always perform a fresh AI analysis, overwriting any existing record.
        Useful for re-scoring after a prompt version bump.
        """
        return self._run_analysis(event)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_existing(self, event: Event) -> EventAIAnalysis | None:
        """Return a matching analysis if one already exists with the current prompt version."""
        try:
            analysis = EventAIAnalysis.objects.get(event=event)
            if analysis.prompt_version == self._prompt_builder.VERSION:
                logger.debug(
                    "Cached AI analysis found for event %s (version %s).",
                    event.id,
                    analysis.prompt_version,
                )
                return analysis
        except EventAIAnalysis.DoesNotExist:
            pass
        return None

    def _run_analysis(self, event: Event) -> tuple[NormalizedAISignals, EventAIAnalysis]:
        """Call OpenAI, validate, persist, and return results."""
        prompt = self._prompt_builder.build(event)
        raw_response, usage, processing_ms = self._call_openai(prompt)

        # Validate strictly – raises AIResponseValidationError on failure.
        signals = validate_and_normalize(raw_response)

        analysis = self._persist(
            event=event,
            prompt_version=prompt.version,
            raw_response=raw_response,
            signals=signals,
            usage=usage,
            processing_ms=processing_ms,
        )

        logger.info(
            "Event AI analysis completed: event_id=%s score=%.2f ms=%d",
            event.id,
            signals.confidence,
            processing_ms,
        )
        return signals, analysis

    def _call_openai(
        self, prompt: Any
    ) -> tuple[dict[str, Any], dict[str, int], int]:
        """
        Send the prompt to OpenAI and return ``(raw_dict, token_usage, ms)``.

        Uses ``response_format`` with a JSON schema to enforce structured output.
        """
        t0 = time.monotonic()

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": prompt.system_message},
                {"role": "user", "content": prompt.user_message},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": EVENT_ANALYSIS_JSON_SCHEMA,
            },
            temperature=0,  # Deterministic output
        )

        processing_ms = int((time.monotonic() - t0) * 1000)

        raw_content: str = response.choices[0].message.content or ""
        raw_dict: dict[str, Any] = json.loads(raw_content)

        usage = {
            "input": getattr(response.usage, "prompt_tokens", 0),
            "output": getattr(response.usage, "completion_tokens", 0),
        }
        return raw_dict, usage, processing_ms

    def _persist(
        self,
        event: Event,
        prompt_version: str,
        raw_response: dict[str, Any],
        signals: NormalizedAISignals,
        usage: dict[str, int],
        processing_ms: int,
    ) -> EventAIAnalysis:
        """Create or update the ``EventAIAnalysis`` record for *event*."""
        from dataclasses import asdict

        defaults: dict[str, Any] = {
            "provider": EventAIAnalysis.Provider.OPENAI,
            "model_name": self._model,
            "prompt_version": prompt_version,
            "raw_response": raw_response,
            "normalized_data": asdict(signals),
            "confidence_score": signals.confidence,
            "analyzed_at": timezone.now(),
            "processing_time_ms": processing_ms,
            "token_usage_input": usage["input"],
            "token_usage_output": usage["output"],
        }

        analysis, created = EventAIAnalysis.objects.update_or_create(
            event=event,
            defaults=defaults,
        )

        logger.debug(
            "%s EventAIAnalysis for event_id=%s.",
            "Created" if created else "Updated",
            event.id,
        )
        return analysis
