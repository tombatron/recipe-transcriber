# Recipe Transcriber

A Flask web application that uses Ollama's vision models to transcribe recipes from images (printed or handwritten) into structured digital format. Features real-time updates and a clean, modern UI inspired by Claude.ai.

## ✨ Features

- 📷 **Camera Capture** - Take photos directly with your device camera
- 📤 **File Upload** - Upload existing recipe images (PNG, JPG, JPEG, WEBP)
- 🤖 **AI-Powered** - Uses Ollama vision models for accurate transcription
- ⚡ **Real-Time Updates** - See processing status updates live via Turbo Streams over WebSocket
- 💾 **Structured Data** - Extracts ingredients, instructions, prep/cook times
- 🎨 **Modern UI** - Clean interface built with Hotwire Turbo and Tailwind CSS

## 🏗️ Tech Stack

- **Backend**: Flask, SQLAlchemy, Flask-Migrate
- **AI/ML**: Ollama (local LLM with vision capabilities)
- **Task Queue**: Celery with Redis broker
- **Real-Time Updates**: Turbo-Flask with WebSocket-based Turbo Streams
- **Frontend**: Hotwire Turbo (Turbo Drive, Turbo Frames, Turbo Streams)
- **Styling**: Tailwind CSS
- **Database**: SQLite

## 🎯 Quick Start

### Prerequisites

