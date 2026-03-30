"""
Celery application configuration.
Workers handle async reconciliation, retention cleanup, and alerts.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

celery_app = Celery(
    "control_fabric",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_soft_time_limit=300,
    task_time_limit=600,
    beat_schedule={
        "reconciliation-every-hour": {
            "task": "app.worker.tasks.run_scheduled_reconciliation",
            "schedule": crontab(minute=0),
        },
        "retention-cleanup-daily": {
            "task": "app.worker.tasks.run_retention_cleanup",
            "schedule": crontab(hour=2, minute=0),
        },
        "alert-on-critical-cases-every-15min": {
            "task": "app.worker.tasks.alert_on_open_critical_cases",
            "schedule": crontab(minute="*/15"),
        },
    },
)
