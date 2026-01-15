import os
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from receipe_transcriber.models import Ingredient, Instruction, Recipe, TranscriptionJob
from receipe_transcriber.tasks.transcription_tasks import transcribe_recipe_task

from .. import db, turbo

bp = Blueprint("main", __name__)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


@bp.route("/")
def index():
    """Main page with upload/camera interface."""

    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    return render_template("index.html")


@bp.route("/recipes")
def recipes():
    from datetime import datetime, timedelta, timezone

    # Define timeout threshold (e.g., 10 minutes)
    TIMEOUT_MINUTES = 10
    timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=TIMEOUT_MINUTES)

    # Get all incomplete jobs
    active_transcription_jobs = (
        db.session.query(TranscriptionJob)
        .filter(TranscriptionJob.completed_at == None)  # noqa: E711
        .order_by(TranscriptionJob.created_at.asc())
        .all()
    )

    # Check for timed out jobs and mark them as failed
    for job in active_transcription_jobs:
        if job.status == "processing":
            # Make created_at timezone-aware if it's naive (for SQLite compatibility)
            job_created_at = job.created_at
            if job_created_at.tzinfo is None:
                job_created_at = job_created_at.replace(tzinfo=timezone.utc)

            if job_created_at < timeout_threshold:
                job.status = "failed"
                job.error_message = (
                    "Processing timed out. Please try reprocessing this recipe."
                )
                job.completed_at = datetime.now(timezone.utc)

    db.session.commit()

    recent_recipes = (
        db.session.query(Recipe).order_by(Recipe.created_at.desc()).limit(5)
    )

    return render_template(
        "components/recent_recipes.html",
        recent_recipes=recent_recipes,
        active_transcription_jobs=active_transcription_jobs,
    )


@bp.route("/recipes-gallery")
def recipes_gallery():
    """View all successfully processed recipes."""
    all_recipes = db.session.query(Recipe).order_by(Recipe.created_at.desc()).all()

    return render_template(
        "recipes_gallery.html",
        all_recipes=all_recipes,
    )


@bp.route("/upload", methods=["POST"])
def upload_image():
    """Handle image upload(s) and start transcription. Returns pending job card(s)."""
    # Support both 'images' (multi) and legacy 'image'
    files = request.files.getlist("images") or request.files.getlist("image")

    if not files or not any(f.filename for f in files):
        flash(render_template("components/no_valid_files.html"))
        return redirect(url_for("main.index")), 302

    # Ensure session has a session_id
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    session_id = session["session_id"]

    for file in files:
        if not file or not file.filename:
            continue

        if not allowed_file(file.filename):
            flash(
                render_template(
                    "components/invalid_file_type.html", filename=file.filename
                )
            )
            continue

        # Save uploaded file
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = Path(current_app.config["UPLOAD_FOLDER"]) / unique_filename
        file.save(filepath)

        # Create transcription job with session_id
        job = TranscriptionJob(
            external_recipe_id=str(uuid.uuid1()),
            session_id=session_id,
            image_path=str(filepath),
            status="pending",
            last_status="Upload received. Queued for processing...",
        )

        db.session.add(job)
        db.session.commit()

        # Start Celery task with URLs
        transcribe_recipe_task.apply_async(
            args=[
                str(filepath),
                url_for("webhooks.update_status", _external=True),
                url_for("webhooks.record_recipe", _external=True),
                job.external_recipe_id,
            ]
        )

    return redirect(url_for("main.index"))


@bp.route("/recipes/<string:external_recipe_id>/delete", methods=["POST"])
def delete_recipe(external_recipe_id):
    """Delete a recipe. Turbo will remove the element from DOM."""
    recipe = (
        db.session.query(Recipe)
        .filter(Recipe.external_recipe_id == external_recipe_id)
        .one_or_none()
    )

    if recipe:
        # Delete associated file if it exists
        if recipe.image_path and os.path.exists(recipe.image_path):
            os.remove(recipe.image_path)

        # Delete from database (cascades to ingredients and instructions)
        db.session.delete(recipe)
        db.session.commit()

        # Refresh entire results area to show remaining recipes
        return turbo.stream(turbo.replace(recipes(), target="results-area"))

    return redirect(url_for("main.index"))


@bp.route("/recipes/<string:external_recipe_id>/reprocess", methods=["POST"])
def reprocess_recipe(external_recipe_id):
    """Reprocess an existing recipe. Reuses the same transcription job and recipe ID."""
    recipe = (
        db.session.query(Recipe)
        .filter(Recipe.external_recipe_id == external_recipe_id)
        .one_or_none()
    )

    if not recipe:
        return "", 404

    # Get or create transcription job for this recipe
    job = (
        db.session.query(TranscriptionJob)
        .filter_by(external_recipe_id=external_recipe_id)
        .one_or_none()
    )

    if not job:
        # Ensure session has a session_id
        if "session_id" not in session:
            session["session_id"] = str(uuid.uuid4())

        session_id = session["session_id"]

        # Create transcription job
        job = TranscriptionJob(
            external_recipe_id=external_recipe_id,
            session_id=session_id,
            image_path=recipe.image_path,  # type: ignore
            status="pending",
            last_status="Reprocessing requested. Queued for processing...",
        )

        db.session.add(job)
    else:
        # Reset existing job for reprocessing
        job.status = "pending"
        job.last_status = "Reprocessing requested. Queued for processing..."
        job.completed_at = None

    db.session.commit()

    # Start Celery task using the same recipe ID
    transcribe_recipe_task.apply_async(
        args=[
            recipe.image_path,
            url_for("webhooks.update_status", _external=True),
            url_for("webhooks.record_recipe", _external=True),
            external_recipe_id,
        ],
        kwargs={"is_reprocessing": True},
    )

    return redirect(url_for("main.index"))


