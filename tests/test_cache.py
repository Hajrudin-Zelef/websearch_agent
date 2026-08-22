"""
Tests unitaires pour core/cache.py.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cache import _cache, _cache_lock, _cache_stats, _get_cached, _set_cached


class TestCache(unittest.TestCase):

    def setUp(self):
        """Vide le cache avant chaque test."""
        with _cache_lock:
            _cache.clear()

    def test_set_and_get(self):
        """Met en cache et recupere."""
        _set_cached("test query", ["tool1"], "result")
        result = _get_cached("test query", ["tool1"])
        self.assertEqual(result, "result")

    def test_cache_miss(self):
        """Retourne None si pas en cache."""
        result = _get_cached("nonexistent", ["tool1"])
        self.assertIsNone(result)

    def test_cache_wrong_tools(self):
        """Differentes tools = different cache key."""
        _set_cached("query", ["tool1"], "result1")
        result = _get_cached("query", ["tool2"])
        self.assertIsNone(result)

    def test_cache_ttl(self):
        """Cache expire apres TTL."""
        import core.cache
        old_ttl = core.cache._CACHE_TTL
        core.cache._CACHE_TTL = 0  # TTL = 0 = expire immediatement

        _set_cached("query", ["tool1"], "result")
        time.sleep(0.01)
        result = _get_cached("query", ["tool1"])
        self.assertIsNone(result)

        core.cache._CACHE_TTL = old_ttl

    def test_cache_lru_eviction(self):
        """Le cache evict LRU quand plein."""
        import core.cache
        old_max = core.cache._CACHE_MAX_SIZE
        core.cache._CACHE_MAX_SIZE = 3

        for i in range(5):
            _set_cached(f"query{i}", ["tool"], f"result{i}")

        stats = _cache_stats()
        self.assertLessEqual(stats["size"], 3)

        core.cache._CACHE_MAX_SIZE = old_max

    def test_cache_stats(self):
        """Retourne les stats du cache."""
        _set_cached("q1", ["t"], "r1")
        _set_cached("q2", ["t"], "r2")
        stats = _cache_stats()
        self.assertEqual(stats["size"], 2)


if __name__ == "__main__":
    unittest.main()
