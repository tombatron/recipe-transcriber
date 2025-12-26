from src.receipe_transcriber import create_app

# Create Flask app
app = create_app()

# Get the configured celery instance
from src.receipe_transcriber import celery

# Push app context for Celery worker
app.app_context().push()
