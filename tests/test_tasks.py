import os
import tempfile
import unittest
from unittest.mock import patch

from receipe_transcriber.tasks.transcription_tasks import transcribe_recipe_task


class TasksTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["SKIP_OLLAMA"] = "1"

    def tearDown(self):
        os.environ["SKIP_OLLAMA"] = "0"

    @patch("receipe_transcriber.tasks.transcription_tasks.requests.post")
    def test_transcribe_recipe_task_returns_payload_and_posts_hooks(self, mock_post):
        image_path = os.path.join(tempfile.gettempdir(), "task.jpg")
        with open(image_path, "wb") as f:
            f.write(b"xyz")

        # Call task with correct signature: (image_path, status_hook, complete_hook, ext_id, is_reprocessing)
        result = transcribe_recipe_task.run(
            image_path,
            "http://localhost/status",
            "http://localhost/complete",
            "ext-123",
            False,
        )

        # Should return structured payload
        self.assertIsInstance(result, dict)
        self.assertEqual(result["external_recipe_id"], "ext-123")
        self.assertIn("ingredients", result)
        self.assertIn("instructions", result)

        # Multiple webhook posts: status updates + completion
        self.assertGreaterEqual(mock_post.call_count, 2)
        # At least one status call uses data= with form encoding
        status_calls = [c for c in mock_post.call_args_list if "data" in c[1]]
        self.assertGreater(len(status_calls), 0)
        # Final completion call uses json= body
        complete_call = mock_post.call_args_list[-1]
        self.assertEqual(
            complete_call[1].get("json", {}).get("external_recipe_id"), "ext-123"
        )


if __name__ == "__main__":
    unittest.main()
