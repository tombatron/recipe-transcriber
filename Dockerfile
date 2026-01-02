FROM python:3.14-slim

WORKDIR /app

# Set Python path to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    flask>=3.0.0 \
    flask-sqlalchemy>=3.0.0 \
    flask-migrate>=4.0.0 \
    turbo-flask>=0.8.0 \
    python-dotenv>=1.0.0 \
    celery[redis]>=5.3.0 \
    redis>=5.0.0 \
    ollama>=0.6.0 \
    pydantic>=2.0.0 \
    pillow>=10.0.0 \
    requests>=2.31.0 \
    gunicorn>=21.0.0 \
    gevent>=23.0.0

# Copy application code
COPY src/ ./src/
COPY app.py celery_app.py ./
COPY migrations/ ./migrations/

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 8000

# Default command (override in compose)
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "2", "--bind", "0.0.0.0:8000", "--timeout", "120", "app:create_app()"]
