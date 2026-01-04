import logging
import os
import random
import time

import requests

from receipe_transcriber.celery_app import celery
from receipe_transcriber.services.ollama_service import ollama_service

# Configure logging
logger = logging.getLogger(__name__)


def get_recipe_data(image_path):
    """
    Fetch recipe data from Ollama or return mock data if testing.
    Set SKIP_OLLAMA=1 env var to use mock data for faster iteration.
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
    return ollama_service.transcribe_recipe(image_path)


def publish_status(external_recipe_id, status, message, status_update_hook):
    requests.post(
        status_update_hook,
        data={
            "external_recipe_id": external_recipe_id,
            "status": status,
            "message": message,
        },
    )


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

    if is_mock:
        time.sleep(random.uniform(1, 10))

    recipe_data = get_recipe_data(image_path)

    publish_status(
        external_recipe_id,
        "processing",
        "Parsing response from model...",
        status_update_hook,
    )

    if is_mock:
        time.sleep(random.uniform(1, 10))

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
    requests.post(processing_complete_hook, json=transcribed_recipe)
    return transcribed_recipe
