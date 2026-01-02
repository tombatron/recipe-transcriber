# GitHub Copilot Instructions - Recipe Transcriber

## Project Overview
Python Flask web application for transcribing recipes from images using Ollama (local LLM). Users can capture photos via device camera or upload existing images. The app uses **Hotwire Turbo for dynamic UI updates** and **Turbo Streams over WebSocket** for real-time status updates from Celery tasks. Tailwind CSS provides styling.

Visual design inspired by Claude.ai's clean, modern aesthetic with focus on simplicity and usability.

## Tech Stack
- **Backend Framework**: Flask
- **AI/ML**: Ollama (local LLM for vision and text processing)
- **Task Queue**: Celery with Redis broker
- **Frontend**: Hotwire Turbo (Turbo Drive, Turbo Frames, Turbo Streams)
- **Real-time Updates**: Turbo-Flask library (WebSocket-based Turbo Streams)
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
│       │   ├── base.html    # Base template with Turbo
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
- Initialize extensions (SQLAlchemy, Flask-Migrate, Celery, Turbo) within factory
- Configure Celery instance with Flask app context
- Initialize Turbo-Flask for WebSocket-based Turbo Streams

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

### Hotwire Turbo Integration

#### Core Concepts
Turbo is a collection of JavaScript libraries that enable modern, fast web applications using server-rendered HTML:

1. **Turbo Drive** - Intercepts link clicks and form submissions, replacing only the `<body>` content without full page reloads
2. **Turbo Frames** - Decompose pages into independent contexts that can be lazy-loaded and updated independently
3. **Turbo Streams** - Deliver page changes as a stream of updates over WebSocket, SSE, or in response to form submissions

#### Turbo Drive
Automatically accelerates links and form submissions by fetching and swapping only the body content:

```html
<!-- Automatic - no attributes needed -->
<a href="/recipes">View Recipes</a>

<!-- Disable for specific links -->
<a href="/download.pdf" data-turbo="false">Download PDF</a>
```

#### Turbo Frames
Decompose pages into independent contexts:

```html
<!-- Frame definition -->
<turbo-frame id="results-area">
  <div>Initial content</div>
</turbo-frame>

<!-- Clicking this link loads content into the frame -->
<turbo-frame id="results-area">
  <a href="/recipes">Load Recipes</a>
</turbo-frame>

<!-- Lazy loading -->
<turbo-frame id="recipe-123" src="/recipes/123">
  <p>Loading...</p>
</turbo-frame>

<!-- Form submission scoped to frame -->
<turbo-frame id="upload-form">
  <form action="/upload" method="post">
    <input type="file" name="image">
    <button>Upload</button>
  </form>
</turbo-frame>
```

**Frame Rules:**
- Responses must contain matching `<turbo-frame id="...">` 
- Content within matching frame replaces the existing frame
- Links and forms within frames target their own frame by default
- Use `data-turbo-frame="_top"` to break out and replace entire page

#### Turbo Streams
Enable multiplexed page updates over WebSocket or in response to form submissions:

**Stream Actions:**
- `append` - Add content to end of target
- `prepend` - Add content to start of target
- `replace` - Replace entire target element
- `update` - Replace content inside target
- `remove` - Delete target element
- `before` - Insert content before target
- `after` - Insert content after target

**WebSocket Streams (Real-time Updates):**

Python (Backend):
```python
from turbo_flask import Turbo

# Initialize in app factory
turbo = Turbo()
turbo.init_app(app)

# In Celery task or route
turbo.push(turbo.append(
    rendered_template,
    target="results-area"
))

# Multiple actions
turbo.push([
    turbo.update(status_html, target="status-123"),
    turbo.replace(recipe_html, target="recipe-123")
])
```

HTML (Frontend):
```html
<!-- Include Turbo helper in base template -->
{{ turbo() }}

<!-- Elements with IDs can be targeted -->
<div id="results-area">
  <!-- Updates appear here -->
</div>

<turbo-frame id="recipe-123">
  <!-- Frame can be replaced entirely -->
</turbo-frame>
```

