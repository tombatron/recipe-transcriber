# GitHub Copilot Instructions - Recipe Transcriber

## Project Overview
Python Flask web application for transcribing recipes from images using Ollama (local LLM). Users can capture photos via device camera or upload existing images. The app uses **HTMX for dynamic UI updates** and **Server-Sent Events (SSE) for real-time status updates** from Celery tasks. Tailwind CSS provides styling.

Visual design inspired by Claude.ai's clean, modern aesthetic with focus on simplicity and usability.

## Tech Stack
- **Backend Framework**: Flask
- **AI/ML**: Ollama (local LLM for vision and text processing)
- **Task Queue**: Celery with Redis broker
- **Frontend**: HTMX + Server-Sent Events (SSE)
- **SSE Library**: flask-sse (uses Redis for pub/sub)
- **Styling**: Tailwind CSS
- **Database**: SQLite with SQLAlchemy ORM
- **Template Engine**: Jinja2

## Architecture Guidelines

### Project Structure
```
receipe-transcriber/
├── pyproject.toml           # Poetry dependencies and project config
├── README.md
├── src/
│   └── receipe_transcriber/
│       ├── __init__.py      # Flask app factory
│       ├── models.py        # SQLAlchemy models
│       ├── config.py        # Configuration management
│       ├── routes/          # Blueprint routes
│       │   ├── __init__.py
│       │   └── main.py
│       ├── templates/       # Jinja2 templates
│       │   ├── base.html    # Base template with HTMX
│       │   ├── components/  # Reusable component templates
│       │   └── layouts/
│       ├── static/
│       │   ├── css/
│       │   │   ├── input.css     # Tailwind input
│       │   │   └── output.css    # Compiled Tailwind
│       │   └── js/
│       │       └── camera.js     # Camera handling (vanilla JS)
│       ├── services/            # Business logic services
│       │   ├── __init__.py
│       │   └── ollama_service.py  # Ollama integration
│       ├── tasks/              # Celery task definitions
│       │   ├── __init__.py
│       │   └── transcription_tasks.py
│       └── utils/           # Helper functions
├── migrations/              # Database migrations (Flask-Migrate)
├── tests/
└── tailwind.config.js       # Tailwind configuration
```

### Flask Application Patterns

#### App Factory Pattern
- Use `create_app()` factory function in `src/receipe_transcriber/__init__.py`
- Register blueprints for route organization
- Initialize extensions (SQLAlchemy, Flask-Migrate, Celery, SSE) within factory
- Configure Celery instance with Flask app context
- Initialize flask-sse with Redis connection

#### Database Models
- Use SQLAlchemy ORM for all database interactions
- Define models in `src/receipe_transcriber/models.py`
- Include `created_at` and `updated_at` timestamps on all models
- Use proper relationships (one-to-many, many-to-many) with backrefs
- Track task states for async operations (pending, processing, completed, failed)

#### Task State Management
- Store Celery task IDs in database for tracking
- `TranscriptionJob` model tracks:
  - Task ID (Celery task UUID)
  - Status (pending, processing, completed, failed)
  - Input (uploaded image reference)
  - Result (extracted recipe data)
  - Error messages if failed
  - Timestamps (created, started, completed)

### HTMX Integration

#### Core Concepts
- HTMX allows HTML to make HTTP requests from any element
- Server responds with HTML fragments that replace/update parts of the page
- No need for complex JavaScript frameworks
- Progressive enhancement - works without JS

#### Basic HTMX Attributes
```html
<!-- Simple form that swaps response into target -->
<form hx-post="/upload" 
      hx-target="#results-area" 
      hx-swap="innerHTML"
      hx-encoding="multipart/form-data">
  <input type="file" name="image">
  <button type="submit">Upload</button>
</form>

<!-- Link that replaces itself -->
<button hx-delete="/recipes/42" 
        hx-target="closest .recipe-card"
        hx-swap="outerHTML"
        hx-confirm="Are you sure?">
  Delete
</button>

<!-- Poll for updates -->
<div hx-get="/job-status/42" 
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  Processing...
</div>
```

#### HTMX Swap Strategies
- `innerHTML` - Replace inner content of target
- `outerHTML` - Replace target element entirely
- `beforebegin` - Insert before target
- `afterbegin` - Insert at start of target (prepend)
- `beforeend` - Insert at end of target (append)
- `afterend` - Insert after target
- `delete` - Remove target element
- `none` - Don't swap, just trigger events

#### HTMX Events
```javascript
// Listen for HTMX events
document.body.addEventListener('htmx:afterSwap', (event) => {
  console.log('Content swapped:', event.detail.target)
})

// Trigger custom behavior on success
document.body.addEventListener('htmx:afterRequest', (event) => {
  if (event.detail.successful) {
    // Show success message
  }
})
```

### Server-Sent Events (SSE) Integration

#### SSE Concepts
- One-way server-to-client communication
- Client opens long-lived HTTP connection
- Server pushes updates as they occur
- Automatic reconnection on disconnect
- Perfect for real-time status updates

