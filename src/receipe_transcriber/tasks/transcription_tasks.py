# from datetime import datetime, timezone
from time import sleep
# from flask import render_template
# from flask_sse import sse
from receipe_transcriber.celery_app import celery
# from receipe_transcriber.models import db, TranscriptionJob, Recipe, Ingredient, Instruction
from receipe_transcriber.services.ollama_service import ollama_service
import os
import logging
import requests

# Configure logging
logger = logging.getLogger(__name__)

def get_recipe_data(image_path):
    """
    Fetch recipe data from Ollama or return mock data if testing.
    Set SKIP_OLLAMA=1 env var to use mock data for faster iteration.
    """
    if os.getenv('SKIP_OLLAMA') == '1':
        # Return mock recipe data for testing
        return {
            'title': 'Test Recipe - Mock Data',
            'prep_time': '15 minutes',
            'cook_time': '30 minutes',
            'servings': '4',
            'notes': 'This is mock data for testing. Set SKIP_OLLAMA=0 to use real Ollama.',
            'ingredients': [
                {'quantity': '2', 'unit': 'cups', 'item': 'flour'},
                {'quantity': '1', 'unit': 'cup', 'item': 'sugar'},
                {'quantity': '3', 'unit': None, 'item': 'eggs'},
            ],
            'instructions': [
                'Preheat oven to 350°F',
                'Mix dry ingredients together',
                'Add wet ingredients and stir',
                'Pour into baking pan',
                'Bake for 30 minutes until golden',
            ]
        }
    
    # Real Ollama call
    return ollama_service.transcribe_recipe(image_path)

def publish_status(job_id, status, message, status_update_hook):
    requests.post(status_update_hook, data={
        'job_id': job_id,
        'status': status,
        'message': message,
    })

