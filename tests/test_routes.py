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
    SQLALCHEMY_DATABASE_URI = "sqlite:///%s" % os.path.join(tempfile.gettempdir(), "rt_test.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "rt_uploads")


class RoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        os.makedirs(self.app.config['UPLOAD_FOLDER'], exist_ok=True)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        # Cleanup uploads
        for root, _, files in os.walk(self.app.config['UPLOAD_FOLDER']):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                except FileNotFoundError:
                    pass

    def test_allowed_file(self):
        from receipe_transcriber.routes.main import allowed_file
        with self.app.app_context():
            self.assertTrue(allowed_file('image.jpg'))
            self.assertTrue(allowed_file('image.jpeg'))
            self.assertTrue(allowed_file('image.png'))
            self.assertTrue(allowed_file('image.webp'))
            self.assertFalse(allowed_file('image.gif'))
            self.assertFalse(allowed_file('image'))

    def test_upload_invalid(self):
        # No file
        resp = self.client.post('/upload')
        self.assertEqual(resp.status_code, 400)
        # Wrong type
        data = {
            'image': (io.BytesIO(b'bad'), 'bad.gif')
        }
        resp = self.client.post('/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)

    @patch('receipe_transcriber.routes.main.transcribe_recipe_task.apply_async')
    def test_upload_valid_starts_job(self, mock_async):
        data = {
            'image': (io.BytesIO(b'fakejpg'), 'test.jpg')
        }
        resp = self.client.post('/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('sse-connect="/stream?channel=job-', html)
        self.assertTrue(mock_async.called)
        with self.app.app_context():
            jobs = db.session.query(TranscriptionJob).all()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].status, 'pending')
            self.assertTrue(os.path.exists(jobs[0].image_path))

    def test_delete_recipe_removes_file_and_record(self):
        with self.app.app_context():
            # Create dummy file and recipe
            image_path = os.path.join(self.app.config['UPLOAD_FOLDER'], 'dummy.jpg')
            with open(image_path, 'wb') as f:
                f.write(b'123')
            recipe = Recipe(title='To Delete', image_path=image_path)
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id
        # Delete
        resp = self.client.delete(f'/recipes/{rid}/delete')
        self.assertEqual(resp.status_code, 200)
        # Verify removal
        with self.app.app_context():
            self.assertIsNone(db.session.get(Recipe, rid))
        self.assertFalse(os.path.exists(image_path))

    @patch('receipe_transcriber.routes.main.transcribe_recipe_task.apply_async')
    def test_reprocess_recipe_starts_job(self, mock_async):
        with self.app.app_context():
            image_path = os.path.join(self.app.config['UPLOAD_FOLDER'], 'img.jpg')
            with open(image_path, 'wb') as f:
                f.write(b'abc')
            recipe = Recipe(title='Reprocess Me', image_path=image_path)
            db.session.add(recipe)
            db.session.commit()
            rid = recipe.id
        resp = self.client.post(f'/recipes/{rid}/reprocess')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_async.called)
        html = resp.get_data(as_text=True)
        self.assertIn('job', html)


if __name__ == '__main__':
    unittest.main()
