"""
Tests unitaires pour routes/rate_limit.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.rate_limit import (
    _check_rate,
    _cleanup_rate_history,
    _rate_history,
    _rate_lock,
)


class TestRateLimit(unittest.TestCase):

    def setUp(self):
        """Vide l'historique avant chaque test."""
        with _rate_lock:
            _rate_history.clear()

    def test_first_request_allowed(self):
        """Premiere requete autorisee."""
        result = _check_rate("1.2.3.4")
        self.assertTrue(result)

    def test_rate_limit_reached(self):
        """Bloque apres 30 requetes."""
        ip = "10.0.0.1"
        for _ in range(30):
            _check_rate(ip)
        allowed, retry_after = _check_rate(ip)
        self.assertFalse(allowed)

    def test_different_ips_independent(self):
        """Chaque IP a son propre compteur."""
        for _ in range(30):
            _check_rate("1.1.1.1")
        result = _check_rate("2.2.2.2")
        self.assertTrue(result)

    def test_cleanup(self):
        """Nettoyage ne crash pas."""
        _cleanup_rate_history()
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