#### Flask-SSE Setup
```python
from flask import Flask
from flask_sse import sse

app = Flask(__name__)
app.config['REDIS_URL'] = 'redis://localhost:6379/0'
app.register_blueprint(sse, url_prefix='/stream')
```

#### Publishing Events from Python
```python
from flask_sse import sse

# In Celery task or webhook
sse.publish(
    {
        "status": "processing",
        "job_id": 42,
        "message": "Processing recipe..."
    },
    type='job-update',
    channel='job-42'
)

# Multiple clients can subscribe to same channel
sse.publish(
    {"recipe_id": 123, "html": "<div>...</div>"},
    type='recipe-complete',
    channel='recipes'
)
```

#### Consuming SSE in Frontend
```html
<!-- Using htmx-sse extension -->
<div hx-ext="sse" 
     sse-connect="/stream?channel=job-42"
     sse-swap="job-update">
  <div>Waiting for updates...</div>
</div>

<!-- Or vanilla JavaScript -->
<script>
const eventSource = new EventSource('/stream?channel=job-42')

eventSource.addEventListener('job-update', (event) => {
  const data = JSON.parse(event.data)
  // Update UI based on data
  document.getElementById('status').innerHTML = data.message
})

eventSource.addEventListener('error', (error) => {
  console.error('SSE error:', error)
  eventSource.close()
})
</script>
```

### HTMX + SSE Workflow Pattern

#### Upload and Process Recipe
```html
<!-- 1. Upload form -->
<form hx-post="/upload" 
      hx-target="#results-area" 
      hx-swap="afterbegin"
      hx-encoding="multipart/form-data">
  <input type="file" name="image" accept="image/*">
  <button type="submit">Upload</button>
</form>

<!-- 2. Results container -->
<div id="results-area"></div>
```

Server responds with:
```html
<!-- 3. Pending job card with SSE listener -->
<div id="job-42" 
     class="recipe-card"
     hx-ext="sse"
     sse-connect="/stream?channel=job-42"
     sse-swap="job-update"
     hx-swap="outerHTML">
  <p>Processing...</p>
</div>
```

Celery task publishes updates:
```python
# 4. Task starts
sse.publish(
    {"html": render_template('components/job_processing.html', job_id=42)},
    type='job-update',
    channel='job-42'
)

# 5. Task completes
sse.publish(
    {"html": render_template('components/recipe_card.html', recipe=recipe)},
    type='job-update',
    channel='job-42'
)
```

### Route Patterns

#### Simple Action Routes
```python
@bp.route('/upload', methods=['POST'])
def upload_image():
    file = request.files.get('image')
    
    if file and allowed_file(file.filename):
        # Save file, create job, start Celery task
        job = create_job(file)
        
        # Return HTML fragment with SSE listener
        return render_template('components/job_pending.html', job=job)
    
    return '<div class="error">Invalid file</div>', 400


@bp.route('/recipes/<int:recipe_id>/delete', methods=['DELETE'])
def delete_recipe(recipe_id):
    recipe = db.session.get(Recipe, recipe_id)
    if recipe:
        db.session.delete(recipe)
        db.session.commit()
    
    # Return empty response - HTMX will delete the element
    return '', 200


@bp.route('/recipes/<int:recipe_id>/reprocess', methods=['POST'])
def reprocess_recipe(recipe_id):
    recipe = db.session.get(Recipe, recipe_id)
    if recipe:
        job = create_reprocess_job(recipe)
        # Return processing status with SSE
        return render_template('components/job_processing.html', job=job)
    
    return '<div class="error">Recipe not found</div>', 404
```

#### SSE Endpoint
```python
from flask_sse import sse

# SSE blueprint is registered at /stream
# Clients connect to /stream?channel=<channel-name>

# No additional routes needed - flask-sse handles it
# Just publish to channels from your code
```

### Celery Task Queue

#### Celery Configuration
- Configure Celery in `src/receipe_transcriber/__init__.py`
- Use Redis as message broker and result backend
- Redis also used for SSE pub/sub
- Configure task serialization (JSON recommended)

#### Task Pattern with SSE
```python
from flask_sse import sse
from flask import render_template

@celery.task(bind=True)
def transcribe_recipe(self, job_id, image_path):
    """
    Transcribe recipe from image using Ollama.
    Pushes updates via SSE throughout processing.
    """
    try:
        # Update status to processing
        with app.app_context():
            job = db.session.get(TranscriptionJob, job_id)
            job.status = 'processing'
            db.session.commit()
            
            html = render_template('components/job_processing.html', job=job)
            sse.publish({'html': html}, type='job-update', channel=f'job-{job_id}')
        
        # Call Ollama service
        result = ollama_service.transcribe(image_path)
        
        # Push completed result
        with app.app_context():
            recipe = create_recipe(result)
            html = render_template('components/recipe_card.html', recipe=recipe)
            sse.publish({'html': html}, type='job-update', channel=f'job-{job_id}')
        
        return result
    except Exception as e:
        # Push error
        with app.app_context():
            html = render_template('components/job_error.html', error=str(e))
            sse.publish({'html': html}, type='job-update', channel=f'job-{job_id}')
        raise
```