Before you begin, ensure you have:
- Python 3.10+
- Redis (`sudo apt install redis` or `brew install redis`)
- Ollama (https://ollama.ai)
- Node.js 18+ and npm (for building Tailwind CSS locally)

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

5. **Install frontend dependencies (Tailwind CLI)**
   ```bash
   npm install
   ```
   This installs the local Tailwind CLI used to build `static/css/output.css`.

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

Open 4 terminals and run:

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Ollama
ollama serve

# Terminal 3: Celery Worker
celery -A celery_app.celery worker --loglevel=info

# Terminal 4: Flask
./run_dev.sh
```

**Option 3: Build Tailwind CSS (Required for Development)**

In a separate terminal, watch for CSS changes and auto-rebuild:

```bash
npx tailwindcss -i ./src/receipe_transcriber/static/css/input.css \
                -o ./src/receipe_transcriber/static/css/output.css --watch
```

> **Important**: Tailwind CSS must be compiled before the app will display properly. The app loads from the built CSS file (not CDN). After installing or modifying `input.css`, rebuild using the command above.
>
> If you've already modified CSS and don't see changes:
> - Make sure the Tailwind watch process is running
> - Check that `output.css` was updated (check file timestamp)
> - Refresh your browser (hard refresh: Ctrl+Shift+R)

### Access the App

Open your browser to: **http://localhost:5000**

## 📖 How It Works

### Architecture Overview

The application uses multiple processes coordinated via Redis and webhooks:

```
┌─────────┐                    ┌─────────────┐
│ Browser │ ◄─Turbo WebSocket──│ Flask Server│
└─────────┘                    └──────▲──────┘
                                      │
                                      │ HTTP Webhooks
                                      │ (status updates)
                               ┌──────┴───────┐      ┌─────────┐
                               │Celery Worker │─────►│ Ollama  │
                               └──────▲───────┘      └─────────┘
                                      │
                                      │ Pick Task
                                      │
                               ┌──────┴──────┐
                               │    Redis    │
                               │  (Broker)   │
                               └──────▲──────┘
                                      │
                                      │ Queue Task
                                      │
                               ┌──────┴──────┐
                               │Flask Server │
                               └─────────────┘
```

### Processing Flow

1. **Upload** - User uploads image via camera or file picker
2. **Queue** - Flask saves image and queues Celery task with webhook URLs
3. **Process** - Celery worker sends image to Ollama (30-120 seconds)
4. **Extract** - Ollama extracts structured recipe data
5. **Webhook** - Worker sends HTTP POST to Flask webhook routes
6. **Stream** - Flask routes receive webhook and push Turbo Streams via WebSocket
7. **Display** - Browser receives and displays recipe in real-time

**Why this architecture?**
- **No Polling**: WebSocket-based Turbo Streams provide instant updates
- **Multi-Process**: Celery workers can run on separate machines (webhooks work across hosts)
- **Decoupled**: Celery doesn't need direct access to Flask internals, just HTTP endpoints
- **Scalable**: Redis coordinates Celery tasks; turbo-flask handles WebSocket connections
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
│   │   ├── base.html         # Base template with Turbo
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

### Turbo Streams Not Updating

**Symptom:** Upload succeeds but no real-time updates appear

1. Check browser console for errors (F12)
2. Verify Redis is running: `redis-cli ping`
3. Check Flask logs for WebSocket connection messages
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

# Redis (for Celery & Turbo WebSocket)
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

### Tailwind CSS Compilation

**Development (Watch Mode)**

Automatically rebuild CSS when you make changes:

```bash
npx tailwindcss -i ./src/receipe_transcriber/static/css/input.css \
                -o ./src/receipe_transcriber/static/css/output.css --watch
```

Run this in a separate terminal while developing. The watch process will:
- Monitor your HTML templates for Tailwind class usage
- Recompile `output.css` whenever you change files
- Output will show in the terminal when rebuilds happen

**Production Build (Minified)**

For production deployment, create a minified build:

```bash
npx tailwindcss -i ./src/receipe_transcriber/static/css/input.css \
                -o ./src/receipe_transcriber/static/css/output.css --minify
```

**Troubleshooting Tailwind Issues**

If styles aren't appearing:
1. Verify `output.css` exists and was recently updated
2. Check that the Tailwind watch process is running
3. Hard refresh your browser: `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
4. Check for errors in the Tailwind CLI terminal output
5. Ensure class names in HTML match Tailwind conventions (no typos)

## 📚 Additional Documentation

- **[.github/copilot-instructions.md](.github/copilot-instructions.md)** - Comprehensive development guide for GitHub Copilot
- **Database Schema** - See `src/receipe_transcriber/models.py`
- **API Routes** - See `src/receipe_transcriber/routes/main.py`

## 🤝 Contributing

This is a learning project demonstrating:
- Flask web application architecture
- Async task processing with Celery
- Real-time updates with Turbo Streams over WebSocket
- AI integration with Ollama
- Modern frontend with Hotwire Turbo

Feel free to explore, modify, and learn from the code!

##  Acknowledgments

- **Ollama** - Local LLM inference
- **Hotwire Turbo** - Modern, server-rendered HTML-over-the-wire framework
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

- Frontend uses Turbo Drive for dynamic page updates without full page reloads
- Turbo Frames for decomposed, independent page sections
- Turbo Streams over WebSocket via turbo-flask for real-time status updates
- Vanilla JavaScript for camera access
- Tailwind CSS for styling (Claude.ai-inspired design)
- Minimal JavaScript - Turbo handles all UI interactions

## License

MIT

## How Does Cross-Process Communication Work?

Great question! Here's how the Celery worker (separate process) can update the browser in real-time:

### The Magic: Webhooks + Redis-backed WebSocket + Turbo Streams

1. **Browser opens WebSocket connection** to Flask via Turbo (automatically established by `{{ turbo() }}`)
2. **Flask queues Celery task** with webhook URLs (status update and completion endpoints)
3. **Celery worker processes** the recipe transcription
4. **Celery makes HTTP POST requests** (webhooks) to Flask routes with status updates
5. **Flask webhook routes** receive the data and call `turbo.push()` to send Turbo Streams
6. **turbo-flask** uses Redis to coordinate streams between Flask processes
7. **Flask forwards** the Turbo Stream to the browser through the WebSocket
8. **Turbo** receives the stream and applies DOM updates (append, replace, update, remove)

**No polling needed!** Webhooks provide loose coupling and Redis-backed WebSocket provides real-time delivery.

### Why This Works

- **Webhooks**: Celery tasks make standard HTTP requests to Flask routes, enabling complete decoupling
- **Turbo Streams**: Flask routes use `turbo.push()` to broadcast updates to connected browsers
- **Redis Coordination**: turbo-flask uses Redis to sync WebSocket messages across multiple Flask processes
- **Real-time**: WebSocket connection provides instant delivery with automatic reconnection

```python
# In Celery worker (separate process)
import requests

# POST to Flask webhook route
requests.post(status_update_hook, data={
    'external_recipe_id': recipe_id,
    'status': 'processing',
    'message': 'Starting transcription...'
})

# Flask route receives webhook and pushes Turbo Stream
@bp.route('/webhooks/status-update', methods=['POST'])
def status_update():
    external_recipe_id = request.form.get('external_recipe_id')
    message = request.form.get('message')
    
    html = render_template('components/job_status.html', 
                         external_recipe_id=external_recipe_id,
                         message=message)
    
    turbo.push(turbo.update(html, target=f'recipe-{external_recipe_id}'))
    
    return '', 204
```

For a deep dive, see [ARCHITECTURE.md](ARCHITECTURE.md).
