from datetime import datetime, timezone

from flask import Blueprint, render_template, request

from .. import turbo
from ..models import Ingredient, Instruction, Recipe, TranscriptionJob, db
from .main import send_results_area_update

bp = Blueprint("webhooks", __name__)

# TODO: Middleware to secure webhook methods.


@bp.route("/update-status", methods=["POST"])
def update_status():
    external_recipe_id = request.form.get("job_id")
    status: str | None = request.form.get("status") or None
    message = request.form.get("message")

    job = (
        db.session.query(TranscriptionJob)
        .filter(TranscriptionJob.external_recipe_id == external_recipe_id)
        .one()
    )
    job.status = status  # type: ignore
    db.session.commit()

    send_results_area_update(
        turbo.replace(
            render_template(
                "components/job_processing.html", external_recipe_id=external_recipe_id, message=message
            ),
            target=f"recipe-{external_recipe_id}",
        )
    )

    return "", 200


@bp.route("/record-recipe", methods=["POST"])
def record_recipe():
    data = request.get_json()
    external_recipe_id = data["external_recipe_id"]
    new_external_recipe_id = data.get("new_external_recipe_id", None)

    # Delete existing... just in case we are reprocessing.
    existing_recipe = (
        db.session.query(Recipe).filter_by(external_recipe_id=external_recipe_id).one_or_none()
    )

    if existing_recipe is not None:
        db.session.delete(existing_recipe)
        db.session.flush()

    # Create new recipe
    new_recipe = Recipe(
        external_recipe_id=(new_external_recipe_id or external_recipe_id),
        title=data["title"],
        image_path=data["image_path"],
        prep_time=data["prep_time"],
        cook_time=data["cook_time"],
        servings=data["servings"],
        notes=data["notes"],
    )

    if "ingredients" in data:
        new_recipe.ingredients = [
            Ingredient(
                item=i["item"], quantity=i["quantity"], unit=i["unit"], order=index
            )
            for index, i in enumerate(data["ingredients"], 1)
        ]

    if "instructions" in data:
        new_recipe.instructions = [
            Instruction(step_number=index, description=instruction)
            for index, instruction in enumerate(data["instructions"], 1)
        ]

    db.session.add(new_recipe)

    job = (
        db.session.query(TranscriptionJob)
        .filter_by(job_id=new_external_recipe_id or external_recipe_id)
        .one_or_none()
    )

    if job is not None:
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)

    db.session.commit()

    # At this point we're always targeting the existing `external_recipe_id`, if we're replacing that, the `new_recipe` should
    # have the new ID we're concerned about.
    send_results_area_update(
        turbo.replace(
            render_template("components/recipe_card.html", recipe=new_recipe),
            target=f"recipe-{external_recipe_id}",
        )
    )

    return "", 200
