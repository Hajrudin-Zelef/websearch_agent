"""
Cache LRU en memoire — resultats de recherche avec TTL.
Extrait de agent.py lors du refactoring.
"""

import time
import threading
from collections import OrderedDict
from core.settings import _get_setting

_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
_CACHE_TTL = 300  # 5 minutes
_CACHE_MAX_SIZE = 200
_cache_lock = threading.Lock()


def _get_cache_ttl() -> int:
    return _get_setting("cache", "ttl", _CACHE_TTL)


def _get_cache_max_size() -> int:
    return _get_setting("cache", "max_size", _CACHE_MAX_SIZE)


def _cache_key(query: str, tools: list[str]) -> str:
    return f"{query}|{'|'.join(tools)}"


def _get_cached(query: str, tools: list[str]) -> str | None:
    key = _cache_key(query, tools)
    with _cache_lock:
        if key in _cache:
            ts, result = _cache[key]
            if time.time() - ts < _get_cache_ttl():
                _cache.move_to_end(key)
                from core.monitoring import cache_stats
                cache_stats.hit()
                return result
            del _cache[key]
    from core.monitoring import cache_stats
    cache_stats.miss()
    return None


def _set_cached(query: str, tools: list[str], result: str):
    key = _cache_key(query, tools)
    with _cache_lock:
        now = time.time()
        # Remove expired entries
        while _cache:
            oldest_key = next(iter(_cache))
            ts, _ = _cache[oldest_key]
            if now - ts > _get_cache_ttl():
                del _cache[oldest_key]
            else:
                break
        # Add new entry, evict LRU if at capacity
        _cache[key] = (now, result)
        _cache.move_to_end(key)
        while len(_cache) > _get_cache_max_size():
            _cache.popitem(last=False)


def _cache_stats() -> dict:
    """Retourne les stats du cache."""
    with _cache_lock:
        return {"size": len(_cache), "max_size": _get_cache_max_size()}


def _cache_clear():
    """Vide le cache."""
    with _cache_lock:
        _cache.clear()
