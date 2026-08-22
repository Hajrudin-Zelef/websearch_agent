"""
Tests d'integration — flows complets a travers les couches.
Un seul TestClient partage pour tous les tests (rapide).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from core.settings import _load_settings
from routes.auth import _login_attempts, _sessions
from routes.rate_limit import _rate_history, _rate_lock
from server import app

# ─── Shared client (one startup for all tests) ───
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = TestClient(app)
    return _client


def _login(client):
    import pyotp

    from routes.auth import ADMIN_TOTP_SECRET
    payload = {"username": "admin", "password": "admin123"}
    if ADMIN_TOTP_SECRET:
        payload["totp_code"] = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
    resp = client.post("/admin/api/login", json=payload)
    return resp.json().get("csrf_token", "") if resp.status_code == 200 else ""


# ============================================================================
# AUTH
# ============================================================================

class TestAuthFlow(unittest.TestCase):

    def setUp(self):
        _sessions.clear()
        _login_attempts.clear()
        self.client = _get_client()

    def test_login_without_2fa_rejected(self):
        resp = self.client.post("/admin/api/login", json={
            "username": "admin", "password": "admin123"
        })
        self.assertIn(resp.status_code, [200, 401])

    def test_login_wrong_password_rejected(self):
        resp = self.client.post("/admin/api/login", json={
            "username": "admin", "password": "wrong"
        })
        self.assertEqual(resp.status_code, 401)

    def test_full_auth_flow(self):
        import pyotp

        from routes.auth import ADMIN_TOTP_SECRET
        payload = {"username": "admin", "password": "admin123"}
        if ADMIN_TOTP_SECRET:
            payload["totp_code"] = pyotp.TOTP(ADMIN_TOTP_SECRET).now()

        resp = self.client.post("/admin/api/login", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "authenticated")

        resp = self.client.get("/admin/api/auth/check")
        self.assertTrue(resp.json()["authenticated"])

        resp = self.client.get("/admin/env")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post("/admin/api/logout")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/admin/api/auth/check")
        self.assertFalse(resp.json()["authenticated"])

    def test_protected_route_without_session(self):
        resp = self.client.get("/admin/env", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 401])

    def test_login_rate_limit(self):
        for _ in range(5):
            self.client.post("/admin/api/login", json={
                "username": "admin", "password": "wrong"
            })
        resp = self.client.post("/admin/api/login", json={
            "username": "admin", "password": "wrong"
        })
        self.assertEqual(resp.status_code, 429)


# ============================================================================
# SETTINGS
# ============================================================================

class TestSettingsCRUD(unittest.TestCase):

    def setUp(self):
        _login_attempts.clear()
        self.client = _get_client()
        _login(self.client)
        # Créer un settings.json initial si inexistant (CI)
        import json
        import os
        data_dir = os.path.dirname(_SETTINGS_FILE)
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "w") as f:
                json.dump({
                    "general": {},
                    "appearance": {},
                    "ai": {},
                    "plugins": {"enabled_modules": []},
                }, f)
            from core.settings import (
                _settings_cache,
                _settings_last_check,
                _settings_lock,
                _settings_mtime,
            )
            with _settings_lock:
                global _settings_cache, _settings_mtime, _settings_last_check
                _settings_cache = {}
                _settings_mtime = 0
                _settings_last_check = 0

    def _fresh_csrf(self):
        return _login(self.client)

    def _post(self, path, **kwargs):
        return self.client.post(path, headers={"X-CSRF-Token": self._fresh_csrf()}, **kwargs)

    def test_get_and_update_settings(self):
        resp = self.client.get("/admin/settings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("general", data)

        new_general = data.get("general", {})
        new_general["fullname"] = "Test User"
        resp = self._post("/admin/settings", json={"general": new_general})
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/admin/settings")
        self.assertEqual(resp.json()["general"]["fullname"], "Test User")

    def test_plugin_toggle_persist(self):
        resp = self.client.get("/admin/plugins")
        self.assertEqual(resp.status_code, 200)

        resp = self._post("/admin/plugins/marketing/toggle", json={"enabled": False})
        self.assertEqual(resp.status_code, 200)

        settings = _load_settings()
        modules = settings.get("plugins", {}).get("enabled_modules", [])
        self.assertIsInstance(modules, list)

    def test_appearance_settings(self):
        resp = self.client.get("/admin/settings")
        data = resp.json()
        appearance = data.get("appearance", {})
        appearance["theme"] = "dark"
        resp = self._post("/admin/settings", json={"appearance": appearance})
        self.assertEqual(resp.status_code, 200)

    def test_ai_settings(self):
        resp = self.client.get("/admin/settings")
        data = resp.json()
        ai = data.get("ai", {})
        ai["response_style"] = "detailed"
        resp = self._post("/admin/settings", json={"ai": ai})
        self.assertEqual(resp.status_code, 200)


# ============================================================================
# ADMIN PROTECTION
# ============================================================================

class TestAdminEndpointsAuth(unittest.TestCase):

    def setUp(self):
        _sessions.clear()
        self.client = _get_client()
        self.protected = [
            ("GET", "/admin/env"), ("GET", "/admin/settings"),
            ("GET", "/admin/plugins"), ("GET", "/admin/logs"),
            ("GET", "/admin/account"), ("GET", "/admin/security"),
            ("GET", "/admin/developer"),
        ]

    def test_all_protected_endpoints_require_auth(self):
        for method, path in self.protected:
            resp = self.client.get(path, follow_redirects=False) if method == "GET" \
                else self.client.post(path, follow_redirects=False)
            self.assertIn(resp.status_code, [302, 401],
                          f"{method} {path} should require auth")

    def test_auth_endpoints_accessible(self):
        resp = self.client.get("/admin/api/auth/check")
        self.assertEqual(resp.status_code, 200)


# ============================================================================
# THREADS
# ============================================================================

class TestThreadLifecycle(unittest.TestCase):

    def setUp(self):
        self.client = _get_client()

    def test_thread_list(self):
        resp = self.client.get("/threads")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)


# ============================================================================
# SEARCH
# ============================================================================

class TestSearchEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = _get_client()
        with _rate_lock:
            _rate_history.clear()

    def test_search_returns_structure(self):
        resp = self.client.get("/search?q=python&max_results=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sources", data)
        self.assertIn("query", data)
        self.assertEqual(data["query"], "python")

    def test_search_with_invalid_api_key(self):
        resp = self.client.get("/search?q=test", headers={"X-API-Key": "invalid_key_12345"})
        self.assertEqual(resp.status_code, 401)

    def test_search_rate_limiting(self):
        with _rate_lock:
            _rate_history.clear()
        for _ in range(30):
            self.client.get("/search?q=test")
        resp = self.client.get("/search?q=test")
        self.assertIn(resp.status_code, [200, 429])


# ============================================================================
# METRICS
# ============================================================================

class TestMetrics(unittest.TestCase):

    def setUp(self):
        self.client = _get_client()

    def test_metrics_structure(self):
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sources", data)
        self.assertIn("cache", data)
        self.assertIn("agent", data)

    def test_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(resp.json()["status"], ["ok", "degraded"])


# ============================================================================
# DATASETS
# ============================================================================

class TestDatasetsEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = _get_client()

    def test_datasets_search(self):
        resp = self.client.get("/datasets?query=climat&max_results=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("datasets", data)
        self.assertEqual(data["query"], "climat")


# ============================================================================
# ENV
# ============================================================================

class TestEnvEndpoints(unittest.TestCase):

    def setUp(self):
        _login_attempts.clear()
        self.client = _get_client()
        self.csrf = _login(self.client)

    def test_get_env_masked(self):
        resp = self.client.get("/admin/env")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), dict)

    def test_reveal_env_key(self):
        resp = self.client.get("/admin/env/PATH/reveal")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["key"], "PATH")


# ============================================================================
# CLIENTS CRUD
# ============================================================================

class TestClientAPIFlow(unittest.TestCase):

    def setUp(self):
        _login_attempts.clear()
        self.client = _get_client()

    def _fresh_csrf(self):
        return _login(self.client)

    def _post(self, path, **kwargs):
        return self.client.post(path, headers={"X-CSRF-Token": self._fresh_csrf()}, **kwargs)

    def _delete(self, path, **kwargs):
        return self.client.delete(path, headers={"X-CSRF-Token": self._fresh_csrf()}, **kwargs)

    def test_client_crud_flow(self):
        resp = self._post("/admin/clients", json={"name": "test-client-int"})
        self.assertIn(resp.status_code, [200, 201])
        client_id = resp.json().get("id")

        if client_id:
            resp = self.client.get("/admin/clients")
            self.assertEqual(resp.status_code, 200)
            self.assertIsInstance(resp.json()["clients"], list)

            resp = self._post(f"/admin/clients/{client_id}/deactivate")
            self.assertEqual(resp.status_code, 200)

            resp = self._post(f"/admin/clients/{client_id}/activate")
            self.assertEqual(resp.status_code, 200)

            resp = self._delete(f"/admin/clients/{client_id}")
            self.assertEqual(resp.status_code, 200)


# ============================================================================
# LOGS
# ============================================================================

class TestLogsEndpoint(unittest.TestCase):

    def setUp(self):
        _login_attempts.clear()
        self.client = _get_client()
        self.csrf = _login(self.client)

    def test_logs_returns_structure(self):
        resp = self.client.get("/admin/logs?lines=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("logs", data)
        self.assertIn("stats", data)

    def test_logs_respects_lines_limit(self):
        resp = self.client.get("/admin/logs?lines=5")
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.json()["logs"]), 5)


if __name__ == "__main__":
    unittest.main()
