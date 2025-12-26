"""
Isolated Celery app initialization.
This module initializes Celery independently to avoid circular imports.
"""
import os
from celery import Celery, Task

# Initialize Celery with Redis broker
celery = Celery(
    'receipe_transcriber',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
)

# Default Celery configuration
celery.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)


def init_celery(app):
    """Configure Celery to work with Flask app context."""
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.conf.update(
        broker_url=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        result_backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    )
    celery.Task = FlaskTask
    celery.set_default()
    return celery
