import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{BASE_DIR / "app.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Celery configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    
    # Redis configuration
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # Upload configuration
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    
    # Ollama configuration
    # Vision model for first pass (handwriting OCR)
    # Options: qwen3-vl (best for handwriting), qwen2.5-vl, llama3.2-vision
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL') or 'qwen3-vl'
    
    # Text model for structuring (second pass). MUST be a text model, not vision!
    # Vision models overthink and return reasoning instead of direct JSON.
    # Good options: llama3.2, granite3.2, mistral, neural-chat
    STRUCTURE_MODEL = os.environ.get('STRUCTURE_MODEL') or 'llama3.2'
