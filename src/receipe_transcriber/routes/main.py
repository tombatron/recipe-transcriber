import os
import uuid
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, current_app
from werkzeug.utils import secure_filename
from flask_sse import sse
from receipe_transcriber import db
from receipe_transcriber.models import TranscriptionJob, Recipe, Ingredient, Instruction
from receipe_transcriber.tasks.transcription_tasks import transcribe_recipe_task

bp = Blueprint('main', __name__)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@bp.route('/')
def index():
    """Main page with upload/camera interface."""
    from flask import url_for
    
    recent_recipes = current_app.db.session.query(Recipe).order_by(Recipe.created_at.desc()).limit(10).all()
    recipe_ids = [r.id for r in recent_recipes]
    job_map = {}
    if recipe_ids:
        jobs = (
            current_app.db.session.query(TranscriptionJob)
            .filter(TranscriptionJob.recipe_id.in_(recipe_ids))
            .order_by(TranscriptionJob.recipe_id, TranscriptionJob.completed_at.desc().nullslast(), TranscriptionJob.created_at.desc())
            .all()
        )
        for job in jobs:
            if job.recipe_id not in job_map:
                job_map[job.recipe_id] = job
    active_jobs = (
        current_app.db.session.query(TranscriptionJob)
        .filter(TranscriptionJob.status.in_(['pending', 'processing']))
        .order_by(TranscriptionJob.created_at.desc())
        .all()
    )
    
    # Generate URLs for templates
    urls = {
        'reprocess': url_for('main.reprocess_recipe', recipe_id=0, _external=False),
        'delete': url_for('main.delete_recipe', recipe_id=0, _external=False)
    }
    
    return render_template('index.html', recent_recipes=recent_recipes, active_jobs=active_jobs, job_map=job_map, urls=urls)


@bp.route('/jobs/<int:job_id>/status')
def job_status(job_id):
    """HTMX poll endpoint to refresh a job card (fallback to SSE)."""
    job = current_app.db.session.get(TranscriptionJob, job_id)
    if not job:
        return '', 404

    from flask import url_for
    urls = {
        'reprocess': url_for('main.reprocess_recipe', recipe_id=0, _external=False),
        'delete': url_for('main.delete_recipe', recipe_id=0, _external=False)
    }

    if job.status == 'failed':
        return render_template('components/job_error.html', job=job, error=job.error_message or 'An error occurred')

    if job.status == 'completed' and job.recipe_id:
        recipe = current_app.db.session.get(Recipe, job.recipe_id)
        if recipe:
            return render_template('components/recipe_card.html', recipe=recipe, job=job, urls=urls)

    # pending or processing fallback
    return render_template('components/job_processing.html', job=job, job_status_url=url_for('main.job_status', job_id=job.id))


@bp.route('/upload', methods=['POST'])
def upload_image():
    """Handle image upload(s) and start transcription. Returns pending job card(s)."""
    files = request.files.getlist('images')
    
    if not files or not any(f.filename for f in files):
        return '<div class="text-red-600">No files provided</div>', 400
    
    # Generate URLs with request context (once for all jobs)
    from flask import url_for
    urls = {
        'reprocess': url_for('main.reprocess_recipe', recipe_id=0, _external=False),
        'delete': url_for('main.delete_recipe', recipe_id=0, _external=False)
    }
    
    job_cards_html = []
    
    for file in files:
        if not file or not file.filename:
            continue
            
        if not allowed_file(file.filename):
            job_cards_html.append(f'<div class="text-red-600 p-4 bg-red-50 rounded-lg mb-4">Invalid file type: {file.filename}</div>')
            continue
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = Path(current_app.config['UPLOAD_FOLDER']) / unique_filename
        file.save(filepath)
        
        # Create transcription job
        job = TranscriptionJob(
            task_id=str(uuid.uuid4()),
            image_path=str(filepath),
            status='pending',
            last_status='Upload received. Queued for processing...'
        )
        current_app.db.session.add(job)
        current_app.db.session.commit()
        
        # Start Celery task with URLs
        transcribe_recipe_task.apply_async(
            args=[job.id, str(filepath), urls],
            task_id=job.task_id
        )
        
        # Render pending job card with SSE listener
        job_cards_html.append(render_template('components/job_status.html', job=job))
    
    if not job_cards_html:
        return '<div class="text-red-600">No valid files to process</div>', 400
    
    # Return all job cards (they'll be prepended to results area)
    return '\n'.join(job_cards_html)


@bp.route('/recipes/<int:recipe_id>/delete', methods=['DELETE'])
def delete_recipe(recipe_id):
    """Delete a recipe. HTMX will remove the element from DOM."""
    recipe = current_app.db.session.get(Recipe, recipe_id)
    if recipe:
        # Delete associated file if it exists
        if recipe.image_path and os.path.exists(recipe.image_path):
            os.remove(recipe.image_path)
        
        # Delete from database (cascades to ingredients and instructions)
        current_app.db.session.delete(recipe)
        current_app.db.session.commit()
        
        # Check if there are any recipes left
        remaining_count = current_app.db.session.query(Recipe).count()
        if remaining_count == 0:
            # Return placeholder with OOB swap to update entire results area
            return '''
            <div id="recipe-''' + str(recipe_id) + '''"></div>
            <div id="results-area" hx-swap-oob="true" class="space-y-6">
                <div id="empty-placeholder" class="bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                    <p class="text-gray-600">No recipes yet. Upload an image to get started!</p>
                </div>
            </div>
            ''', 200
    
    # Return empty response - HTMX will handle the swap
    return '', 200


@bp.route('/recipes/<int:recipe_id>/reprocess', methods=['POST'])
def reprocess_recipe(recipe_id):
    """Reprocess an existing recipe. Returns processing status."""
    recipe = current_app.db.session.get(Recipe, recipe_id)
    if not recipe or not recipe.image_path or not os.path.exists(recipe.image_path):
        return '<div class="text-red-600">Recipe not found</div>', 404
    
    # Create new transcription job
    job = TranscriptionJob(
        task_id=str(uuid.uuid4()),
        image_path=recipe.image_path,
        status='pending',
        last_status='Reprocessing requested. Queued for processing...'
    )
    current_app.db.session.add(job)
    current_app.db.session.commit()
    
    # Generate URLs with request context
    from flask import url_for
    urls = {
        'reprocess': url_for('main.reprocess_recipe', recipe_id=0, _external=False),
        'delete': url_for('main.delete_recipe', recipe_id=0, _external=False)
    }
    
    # Start Celery task - will update the original recipe
    transcribe_recipe_task.apply_async(
        args=[job.id, recipe.image_path, urls, recipe_id],
        task_id=job.task_id
    )
    
    # Return processing status with SSE listener (maintain recipe ID for stable DOM)
    return render_template('components/job_processing.html', job=job, recipe_id=recipe_id)


@bp.route('/recipes/<int:recipe_id>')
def recipe_detail(recipe_id):
    """View a single recipe."""
    recipe = current_app.db.session.get(Recipe, recipe_id)
    if not recipe:
        return "Recipe not found", 404
    
    return render_template('recipe_detail.html', recipe=recipe)
