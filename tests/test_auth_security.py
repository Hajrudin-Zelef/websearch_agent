"""
Tests de sécurité pour l'authentification admin.
P1: Constant-time comparison + hash Argon2id + migration auto.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConstantTimeComparison(unittest.TestCase):
    """Vérifie que la comparaison utilise secrets.compare_digest (constant-time)."""

    def test_login_uses_secrets_compare_digest(self):
        """Le code de login doit importer et utiliser secrets.compare_digest."""
        import inspect

        from routes import admin
        source = inspect.getsource(admin.login)
        self.assertIn("secrets.compare_digest", source,
                       "login() doit utiliser secrets.compare_digest pour la comparaison")

    def test_password_change_uses_secrets_compare_digest(self):
        """Le changement de mot de passe doit utiliser secrets.compare_digest."""
        import inspect

        from routes import admin
        source = inspect.getsource(admin.update_account_password)
        self.assertIn("secrets.compare_digest", source,
                       "update_account_password() doit utiliser secrets.compare_digest")

    def test_no_direct_password_comparison(self):
        """Aucune comparaison directe de mot de passe avec != ne doit exister."""
        import inspect

        from routes import admin
        source = inspect.getsource(admin)
        # Cherche les comparaisons suspectes: req.password != ou current !=
        lines = source.split('\n')
        suspicious = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if '!=' in stripped and ('password' in stripped.lower() or 'current' in stripped.lower()):
                if 'ADMIN_PASSWORD' in stripped and 'secrets.compare_digest' not in stripped:
                    suspicious.append(f"  L{i}: {stripped}")
        self.assertEqual(suspicious, [],
                         "Comparaisons de password non constant-time trouvées:\n" +
                         "\n".join(suspicious))


class TestPasswordHashing(unittest.TestCase):
    """Vérifie le hashing Argon2id des mots de passe."""

    def test_argon2_importable(self):
        """argon2 doit être installé et importable."""
        import argon2
        self.assertTrue(hasattr(argon2, 'PasswordHasher'))

    def test_hash_password_returns_string(self):
        """hash_password doit retourner un hash Argon2."""
        from core.password import hash_password
        h = hash_password("test_password_123")
        self.assertIsInstance(h, str)
        self.assertTrue(h.startswith("$argon2"))

    def test_verify_password_correct(self):
        """verify_password doit retourner True pour le bon mot de passe."""
        from core.password import hash_password, verify_password
        h = hash_password("my_secret")
        self.assertTrue(verify_password("my_secret", h))

    def test_verify_password_incorrect(self):
        """verify_password doit retourner False pour un mauvais mot de passe."""
        from core.password import hash_password, verify_password
        h = hash_password("my_secret")
        self.assertFalse(verify_password("wrong_password", h))

    def test_hash_unique_per_call(self):
        """Deux hashs du même mot de passe doivent être différents (salt aléatoire)."""
        from core.password import hash_password
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        self.assertNotEqual(h1, h2)


class TestPasswordMigration(unittest.TestCase):
    """Vérifie la migration auto ADMIN_PASSWORD → ADMIN_PASSWORD_HASH."""

    def test_migrate_legacy_password(self):
        """ADMIN_PASSWORD legacy doit être migré vers ADMIN_PASSWORD_HASH."""
        from core.password import (
            migrate_legacy_password,
            verify_password,
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("ADMIN_USER=admin\n")
            f.write("ADMIN_PASSWORD=legacy_pass_123\n")
            f.write("OPENROUTER_API_KEY=sk-test\n")
            env_path = f.name

        try:
            result = migrate_legacy_password(Path(env_path))
            self.assertTrue(result["migrated"], "La migration doit retourner True")

            # Lire le fichier .env mis à jour
            content = Path(env_path).read_text()
            self.assertNotIn("ADMIN_PASSWORD=", content,
                             "ADMIN_PASSWORD ne doit plus être en clair")
            self.assertIn("ADMIN_PASSWORD_HASH=", content,
                          "ADMIN_PASSWORD_HASH doit être présent")

            # Extraire le hash et vérifier
            for line in content.splitlines():
                if line.startswith("ADMIN_PASSWORD_HASH="):
                    stored_hash = line.split("=", 1)[1]
                    self.assertTrue(verify_password("legacy_pass_123", stored_hash),
                                    "Le hash doit correspondre au mot de passe legacy")
                    break
            else:
                self.fail("ADMIN_PASSWORD_HASH non trouvé dans le fichier")
        finally:
            os.unlink(env_path)

    def test_no_migration_when_hash_exists(self):
        """Si ADMIN_PASSWORD_HASH existe déjà, pas de migration."""
        from core.password import migrate_legacy_password

        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("ADMIN_USER=admin\n")
            f.write("ADMIN_PASSWORD=old_pass\n")
            f.write("ADMIN_PASSWORD_HASH=$argon2id$test\n")
            env_path = f.name

        try:
            result = migrate_legacy_password(Path(env_path))
            self.assertFalse(result["migrated"])
        finally:
            os.unlink(env_path)

    def test_no_migration_when_no_password(self):
        """Si ni ADMIN_PASSWORD ni ADMIN_PASSWORD_HASH, pas de migration."""
        from core.password import migrate_legacy_password

        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("ADMIN_USER=admin\n")
            f.write("OPENROUTER_API_KEY=sk-test\n")
            env_path = f.name

        try:
            result = migrate_legacy_password(Path(env_path))
            self.assertFalse(result["migrated"])
        finally:
            os.unlink(env_path)

    def test_admin_password_not_in_env_after_startup(self):
        """Au démarrage, ADMIN_PASSWORD ne doit pas persister en clair."""
        from core.password import (
            hash_password,
            migrate_legacy_password,
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("ADMIN_PASSWORD=secret123\n")
            f.write("ADMIN_PASSWORD_HASH=" + hash_password("secret123") + "\n")
            env_path = f.name

        try:
            # Simule le démarrage: load + migrate
            result = migrate_legacy_password(Path(env_path))
            content = Path(env_path).read_text()
            self.assertNotIn("ADMIN_PASSWORD=secret123", content)
        finally:
            os.unlink(env_path)


class TestLoginNegative(unittest.TestCase):
    """Tests négatifs pour le login."""

    def test_wrong_password_returns_401_no_field_leak(self):
        """Mauvais mot de passe → 401, pas d'info sur quel champ est faux."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        from routes.admin import login
        from routes.auth import LoginRequest

        request = MagicMock()
        request.client.host = "127.0.0.1"

        req = LoginRequest(username="admin", password="wrong_password", totp_code=None)

        with patch('routes.auth.ADMIN_USER', 'admin'), \
             patch('routes.auth._check_login_rate', return_value=True), \
             patch('routes.auth.ADMIN_TOTP_SECRET', ''):
            # Patch ADMIN_PASSWORD_HASH to require hash verification
            from core.password import hash_password
            with patch('routes.auth.ADMIN_PASSWORD_HASH', hash_password("correct_password")):
                with patch('routes.auth.ADMIN_PASSWORD', None):
                    import asyncio
                    try:
                        asyncio.run(login(req, request))
                        self.fail("Devrait lever HTTPException 401")
                    except HTTPException as e:
                        self.assertEqual(e.status_code, 401)
                        self.assertEqual(e.detail, "Identifiants incorrects")


if __name__ == "__main__":
    unittest.main()
