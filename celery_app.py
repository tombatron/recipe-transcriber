"""Entry point for Celery worker (lean, no Flask app context)."""

from src.receipe_transcriber import celery