@bp.route("/recipes/<string:external_recipe_id>/delete-failed-job", methods=["POST"])
def delete_failed_job(external_recipe_id):
    """Delete a failed transcription job. Turbo will remove the element from DOM."""
    job = (
        db.session.query(TranscriptionJob)
        .filter(TranscriptionJob.external_recipe_id == external_recipe_id)
        .one_or_none()
    )

    if job and job.status == "failed":
        # Delete the job
        db.session.delete(job)
        db.session.commit()

        # Refresh entire results area
        return turbo.stream(turbo.replace(recipes(), target="results-area"))

    return redirect(url_for("main.index"))


@bp.route("/recipes/<string:external_recipe_id>/detail")
def recipe_detail(external_recipe_id):
    """View a single recipe."""
    recipe = (
        db.session.query(Recipe)
        .filter(Recipe.external_recipe_id == external_recipe_id)
        .one_or_none()
    )

    if not recipe:
        return "Recipe not found", 404

    return render_template("recipe_detail.html", recipe=recipe)


@bp.route("/recipes/<string:external_recipe_id>/edit")
def edit_recipe(external_recipe_id):
    """Edit a recipe - returns edit form in Turbo frame."""
    recipe = (
        db.session.query(Recipe)
        .filter(Recipe.external_recipe_id == external_recipe_id)
        .one_or_none()
    )

    if not recipe:
        return "Recipe not found", 404

    return render_template(
        "components/recipe_edit_form.html", recipe=recipe, errors=None
    )


@bp.route("/recipes/<string:external_recipe_id>/detail-card")
def recipe_detail_card(external_recipe_id):
    """Return just the recipe card component for Cancel action."""
    recipe = (
        db.session.query(Recipe)
        .filter(Recipe.external_recipe_id == external_recipe_id)
        .one_or_none()
    )

    if not recipe:
        return "Recipe not found", 404

    # Get the associated transcription job for metadata display
    job = recipe.transcription_job

    return render_template("components/recipe_card.html", recipe=recipe, job=job)


@bp.route("/recipes/<string:external_recipe_id>/update", methods=["POST"])
def update_recipe(external_recipe_id):
    """Update a recipe with form data. Returns Turbo stream replacement."""
    recipe = (
        db.session.query(Recipe)
        .filter(Recipe.external_recipe_id == external_recipe_id)
        .one_or_none()
    )

    if not recipe:
        return "Recipe not found", 404

    # Validate required fields
    errors = {}
    title = request.form.get("title", "").strip()
    if not title:
        errors["title"] = "Title is required"

    # If validation fails, return form with errors
    if errors:
        return render_template(
            "components/recipe_edit_form.html", recipe=recipe, errors=errors
        )

    # Update recipe metadata
    recipe.title = title
    recipe.prep_time = request.form.get("prep_time", "").strip() or None
    recipe.cook_time = request.form.get("cook_time", "").strip() or None
    recipe.servings = request.form.get("servings", "").strip() or None
    recipe.notes = request.form.get("notes", "").strip() or None

    # Delete existing ingredients and instructions (cascade handles this)
    for ingredient in recipe.ingredients:
        db.session.delete(ingredient)
    for instruction in recipe.instructions:
        db.session.delete(instruction)

    # Parse and create new ingredients
    ingredient_indices = []
    for key in request.form.keys():
        if key.startswith("ingredients[") and key.endswith("][item]"):
            # Extract index from "ingredients[0][item]"
            idx = int(key.split("[")[1].split("]")[0])
            ingredient_indices.append(idx)

    for idx in sorted(set(ingredient_indices)):
        item = request.form.get(f"ingredients[{idx}][item]", "").strip()
        if item:  # Only add if item is not empty
            quantity = (
                request.form.get(f"ingredients[{idx}][quantity]", "").strip() or None
            )
            unit = request.form.get(f"ingredients[{idx}][unit]", "").strip() or None

            ingredient = Ingredient(item=item, quantity=quantity, unit=unit, order=idx)
            recipe.ingredients.append(ingredient)

    # Parse and create new instructions
    instruction_indices = []
    for key in request.form.keys():
        if key.startswith("instructions[") and key.endswith("][description]"):
            # Extract index from "instructions[0][description]"
            idx = int(key.split("[")[1].split("]")[0])
            instruction_indices.append(idx)

    for idx in sorted(set(instruction_indices)):
        description = request.form.get(f"instructions[{idx}][description]", "").strip()
        if description:  # Only add if description is not empty
            instruction = Instruction(
                step_number=idx + 1, description=description  # step_number is 1-indexed
            )
            recipe.instructions.append(instruction)

    # Commit changes
    db.session.commit()

    # Get the associated transcription job for metadata display
    job = recipe.transcription_job

    # Return Turbo stream to replace the frame with updated recipe card
    return turbo.stream(
        turbo.replace(
            render_template("components/recipe_card.html", recipe=recipe, job=job),
            target=f"recipe-{external_recipe_id}",
        )
    )
