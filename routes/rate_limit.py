"""
Rate limiting — sliding window, borne, sans memory leak.
Extrait de server.py lors du refactoring.
"""

import time
import threading
from collections import defaultdict, deque

_RATE_WINDOW = 60
_RATE_MAX = 30
_RATE_MAX_IPS = 10000
_rate_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_RATE_MAX + 1))
_rate_lock = threading.Lock()


def _check_rate(client_ip: str) -> bool:
    """Verifie si le client a depasse la limite de requetes."""
    now = time.time()
    window_start = now - _RATE_WINDOW
    with _rate_lock:
        if len(_rate_history) > _RATE_MAX_IPS:
            _cleanup_rate_history_locked(now)

        hits = _rate_history[client_ip]

        while hits and hits[0] < window_start:
            hits.popleft()

        if len(hits) >= _RATE_MAX:
            return False

        hits.append(now)
        return True


def _cleanup_rate_history_locked(now: float = None):
    """Nettoyage des IPs inactives (doit etre appele avec _rate_lock)."""
    if now is None:
        now = time.time()
    window_start = now - _RATE_WINDOW
    empty_ips = [
        ip for ip, hits in _rate_history.items()
        if not hits or hits[-1] < window_start
    ]
    for ip in empty_ips:
        del _rate_history[ip]


def _cleanup_rate_history():
    """Nettoyage periodique des IPs inactives."""
    now = time.time()
    with _rate_lock:
        _cleanup_rate_history_locked(now)


def _get_rate_lock():
    """Retourne le lock pour le partage avec auth.py."""
    return _rate_lock
