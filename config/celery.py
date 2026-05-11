"""
Celery application instance for the food truck platform.

This module must be imported by ``config/__init__.py`` so that the Celery
app is loaded whenever Django starts and ``@shared_task`` decorators work.
"""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("foodtruck")

# Namespace "CELERY_" means all celery-related config keys must be prefixed.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all INSTALLED_APPS (looks for tasks/ packages and tasks.py).
app.autodiscover_tasks()
