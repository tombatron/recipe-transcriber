import os
import uuid
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, current_app, session, Response
from werkzeug.utils import secure_filename
from flask import url_for
from receipe_transcriber import db
from receipe_transcriber.models import TranscriptionJob, Recipe, Ingredient, Instruction
from receipe_transcriber.tasks.transcription_tasks import transcribe_recipe_task
from .. import turbo

bp = Blueprint('main', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@bp.route('/')
def index():
    """Main page with upload/camera interface."""   

    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        
    return render_template('index.html')

@bp.route('/recipes')
def recipes():
    recent_recipes = current_app.db.session.query(Recipe).order_by(Recipe.created_at.desc()).limit(10).all()
    
    return render_template('components/recent_recipes.html', recent_recipes=recent_recipes)

# TODO: Move to the webhooks blueprint.
@bp.route('/jobs/<int:job_id>/status')
def job_status(job_id):
    """HTMX poll endpoint to refresh a job card (fallback to SSE)."""
    job = current_app.db.session.get(TranscriptionJob, job_id)
    if not job:
        return '', 404

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
    
    # Ensure session has a session_id
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']

    processed_files = 0

    turbo_operations = []
    
    for file in files:
        if not file or not file.filename:
            continue
            
        if not allowed_file(file.filename):
            turbo.push(turbo.prepend(render_template('components/invalid_file_type.html', filename=file.filename), target='results-area'))
            continue
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = Path(current_app.config['UPLOAD_FOLDER']) / unique_filename
        file.save(filepath)
        
        # Create transcription job with session_id
        job = TranscriptionJob(
            job_id=str(uuid.uuid1()),
            session_id=session_id,
            image_path=str(filepath),
            status='pending',
            last_status='Upload received. Queued for processing...'
        )

        # TODO: Fix how we're interacting with the DB here. 
        current_app.db.session.add(job)
        current_app.db.session.commit()
        
        # Start Celery task with URLs
        transcribe_recipe_task.apply_async(
            args=[job.job_id, str(filepath), url_for('webhooks.update_status', _external=True), url_for('webhooks.record_recipe', _external=True)]
        )
        
        # Render pending job card using Turbo.
        # turbo.push(turbo.prepend(render_template('components/job_status.html', job=job), target='results-area'))
        turbo_operations.append(turbo.prepend(render_template('components/job_status.html', job=job), target='results-area'))
        processed_files += 1
    
    # if not processed_files:
    #     return render_template('components/no_valid_files.html'), 400
    
    # TODO: Need to handle the case where the websocket isn't available.
    return Response(turbo.push(turbo_operations), mimetype='text/vnd.turbo-stream.html')


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
    
    # Ensure session has a session_id
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    
    # Create new transcription job with session_id
    job = TranscriptionJob(
        task_id=str(uuid.uuid4()),
        session_id=session_id,
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
