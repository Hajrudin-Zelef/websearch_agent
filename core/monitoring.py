"""
Monitoring — compteurs par source, latence, erreurs.
Extrait de agent.py lors du refactoring.
"""

import time
import os
import logging
import sqlite3
import threading
from pathlib import Path
from collections import defaultdict

_METRICS_DB_PATH = os.getenv("METRICS_DB_PATH", str(Path(__file__).parent.parent / "data" / "metrics.db"))
_METRICS_RETENTION_SECONDS = 7 * 24 * 3600  # 7 jours
_METRICS_SNAPSHOT_INTERVAL = 60  # secondes


class SourceStats:
    """Statistiques par source de recherche, avec breakdown par origine (chat/search)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stats: dict[str, dict] = defaultdict(lambda: {
            "calls": 0,
            "success": 0,
            "errors": 0,
            "total_time": 0.0,
            "min_time": float("inf"),
            "max_time": 0.0,
        })
        # breakdown par origine: {"chat": {...}, "search": {...}}
        self._by_origin: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
            "calls": 0,
            "success": 0,
            "errors": 0,
            "total_time": 0.0,
        }))

    def record(self, source: str, success: bool, duration: float, origin: str = "unknown"):
        """Enregistre un appel source, avec son origine (chat/search)."""
        with self._lock:
            s = self._stats[source]
            s["calls"] += 1
            if success:
                s["success"] += 1
            else:
                s["errors"] += 1
            s["total_time"] += duration
            s["min_time"] = min(s["min_time"], duration)
            s["max_time"] = max(s["max_time"], duration)

            o = self._by_origin[origin][source]
            o["calls"] += 1
            if success:
                o["success"] += 1
            else:
                o["errors"] += 1
            o["total_time"] += duration

    def get(self, source: str) -> dict:
        """Retourne les stats d'une source."""
        with self._lock:
            s = self._stats[source].copy()
            if s["calls"] > 0:
                s["avg_time"] = s["total_time"] / s["calls"]
                s["error_rate"] = s["errors"] / s["calls"]
            else:
                s["avg_time"] = 0.0
                s["error_rate"] = 0.0
            if s["min_time"] == float("inf"):
                s["min_time"] = 0.0
            return s

    def all(self) -> dict[str, dict]:
        """Retourne les stats de toutes les sources."""
        with self._lock:
            sources = list(self._stats.keys())
        return {s: self.get(s) for s in sources}

    def by_origin(self) -> dict[str, dict]:
        """Retourne le breakdown calls/success/errors/avg_time par origine (chat/search)."""
        with self._lock:
            result = {}
            for origin, sources in self._by_origin.items():
                calls = sum(v["calls"] for v in sources.values())
                success = sum(v["success"] for v in sources.values())
                errors = sum(v["errors"] for v in sources.values())
                total_time = sum(v["total_time"] for v in sources.values())
                result[origin] = {
                    "calls": calls,
                    "success": success,
                    "errors": errors,
                    "avg_time": total_time / calls if calls > 0 else 0.0,
                    "error_rate": errors / calls if calls > 0 else 0.0,
                }
            return result

    def reset(self):
        """Remet les compteurs à zéro."""
        with self._lock:
            self._by_origin.clear()
            self._stats.clear()


class CacheStats:
    """Statistiques du cache."""

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def hit(self):
        with self._lock:
            self._hits += 1

    def miss(self):
        with self._lock:
            self._misses += 1

    def get(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "total": total,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }

    def reset(self):
        with self._lock:
            self._hits = 0
            self._misses = 0