**Form Response Streams:**

```python
@app.route('/upload', methods=['POST'])
def upload():
    # Process upload
    job = create_job(file)
    
    # Return Turbo Stream response
    return turbo.stream([
        turbo.append(
            render_template('components/job_processing.html', job=job),
            target="results-area"
        )
    ])
```

### Turbo Workflow Pattern

#### Upload and Process Recipe

**Template Structure:**
```html
<!-- index.html -->
<form action="/upload" method="post" enctype="multipart/form-data">
  <input type="file" name="images" multiple>
  <button type="submit">Upload</button>
</form>

<turbo-frame id="results-area" src="/recipes">
  Loading recipes...
</turbo-frame>
```

**Route Handler:**
```python
@bp.route('/upload', methods=['POST'])
def upload_image():
    files = request.files.getlist('images')
    
    for file in files:
        if file and allowed_file(file.filename):
            # Save file, create job, queue task
            job = create_job(file)
            transcribe_recipe_task.delay(job.id)
    
    # Redirect back to index - Turbo will handle smoothly
    return redirect(url_for('main.index'))
```

**Celery Task with Turbo Streams:**
```python
@celery.task(bind=True)
def transcribe_recipe_task(self, job_id):
    """
    Transcribe recipe and push updates via Turbo Streams.
    """
    with app.app_context():
        job = db.session.get(TranscriptionJob, job_id)
        
        # Push processing status
        turbo.push(turbo.update(
            render_template('components/job_processing.html',
                          external_recipe_id=job.external_recipe_id),
            target=f"recipe-{job.external_recipe_id}"
        ))
        
        # Call Ollama service
        result = ollama_service.transcribe(job.image_path)
        
        # Save recipe
        recipe = create_recipe(result, job)
        
        # Push completed recipe
        turbo.push(turbo.replace(
            render_template('components/recipe_card.html', 
                          recipe=recipe, job=job),
            target=f"recipe-{job.external_recipe_id}"
        ))
```

**Component Template:**
```html
<!-- components/job_processing.html -->
<turbo-frame id="recipe-{{ external_recipe_id }}" 
             class="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
  <div class="flex items-center space-x-4">
    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600"></div>
    <div>
      <p class="text-lg font-semibold text-gray-900">Processing your recipe...</p>
    </div>
  </div>
</turbo-frame>
```

```html
<!-- components/recipe_card.html -->
<turbo-frame id="recipe-{{ recipe.external_recipe_id }}" 
             class="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
  <h2>{{ recipe.title }}</h2>
  <!-- Recipe details -->
</turbo-frame>
```

### Route Patterns

#### Action Routes with Turbo
```python
@bp.route('/upload', methods=['POST'])
def upload_image():
    files = request.files.getlist('images')
    
    for file in files:
        if file and allowed_file(file.filename):
            # Save file, create job, start Celery task
            job = create_job(file)
            transcribe_recipe_task.delay(job.id)
    
    # Redirect - Turbo handles this smoothly
    return redirect(url_for('main.index'))


@bp.route('/recipes/<int:recipe_id>/delete', methods=['DELETE'])
def delete_recipe(recipe_id):
    recipe = db.session.get(Recipe, recipe_id)
    if recipe:
        db.session.delete(recipe)
        db.session.commit()
        
        # Use Turbo Stream to remove element
        return turbo.stream(
            turbo.remove(target=f"recipe-{recipe.external_recipe_id}")
        )
    
    return '', 404


@bp.route('/recipes')
def recipes():
    """Return all recipes as turbo frame."""
    recipes = Recipe.query.order_by(Recipe.created_at.desc()).limit(5).all()
    jobs = TranscriptionJob.query.filter_by(
        status='processing'
    ).order_by(TranscriptionJob.created_at.desc()).all()
    
    return render_template('components/recent_recipes.html', 
                         recipes=recipes, jobs=jobs)
```

### Celery Task Queue

