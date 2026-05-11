# Load Celery app so @shared_task decorators are registered at startup.
from .celery import app as celery_app  # noqa: F401

__all__ = ["celery_app"]