@celery.task(bind=True)
def transcribe_recipe_task(self, job_id, image_path, status_update_hook, processing_complete_hook):
    """
    Transcribe recipe from image using Ollama.
    Publishes updates via Server-Sent Events (SSE) to Redis.
    
    Args:
        job_id: Database ID of the TranscriptionJob
        image_path: Path to the uploaded image
        urls: Dict with 'reprocess' and 'delete' URL templates
        reprocess_recipe_id: If set, this is a reprocess of an existing recipe
    """
    logger.info(f"Job {job_id}: Starting transcription.")

    try:
        # def publish_status(job_obj, message, status=None):
        #     """Update job message/status, persist, and emit SSE card to session channel."""
        #     logger.debug(f"Task {task_id}: Publishing status '{message}' (status={status})")

        #     if status:
        #         job_obj.status = status
        #         if status == 'processing' and not job_obj.started_at:
        #             job_obj.started_at = datetime.now(timezone.utc)
        #     job_obj.last_status = message
        #     db.session.commit()
            
        #     # Determine container_id for this update
        #     target_id = f'recipe-{reprocess_recipe_id}' if reprocess_recipe_id else f'job-{job_obj.id}'
        #     html_fragment = render_template('components/job_processing.html', job=job_obj, recipe_id=reprocess_recipe_id)
            
        #     # Publish to session channel with target element
        #     wrapped_html = f'<div id="{target_id}" hx-swap-oob="true">{html_fragment}</div>'
        #     sse.publish(wrapped_html, type='recipe-update', channel=f'session-{job_obj.session_id}')

        # Update job status to processing
        # logger.info(f"Task {job_id}: Fetching job from database")
        # job: TranscriptionJob | None = db.session.get(TranscriptionJob, job_id)
        # assert job is not None, f"TranscriptionJob {job_id} not found"
        publish_status(job_id, 'processing', 'Starting transcription...', status_update_hook)

        if os.getenv('SKIP_OLLAMA') == '1':
            sleep(2)

        recipe_data = get_recipe_data(image_path)

        if os.getenv('SKIP_OLLAMA') == '1':
            sleep(2)

        publish_status(job_id, 'processing', 'Parsing response from model...', status_update_hook)
        
        # Handle lists in recipe_data
        cook_time = recipe_data.get('cook_time')

        if isinstance(cook_time, list):
            cook_time = ', '.join(str(t) for t in cook_time if t)
        
        notes = recipe_data.get('notes')

        if isinstance(notes, list):
            notes = '\n'.join(str(n) for n in notes if n)
        
        servings = recipe_data.get('servings')

        if servings and not isinstance(servings, str):
            servings = str(servings)

        title = recipe_data.get('title', 'Untitled Recipe')
        prep_time = recipe_data.get('prep_time')
        instructions = recipe_data.get('instructions', [])
        ingredients = recipe_data.get('ingredients', [])

        requests.post(processing_complete_hook, json={
            'job_id': job_id,
            'title': title,
            'prep_time': prep_time,
            'cook_time': cook_time,
            'servings': servings,
            'ingredients': ingredients,
            'instructions': instructions,
            'notes': notes
        })

        # if reprocess_recipe_id:
        #     # We're going to recreate the existing recipe so we're going to delete
        #     # the existing one first.
        #     recipe = db.session.get(Recipe, reprocess_recipe_id)
        #     db.session.delete(recipe)
        #     db.session.commit()

        # # Create new recipe
        # recipe = Recipe(
        #     title=recipe_data.get('title', 'Untitled Recipe'),
        #     prep_time=recipe_data.get('prep_time'),
        #     cook_time=cook_time,
        #     servings=servings,
        #     notes=notes,
        #     image_path=image_path
        # )
        # db.session.add(recipe)
        
        # Flush to get recipe.id, but don't commit yet
        # logger.info(f"Job {job_id}: Flushing recipe to get ID")
        # db.session.flush()
        # logger.info(f"Job {job_id}: Recipe flushed, ID={recipe.id}")

        # if os.getenv('SKIP_OLLAMA') == '1':
        #     sleep(2)            
        
        # # Update job status WITHOUT committing (avoid mid-transaction commits)
        # logger.info(f"Job {job_id}: Adding {len(recipe_data.get('ingredients', []))} ingredients")
        # job.last_status = 'Saving recipe details...'

        # Add ingredients
        # for idx, ing in enumerate():
        #     ingredient = Ingredient(
        #         recipe_id=recipe.id,
        #         quantity=ing.get('quantity'),
        #         unit=ing.get('unit'),
        #         item=ing.get('item'),
        #         order=idx
        #     )
        #     db.session.add(ingredient)
        
        # logger.info(f"Job {job_id}: Adding {len(recipe_data.get('instructions', []))} instructions")
        # Add instructions
        # for idx, inst in enumerate(recipe_data.get('instructions', []), 1):
        #     if isinstance(inst, dict):
        #         description = inst.get('description') or inst.get('step') or ''
        #     else:
        #         description = str(inst)
            
        #     instruction = Instruction(
        #         recipe_id=recipe.id,
        #         step_number=idx,
        #         description=description
        #     )
        #     db.session.add(instruction)
        
        # Commit ingredients and instructions
        # logger.info(f"Job {job_id}: Committing ingredients and instructions to database")
        # db.session.commit()
        # logger.info(f"Job {job_id}: Successfully committed recipe details")
        
        # Update job status
        # logger.info(f"Job {job_id}: Updating job to completed status")
        # job.status = 'completed'
        # job.last_status = 'Completed'
        # job.recipe_id = recipe.id
        # job.completed_at = datetime.now(timezone.utc)
        
        # db.session.commit()
        # logger.info(f"Job {job_id}: Job status updated successfully")
        
        # Publish completed recipe via SSE (pass URLs to template)
        # Use recipe-based container_id for stable DOM (always recipe-<id>)
        # container_id_recipe = f'recipe-{recipe.id}'
        # logger.info(f"Job {job_id}: Rendering final recipe card, container_id={container_id_recipe}")

        # Render recipe card with stable recipe-based container id
        # recipe_html = render_template(
        #     'components/recipe_card.html',
        #     recipe=recipe,
        #     job=job,
        #     urls=urls,
        #     container_id=container_id_recipe,
        # )

        # Determine the processing card id to delete (matches in-flight processing card)
        # processing_target_id = f'recipe-{reprocess_recipe_id}' if reprocess_recipe_id else f'job-{job_id}'

        # # Create wrapper that will:
        # # 1. Delete the processing card
        # # 2. Prepend the recipe to results area (out-of-band)
        # # 3. Remove the empty placeholder if it exists
        # html = f'''
        #     <div id="{processing_target_id}" hx-swap-oob="delete"></div>
        #     <div hx-swap-oob="afterbegin:#results-area">{recipe_html}</div>
        #     <div id="empty-placeholder" hx-swap-oob="delete"></div>
        # '''
        
        # logger.info(f"Job {job_id}: Publishing completed recipe to SSE session channel")
        # sse.publish(html, type='recipe-update', channel=f'session-{job.session_id}')
        # logger.info(f"Job {job_id}: Task completed successfully")
        
        # return {'status': 'completed', 'recipe_id': recipe.id}
        
    except Exception as e:

        # # Update job with error
        # logger.error(f"Job {job_id}: Task failed with error: {str(e)}", exc_info=True)
        # job: TranscriptionJob | None = db.session.get(TranscriptionJob, job_id)
        # assert job is not None, f"TranscriptionJob {job_id} not found"
        # job.status = 'failed'
        # job.last_status = f'Failed: {str(e)}'
        # job.error_message = str(e)
        # job.completed_at = datetime.utcnow()
        # db.session.commit()
        # logger.info(f"Job {job_id}: Error status saved to database")
        
        # # Publish error via SSE to session channel
        # error_html = render_template('components/job_error.html', job=job, error=str(e))
        # wrapped_html = f'<div id="job-{job_id}" hx-swap-oob="true">{error_html}</div>'
        # sse.publish(wrapped_html, type='recipe-update', channel=f'session-{job.session_id}')
        
        raise
