import logging
import os
import random
import time

import requests

from receipe_transcriber.celery_app import celery
from receipe_transcriber.services.ollama_service import ollama_service

# Configure logging
logger = logging.getLogger(__name__)


def get_recipe_data(image_path, status_callback=None):
    """
    Fetch recipe data from Ollama or return mock data if testing.
    Set SKIP_OLLAMA=1 env var to use mock data for faster iteration.

    Args:
        image_path: Path to the recipe image
        status_callback: Optional callback function for status updates
    """
    if os.getenv("SKIP_OLLAMA") == "1":
        # Return mock recipe data for testing
        return {
            "title": "Test Recipe - Mock Data",
            "prep_time": "15 minutes",
            "cook_time": "30 minutes",
            "servings": "4",
            "notes": "This is mock data for testing. Set SKIP_OLLAMA=0 to use real Ollama.",
            "ingredients": [
                {"quantity": "2", "unit": "cups", "item": "flour"},
                {"quantity": "1", "unit": "cup", "item": "sugar"},
                {"quantity": "3", "unit": None, "item": "eggs"},
            ],
            "instructions": [
                "Preheat oven to 350°F",
                "Mix dry ingredients together",
                "Add wet ingredients and stir",
                "Pour into baking pan",
                "Bake for 30 minutes until golden",
            ],
        }

    # Real Ollama call
    return ollama_service.transcribe_recipe(image_path, status_callback=status_callback)


def publish_status(external_recipe_id, status, message, status_update_hook):
    try:
        logger.info(f"Publishing status: {status} - {message}")
        response = requests.post(
            status_update_hook,
            data={
                "external_recipe_id": external_recipe_id,
                "status": status,
                "message": message,
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Status published successfully to {status_update_hook}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to publish status to {status_update_hook}: {e}")
        # Don't raise - allow task to continue even if status update fails


@celery.task(bind=True)
def transcribe_recipe_task(
    _,
    image_path,
    status_update_hook,
    processing_complete_hook,
    external_recipe_id,
    is_reprocessing=False,
):
    is_mock = os.getenv("SKIP_OLLAMA") == "1"

    # Use appropriate status message for initial state
    initial_message = (
        "Reprocessing your recipe..."
        if is_reprocessing
        else "Starting transcription..."
    )

    publish_status(
        external_recipe_id,
        "processing",
        initial_message,
        status_update_hook,
    )

    try:
        if is_mock:
            time.sleep(random.uniform(1, 10))

        # Create a status update callback
        def status_update(message):
            publish_status(
                external_recipe_id,
                "processing",
                message,
                status_update_hook,
            )

        recipe_data = get_recipe_data(image_path, status_callback=status_update)

        # Extract data from processed recipe image.
        cook_time = recipe_data.get("cook_time")

        if isinstance(cook_time, list):
            cook_time = ", ".join(str(t) for t in cook_time if t)

        notes = recipe_data.get("notes")

        if isinstance(notes, list):
            notes = "\n".join(str(n) for n in notes if n)

        servings = recipe_data.get("servings")

        if servings and not isinstance(servings, str):
            servings = str(servings)

        title = recipe_data.get("title", "Untitled Recipe")
        prep_time = recipe_data.get("prep_time")
        instructions = recipe_data.get("instructions", [])
        ingredients = recipe_data.get("ingredients", [])

        transcribed_recipe = {
            "external_recipe_id": external_recipe_id,
            "image_path": image_path,
            "title": title,
            "prep_time": prep_time,
            "cook_time": cook_time,
            "servings": servings,
            "ingredients": ingredients,
            "instructions": instructions,
            "notes": notes,
        }

        # Final status update before saving
        publish_status(
            external_recipe_id,
            "processing",
            f"Recipe '{title}' complete! Saving...",
            status_update_hook,
        )

        try:
            logger.info(f"Posting recipe data to {processing_complete_hook}")
            response = requests.post(
                processing_complete_hook, json=transcribed_recipe, timeout=10
            )
            response.raise_for_status()
            logger.info(
                f"Recipe data posted successfully, status: {response.status_code}"
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to post recipe data to webhook: {e}")
            # Still publish failure status to update UI
            publish_status(
                external_recipe_id,
                "failed",
                f"Failed to save recipe: {str(e)}",
                status_update_hook,
            )
            raise

        return transcribed_recipe
    except Exception as e:
        # Log error and publish failed status
        error_message = str(e)
        logger.error(f"Task failed for {external_recipe_id}: {error_message}")

        # Publish failure status to update UI (truncate error if too long)
        display_error = (
            (error_message[:200] + "...") if len(error_message) > 200 else error_message
        )

        publish_status(
            external_recipe_id,
            "failed",
            f"Processing failed: {display_error}",
            status_update_hook,
        )

        # Re-raise the exception so Celery knows the task failed
        raise
