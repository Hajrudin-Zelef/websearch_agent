"""
Tests de securite pour CSRF.
P2: Implementation complete — token emis au login, verifie sur routes mutantes,
    rotation apres chaque mutation (nouveau token dans X-CSRF-Token reponse).
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
    """Verifie la generation et validation des tokens CSRF."""

    def setUp(self):
        _csrf_tokens.clear()
        _sessions.clear()

    def test_generate_csrf_token_returns_string(self):
        session = _create_session()
        token = generate_csrf_token(session)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)

    def test_validate_csrf_token_valid(self):
        session = _create_session()
        csrf = generate_csrf_token(session)
        self.assertTrue(validate_csrf_token(session, csrf))

    def test_validate_csrf_token_single_use(self):
        session = _create_session()
        csrf = generate_csrf_token(session)
        self.assertTrue(validate_csrf_token(session, csrf))
        self.assertFalse(validate_csrf_token(session, csrf))

    def test_validate_csrf_token_wrong_session(self):
        session1 = _create_session()
        session2 = _create_session()
        csrf = generate_csrf_token(session1)
        self.assertFalse(validate_csrf_token(session2, csrf))

    def test_validate_csrf_token_invalid(self):
        session = _create_session()
        self.assertFalse(validate_csrf_token(session, "fake_token"))

    def test_validate_csrf_token_expired(self):
        session = _create_session()
        csrf = generate_csrf_token(session)
        key = f"{session}:{csrf}"
        _csrf_tokens[key] = time.time() - 1
        self.assertFalse(validate_csrf_token(session, csrf))


class TestCSRFMiddlewareIntegration(unittest.TestCase):
    """Verifie que le middleware CSRF est present."""

    def test_login_returns_csrf_token(self):
        from routes.admin import login
        import inspect
        source = inspect.getsource(login)
        self.assertIn("generate_csrf_token", source)

    def test_csrf_token_in_response(self):
        from routes.admin import login
        import inspect
        source = inspect.getsource(login)
        self.assertIn("csrf_token", source)

    def test_middleware_checks_csrf_on_post(self):
        server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "server.py"
        )
        with open(server_path) as f:
            source = f.read()
        self.assertIn("X-CSRF-Token", source)
        self.assertIn("validate_csrf_token", source)

    def test_login_excluded_from_csrf(self):
        from routes.admin import login
        import inspect
        source = inspect.getsource(login)
        self.assertNotIn("validate_csrf_token", source)


class TestCSRFTokenRotation(unittest.TestCase):
    """Verifie que le serveur retourne un nouveau token CSRF apres chaque mutation."""

    def setUp(self):
        _csrf_tokens.clear()
        _sessions.clear()

    def test_middleware_returns_new_csrf_in_response_header(self):
        """Apres un POST admin reussi, le header X-CSRF-Token doit etre present."""
        server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "server.py"
        )
        with open(server_path) as f:
            source = f.read()
        self.assertIn('response.headers["X-CSRF-Token"]', source)
        self.assertIn("generate_csrf_token(session_token)", source)

    def test_middleware_rotates_only_on_mutating_admin(self):
        """La rotation ne doit se faire que sur POST/PUT/DELETE /admin."""
        server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "server.py"
        )
        with open(server_path) as f:
            source = f.read()
        self.assertIn('if path.startswith("/admin") and method in ("POST", "PUT", "DELETE")',
                       source)

    def test_utils_js_reads_new_token_from_response(self):
        """utils.js doit lire X-CSRF-Token depuis la reponse et mettre a jour localStorage."""
        utils_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "admin", "utils.js"
        )
        with open(utils_path) as f:
            source = f.read()
        self.assertIn("res.headers.get('X-CSRF-Token')", source)
        self.assertIn("localStorage.setItem('csrf_token'", source)

    def test_setCsrfToken_persists_to_localStorage(self):
        """setCsrfToken() doit sauvegarder le token dans localStorage."""
        utils_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "admin", "utils.js"
        )
        with open(utils_path) as f:
            source = f.read()
        self.assertIn("localStorage.setItem('csrf_token', token)", source)

    def test_two_consecutive_mutations_both_succeed(self):
        """Deux POST consecutifs doivent reussir grace a la rotation du token."""
        session = _create_session()
        csrf1 = generate_csrf_token(session)
        # First use
        self.assertTrue(validate_csrf_token(session, csrf1))
        # Generate replacement (simulates server rotation)
        csrf2 = generate_csrf_token(session)
        # Second use with new token
        self.assertTrue(validate_csrf_token(session, csrf2))
        # Old token is dead
        self.assertFalse(validate_csrf_token(session, csrf1))


class TestFrontendCSRF(unittest.TestCase):
    """Verifie que le frontend envoie le token CSRF."""

    def test_utils_js_sends_csrf_header(self):
        utils_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "admin", "utils.js"
        )
        with open(utils_path) as f:
            source = f.read()
        self.assertIn("X-CSRF-Token", source)

    def test_utils_js_reads_csrf_from_storage(self):
        init_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "admin", "js", "init.js"
        )
        with open(init_path) as f:
            source = f.read()
        self.assertIn("csrf_token", source)


if __name__ == "__main__":
    unittest.main()
