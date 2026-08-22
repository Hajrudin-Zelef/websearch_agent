"""
Tests unitaires pour routes/auth.py.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.auth import (
    _cleanup_sessions,
    _create_session,
    _sessions,
    _validate_session,
)


class TestAuth(unittest.TestCase):

    def setUp(self):
        """Vide les sessions avant chaque test."""
        _sessions.clear()

    def test_create_session(self):
        """Cree une session et retourne un token."""
        token = _create_session()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)

    def test_validate_session_valid(self):
        """Valide une session existante."""
        token = _create_session()
        self.assertTrue(_validate_session(token))

    def test_validate_session_invalid(self):
        """Rejette un token invalide."""
        self.assertFalse(_validate_session("invalid_token"))

    def test_validate_session_expired(self):
        """Rejette une session expiree."""
        token = _create_session()
        _sessions[token] = time.time() - 1  # Expiree
        self.assertFalse(_validate_session(token))

    def test_cleanup_sessions(self):
        """Nettoie les sessions expirees."""
        token1 = _create_session()
        token2 = _create_session()
        _sessions[token1] = time.time() - 1  # Expiree
        _cleanup_sessions()
        self.assertNotIn(token1, _sessions)
        self.assertIn(token2, _sessions)


if __name__ == "__main__":
    unittest.main()
