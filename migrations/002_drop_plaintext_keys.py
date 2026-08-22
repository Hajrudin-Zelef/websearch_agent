"""
Migration 002: Suppression des colonnes api_key et client_secret en clair.
SQLite ne supporte pas DROP COLUMN nativement, donc on recrée la table.
"""

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger("websearch-agent.migrations")

_DB_PATH = os.getenv("THREADS_DB_PATH", str(Path(__file__).parent.parent / "data" / "threads.db"))


def migrate_002_drop_plaintext_keys():
    """Supprime les colonnes api_key et client_secret en clair de la table clients."""
    if not os.path.exists(_DB_PATH):
        logger.info("DB non trouvée, migration 002 non nécessaire")
        return

    db = sqlite3.connect(_DB_PATH)
    try:
        # Vérifier si les colonnes existent encore
        cursor = db.execute("PRAGMA table_info(clients)")
        columns = [row[1] for row in cursor.fetchall()]

        if "api_key" not in columns and "client_secret" not in columns:
            logger.info("Migration 002 déjà appliquée")
            return

        logger.warning("Migration 002: suppression des colonnes api_key et client_secret en clair")

        # Vérifier que api_key_hash existe pour toutes les lignes
        if "api_key" in columns:
            rows_without_hash = db.execute(
                "SELECT COUNT(*) FROM clients WHERE api_key_hash IS NULL OR api_key_hash = ''"
            ).fetchone()[0]
            if rows_without_hash > 0:
                raise RuntimeError(
                    f"Migration impossible: {rows_without_hash} lignes sans api_key_hash. "
                    "Veuillez d'abord hasher les clés existantes."
                )

        # Recréer la table sans les colonnes en clair
        db.execute("""
            CREATE TABLE IF NOT EXISTS clients_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_key_hash TEXT UNIQUE NOT NULL,
                client_secret_hash TEXT NOT NULL DEFAULT '',
                description TEXT DEFAULT '',
                created_at REAL NOT NULL,
                last_used_at REAL,
                active INTEGER DEFAULT 1,
                request_count INTEGER DEFAULT 0,
                scopes TEXT NOT NULL DEFAULT '[]',
                rate_limit INTEGER NOT NULL DEFAULT 30
            )
        """)

        # Copier les données
        db.execute("""
            INSERT INTO clients_new (id, name, api_key_hash, client_secret_hash, description,
                                     created_at, last_used_at, active, request_count, scopes, rate_limit)
            SELECT id, name, api_key_hash, client_secret_hash, description,
                   created_at, last_used_at, active, request_count, scopes, rate_limit
            FROM clients
        """)

        # Supprimer l'ancienne table et renommer
        db.execute("DROP TABLE clients")
        db.execute("ALTER TABLE clients_new RENAME TO clients")

        # Recréer les index
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_api_key_hash ON clients(api_key_hash)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_secret_hash ON clients(client_secret_hash) WHERE client_secret_hash != ''")
        db.execute("CREATE INDEX IF NOT EXISTS idx_clients_active ON clients(active)")

        db.commit()
        logger.warning("Migration 002 terminée: colonnes api_key et client_secret supprimées")

    except Exception as e:
        db.rollback()
        logger.error("Migration 002 échouée: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_002_drop_plaintext_keys()
