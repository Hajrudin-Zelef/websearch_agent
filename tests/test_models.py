"""
Tests unitaires pour core/models.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import (
    MODEL_POOL,
    _get_max_tokens_synthesis,
    _get_max_tokens_tool,
    _get_synthesis_timeout,
    _get_tool_timeout,
    _pick_random_models,
)


class TestModels(unittest.TestCase):

    def test_model_pool_not_empty(self):
        """Le pool contient au moins 1 modele."""
        self.assertGreater(len(MODEL_POOL), 0)

    def test_model_pool_structure(self):
        """Chaque modele a les champs requis."""
        for model in MODEL_POOL:
            self.assertIn("model", model)
            self.assertIn("timeout", model)
            self.assertIn("weight", model)
            self.assertGreater(model["timeout"], 0)
            self.assertGreater(model["weight"], 0)

    def test_pick_random_models_count(self):
        """Retourne le bon nombre de modeles."""
        selected = _pick_random_models(count=2)
        self.assertEqual(len(selected), 2)

    def test_pick_random_models_no_duplicates(self):
        """Pas de doublons."""
        selected = _pick_random_models(count=3)
        models = [m["model"] for m in selected]
        self.assertEqual(len(models), len(set(models)))

    def test_pick_random_models_more_than_pool(self):
        """Ne depasse pas la taille du pool."""
        selected = _pick_random_models(count=100)
        self.assertLessEqual(len(selected), len(MODEL_POOL))

    def test_get_tool_timeout(self):
        """Retourne un timeout positif."""
        timeout = _get_tool_timeout()
        self.assertGreater(timeout, 0)

    def test_get_synthesis_timeout(self):
        """Retourne un timeout positif."""
        timeout = _get_synthesis_timeout()
        self.assertGreater(timeout, 0)

    def test_get_max_tokens_tool(self):
        """Retourne un max_tokens positif."""
        tokens = _get_max_tokens_tool()
        self.assertGreater(tokens, 0)

    def test_get_max_tokens_synthesis(self):
        """Retourne un max_tokens positif."""
        tokens = _get_max_tokens_synthesis()
        self.assertGreater(tokens, 0)


if __name__ == "__main__":
    unittest.main()
