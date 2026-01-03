import io
import os
import tempfile
import unittest
from unittest.mock import patch

from receipe_transcriber import create_app, db
from receipe_transcriber.config import Config
from receipe_transcriber.models import Recipe, TranscriptionJob


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///%s" % os.path.join(
        tempfile.gettempdir(), "rt_test.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "rt_uploads")


class RoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        os.makedirs(self.app.config["UPLOAD_FOLDER"], exist_ok=True)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        # Cleanup uploads
        for root, _, files in os.walk(self.app.config["UPLOAD_FOLDER"]):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                except FileNotFoundError:
                    pass

    def test_allowed_file(self):
        from receipe_transcriber.routes.main import allowed_file

        with self.app.app_context():
            self.assertTrue(allowed_file("image.jpg"))
            self.assertTrue(allowed_file("image.jpeg"))
            self.assertTrue(allowed_file("image.png"))
            self.assertTrue(allowed_file("image.webp"))
            self.assertFalse(allowed_file("image.gif"))
            self.assertFalse(allowed_file("image"))

    def test_upload_invalid(self):
        resp = self.client.post("/upload")
        self.assertEqual(resp.status_code, 302)

    @patch("receipe_transcriber.routes.main.transcribe_recipe_task.apply_async")
    def test_upload_valid_starts_job(self, mock_async):
        data = {"images": (io.BytesIO(b"fakejpg"), "test.jpg")}
        resp = self.client.post(
            "/upload", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(mock_async.called)
        with self.app.app_context():
            jobs = db.session.query(TranscriptionJob).all()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].status, "pending")
            self.assertTrue(os.path.exists(jobs[0].image_path))

    def test_delete_recipe_removes_file_and_record(self):
        with self.app.app_context():
            image_path = os.path.join(self.app.config["UPLOAD_FOLDER"], "dummy.jpg")
            with open(image_path, "wb") as f:
                f.write(b"123")
            job = TranscriptionJob(
                external_recipe_id="ext-del",
                session_id="sess",
                image_path=image_path,
            )
            recipe = Recipe(
                external_recipe_id="ext-del", title="To Delete", image_path=image_path
            )
            db.session.add_all([job, recipe])
            db.session.commit()
        with self.app.test_request_context():
            resp = self.client.post("/recipes/ext-del/delete")
            # Turbo push succeeds in test context -> 204
            self.assertIn(resp.status_code, (200, 204, 302))
        with self.app.app_context():
            self.assertIsNone(
                db.session.query(Recipe)
                .filter_by(external_recipe_id="ext-del")
                .one_or_none()
            )
        self.assertFalse(os.path.exists(image_path))

    @patch("receipe_transcriber.routes.main.transcribe_recipe_task.apply_async")
    def test_reprocess_recipe_starts_job(self, mock_async):
        with self.app.app_context():
            image_path = os.path.join(self.app.config["UPLOAD_FOLDER"], "img.jpg")
            with open(image_path, "wb") as f:
                f.write(b"abc")
            job = TranscriptionJob(
                external_recipe_id="ext-reproc",
                session_id="sess",
                image_path=image_path,
            )
            recipe = Recipe(
                external_recipe_id="ext-reproc",
                title="Reprocess Me",
                image_path=image_path,
            )
            db.session.add_all([job, recipe])
            db.session.commit()
        with self.app.test_request_context():
            resp = self.client.post("/recipes/ext-reproc/reprocess")
            # Turbo push succeeds -> 200; fallback redirect -> 302
            self.assertIn(resp.status_code, (200, 302))
        self.assertTrue(mock_async.called)


if __name__ == "__main__":
    unittest.main()
