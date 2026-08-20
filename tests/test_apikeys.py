"""
Tests de sécurité pour les clés API en DB.
P3: Suppression de la colonne api_key en clair.
"""

import unittest
import os
import sys
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import (
    create_client,
    list_clients,
    get_client,
    get_client_by_api_key,
    _hash_api_key,
    _get_db,
    _init_schema,
    delete_client,
)


class TestAPIKeyPlaintextRemoved(unittest.TestCase):
    """Vérifie que api_key en clair n'est plus stocké en DB."""

    def test_clients_table_no_plaintext_api_key(self):
        """La table clients ne doit plus avoir de colonne api_key en clair."""
        db = _get_db()
        cursor = db.execute("PRAGMA table_info(clients)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertNotIn("api_key", columns,
                         "La colonne api_key ne doit plus exister")

    def test_clients_table_no_plaintext_client_secret(self):
        """La table clients ne doit plus avoir de colonne client_secret en clair."""
        db = _get_db()
        cursor = db.execute("PRAGMA table_info(clients)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertNotIn("client_secret", columns,
                         "La colonne client_secret ne doit plus exister")

    def test_create_client_stores_only_hash(self):
        """Après create_client, la DB ne doit contenir que le hash."""
        client = create_client("test_no_plaintext")
        client_id = client["id"]

        try:
            db = _get_db()
            row = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
            # Les colonnes api_key et client_secret ne doivent pas exister
            keys = dict(row).keys() if row else {}
            self.assertNotIn("api_key", keys)
            self.assertNotIn("client_secret", keys)
            # Le hash doit être présent
            self.assertIn("api_key_hash", keys)
            self.assertIn("client_secret_hash", keys)
        finally:
            delete_client(client_id)

    def test_api_key_returned_once_at_creation(self):
        """La clé API en clair n'est retournée qu'à la création."""
        client = create_client("test_return_once")
        self.assertIn("api_key", client)
        self.assertIn("client_secret", client)
        delete_client(client["id"])

    def test_list_clients_no_plaintext(self):
        """list_clients ne doit pas retourner de clé en clair."""
        client = create_client("test_list_no_plaintext")
        try:
            clients = list_clients()
            for c in clients:
                self.assertNotIn("api_key", c)
                self.assertNotIn("client_secret", c)
        finally:
            delete_client(client["id"])

    def test_get_client_no_plaintext(self):
        """get_client ne doit pas retourner de clé en clair."""
        client = create_client("test_get_no_plaintext")
        try:
            fetched = get_client(client["id"])
            self.assertNotIn("api_key", fetched)
            self.assertNotIn("client_secret", fetched)
        finally:
            delete_client(client["id"])


class TestAPIKeyAuthentication(unittest.TestCase):
    """Vérifie que l'authentification par clé API fonctionne toujours."""

    def test_auth_by_api_key_works(self):
        """L'authentification par clé API doit fonctionner après migration."""
        client = create_client("test_auth_key")
        api_key = client["api_key"]
        try:
            found = get_client_by_api_key(api_key)
            self.assertIsNotNone(found)
            self.assertEqual(found["id"], client["id"])
        finally:
            delete_client(client["id"])

    def test_auth_by_wrong_api_key_fails(self):
        """Une mauvaise clé API doit échouer."""
        found = get_client_by_api_key("ws_wrong_key_12345")
        self.assertIsNone(found)


class TestMigrationScript(unittest.TestCase):
    """Vérifie le script de migration."""

    def test_migration_idempotent(self):
        """La migration doit être idempotente (rejouable sans erreur)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'm002', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 'migrations', '002_drop_plaintext_keys.py')
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.migrate_002_drop_plaintext_keys()
        mod.migrate_002_drop_plaintext_keys()  # Deuxième exécution


if __name__ == "__main__":
    unittest.main()