#### Celery Configuration
- Configure Celery in `src/receipe_transcriber/__init__.py`
- Use Redis as message broker and result backend
- Configure task serialization (JSON recommended)

#### Task Pattern with Turbo Streams
```python
from turbo_flask import Turbo
from flask import render_template

@celery.task(bind=True)
def transcribe_recipe(self, job_id):
    """
    Transcribe recipe from image using Ollama.
    Pushes updates via Turbo Streams throughout processing.
    """
    try:
        # Update status to processing
        with app.app_context():
            job = db.session.get(TranscriptionJob, job_id)
            job.status = 'processing'
            job.started_at = datetime.utcnow()
            db.session.commit()
            
            # Push processing status via Turbo Stream
            turbo.push(turbo.update(
                render_template('components/job_processing.html',
                              external_recipe_id=job.external_recipe_id),
                target=f"recipe-{job.external_recipe_id}"
            ))
        
        # Call Ollama service
        result = ollama_service.transcribe(image_path)
        
        # Save recipe and push completed result
        with app.app_context():
            recipe = create_recipe(result, job)
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            db.session.commit()
            
            # Push completed recipe card via Turbo Stream
            turbo.push(turbo.replace(
                render_template('components/recipe_card.html', 
                              recipe=recipe, job=job),
                target=f"recipe-{job.external_recipe_id}"
            ))
        
        return result
    except Exception as e:
        # Push error
        with app.app_context():
            job.status = 'failed'
            job.error_message = str(e)
            db.session.commit()
            
            turbo.push(turbo.update(
                render_template('components/job_error.html',
                              external_recipe_id=job.external_recipe_id,
                              error=str(e)),
                target=f"recipe-{job.external_recipe_id}"
            ))
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

#### Base Template with Turbo
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Recipe Transcriber{% endblock %}</title>
  <link href="{{ url_for('static', filename='css/output.css') }}" rel="stylesheet">
  
  <!-- Turbo-Flask helper - includes Turbo and WebSocket connection -->
  {{ turbo() }}
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
- turbo-flask (WebSocket-based Turbo Streams)
- python-dotenv
- celery[redis]
- redis
- ollama (Python client for Ollama)
- pillow (image processing)
- requests

### Running the Application

#### Development Services
```bash
# 1. Start Redis (required for Celery and Turbo WebSocket)
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

## Key Features of Turbo Implementation

### Advantages of Turbo
- **WebSocket-based**: Real-time bidirectional communication for instant updates
- **No Polling**: Server pushes updates as they happen, no client polling needed
- **Server-rendered**: All HTML generated on server, minimal client-side JavaScript
- **Progressive Enhancement**: Works smoothly with standard form submissions
- **Frames and Streams**: Modular page updates with independent frame contexts

### Implementation Benefits
- **Simpler Backend**: Single library (turbo-flask) handles both interactions and real-time updates
- **Reliable**: WebSocket connection managed by Turbo library with auto-reconnect
- **Easier Debugging**: Turbo Dev Tools show frame boundaries and stream messages
- **Better UX**: Smooth page transitions and instant updates without flicker
- **Type Safety**: Python methods for creating streams (turbo.append, turbo.replace, etc.)

## Best Practices

### Turbo Frames
1. Use semantic, unique IDs for frames
2. Keep frame responses focused (return just the frame content)
3. Use lazy loading (src attribute) for non-critical content
4. Break out of frames when needed with `data-turbo-frame="_top"`
5. Test frame boundaries to ensure correct scope

### Turbo Streams
1. Target specific elements with unique IDs
2. Use appropriate stream actions (append, replace, update, remove)
3. Keep stream payloads small (send HTML fragments, not full pages)
4. Handle errors gracefully in tasks before pushing streams
5. Use turbo.push() for WebSocket streams from background tasks

### General
1. Return HTML fragments from routes, not JSON
2. Server renders everything - no client-side templating
3. Minimal client-side JavaScript (only for camera)
4. Progressive enhancement - forms work without JS
5. Use Turbo for interactions and real-time updates together
