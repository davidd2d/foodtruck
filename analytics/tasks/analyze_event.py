"""
Celery task: asynchronous AI analysis of a single event.

Design decisions:
- Idempotent: skips already-analysed events unless ``force=True``.
- Retry-safe: non-fatal errors are retried with exponential back-off.
- Measures and logs processing duration end-to-end (including DB writes).
- Separates the Celery task (thin shell) from the service layer (all logic).
"""
from __future__ import annotations

import logging
import time

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.db import OperationalError

logger = logging.getLogger(__name__)

_MAX_RETRIES: int = 3
_RETRY_BACKOFF_BASE_S: int = 60  # seconds; doubled on each retry


@shared_task(
    bind=True,
    name="analytics.tasks.analyze_event",
    max_retries=_MAX_RETRIES,
    default_retry_delay=_RETRY_BACKOFF_BASE_S,
    acks_late=True,  # Acknowledge only after successful completion / final failure
)
def analyze_event_task(self, event_id: int, *, force: bool = False) -> dict:
    """
    Perform AI analysis for the event identified by *event_id*.

    Parameters
    ----------
    event_id:
        Primary key of the ``analytics.Event`` to analyse.
    force:
        When ``True``, bypass the idempotency guard and re-analyse even if
        a current-version ``EventAIAnalysis`` already exists.

    Returns
    -------
    dict
        ``{"event_id": int, "status": "completed"|"skipped", "final_score": int|None}``
    """
    from analytics.models import Event, EventAIAnalysis
    from analytics.services.ai_analysis import EventAIAnalysisService
    from analytics.services.feature_extraction import EventFeatureExtractor
    from analytics.services.prompts import CURRENT_PROMPT_VERSION
    from analytics.services.scoring import EventScoringService

    t0 = time.monotonic()

    # --- Load event -----------------------------------------------------------
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        logger.error("analyze_event_task: Event(id=%s) not found – aborting.", event_id)
        return {"event_id": event_id, "status": "not_found", "final_score": None}

    # --- Idempotency guard ----------------------------------------------------
    if not force:
        already_done = EventAIAnalysis.objects.filter(
            event=event,
            prompt_version=CURRENT_PROMPT_VERSION,
        ).exists()
        if already_done:
            logger.info(
                "analyze_event_task: Event(id=%s) already analysed at current prompt version – skipping.",
                event_id,
            )
            return {"event_id": event_id, "status": "skipped", "final_score": None}

    # --- Analysis + scoring ---------------------------------------------------
    try:
        ai_service = EventAIAnalysisService()
        extractor = EventFeatureExtractor()
        scorer = EventScoringService()

        if force:
            signals, _analysis = ai_service.analyse_force(event)
        else:
            signals, _analysis = ai_service.analyse(event)

        features = extractor.extract(event)
        result = scorer.score(features, signals)

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        logger.info(
            "analyze_event_task completed: event_id=%s score=%d elapsed_ms=%d",
            event_id,
            result.final_score,
            elapsed_ms,
        )
        return {
            "event_id": event_id,
            "status": "completed",
            "final_score": result.final_score,
            "elapsed_ms": elapsed_ms,
        }

    except OperationalError as exc:
        # Transient DB error – retry
        logger.warning(
            "analyze_event_task: DB error for event_id=%s, retrying. exc=%s",
            event_id,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=_RETRY_BACKOFF_BASE_S * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            logger.error("analyze_event_task: max retries exceeded for event_id=%s.", event_id)
            raise

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "analyze_event_task: unexpected error for event_id=%s.",
            event_id,
        )
        try:
            raise self.retry(exc=exc, countdown=_RETRY_BACKOFF_BASE_S * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            logger.error(
                "analyze_event_task: max retries exceeded for event_id=%s – giving up.",
                event_id,
            )
            raise
