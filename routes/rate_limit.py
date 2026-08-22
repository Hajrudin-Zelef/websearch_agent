"""
Rate limiting — sliding window, borne, sans memory leak.
Supporte des limites custom par client.
Extrait de server.py lors du refactoring.
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import defaultdict, deque

_RATE_WINDOW = 60
_RATE_MAX = 30  # Default limit (per IP or per client)
_RATE_MAX_IPS = 10000
_RATE_MAX_ABSOLUTE = int(os.getenv("RATE_MAX_ABSOLUTE", "10000"))
_rate_history: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = threading.Lock()


def _check_rate(key: str, max_requests: int = _RATE_MAX) -> tuple[bool, int]:
    """Verifie si la cle a depasse la limite de requetes.

    Args:
        key: Cle de rate limit (IP, api_key, client_id, etc.)
        max_requests: Nombre max de requetes dans la fenetre (defaut: 30)

    Returns:
        Tuple (allowed: bool, retry_after: int seconds)
    """
    max_requests = max(1, min(max_requests, _RATE_MAX_ABSOLUTE))
    now = time.time()
    window_start = now - _RATE_WINDOW
    with _rate_lock:
        if len(_rate_history) > _RATE_MAX_IPS:
            _cleanup_rate_history_locked(now)

        hits = _rate_history[key]

        # Manual cleanup: remove entries outside window
        while hits and hits[0] < window_start:
            hits.popleft()

        if len(hits) >= max_requests:
            oldest = hits[0] if hits else now
            retry_after = math.ceil(_RATE_WINDOW - (now - oldest))
            return False, max(1, retry_after)

        hits.append(now)
        return True, 0


def _cleanup_rate_history_locked(now: float = None):
    """Nettoyage des cles inactives (doit etre appele avec _rate_lock)."""
    if now is None:
        now = time.time()
    window_start = now - _RATE_WINDOW
    empty_keys = [
        key for key, hits in _rate_history.items()
        if not hits or hits[-1] < window_start
    ]
    for key in empty_keys:
        del _rate_history[key]


def _cleanup_rate_history():
    """Nettoyage periodique des cles inactives."""
    now = time.time()
    with _rate_lock:
        _cleanup_rate_history_locked(now)


def _get_rate_lock():
    """Retourne le lock pour le partage avec auth.py."""
    return _rate_lock
