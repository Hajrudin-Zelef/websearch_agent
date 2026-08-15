"""
Monitoring — compteurs par source, latence, erreurs.
Extrait de agent.py lors du refactoring.
"""

import time
import threading
from collections import defaultdict


class SourceStats:
    """Statistiques par source de recherche."""

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

    def record(self, source: str, success: bool, duration: float):
        """Enregistre une appels source."""
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

    def reset(self):
        """Remet les compteurs à zéro."""
        with self._lock:
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
    }
