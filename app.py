"""
Flask application entry point.
Run with: python app.py
Or use: flask run (with FLASK_APP=src.receipe_transcriber)
"""
from src.receipe_transcriber import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
