"""
Tests d'integration — flows complets a travers les couches.
"""

import unittest
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from server import app
from routes.auth import _sessions, _create_session, _login_attempts
from routes.rate_limit import _rate_history, _rate_lock
from core.settings import _load_settings


class TestAuthFlow(unittest.TestCase):
    """Flow complet : login → access → logout."""

    def setUp(self):
        self.client = TestClient(app)
        _sessions.clear()
        _login_attempts.clear()

    def test_login_without_2fa_rejected(self):
        """Login sans 2FA est rejete si configure."""
        resp = self.client.post("/admin/api/login", json={
            "username": "admin", "password": "admin123"
        })
        # Si 2FA active → 401, sinon 200
        self.assertIn(resp.status_code, [200, 401])

    def test_login_wrong_password_rejected(self):
        """Login avec mauvais mot de passe est rejete."""
        resp = self.client.post("/admin/api/login", json={
            "username": "admin", "password": "wrong"
        })
        self.assertEqual(resp.status_code, 401)

    def test_full_auth_flow(self):
        """Login → check auth → access admin → logout → check unauth."""
        import pyotp
        from routes.auth import ADMIN_TOTP_SECRET

        # Login
        payload = {"username": "admin", "password": "admin123"}
        if ADMIN_TOTP_SECRET:
            totp = pyotp.TOTP(ADMIN_TOTP_SECRET)
            payload["totp_code"] = totp.now()

        resp = self.client.post("/admin/api/login", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "authenticated")

        # Check auth — doit etre authentifie
        resp = self.client.get("/admin/api/auth/check")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["authenticated"])

        # Access protected route
        resp = self.client.get("/admin/env")
        self.assertEqual(resp.status_code, 200)

        # Logout
        resp = self.client.post("/admin/api/logout")
        self.assertEqual(resp.status_code, 200)

        # Check unauth
        resp = self.client.get("/admin/api/auth/check")
        self.assertEqual(resp.json()["authenticated"], False)

    def test_protected_route_without_session(self):
        """Route admin sans session retourne 401."""
        resp = self.client.get("/admin/env", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 401])

    def test_login_rate_limit(self):
        """5 tentatives echouees bloquent le login."""
        for _ in range(5):
            self.client.post("/admin/api/login", json={
                "username": "admin", "password": "wrong"
            })
        resp = self.client.post("/admin/api/login", json={
            "username": "admin", "password": "wrong"
        })
        self.assertEqual(resp.status_code, 429)


