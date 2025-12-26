import unittest

from receipe_transcriber.services.ollama_service import OllamaService


class ServicesTestCase(unittest.TestCase):
    def test_extract_json_from_text(self):
        svc = OllamaService()
        text = """
        Here is some output:
        ```json
        {"title":"Sample","ingredients":[],"instructions":[],"prep_time":null,"cook_time":null,"servings":null,"notes":null}
        ```
        """
        result = svc._extract_json_from_text(text)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['title'], 'Sample')


if __name__ == '__main__':
    unittest.main()
