import os
import tempfile
import unittest
from unittest.mock import patch

from receipe_transcriber import create_app, db
from receipe_transcriber.config import Config
from receipe_transcriber.models import TranscriptionJob, Recipe, Ingredient, Instruction
from receipe_transcriber.tasks.transcription_tasks import transcribe_recipe_task


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///%s" % os.path.join(tempfile.gettempdir(), "rt_tasks_test.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "rt_uploads")


class TasksTestCase(unittest.TestCase):
    def setUp(self):
        os.environ['SKIP_OLLAMA'] = '1'
        self.app = create_app(TestingConfig)
        os.makedirs(self.app.config['UPLOAD_FOLDER'], exist_ok=True)
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.environ['SKIP_OLLAMA'] = '0'

    @patch('receipe_transcriber.tasks.transcription_tasks.sse.publish')
    @patch('receipe_transcriber.tasks.transcription_tasks.get_app')
    def test_transcribe_recipe_task_mock_path(self, mock_get_app, mock_publish):
        # Create dummy image and job
        image_path = os.path.join(self.app.config['UPLOAD_FOLDER'], 'task.jpg')
        with open(image_path, 'wb') as f:
            f.write(b'xyz')
        with self.app.app_context():
            job = TranscriptionJob(task_id='t1', image_path=image_path)
            db.session.add(job)
            db.session.commit()
            job_id = job.id
        urls = {'reprocess': '/recipes/0/reprocess', 'delete': '/recipes/0/delete'}
        # Ensure task uses our test app and DB
        mock_get_app.return_value = self.app
        # Run task synchronously via .run()
        result = transcribe_recipe_task.run(job_id, image_path, urls)
        self.assertEqual(result['status'], 'completed')
        with self.app.app_context():
            job = db.session.get(TranscriptionJob, job_id)
            self.assertEqual(job.status, 'completed')
            self.assertIsNotNone(job.recipe_id)
            recipe = db.session.get(Recipe, job.recipe_id)
            self.assertIsNotNone(recipe)
            self.assertGreaterEqual(len(recipe.ingredients), 1)
            self.assertGreaterEqual(len(recipe.instructions), 1)
        # SSE publish called multiple times
        self.assertTrue(mock_publish.called)


if __name__ == '__main__':
    unittest.main()
