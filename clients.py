"""
Clients API — gestion des clés d'API pour les apps connectées.

Permet d'identifier et tracker les apps qui utilisent l'API.
"""

import hashlib
import json
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

# Available scopes for API clients
AVAILABLE_SCOPES = {
    "read": "Lire les conversations et rechercher",
    "write": "Envoyer des messages et creer des threads",
    "admin": "Gerer les settings, clients et administration",
}
DEFAULT_SCOPES = ["read", "write"]
DEFAULT_RATE_LIMIT = 30  # requests per 60s window

# ============================================================================
# SINGLETON
# ============================================================================

_db: Optional[sqlite3.Connection] = None
_db_lock = threading.Lock()
_write_lock = threading.Lock()  # Protects write operations


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
        _db = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=15)
        _db.row_factory = sqlite3.Row
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA synchronous=NORMAL")
        _db.execute("PRAGMA foreign_keys=ON")
        _db.execute("PRAGMA cache_size=-8000")
        _db.execute("PRAGMA busy_timeout=5000")
        _db.execute("PRAGMA temp_store=MEMORY")
        _db.execute("PRAGMA mmap_size=268435456")
        _db.execute("PRAGMA wal_autocheckpoint=1000")
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
            client_secret TEXT UNIQUE NOT NULL DEFAULT '',
            client_secret_hash TEXT UNIQUE NOT NULL DEFAULT '',
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
            timestamp REAL NOT NULL,
            query TEXT,
            tools_used TEXT,
            path TEXT,
            models_used TEXT,
            response_time_ms INTEGER,
            cached INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_client_logs_client ON client_logs(client_id);
        CREATE INDEX IF NOT EXISTS idx_client_logs_timestamp ON client_logs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_client_logs_client_time ON client_logs(client_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_clients_api_key_hash ON clients(api_key_hash);
    """)

    # Migration: add client_secret columns if missing
    cursor = db.execute("PRAGMA table_info(clients)")
    columns = [row[1] for row in cursor.fetchall()]
    if "client_secret" not in columns:
        db.execute("ALTER TABLE clients ADD COLUMN client_secret TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE clients ADD COLUMN client_secret_hash TEXT NOT NULL DEFAULT ''")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_secret ON clients(client_secret) WHERE client_secret != ''")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_secret_hash ON clients(client_secret_hash) WHERE client_secret_hash != ''")
    if "scopes" not in columns:
        db.execute("ALTER TABLE clients ADD COLUMN scopes TEXT NOT NULL DEFAULT '[]'")
    if "rate_limit" not in columns:
        db.execute(f"ALTER TABLE clients ADD COLUMN rate_limit INTEGER NOT NULL DEFAULT {DEFAULT_RATE_LIMIT}")
    db.commit()


# ============================================================================
# API KEY GENERATION
# ============================================================================

def _generate_api_key() -> str:
    """Génère une clé d'API au format ws_xxxxx."""
    random_part = secrets.token_hex(16)
    return f"ws_{random_part}"


def _generate_client_secret() -> str:
    """Génère un client_secret au format cs_xxxxx."""
    random_part = secrets.token_hex(20)
    return f"cs_{random_part}"


def _hash_value(value: str) -> str:
    """Hash une valeur pour le stockage sécurisé."""
    return hashlib.sha256(value.encode()).hexdigest()


def _hash_api_key(api_key: str) -> str:
    """Hash une clé d'API pour le stockage sécurisé."""
    return _hash_value(api_key)


# ============================================================================
# CLIENT CRUD
# ============================================================================

def create_client(name: str, description: str = "", scopes: list[str] | None = None, rate_limit: int = DEFAULT_RATE_LIMIT) -> dict:
    """Crée un nouveau client avec une clé d'API et un client_secret. Retourne le client avec les credentials."""
    db = _get_db()
    client_id = str(uuid.uuid4())
    api_key = _generate_api_key()
    api_key_hash = _hash_api_key(api_key)
    client_secret = _generate_client_secret()
    client_secret_hash = _hash_value(client_secret)
    scopes = scopes if scopes is not None else DEFAULT_SCOPES.copy()
    now = time.time()

    with _write_lock:
        db.execute(
            "INSERT INTO clients (id, name, api_key, api_key_hash, client_secret, client_secret_hash, description, scopes, rate_limit, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (client_id, name, api_key, api_key_hash, client_secret, client_secret_hash, description, json.dumps(scopes), rate_limit, now),
        )
        db.commit()

    logger.info("Client créé: %s (%s)", name, client_id)

    return {
        "id": client_id,
        "name": name,
        "api_key": api_key,
        "client_secret": client_secret,
        "description": description,
        "scopes": scopes,
        "rate_limit": rate_limit,
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


def authenticate_client(client_id: str, client_secret: str) -> Optional[dict]:
    """Authentifie un client via client_id + client_secret (pour OAuth2 token endpoint)."""
    db = _get_db()
    row = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not row or not row["active"]:
        return None
    stored_hash = row["client_secret_hash"]
    if not stored_hash:
        return None
    if _hash_value(client_secret) != stored_hash:
        return None
    return _row_to_dict(row)


def deactivate_client(client_id: str) -> bool:
    """Désactive un client (révoque sa clé)."""
    db = _get_db()
    with _write_lock:
        cursor = db.execute("UPDATE clients SET active = 0 WHERE id = ?", (client_id,))
        db.commit()
    return cursor.rowcount > 0


def activate_client(client_id: str) -> bool:
    """Réactive un client."""
    db = _get_db()
    with _write_lock:
        cursor = db.execute("UPDATE clients SET active = 1 WHERE id = ?", (client_id,))
        db.commit()
    return cursor.rowcount > 0


def delete_client(client_id: str) -> bool:
    """Supprime un client et ses logs."""
    db = _get_db()
    with _write_lock:
        cursor = db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        db.commit()
    return cursor.rowcount > 0


def regenerate_api_key(client_id: str) -> Optional[dict]:
    """Régénère la clé d'API et le client_secret d'un client. Retourne les nouveaux credentials."""
    db = _get_db()
    client = get_client(client_id)
    if not client:
        return None

    new_api_key = _generate_api_key()
    new_api_key_hash = _hash_api_key(new_api_key)
    new_secret = _generate_client_secret()
    new_secret_hash = _hash_value(new_secret)

    db.execute(
        "UPDATE clients SET api_key = ?, api_key_hash = ?, client_secret = ?, client_secret_hash = ? WHERE id = ?",
        (new_api_key, new_api_key_hash, new_secret, new_secret_hash, client_id),
    )
    db.commit()

    logger.info("Clé régénérée pour client: %s (%s)", client["name"], client_id)

    return {
        "id": client_id,
        "name": client["name"],
        "api_key": new_api_key,
        "client_secret": new_secret,
    }


def update_client_scopes(client_id: str, scopes: list[str]) -> Optional[dict]:
    """Met à jour les scopes d'un client. Retourne le client mis à jour."""
    db = _get_db()
    client = get_client(client_id)
    if not client:
        return None

    # Validate scopes
    invalid = set(scopes) - set(AVAILABLE_SCOPES.keys())
    if invalid:
        raise ValueError(f"Scopes invalides: {', '.join(invalid)}")

    with _write_lock:
        db.execute(
            "UPDATE clients SET scopes = ? WHERE id = ?",
            (json.dumps(scopes), client_id),
        )
        db.commit()

    logger.info("Scopes mis à jour pour client %s: %s", client_id, scopes)
    return get_client(client_id)


def update_client_rate_limit(client_id: str, rate_limit: int) -> Optional[dict]:
    """Met à jour le rate limit d'un client (requests per 60s). Retourne le client mis à jour."""
    db = _get_db()
    client = get_client(client_id)
    if not client:
        return None

    if rate_limit < 1 or rate_limit > 10000:
        raise ValueError("Rate limit doit etre entre 1 et 10000")

    with _write_lock:
        db.execute(
            "UPDATE clients SET rate_limit = ? WHERE id = ?",
            (rate_limit, client_id),
        )
        db.commit()

    logger.info("Rate limit mis à jour pour client %s: %d", client_id, rate_limit)
    return get_client(client_id)


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
    metadata: dict = None,
):
    """Log une requête API effectuée par un client avec métadonnées."""
    db = _get_db()
    now = time.time()

    # Extraire les métadonnées de l'agent
    query = ""
    tools_used = ""
    path = ""
    models_used = ""
    response_time_ms = 0
    cached = 0

    if metadata:
        query = metadata.get("query", "")
        tools_used = ",".join(metadata.get("tools_used", []))
        path = metadata.get("path", "")
        models_used = ",".join(metadata.get("models_used", []))
        response_time_ms = metadata.get("response_time_ms", 0)
        cached = 1 if metadata.get("cached", False) else 0

    with _write_lock:
        db.execute(
            """INSERT INTO client_logs
               (client_id, endpoint, method, status_code, ip_address, user_agent, timestamp,
                query, tools_used, path, models_used, response_time_ms, cached)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (client_id, endpoint, method, status_code, ip_address, user_agent, now,
             query, tools_used, path, models_used, response_time_ms, cached),
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
    scopes_raw = row["scopes"] if "scopes" in row.keys() else "[]"
    try:
        scopes = json.loads(scopes_raw)
    except (json.JSONDecodeError, TypeError):
        scopes = []
    rate_limit = row["rate_limit"] if "rate_limit" in row.keys() else DEFAULT_RATE_LIMIT
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
        "active": bool(row["active"]),
        "request_count": row["request_count"],
        "scopes": scopes,
        "rate_limit": rate_limit,
    }
