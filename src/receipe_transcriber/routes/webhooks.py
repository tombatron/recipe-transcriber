from datetime import datetime, timezone

from flask import Blueprint, request

from .. import turbo
from ..models import Ingredient, Instruction, Recipe, TranscriptionJob, db
from .main import recipes

bp = Blueprint("webhooks", __name__)

# TODO: Middleware to secure webhook methods.


@bp.route("/update-status", methods=["POST"])
def update_status():
    external_recipe_id = request.form.get("external_recipe_id")
    status: str | None = request.form.get("status") or None
    message: str | None = request.form.get("message") or None

    job = (
        db.session.query(TranscriptionJob)
        .filter(TranscriptionJob.external_recipe_id == external_recipe_id)
        .one_or_none()
    )

    if not job:
        # Job not found - could be a race condition or already deleted
        # Return 200 to acknowledge webhook (prevent retries) but assume no-op
        return "", 200

    job.status = status  # type: ignore
    job.last_status = message  # type: ignore

    # If status is failed, store error message and mark as completed
    if status == "failed":
        job.error_message = message
        job.completed_at = datetime.now(timezone.utc)

    db.session.commit()

    turbo.push(turbo.replace(recipes(), target="results-area"))

    return "", 200


@bp.route("/record-recipe", methods=["POST"])
def record_recipe():
    data = request.get_json()
    external_recipe_id = data["external_recipe_id"]

    # Check if recipe already exists
    existing_recipe = (
        db.session.query(Recipe)
        .filter_by(external_recipe_id=external_recipe_id)
        .one_or_none()
    )

    if existing_recipe is not None:
        # Update existing recipe (reprocessing case)
        existing_recipe.title = data["title"]
        existing_recipe.image_path = data["image_path"]
        existing_recipe.prep_time = data["prep_time"]
        existing_recipe.cook_time = data["cook_time"]
        existing_recipe.servings = data["servings"]
        existing_recipe.notes = data["notes"]

        # Clear and update ingredients
        existing_recipe.ingredients.clear()
        if "ingredients" in data:
            existing_recipe.ingredients = [
                Ingredient(
                    item=i["item"], quantity=i["quantity"], unit=i["unit"], order=index
                )
                for index, i in enumerate(data["ingredients"], 1)
            ]

        # Clear and update instructions
        existing_recipe.instructions.clear()
        if "instructions" in data:
            existing_recipe.instructions = [
                Instruction(step_number=index, description=instruction)
                for index, instruction in enumerate(data["instructions"], 1)
            ]

        recipe = existing_recipe
    else:
        # Create new recipe
        recipe = Recipe(
            external_recipe_id=external_recipe_id,
            title=data["title"],
            image_path=data["image_path"],
            prep_time=data["prep_time"],
            cook_time=data["cook_time"],
            servings=data["servings"],
            notes=data["notes"],
        )

        if "ingredients" in data:
            recipe.ingredients = [
                Ingredient(
                    item=i["item"], quantity=i["quantity"], unit=i["unit"], order=index
                )
                for index, i in enumerate(data["ingredients"], 1)
            ]

        if "instructions" in data:
            recipe.instructions = [
                Instruction(step_number=index, description=instruction)
                for index, instruction in enumerate(data["instructions"], 1)
            ]

        db.session.add(recipe)

    # Update the transcription job
    job = (
        db.session.query(TranscriptionJob)
        .filter_by(external_recipe_id=external_recipe_id)
        .one_or_none()
    )

    if job is not None:
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)

    db.session.commit()

    turbo.push(turbo.replace(recipes(), target="results-area"))

    return "", 200
