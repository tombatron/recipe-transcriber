import os
import uuid
from pathlib import Path
from flask import Blueprint, render_template, request, current_app, session, Response
from werkzeug.utils import secure_filename
from flask import url_for
from receipe_transcriber import db
from receipe_transcriber.models import TranscriptionJob, Recipe
from receipe_transcriber.tasks.transcription_tasks import transcribe_recipe_task, reprocess_transcribe_recipe_task
from .. import turbo, db

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

@bp.route('/recipes/<string:external_recipe_id>/delete', methods=['DELETE'])
def delete_recipe(external_recipe_id):
    """Delete a recipe. Turbo will remove the element from DOM."""
    recipe = db.session.query(Recipe).filter(Recipe.job_id == external_recipe_id).one_or_none()

    if recipe:
        # Delete associated file if it exists
        if recipe.image_path and os.path.exists(recipe.image_path):
            os.remove(recipe.image_path)
        
        # Delete from database (cascades to ingredients and instructions)
        db.session.delete(recipe)
        db.session.commit()

        turbo.push(turbo.remove(target=f'recipe-{recipe.job_id}'))
    
    return '', 200 #Response(turbo.push(turbo.remove(target=f'recipe-{recipe.job_id}')), mimetype='text/vnd.turbo-stream.html')


@bp.route('/recipes/<string:external_recipe_id>/reprocess', methods=['POST'])
def reprocess_recipe(external_recipe_id):
    """Reprocess an existing recipe. Returns processing status."""
    recipe = db.session.query(Recipe).filter(Recipe.job_id == external_recipe_id).one_or_none()

    if not recipe:
        return '', 404
    
    # Ensure session has a session_id
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']

    # TODO: Consolidate this with the upload logic. 
    
    # Create new transcription job with session_id
    job = TranscriptionJob(
        job_id=str(uuid.uuid1()),
        session_id=session_id,
        image_path=recipe.image_path, #type: ignore
        status='pending',
        last_status='Reprocessing requested. Queued for processing...'
    )

    db.session.add(job)
    db.session.commit()
    
    # Start Celery task - will update the original recipe
    reprocess_transcribe_recipe_task.apply_async(
        args=[external_recipe_id, job.job_id, recipe.image_path, url_for('webhooks.update_status', _external=True), url_for('webhooks.record_recipe', _external=True)],
    )

    # Targeting the existing recipe card for replacement, not the new one because it doesn't
    # exist yet.    
    turbo.push(turbo.replace(render_template('components/job_status.html', job=job), target=f'receipt-{external_recipe_id}'))
    
    return '', 200

@bp.route('/recipes/<int:recipe_id>')
def recipe_detail(recipe_id):
    """View a single recipe."""
    recipe = current_app.db.session.get(Recipe, recipe_id)
    if not recipe:
        return "Recipe not found", 404
    
    return render_template('recipe_detail.html', recipe=recipe)