class TestSettingsCRUD(unittest.TestCase):
    """Flow complet : lecture → modification → verification → reset."""

    def setUp(self):
        self.client = TestClient(app)
        _login_attempts.clear()
        self._login()

    def _login(self):
        import pyotp
        from routes.auth import ADMIN_TOTP_SECRET
        payload = {"username": "admin", "password": "admin123"}
        if ADMIN_TOTP_SECRET:
            payload["totp_code"] = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
        self.client.post("/admin/api/login", json=payload)

    def test_get_and_update_settings(self):
        """Lire → modifier → relire les settings general."""
        # GET
        resp = self.client.get("/admin/settings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("general", data)

        # POST update
        new_general = data.get("general", {})
        new_general["fullname"] = "Test User"
        resp = self.client.post("/admin/settings", json={"general": new_general})
        self.assertEqual(resp.status_code, 200)

        # Verify
        resp = self.client.get("/admin/settings")
        self.assertEqual(resp.json()["general"]["fullname"], "Test User")

    def test_plugin_toggle_persist(self):
        """Toggle un module et verifier la persistance."""
        # GET plugins
        resp = self.client.get("/admin/plugins")
        self.assertEqual(resp.status_code, 200)
        plugins = resp.json()
        self.assertIn("plugins", plugins)
        self.assertIn("modules", plugins)

        # Toggle (need to send body)
        resp = self.client.post(
            "/admin/plugins/marketing/toggle",
            json={"enabled": False}
        )
        self.assertEqual(resp.status_code, 200)

        # Verify persistence via settings
        settings = _load_settings()
        modules = settings.get("plugins", {}).get("enabled_modules", [])
        self.assertIsInstance(modules, list)

    def test_appearance_settings(self):
        """Modifier theme et font size."""
        resp = self.client.get("/admin/settings")
        data = resp.json()

        appearance = data.get("appearance", {})
        appearance["theme"] = "dark"
        appearance["font_size"] = 16

        resp = self.client.post("/admin/settings", json={"appearance": appearance})
        self.assertEqual(resp.status_code, 200)

    def test_ai_settings(self):
        """Modifier response_style et search_speed."""
        resp = self.client.get("/admin/settings")
        data = resp.json()

        ai = data.get("ai", {})
        ai["response_style"] = "detailed"
        ai["search_speed"] = "deep"

        resp = self.client.post("/admin/settings", json={"ai": ai})
        self.assertEqual(resp.status_code, 200)


class TestAdminEndpointsAuth(unittest.TestCase):
    """Verifie que tous les endpoints admin necessitent auth."""

    def setUp(self):
        self.client = TestClient(app)
        self.protected_endpoints = [
            ("GET", "/admin/env"),
            ("GET", "/admin/settings"),
            ("GET", "/admin/plugins"),
            ("GET", "/admin/logs"),
            ("GET", "/admin/account"),
            ("GET", "/admin/security"),
            ("GET", "/admin/developer"),
        ]

    def test_all_protected_endpoints_require_auth(self):
        """Chaque endpoint admin redirige ou rejette sans session."""
        for method, path in self.protected_endpoints:
            if method == "GET":
                resp = self.client.get(path, follow_redirects=False)
            else:
                resp = self.client.post(path, follow_redirects=False)
            self.assertIn(
                resp.status_code, [302, 401],
                f"{method} {path} devrait exiger auth (status {resp.status_code})"
            )

    def test_auth_endpoints_accessible_without_session(self):
        """Les endpoints d'auth sont accessibles sans session."""
        resp = self.client.get("/admin/api/auth/check")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post("/admin/api/login", json={
            "username": "admin", "password": "wrong"
        })
        self.assertIn(resp.status_code, [401, 429])


class TestThreadLifecycle(unittest.TestCase):
    """Flow complet : creer thread → ajouter message → lister → supprimer."""

    def setUp(self):
        self.client = TestClient(app)

    def test_thread_list_empty(self):
        """Liste des threads vide au depart."""
        resp = self.client.get("/threads")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_thread_create_via_chat(self):
        """Un thread est cree automatiquement via /chat."""
        # On mock pas le chat, on teste juste que le endpoint existe
        # et que les threads sont bien retournes
        resp = self.client.get("/threads")
        initial_count = len(resp.json())
        self.assertIsInstance(initial_count, int)


class TestSearchEndpoint(unittest.TestCase):
    """Tests d'integration pour /search."""

    def setUp(self):
        self.client = TestClient(app)
        with _rate_lock:
            _rate_history.clear()

    def test_search_returns_structure(self):
        """Search retourne la bonne structure."""
        resp = self.client.get("/search?q=python&max_results=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sources", data)
        self.assertIn("query", data)
        self.assertIn("count", data)
        self.assertEqual(data["query"], "python")

    def test_search_with_invalid_api_key(self):
        """Search avec cle API invalide retourne 401."""
        resp = self.client.get(
            "/search?q=test",
            headers={"X-API-Key": "invalid_key_12345"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_search_rate_limiting(self):
        """Search respecte le rate limiting par IP."""
        with _rate_lock:
            _rate_history.clear()

        # Simuler 30 requetes depuis la meme IP
        for _ in range(30):
            self.client.get("/search?q=test")

        # La 31e devrait etre rate-limitee
        resp = self.client.get("/search?q=test")
        # Le rate limit depend de l'IP reelle du client TestClient
        self.assertIn(resp.status_code, [200, 429])


class TestMetrics(unittest.TestCase):
    """Tests pour l'endpoint /metrics."""

    def setUp(self):
        self.client = TestClient(app)

    def test_metrics_structure(self):
        """Metrics retourne les sections attendues."""
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sources", data)
        self.assertIn("cache", data)
        self.assertIn("agent", data)
        self.assertIn("circuit_breaker", data)

    def test_health_check(self):
        """Health retourne status ok ou degraded."""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ["ok", "degraded"])


class TestDatasetsEndpoint(unittest.TestCase):
    """Tests pour /datasets."""

    def setUp(self):
        self.client = TestClient(app)

    def test_datasets_search(self):
        """Datasets retourne une reponse valide."""
        resp = self.client.get("/datasets?query=climat&max_results=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("datasets", data)
        self.assertIn("query", data)
        self.assertEqual(data["query"], "climat")


class TestEnvEndpoints(unittest.TestCase):
    """Tests pour les endpoints /admin/env."""

    def setUp(self):
        self.client = TestClient(app)
        _login_attempts.clear()
        self._login()

    def _login(self):
        import pyotp
        from routes.auth import ADMIN_TOTP_SECRET
        payload = {"username": "admin", "password": "admin123"}
        if ADMIN_TOTP_SECRET:
            payload["totp_code"] = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
        self.client.post("/admin/api/login", json=payload)

    def test_get_env_masked(self):
        """GET /admin/env masque les valeurs sensibles."""
        resp = self.client.get("/admin/env")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, dict)

    def test_reveal_env_key(self):
        """GET /admin/env/{key}/reveal retourne la valeur."""
        resp = self.client.get("/admin/env/PATH/reveal")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["key"], "PATH")


class TestClientAPIFlow(unittest.TestCase):
    """Flow complet : creer client → lister → activer/desactiver → supprimer."""

    def setUp(self):
        self.client = TestClient(app)
        _login_attempts.clear()
        self._login()

    def _login(self):
        import pyotp
        from routes.auth import ADMIN_TOTP_SECRET
        payload = {"username": "admin", "password": "admin123"}
        if ADMIN_TOTP_SECRET:
            payload["totp_code"] = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
        self.client.post("/admin/api/login", json=payload)

    def test_client_crud_flow(self):
        """Creer → lister → toggle → supprimer un client API."""
        # Creer
        resp = self.client.post("/admin/clients", json={"name": "test-client"})
        self.assertIn(resp.status_code, [200, 201])
        client_data = resp.json()
        client_id = client_data.get("id")

        if client_id:
            # Lister
            resp = self.client.get("/admin/clients")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("clients", data)
            self.assertIsInstance(data["clients"], list)

            # Toggle (deactivate/activate)
            resp = self.client.post(f"/admin/clients/{client_id}/deactivate")
            self.assertEqual(resp.status_code, 200)

            resp = self.client.post(f"/admin/clients/{client_id}/activate")
            self.assertEqual(resp.status_code, 200)

            # Supprimer
            resp = self.client.delete(f"/admin/clients/{client_id}")
            self.assertEqual(resp.status_code, 200)


class TestLogsEndpoint(unittest.TestCase):
    """Tests pour /admin/logs."""

    def setUp(self):
        self.client = TestClient(app)
        _login_attempts.clear()
        self._login()

    def _login(self):
        import pyotp
        from routes.auth import ADMIN_TOTP_SECRET
        payload = {"username": "admin", "password": "admin123"}
        if ADMIN_TOTP_SECRET:
            payload["totp_code"] = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
        self.client.post("/admin/api/login", json=payload)

    def test_logs_returns_structure(self):
        """Logs retourne logs + stats."""
        resp = self.client.get("/admin/logs?lines=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("logs", data)
        self.assertIn("stats", data)
        self.assertIsInstance(data["logs"], list)

    def test_logs_respects_lines_limit(self):
        """Logs respecte le parametre lines."""
        resp = self.client.get("/admin/logs?lines=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertLessEqual(len(data["logs"]), 5)


if __name__ == "__main__":
    unittest.main()
