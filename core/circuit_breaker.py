"""
Circuit Breaker pour les sources externes.
Apres N echecs consecutifs, skip la source pendant T secondes.
"""

import threading
import time
from collections import defaultdict


class CircuitBreaker:
    """Circuit breaker par source."""

    def __init__(self, failure_threshold: int = 3, recovery_time: float = 60.0):
        self._failure_threshold = failure_threshold
        self._recovery_time = recovery_time
        self._lock = threading.Lock()
        self._failures: dict[str, int] = defaultdict(int)
        self._last_failure: dict[str, float] = {}
        self._circuit_open: dict[str, float] = {}

    def allow_request(self, source: str) -> bool:
        """Verifie si une requete est autorisee pour cette source."""
        with self._lock:
            if source in self._circuit_open:
                elapsed = time.time() - self._circuit_open[source]
                if elapsed < self._recovery_time:
                    return False  # Circuit ouvert, skip
                else:
                    # Recovery time passe -> half-open
                    del self._circuit_open[source]
                    return True
            return True

    def record_success(self, source: str):
        """Enregistre un succes — reset le compteur."""
        with self._lock:
            self._failures[source] = 0
            if source in self._circuit_open:
                del self._circuit_open[source]

    def record_failure(self, source: str):
        """Enregistre un echec — ouvre le circuit si seuil atteint."""
        with self._lock:
            self._failures[source] += 1
            self._last_failure[source] = time.time()
            if self._failures[source] >= self._failure_threshold:
                self._circuit_open[source] = time.time()

    def is_open(self, source: str) -> bool:
        """Verifie si le circuit est ouvert."""
        with self._lock:
            if source not in self._circuit_open:
                return False
            elapsed = time.time() - self._circuit_open[source]
            return elapsed < self._recovery_time

    def stats(self) -> dict:
        """Retourne les stats de tous les circuits."""
        with self._lock:
            now = time.time()
            result = {}
            all_sources = set(list(self._failures.keys()) + list(self._circuit_open.keys()))
            for source in all_sources:
                is_open = False
                if source in self._circuit_open:
                    elapsed = now - self._circuit_open[source]
                    is_open = elapsed < self._recovery_time
                result[source] = {
                    "failures": self._failures[source],
                    "state": "open" if is_open else "closed",
                }
            return result


# Instance globale
circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_time=60.0)
