"""
Threads de conversation — SQLite pour persister l'historique.

Stocke les conversations avec follow-ups, permet de reprendre un thread.
"""

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("websearch-agent.threads")

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
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at REAL NOT NULL,
            metadata TEXT DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
        CREATE INDEX IF NOT EXISTS idx_threads_updated ON threads(updated_at DESC);
    """)
    db.commit()


# ============================================================================
# API
# ============================================================================

def create_thread(first_question: str) -> str:
    """Cree un nouveau thread avec la premiere question. Retourne le thread_id."""
    db = _get_db()
    thread_id = str(uuid.uuid4())
    now = time.time()
    title = first_question[:100].strip()

    db.execute(
        "INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (thread_id, title, now, now),
    )
    db.execute(
        "INSERT INTO messages (id, thread_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), thread_id, "user", first_question, now),
    )
    db.commit()
    logger.info("Thread cree: %s (%s)", thread_id[:8], title[:50])
    return thread_id


def add_message(thread_id: str, role: str, content: str, metadata: dict | None = None) -> str:
    """Ajoute un message a un thread existant. Retourne le message_id."""
    db = _get_db()
    message_id = str(uuid.uuid4())
    now = time.time()

    db.execute(
        "INSERT INTO messages (id, thread_id, role, content, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
        (message_id, thread_id, role, content, now, json.dumps(metadata or {})),
    )
    db.execute(
        "UPDATE threads SET updated_at = ? WHERE id = ?",
        (now, thread_id),
    )
    db.commit()
    return message_id


def get_thread(thread_id: str) -> Optional[dict]:
    """Retourne un thread avec tous ses messages."""
    db = _get_db()
    thread = db.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
    if not thread:
        return None

    messages = db.execute(
        "SELECT * FROM messages WHERE thread_id = ? ORDER BY created_at ASC",
        (thread_id,),
    ).fetchall()

    return {
        "id": thread["id"],
        "title": thread["title"],
        "created_at": thread["created_at"],
        "updated_at": thread["updated_at"],
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "created_at": m["created_at"],
                "metadata": json.loads(m["metadata"]) if m["metadata"] else {},
            }
            for m in messages
        ],
    }


def list_threads(limit: int = 50) -> list[dict]:
    """Liste les threads tries par derniere activite."""
    db = _get_db()
    rows = db.execute(
        "SELECT id, title, created_at, updated_at FROM threads ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()

    return [
        {
            "id": r["id"],
            "title": r["title"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def delete_thread(thread_id: str) -> bool:
    """Supprime un thread et ses messages. Retourne True si supprime."""
    db = _get_db()
    cursor = db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
    db.commit()
    deleted = cursor.rowcount > 0
    if deleted:
        logger.info("Thread supprime: %s", thread_id[:8])
    return deleted


def get_thread_context(thread_id: str, max_messages: int = 10) -> list[dict]:
    """Retourne les derniers messages d'un thread pour le contexte LLM."""
    db = _get_db()
    messages = db.execute(
        "SELECT role, content FROM messages WHERE thread_id = ? ORDER BY created_at DESC LIMIT ?",
        (thread_id, max_messages),
    ).fetchall()

    # Inverser pour avoir l'ordre chronologique
    return [
        {"role": m["role"], "content": m["content"]}
        for m in reversed(messages)
    ]
