# Recipe Transcriber

A Flask web application that uses Ollama's vision models to transcribe recipes from images (printed or handwritten) into structured digital format. Features real-time updates and a clean, modern UI inspired by Claude.ai.

## ✨ Features

- 📷 **Camera Capture** - Take photos directly with your device camera
- 📤 **File Upload** - Upload existing recipe images (PNG, JPG, JPEG, WEBP)
- 🤖 **AI-Powered** - Uses Ollama vision models for accurate transcription
- ⚡ **Real-Time Updates** - See processing status updates live via Server-Sent Events
- 💾 **Structured Data** - Extracts ingredients, instructions, prep/cook times
- 🎨 **Modern UI** - Clean interface built with HTMX and Tailwind CSS

## 🏗️ Tech Stack

- **Backend**: Flask, SQLAlchemy, Flask-Migrate
- **AI/ML**: Ollama (local LLM with vision capabilities)
- **Task Queue**: Celery with Redis broker
- **Real-Time Updates**: Flask-SSE with Redis Pub/Sub
- **Frontend**: HTMX + Server-Sent Events (SSE)
- **Styling**: Tailwind CSS
- **Database**: SQLite

## 🎯 Quick Start

### Prerequisites

Before you begin, ensure you have:
- Python 3.10+
- Redis (`sudo apt install redis` or `brew install redis`)
- Ollama (https://ollama.ai)

### Installation

1. **Install dependencies**
   ```bash
   pip install -e .
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   The default values in `.env.example` work for most local development setups. Edit `.env` if you need custom configuration for:
   - Database location
   - Redis connection URL
   - Ollama API endpoint
   - Secret key for Flask sessions

3. **Pull Ollama vision model**
   ```bash
   ollama pull llava:latest
   ```

4. **Initialize database**
   ```bash
   export FLASK_APP=src.receipe_transcriber
   flask db upgrade
   ```
   Or use the automated script:
   ```bash
   ./setup_database.sh
   ```

### Running the Application

**Option 1: Use VS Code Tasks (Recommended)**

Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) and run:
- "Tasks: Run Task" → "Start All Services"

This will start Redis, Ollama, and Tailwind CSS watch mode in the background.

Then start Flask and Celery:
```bash
# Terminal 1: Flask
./run_dev.sh

# Terminal 2: Celery
celery -A celery_app.celery worker --loglevel=info
```

**Option 2: Manual Setup**

Open 3 terminals and run:

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery Worker
celery -A celery_app.celery worker --loglevel=info

# Terminal 3: Flask + Ollama (in background)
ollama serve &
./run_dev.sh
```

**Option 4: Build Tailwind (Development)**
```bash
# Terminal 4 (optional, only if modifying CSS)
tailwindcss -i ./src/receipe_transcriber/static/css/input.css \
            -o ./src/receipe_transcriber/static/css/output.css --watch
```

### Access the App

Open your browser to: **http://localhost:5000**

## 📖 How It Works

### Architecture Overview

The application uses multiple processes coordinated via Redis:

```
┌─────────┐                    ┌─────────────┐
│ Browser │ ◄──SSE Connection─►│ Flask Server│
└─────────┘                    └──────┬──────┘
                                      │
                                      │ Queue Task
                                      ▼
                               ┌─────────────┐
                               │    Redis    │
                               │  (Broker)   │
                               └──────┬──────┘
                                      │
                                      │ Pick Task
                                      ▼
                               ┌──────────────┐      ┌─────────┐
                               │Celery Worker │─────►│ Ollama  │
                               └──────┬───────┘      └─────────┘
                                      │
                                      │ Publish Updates
                                      ▼
                               ┌─────────────┐
                               │    Redis    │
                               │  (Pub/Sub)  │
                               └──────┬──────┘
                                      │
                                      │ SSE Stream
                                      ▼
                               ┌─────────────┐
                               │ Flask Server│────► Browser
                               └─────────────┘
```

### Processing Flow

1. **Upload** - User uploads image via camera or file picker
2. **Queue** - Flask saves image and queues Celery task
3. **Process** - Celery worker sends image to Ollama (30-120 seconds)
4. **Extract** - Ollama extracts structured recipe data
5. **Update** - Worker publishes updates to Redis Pub/Sub
6. **Stream** - Flask forwards updates to browser via SSE
7. **Display** - Browser receives and displays recipe in real-time

**Why this architecture?**
- **No Polling**: Server-Sent Events provide real-time updates
- **Multi-Process**: Celery workers can run on separate machines
- **Scalable**: Redis Pub/Sub works across all Flask processes
- **Reliable**: Tasks are persisted in Redis queue

## 🧪 Project Structure

```
receipe-transcriber/
├── src/receipe_transcriber/
│   ├── __init__.py           # Flask app factory
│   ├── config.py             # Configuration
│   ├── models.py             # Database models
│   ├── routes/
│   │   └── main.py           # HTTP routes
│   ├── services/
│   │   └── ollama_service.py # Ollama integration
│   ├── tasks/
│   │   └── transcription_tasks.py  # Celery tasks
│   ├── templates/
│   │   ├── base.html         # Base template with HTMX
│   │   ├── index.html        # Main page
│   │   └── components/       # Reusable components
│   └── static/
│       ├── css/              # Tailwind CSS
│       └── js/
│           └── camera.js     # Camera handling
├── migrations/               # Database migrations
├── app.py                    # Flask entry point
├── celery_app.py            # Celery entry point
└── pyproject.toml           # Dependencies
```

## 🐛 Troubleshooting

### Database Errors

**Error:** `The current Flask app is not registered with this 'SQLAlchemy' instance`

```bash
# Initialize the database
export FLASK_APP=src.receipe_transcriber
flask db upgrade
```

### Redis Connection Issues

**Error:** `redis.exceptions.ConnectionError`

```bash
# Check if Redis is running
redis-cli ping  # Should return "PONG"

# If not, start Redis
redis-server
```

### Celery Not Processing Tasks

**Symptom:** Images upload but nothing happens

```bash
# Check Celery is running with correct app
celery -A celery_app.celery worker --loglevel=info

# Verify Redis connection
redis-cli ping
```

### Ollama Connection Errors

**Error:** `Connection refused` or `Ollama not found`

```bash
# Start Ollama
ollama serve

# Verify model is installed
ollama list  # Should show llava:latest

# Pull model if missing
ollama pull llava:latest
```

### Camera Not Working

**Issue:** Browser doesn't request camera permission

- Use **https://** or **localhost** (required for camera API)
- Check browser permissions (🔒 icon in address bar)
- Try a different browser (Chrome/Firefox recommended)

### SSE Not Updating

**Symptom:** Upload succeeds but no real-time updates appear

1. Check browser console for errors (F12)
2. Verify Redis is running: `redis-cli ping`
3. Check Flask logs for SSE connection messages
4. Ensure `REDIS_URL` is correct in .env

## 🔧 Configuration

Environment variables (`.env` file):

```bash
# Flask
FLASK_APP=src.receipe_transcriber
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=sqlite:///app.db

# Redis (for Celery & SSE)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llava:latest

# File Upload
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216  # 16MB
```

## 🧑‍💻 Development

### Database Migrations

```bash
# Create new migration
export FLASK_APP=src.receipe_transcriber
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade

# Rollback migration
flask db downgrade
```

### Running Tests

```bash
pytest tests/
```

### Tailwind CSS Development

```bash
# Watch mode (auto-rebuild on changes)
tailwindcss -i ./src/receipe_transcriber/static/css/input.css \
            -o ./src/receipe_transcriber/static/css/output.css --watch

# Production build (minified)
tailwindcss -i ./src/receipe_transcriber/static/css/input.css \
            -o ./src/receipe_transcriber/static/css/output.css --minify
```

## 📚 Additional Documentation

- **[.github/copilot-instructions.md](.github/copilot-instructions.md)** - Comprehensive development guide for GitHub Copilot
- **Database Schema** - See `src/receipe_transcriber/models.py`
- **API Routes** - See `src/receipe_transcriber/routes/main.py`

## 🤝 Contributing

This is a learning project demonstrating:
- Flask web application architecture
- Async task processing with Celery
- Real-time updates with Server-Sent Events
- AI integration with Ollama
- Modern frontend with HTMX

Feel free to explore, modify, and learn from the code!

##  Acknowledgments

- **Ollama** - Local LLM inference
- **HTMX** - HTML-first approach to modern web apps
- **Flask** - Web framework
- **Tailwind CSS** - Styling
- **Claude.ai** - UI design inspiration

4. **Tailwind CSS Watch** (in terminal 4, optional for development)
   ```bash
   # Download Tailwind CLI from https://github.com/tailwindlabs/tailwindcss/releases
   tailwindcss -i ./src/receipe_transcriber/static/css/input.css -o ./src/receipe_transcriber/static/css/output.css --watch
   ```

   Or build once for production:
   ```bash
   tailwindcss -i ./src/receipe_transcriber/static/css/input.css -o ./src/receipe_transcriber/static/css/output.css --minify
   ```

5. **Access the application**
   Open your browser to `http://localhost:5000`

## Usage

1. **Capture or Upload**: Use your device camera to take a photo of a recipe, or upload an existing image
2. **Processing**: The image is sent to Ollama for AI-powered transcription
3. **View Results**: The extracted recipe appears in real-time with ingredients, instructions, and metadata
4. **Stored**: All recipes are saved to the SQLite database for future reference

## Configuration

Key configuration options in `.env`:

- `OLLAMA_MODEL`: Vision model to use (default: `llava:latest`)
- `OLLAMA_BASE_URL`: Ollama API URL (default: `http://localhost:11434`)
- `CELERY_BROKER_URL`: Redis connection for Celery
- `DATABASE_URL`: SQLite database path

## Development

- Frontend uses HTMX for dynamic updates without full page reloads
- Server-Sent Events (SSE) via flask-sse for real-time status updates
- Vanilla JavaScript for camera access and file uploads
- Tailwind CSS for styling (Claude.ai-inspired design)
- Minimal JavaScript - HTMX loaded via local copy

## License

MIT

## How Does Cross-Process Communication Work?

Great question! Here's how the Celery worker (separate process) can update the browser in real-time:

### The Magic: Redis Pub/Sub + Server-Sent Events (SSE)

1. **Browser opens SSE connection** to Flask via HTMX SSE extension (e.g., `/stream?channel=job-123`)
2. **Celery worker** publishes HTML fragments to a Redis channel via flask-sse
3. **Flask server** is subscribed to that Redis channel via flask-sse
4. **Flask forwards** the message to the browser through the open SSE connection
5. **HTMX receives** the HTML and swaps it into the DOM

**No webhooks or polling needed!** Redis Pub/Sub acts as a message bus between processes.

### Why This Works

- **flask-sse** automatically handles Redis Pub/Sub subscriptions
- When you call `sse.publish(html, type='job-update', channel='job-123')` from Celery, it publishes to Redis
- Flask (with flask-sse) subscribes to these channels and forwards to connected browsers
- All communication is real-time using Server-Sent Events

```python
# In Celery worker (separate process)
from flask_sse import sse

html = render_template('components/recipe_card.html', recipe=recipe)
sse.publish(html, type='job-update', channel=f'job-{job_id}')

# Flask is listening on 'user-abc123' channel
# Automatically forwards to browser via SSE
```

For a deep dive, see [ARCHITECTURE.md](ARCHITECTURE.md).
