"""
Tests unitaires pour OAuth2 (routes/oauth.py) et client_secret (clients.py).
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.oauth import create_access_token, verify_access_token
from clients import (
    create_client,
    authenticate_client,
    delete_client,
    _hash_value,
)


class TestOAuth2Token(unittest.TestCase):

    def setUp(self):
        self.client = create_client("test-oauth", "test")
        self.client_id = self.client["id"]
        self.client_secret = self.client["client_secret"]

    def tearDown(self):
        delete_client(self.client_id)

    def test_create_and_verify_token(self):
        """JWT créé puis vérifié avec succès."""
        token = create_access_token(self.client_id, "test-oauth")
        payload = verify_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], self.client_id)
        self.assertEqual(payload["name"], "test-oauth")
        self.assertEqual(payload["iss"], "websearch-agent")

    def test_verify_expired_token(self):
        """Token expiré est rejeté."""
        import jwt
        from datetime import datetime, timedelta, timezone
        from routes.oauth import _JWT_SECRET, _JWT_ALGORITHM

        now = datetime.now(timezone.utc)
        payload = {
            "sub": self.client_id,
            "name": "test",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
            "iss": "websearch-agent",
        }
        token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)
        result = verify_access_token(token)
        self.assertIsNone(result)

    def test_verify_invalid_token(self):
        """Token avec signature invalide est rejeté."""
        result = verify_access_token("invalid.token.here")
        self.assertIsNone(result)

    def test_verify_wrong_issuer(self):
        """Token avec mauvais issuer est rejeté."""
        import jwt
        from datetime import datetime, timedelta, timezone
        from routes.oauth import _JWT_SECRET, _JWT_ALGORITHM

        now = datetime.now(timezone.utc)
        payload = {
            "sub": self.client_id,
            "name": "test",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "iss": "wrong-issuer",
        }
        token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)
        result = verify_access_token(token)
        self.assertIsNone(result)


class TestClientSecret(unittest.TestCase):

    def setUp(self):
        self.client = create_client("test-secret", "test")
        self.client_id = self.client["id"]
        self.client_secret = self.client["client_secret"]

    def tearDown(self):
        delete_client(self.client_id)

    def test_create_client_has_secret(self):
        """Le client créé a un client_secret."""
        self.assertIn("client_secret", self.client)
        self.assertTrue(self.client["client_secret"].startswith("cs_"))
        self.assertEqual(len(self.client["client_secret"]), 43)  # cs_ + 40 hex chars

    def test_authenticate_client_valid(self):
        """Authentification avec bons credentials."""
        result = authenticate_client(self.client_id, self.client_secret)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], self.client_id)
        self.assertEqual(result["name"], "test-secret")

    def test_authenticate_client_wrong_secret(self):
        """Authentification avec mauvais secret échoue."""
        result = authenticate_client(self.client_id, "cs_wrong")
        self.assertIsNone(result)

    def test_authenticate_client_wrong_id(self):
        """Authentification avec mauvais ID échoue."""
        result = authenticate_client("nonexistent-id", self.client_secret)
        self.assertIsNone(result)

    def test_authenticate_inactive_client(self):
        """Client inactif ne peut pas s'authentifier."""
        from clients import deactivate_client
        deactivate_client(self.client_id)
        result = authenticate_client(self.client_id, self.client_secret)
        self.assertIsNone(result)

    def test_hash_value_deterministic(self):
        """Le hash est déterministe."""
        h1 = _hash_value("test")
        h2 = _hash_value("test")
        self.assertEqual(h1, h2)

    def test_hash_value_different(self):
        """Des valeurs différentes produisent des hash différents."""
        h1 = _hash_value("value1")
        h2 = _hash_value("value2")
        self.assertNotEqual(h1, h2)


class TestOAuth2Endpoint(unittest.TestCase):

    def setUp(self):
        from fastapi.testclient import TestClient
        from server import app
        self.app = app
        self.client_obj = create_client("test-endpoint", "test")
        self.client_id = self.client_obj["id"]
        self.client_secret = self.client_obj["client_secret"]

    def tearDown(self):
        delete_client(self.client_id)

    def test_token_endpoint_valid(self):
        """POST /oauth/token avec credentials valides."""
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            response = client.post("/oauth/token", json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("access_token", data)
            self.assertEqual(data["token_type"], "Bearer")
            self.assertEqual(data["expires_in"], 3600)
            self.assertEqual(data["client_id"], self.client_id)

    def test_token_endpoint_invalid_secret(self):
        """POST /oauth/token avec mauvais secret."""
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            response = client.post("/oauth/token", json={
                "client_id": self.client_id,
                "client_secret": "cs_wrong",
            })
            self.assertEqual(response.status_code, 401)

    def test_token_endpoint_invalid_client(self):
        """POST /oauth/token avec client inexistant."""
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            response = client.post("/oauth/token", json={
                "client_id": "nonexistent",
                "client_secret": "cs_anything",
            })
            self.assertEqual(response.status_code, 401)

    def test_chat_with_jwt_token(self):
        """POST /chat avec JWT Authorization header."""
        from fastapi.testclient import TestClient
        token = create_access_token(self.client_id, "test-endpoint")
        with TestClient(self.app) as client:
            response = client.post("/chat",
                json={"message": "test"},
                headers={"Authorization": f"Bearer {token}"},
            )
            # Should not return 401 (might return 200 or error depending on agent)
            self.assertNotEqual(response.status_code, 401)

    def test_chat_with_api_key_still_works(self):
        """POST /chat avec X-API-Key header fonctionne toujours (backward compat)."""
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            response = client.post("/chat",
                json={"message": "test"},
                headers={"X-API-Key": self.client_obj["api_key"]},
            )
            # Should not return 401
            self.assertNotEqual(response.status_code, 401)

    def test_chat_without_credentials_uses_ip_rate_limit(self):
        """POST /chat sans credentials tombe sur le rate limit IP."""
        from fastapi.testclient import TestClient
        with TestClient(self.app) as client:
            response = client.post("/chat", json={"message": "test"})
            # Should not return 401 (backward compatible)
            self.assertNotEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
