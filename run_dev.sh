#!/bin/bash

echo "Recipe Transcriber Development Setup"
echo "===================================="
echo ""
echo "Make sure you have the following running in separate terminals:"
echo "1. Redis: redis-server"
echo "2. Celery: celery -A celery_app.celery worker --loglevel=info"
echo "3. Ollama: Make sure Ollama is running with llava model"
echo ""
echo "Starting Flask development server..."
echo ""

export FLASK_APP=src.receipe_transcriber
export FLASK_ENV=development

flask run