class AgentStats:
    """Statistiques de l'agent."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls = 0
        self._success = 0
        self._errors = 0
        self._total_time = 0.0

    def record(self, success: bool, duration: float):
        with self._lock:
            self._calls += 1
            if success:
                self._success += 1
            else:
                self._errors += 1
            self._total_time += duration

    def get(self) -> dict:
        with self._lock:
            return {
                "calls": self._calls,
                "success": self._success,
                "errors": self._errors,
                "avg_time": self._total_time / self._calls if self._calls > 0 else 0.0,
                "error_rate": self._errors / self._calls if self._calls > 0 else 0.0,
            }

    def reset(self):
        with self._lock:
            self._calls = 0
            self._success = 0
            self._errors = 0
            self._total_time = 0.0


class RateLimitStats:
    """Statistiques du rate limiting."""

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = 0
        self._by_client: dict[str, int] = defaultdict(int)

    def record(self, client_key: str):
        with self._lock:
            self._hits += 1
            self._by_client[client_key] += 1

    def get(self) -> dict:
        with self._lock:
            top = sorted(self._by_client.items(), key=lambda x: x[1], reverse=True)[:10]
            return {
                "hits": self._hits,
                "top_clients": [{"key": k, "count": v} for k, v in top],
            }

    def reset(self):
        with self._lock:
            self._hits = 0
            self._by_client.clear()


# Instances globales
source_stats = SourceStats()
cache_stats = CacheStats()
agent_stats = AgentStats()
rate_limit_stats = RateLimitStats()


def get_all_metrics() -> dict:
    """Retourne toutes les métriques."""
    return {
        "sources": source_stats.all(),
        "cache": cache_stats.get(),
        "agent": agent_stats.get(),
        "rate_limit": rate_limit_stats.get(),
        "by_origin": source_stats.by_origin(),
    }


# ============================================================================
# PERSISTANCE — historique des metriques (SQLite, snapshot periodique)
# ============================================================================

_metrics_db_lock = threading.Lock()
_metrics_db: sqlite3.Connection | None = None
_snapshot_thread_started = False


def _get_metrics_db() -> sqlite3.Connection:
    global _metrics_db
    if _metrics_db is not None:
        return _metrics_db
    with _metrics_db_lock:
        if _metrics_db is not None:
            return _metrics_db
        os.makedirs(os.path.dirname(_METRICS_DB_PATH), exist_ok=True)
        db = sqlite3.connect(_METRICS_DB_PATH, check_same_thread=False, timeout=15)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("""
            CREATE TABLE IF NOT EXISTS metrics_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                sources_calls INTEGER NOT NULL,
                sources_success INTEGER NOT NULL,
                sources_errors INTEGER NOT NULL,
                cache_hits INTEGER NOT NULL,
                cache_misses INTEGER NOT NULL,
                agent_calls INTEGER NOT NULL,
                agent_success INTEGER NOT NULL,
                agent_avg_time REAL NOT NULL,
                chat_calls INTEGER NOT NULL DEFAULT 0,
                chat_avg_time REAL NOT NULL DEFAULT 0,
                search_calls INTEGER NOT NULL DEFAULT 0,
                search_avg_time REAL NOT NULL DEFAULT 0
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics_snapshots(ts DESC)")
        db.commit()
        _metrics_db = db
    return _metrics_db


def save_snapshot():
    """Enregistre un snapshot courant des metriques + purge au-dela de la retention."""
    try:
        m = get_all_metrics()
        sources = m["sources"]
        total_calls = sum(v["calls"] for v in sources.values())
        total_success = sum(v["success"] for v in sources.values())
        total_errors = sum(v["errors"] for v in sources.values())
        by_origin = m["by_origin"]
        chat = by_origin.get("chat", {})
        search = by_origin.get("search", {})

        db = _get_metrics_db()
        now = time.time()
        with _metrics_db_lock:
            db.execute(
                """INSERT INTO metrics_snapshots
                   (ts, sources_calls, sources_success, sources_errors,
                    cache_hits, cache_misses, agent_calls, agent_success, agent_avg_time,
                    chat_calls, chat_avg_time, search_calls, search_avg_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now, total_calls, total_success, total_errors,
                    m["cache"].get("hits", 0), m["cache"].get("misses", 0),
                    m["agent"].get("calls", 0), m["agent"].get("success", 0), m["agent"].get("avg_time", 0.0),
                    chat.get("calls", 0), chat.get("avg_time", 0.0),
                    search.get("calls", 0), search.get("avg_time", 0.0),
                ),
            )
            cutoff = now - _METRICS_RETENTION_SECONDS
            db.execute("DELETE FROM metrics_snapshots WHERE ts < ?", (cutoff,))
            db.commit()
    except Exception:
        logging.getLogger("websearch-agent.monitoring").warning("Snapshot metrics echoue", exc_info=True)


def get_history(since_seconds: int = 3600) -> list[dict]:
    """Retourne l'historique des snapshots depuis N secondes."""
    db = _get_metrics_db()
    cutoff = time.time() - since_seconds
    with _metrics_db_lock:
        rows = db.execute(
            "SELECT * FROM metrics_snapshots WHERE ts >= ? ORDER BY ts ASC",
            (cutoff,),
        ).fetchall()
    cols = [c[0] for c in db.execute("SELECT * FROM metrics_snapshots LIMIT 0").description]
    return [dict(zip(cols, row)) for row in rows]


def start_snapshot_thread():
    """Demarre le thread de snapshot periodique (idempotent)."""
    global _snapshot_thread_started
    if _snapshot_thread_started:
        return
    _snapshot_thread_started = True

    def _loop():
        while True:
            time.sleep(_METRICS_SNAPSHOT_INTERVAL)
            save_snapshot()

    t = threading.Thread(target=_loop, daemon=True, name="metrics-snapshot")
    t.start()
