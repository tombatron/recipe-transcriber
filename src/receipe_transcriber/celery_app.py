"""Lean Celery app initialization (no Flask app context required)."""

import os

from celery import Celery

celery = Celery(
    "receipe_transcriber",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

# Import tasks to register them; no Flask app context needed
from receipe_transcriber.tasks import transcription_tasks  # noqa: F401


def init_celery(app):
    """Optional override to sync broker/backend from Flask config without binding context."""
    celery.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL", celery.conf.broker_url),
        result_backend=app.config.get(
            "CELERY_RESULT_BACKEND", celery.conf.result_backend
        ),
    )
    return celery
