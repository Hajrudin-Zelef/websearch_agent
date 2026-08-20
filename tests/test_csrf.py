"""
Tests de sécurité pour CSRF.
P2: Implémentation complète — token émis au login, vérifié sur routes mutantes.
"""

import unittest
import os
import sys
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.auth import (
    generate_csrf_token,
    validate_csrf_token,
    _csrf_tokens,
    _create_session,
    _sessions,
)


class TestCSRFTokenGeneration(unittest.TestCase):
    """Vérifie la génération et validation des tokens CSRF."""

    def setUp(self):
        _csrf_tokens.clear()
        _sessions.clear()

    def test_generate_csrf_token_returns_string(self):
        """generate_csrf_token doit retourner un token non vide."""
        session = _create_session()
        token = generate_csrf_token(session)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)

    def test_validate_csrf_token_valid(self):
        """Un token valide doit être accepté."""
        session = _create_session()
        csrf = generate_csrf_token(session)
        self.assertTrue(validate_csrf_token(session, csrf))

    def test_validate_csrf_token_single_use(self):
        """Un token ne peut être utilisé qu'une seule fois (replay échoue)."""
        session = _create_session()
        csrf = generate_csrf_token(session)
        self.assertTrue(validate_csrf_token(session, csrf))
        self.assertFalse(validate_csrf_token(session, csrf))

    def test_validate_csrf_token_wrong_session(self):
        """Token valide mais pour une autre session → échoue."""
        session1 = _create_session()
        session2 = _create_session()
        csrf = generate_csrf_token(session1)
        self.assertFalse(validate_csrf_token(session2, csrf))

    def test_validate_csrf_token_invalid(self):
        """Token inexistant → échoue."""
        session = _create_session()
        self.assertFalse(validate_csrf_token(session, "fake_token"))

    def test_validate_csrf_token_expired(self):
        """Token expiré → échoue."""
        session = _create_session()
        csrf = generate_csrf_token(session)
        key = f"{session}:{csrf}"
        _csrf_tokens[key] = time.time() - 1  # Expire
        self.assertFalse(validate_csrf_token(session, csrf))


class TestCSRFMiddlewareIntegration(unittest.TestCase):
    """Vérifie que le middleware CSRF est présent."""

    def test_login_returns_csrf_token(self):
        """La réponse de login doit contenir un token CSRF."""
        from routes.admin import login
        import inspect
        source = inspect.getsource(login)
        self.assertIn("generate_csrf_token", source,
                       "login() doit appeler generate_csrf_token")

    def test_csrf_token_in_response(self):
        """Le token CSRF doit être dans la réponse JSON de login."""
        from routes.admin import login
        import inspect
        source = inspect.getsource(login)
        self.assertIn("csrf_token", source,
                       "login() doit retourner csrf_token dans la réponse")

    def test_middleware_checks_csrf_on_post(self):
        """Le middleware doit vérifier X-CSRF-Token sur les routes POST /admin."""
        # Vérifie que le middleware existe dans server.py
        server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "server.py"
        )
        with open(server_path) as f:
            source = f.read()
        self.assertIn("X-CSRF-Token", source,
                       "Le middleware doit vérifier le header X-CSRF-Token")
        self.assertIn("validate_csrf_token", source,
                       "Le middleware doit appeler validate_csrf_token")

    def test_login_excluded_from_csrf(self):
        """La route login ne doit PAS être protégée par CSRF."""
        from routes.admin import login
        import inspect
        source = inspect.getsource(login)
        # Login ne doit pas avoir de check CSRF (c'est là qu'on émet le token)
        self.assertNotIn("validate_csrf_token", source,
                         "Login ne doit pas valider un token CSRF")


class TestFrontendCSRF(unittest.TestCase):
    """Vérifie que le frontend envoie le token CSRF."""

    def test_utils_js_sends_csrf_header(self):
        """admin/utils.js doit envoyer X-CSRF-Token sur les requêtes mutantes."""
        utils_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "admin", "utils.js"
        )
        with open(utils_path) as f:
            source = f.read()
        self.assertIn("X-CSRF-Token", source,
                       "utils.js doit envoyer le header X-CSRF-Token")

    def test_utils_js_reads_csrf_from_storage(self):
        """admin/init.js doit lire le token CSRF depuis le stockage."""
        init_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "admin", "js", "init.js"
        )
        with open(init_path) as f:
            source = f.read()
        self.assertIn("csrf_token", source,
                       "init.js doit lire csrf_token depuis localStorage")


if __name__ == "__main__":
    unittest.main()
