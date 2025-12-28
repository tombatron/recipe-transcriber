import os
from flask import Flask
from flask_migrate import Migrate
from turbo_flask import Turbo

from .config import Config

# Import db from models (single source of truth)
from .models import db

migrate = Migrate()
turbo = Turbo()


def make_celery(app):
    """Configure Celery with Flask app context."""
    from .celery_app import init_celery
    return init_celery(app)

def create_app(config_class=Config):
    app = Flask(__name__)
    turbo.init_app(app)
    
    # Load config FIRST
    app.config.from_object(config_class)
    
    # Set secret key for sessions
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'dev-key-change-in-production'
    
    # Configure Redis URL for SSE
    if not app.config.get('REDIS_URL'):
        app.config['REDIS_URL'] = 'redis://localhost:6379/0'
        
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize Celery
    make_celery(app)
    
    # Store db instance on app for easy access
    app.db = db
    
    # Register blueprints
    from .routes import main
    app.register_blueprint(main.bp)
    
    # Add CLI command for database initialization
    @app.cli.command()
    def init_db():
        """Initialize the database."""
        from .models import Recipe, Ingredient, Instruction, TranscriptionJob
        db.create_all()
        print("Database tables created successfully!")
    
    return app

# Export celery instance for Celery worker
from .celery_app import celery

__all__ = ['create_app', 'db', 'celery']