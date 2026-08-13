"""
Clients API — gestion des clés d'API pour les apps connectées.

Permet d'identifier et tracker les apps qui utilisent l'API.
"""

import hashlib
import logging
import os
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("websearch-agent.clients")

# ============================================================================
# CONFIG
# ============================================================================

_DB_PATH = os.getenv("THREADS_DB_PATH", str(Path(__file__).parent / "data" / "threads.db"))

# ============================================================================
# SINGLETON
# ============================================================================

_db: Optional[sqlite3.Connection] = None
_db_lock = threading.Lock()


def _get_db() -> sqlite3.Connection:
    global _db
    if _db is not None:
        try:
            _db.execute("SELECT 1")
            return _db
        except Exception:
            _db = None
    with _db_lock:
        if _db is not None:
            try:
                _db.execute("SELECT 1")
                return _db
            except Exception:
                _db = None
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        _db = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _db.row_factory = sqlite3.Row
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA foreign_keys=ON")
        _init_schema(_db)
    return _db


def _init_schema(db: sqlite3.Connection):
    """Cree les tables si elles n'existent pas."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            api_key_hash TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at REAL NOT NULL,
            last_used_at REAL,
            active INTEGER DEFAULT 1,
            request_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS client_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT REFERENCES clients(id) ON DELETE CASCADE,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            status_code INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            timestamp REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_client_logs_client ON client_logs(client_id);
        CREATE INDEX IF NOT EXISTS idx_client_logs_timestamp ON client_logs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_clients_api_key_hash ON clients(api_key_hash);
    """)
    db.commit()


# ============================================================================
# API KEY GENERATION
# ============================================================================

def _generate_api_key() -> str:
    """Génère une clé d'API au format ws_xxxxx."""
    random_part = secrets.token_hex(16)
    return f"ws_{random_part}"


def _hash_api_key(api_key: str) -> str:
    """Hash une clé d'API pour le stockage sécurisé."""
    return hashlib.sha256(api_key.encode()).hexdigest()


# ============================================================================
# CLIENT CRUD
# ============================================================================

def create_client(name: str, description: str = "") -> dict:
    """Crée un nouveau client avec une clé d'API. Retourne le client avec la clé."""
    db = _get_db()
    client_id = str(uuid.uuid4())
    api_key = _generate_api_key()
    api_key_hash = _hash_api_key(api_key)
    now = time.time()

    db.execute(
        "INSERT INTO clients (id, name, api_key, api_key_hash, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (client_id, name, api_key, api_key_hash, description, now),
    )
    db.commit()

    logger.info("Client créé: %s (%s)", name, client_id)

    return {
        "id": client_id,
        "name": name,
        "api_key": api_key,  # Retournée une seule fois
        "description": description,
        "created_at": now,
        "active": True,
        "request_count": 0,
    }


def list_clients(include_inactive: bool = False) -> list[dict]:
    """Liste tous les clients."""
    db = _get_db()
    query = "SELECT * FROM clients"
    if not include_inactive:
        query += " WHERE active = 1"
    query += " ORDER BY created_at DESC"

    rows = db.execute(query).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_client(client_id: str) -> Optional[dict]:
    """Récupère un client par son ID."""
    db = _get_db()
    row = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_client_by_api_key(api_key: str) -> Optional[dict]:
    """Récupère un client par sa clé d'API (via le hash)."""
    db = _get_db()
    api_key_hash = _hash_api_key(api_key)
    row = db.execute("SELECT * FROM clients WHERE api_key_hash = ?", (api_key_hash,)).fetchone()
    if row and row["active"]:
        return _row_to_dict(row)
    return None


def deactivate_client(client_id: str) -> bool:
    """Désactive un client (révoque sa clé)."""
    db = _get_db()
    cursor = db.execute("UPDATE clients SET active = 0 WHERE id = ?", (client_id,))
    db.commit()
    return cursor.rowcount > 0


def activate_client(client_id: str) -> bool:
    """Réactive un client."""
    db = _get_db()
    cursor = db.execute("UPDATE clients SET active = 1 WHERE id = ?", (client_id,))
    db.commit()
    return cursor.rowcount > 0


def delete_client(client_id: str) -> bool:
    """Supprime un client et ses logs."""
    db = _get_db()
    cursor = db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    db.commit()
    return cursor.rowcount > 0


def regenerate_api_key(client_id: str) -> Optional[dict]:
    """Régénère la clé d'API d'un client. Retourne la nouvelle clé."""
    db = _get_db()
    client = get_client(client_id)
    if not client:
        return None

    new_api_key = _generate_api_key()
    new_api_key_hash = _hash_api_key(new_api_key)

    db.execute(
        "UPDATE clients SET api_key = ?, api_key_hash = ? WHERE id = ?",
        (new_api_key, new_api_key_hash, client_id),
    )
    db.commit()

    logger.info("Clé régénérée pour client: %s (%s)", client["name"], client_id)

    return {
        "id": client_id,
        "name": client["name"],
        "api_key": new_api_key,
    }


# ============================================================================
# REQUEST LOGGING
# ============================================================================

def log_request(
    client_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    ip_address: str = "",
    user_agent: str = "",
):
    """Log une requête API effectuée par un client."""
    db = _get_db()
    now = time.time()

    db.execute(
        """INSERT INTO client_logs (client_id, endpoint, method, status_code, ip_address, user_agent, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (client_id, endpoint, method, status_code, ip_address, user_agent, now),
    )

    # Mettre à jour le compteur et la dernière utilisation
    db.execute(
        """UPDATE clients
           SET request_count = request_count + 1, last_used_at = ?
           WHERE id = ?""",
        (now, client_id),
    )
    db.commit()


def get_client_logs(client_id: str, limit: int = 50) -> list[dict]:
    """Récupère les logs récents d'un client."""
    db = _get_db()
    rows = db.execute(
        """SELECT * FROM client_logs
           WHERE client_id = ?
           ORDER BY timestamp DESC
           LIMIT ?""",
        (client_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_client_stats() -> dict:
    """Statistiques globales sur les clients."""
    db = _get_db()

    total = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM clients WHERE active = 1").fetchone()[0]
    total_requests = db.execute("SELECT COALESCE(SUM(request_count), 0) FROM clients").fetchone()[0]

    # Top 5 des clients les plus actifs
    top_clients = db.execute(
        """SELECT name, request_count, last_used_at
           FROM clients
           WHERE active = 1
           ORDER BY request_count DESC
           LIMIT 5"""
    ).fetchall()

    return {
        "total_clients": total,
        "active_clients": active,
        "total_requests": total_requests,
        "top_clients": [dict(row) for row in top_clients],
    }


# ============================================================================
# HELPERS
# ============================================================================

def _row_to_dict(row) -> dict:
    """Convertit une row SQLite en dict (sans le hash)."""
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
        "active": bool(row["active"]),
        "request_count": row["request_count"],
    }
