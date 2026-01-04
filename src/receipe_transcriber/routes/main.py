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

from receipe_transcriber.models import Recipe, TranscriptionJob
from receipe_transcriber.tasks.transcription_tasks import transcribe_recipe_task

from .. import db

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
    active_transcription_jobs = (
        db.session.query(TranscriptionJob)
        .filter(TranscriptionJob.completed_at == None)  # noqa: E711
        .order_by(TranscriptionJob.created_at.asc())
        .all()
    )

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
