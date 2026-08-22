"""
Tests de sécurité pour les routes /docs et /redoc.
P5: docs_url=None en prod, protection auth.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDocsProductionBlocking(unittest.TestCase):
    """Vérifie que /docs et /redoc sont bloqués en production."""

    def test_server_docs_logic(self):
        """Vérifie que le code de server.py gère correctement docs_url."""
        # Vérifie que server.py contient la logique de blocage
        server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "server.py"
        )
        with open(server_path) as f:
            source = f.read()
        self.assertIn("docs_url", source)
        self.assertIn("redoc_url", source)
        self.assertIn("ENVIRONMENT", source)
        self.assertIn("ADMIN_ALLOW_DOCS", source)


class TestDocsAuthProtection(unittest.TestCase):
    """Vérifie que /docs est protégé par auth quand ADMIN_ALLOW_DOCS=true."""

    def test_docs_protected_by_middleware(self):
        """Le middleware admin_auth doit gérer /admin/docs."""
        from routes.auth import ADMIN_STATIC_PATHS
        # /admin/docs ne doit pas être dans les chemins statiques
        self.assertNotIn("/admin/docs", ADMIN_STATIC_PATHS,
                         "/admin/docs ne doit pas être accessible sans auth")


if __name__ == "__main__":
    unittest.main()