### Camera Handling (Vanilla JavaScript)

#### Simple Camera Module
```javascript
// static/js/camera.js
class Camera {
  constructor() {
    this.stream = null
  }

  async start(videoElement) {
    this.stream = await navigator.mediaDevices.getUserMedia({ 
      video: { facingMode: 'environment' } 
    })
    videoElement.srcObject = this.stream
  }

  capture(videoElement, canvasElement) {
    const ctx = canvasElement.getContext('2d')
    canvasElement.width = videoElement.videoWidth
    canvasElement.height = videoElement.videoHeight
    ctx.drawImage(videoElement, 0, 0)
    
    return new Promise((resolve) => {
      canvasElement.toBlob(resolve, 'image/jpeg', 0.9)
    })
  }

  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop())
      this.stream = null
    }
  }
}

// Usage in HTML
const camera = new Camera()
document.getElementById('start-camera').addEventListener('click', () => {
  camera.start(document.getElementById('video'))
})
```

### Tailwind CSS Guidelines

#### Design Philosophy: Claude.ai-Inspired
- Clean, minimalist interface with plenty of whitespace
- Warm, inviting color palette (soft oranges/coppers as accents)
- Smooth, subtle animations and transitions
- Focus on content and functionality over decoration
- Professional yet approachable aesthetic

#### Color Palette
```javascript
// tailwind.config.js
theme: {
  extend: {
    colors: {
      'claude-orange': '#D97706',
      'claude-bg': '#F5F5F4',
    }
  }
}
```

#### Component Styling Patterns

**Card/Panel:**
```html
<div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
  <!-- Content -->
</div>
```

**Primary Button:**
```html
<button class="bg-amber-600 hover:bg-amber-700 text-white font-semibold px-6 py-3 rounded-xl transition-colors shadow-sm hover:shadow-md">
  Upload
</button>
```

**Loading State:**
```html
<div class="flex items-center space-x-4">
  <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600"></div>
  <p>Processing...</p>
</div>
```

### Template Guidelines

#### Base Template with HTMX
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Recipe Transcriber{% endblock %}</title>
  <link href="{{ url_for('static', filename='css/output.css') }}" rel="stylesheet">
  
  <!-- HTMX Core -->
  <script src="https://unpkg.com/htmx.org@1.9.10"></script>
  
  <!-- HTMX SSE Extension -->
  <script src="https://unpkg.com/htmx.org@1.9.10/dist/ext/sse.js"></script>
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
```

#### Component Templates
- Create partial templates for reusable components
- Store in `templates/components/`
- Each component should be self-contained HTML

### Dependencies (pyproject.toml)
Essential packages:
- flask
- flask-sqlalchemy
- flask-migrate
- flask-sse
- python-dotenv
- celery[redis]
- redis
- ollama (Python client for Ollama)
- pillow (image processing)
- requests

### Running the Application

#### Development Services
```bash
# 1. Start Redis (required for Celery and SSE)
redis-server

# 2. Start Flask app
flask run

# 3. Start Celery worker
celery -A celery_app.celery worker --loglevel=info

# 4. Build Tailwind CSS (watch mode)
tailwindcss -i ./src/receipe_transcriber/static/css/input.css -o ./src/receipe_transcriber/static/css/output.css --watch

# 5. Ensure Ollama is running
ollama run llava
```

## Key Differences from Turbo/Stimulus

### Before (Turbo + Stimulus)
- Required WebSocket connection
- Complex client state management
- Multiple JavaScript controllers
- Turbo Frames and Streams concepts
- Import maps and ES modules

### After (HTMX + SSE)
- Simple HTTP requests from HTML attributes
- Server handles all state
- Minimal JavaScript (only for camera)
- SSE for real-time updates
- Single CDN script tag

### Migration Benefits
- **Simpler**: HTML-first approach, less JavaScript
- **More Reliable**: No WebSocket multi-process issues
- **Easier Debugging**: Just HTTP requests visible in DevTools
- **Better DX**: Write HTML, not JavaScript controllers
- **Progressive Enhancement**: Works without JavaScript (except camera)

## Best Practices

### HTMX
1. Use semantic HTML attributes
2. Keep responses focused (return just what needs to update)
3. Use appropriate swap strategies
4. Leverage HTMX events for custom behavior
5. Test with network throttling to see loading states

### SSE
1. Use specific channels per job/user
2. Close connections when done
3. Handle reconnection gracefully
4. Send complete HTML in messages (easier to swap)
5. Use typed events (type='job-update') for clarity

### General
1. Return HTML fragments, not JSON
2. Server renders everything
3. Minimal client-side JavaScript
4. Progressive enhancement first
5. Use HTMX for interactions, SSE for real-time updates
