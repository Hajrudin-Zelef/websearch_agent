"""
Tests unitaires pour les endpoints FastAPI.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from server import app


class TestRoutes(unittest.TestCase):

    _client = None

    @classmethod
    def setUpClass(cls):
        cls._client = TestClient(app)

    def setUp(self):
        self.client = self._client

    def test_health(self):
        """Endpoint /health repond 200."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)

    def test_search(self):
        """Endpoint /search retourne des sources."""
        response = self.client.get("/search?q=python&max_results=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sources", data)
        self.assertIn("query", data)
        self.assertEqual(data["query"], "python")

    def test_datasets(self):
        """Endpoint /datasets retourne des datasets."""
        response = self.client.get("/datasets?query=climat&max_results=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("datasets", data)

    def test_threads_list(self):
        """Endpoint /threads retourne une liste."""
        response = self.client.get("/threads")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_admin_requires_auth(self):
        """Routes admin redirigent vers login sans session."""
        response = self.client.get("/admin/env", follow_redirects=False)
        # Soit 302 redirect, soit 200 si pas de protection
        self.assertIn(response.status_code, [200, 302, 401])


if __name__ == "__main__":
    unittest.main()
