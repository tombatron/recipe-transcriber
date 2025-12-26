import os
import tempfile
import unittest

from receipe_transcriber import create_app, db
from receipe_transcriber.config import Config
from receipe_transcriber.models import Recipe, Ingredient, Instruction


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///%s" % os.path.join(tempfile.gettempdir(), "rt_models_test.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ModelsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_recipe_relationships(self):
        with self.app.app_context():
            recipe = Recipe(title='Test Recipe')
            db.session.add(recipe)
            db.session.flush()
            ing1 = Ingredient(recipe_id=recipe.id, item='Flour', quantity='2', unit='cups', order=0)
            ing2 = Ingredient(recipe_id=recipe.id, item='Sugar', quantity='1', unit='cup', order=1)
            inst1 = Instruction(recipe_id=recipe.id, step_number=1, description='Mix dry')
            inst2 = Instruction(recipe_id=recipe.id, step_number=2, description='Bake')
            db.session.add_all([ing1, ing2, inst1, inst2])
            db.session.commit()
            # Verify
            self.assertEqual(len(recipe.ingredients), 2)
            self.assertEqual(len(recipe.instructions), 2)
            self.assertEqual(recipe.ingredients[0].item, 'Flour')
            self.assertEqual(recipe.instructions[1].step_number, 2)


if __name__ == '__main__':
    unittest.main()
