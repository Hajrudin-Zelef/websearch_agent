"""
Authentification admin — sessions, 2FA, middleware.
Extrait de server.py lors du refactoring.
"""

import os
import time
import secrets
from collections import defaultdict
from pydantic import BaseModel

# --- Authentication ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_TOTP_SECRET = os.getenv("ADMIN_TOTP_SECRET", "")
_sessions: dict[str, float] = {}  # token -> expiry timestamp
_SESSION_TTL = 86400  # 24 hours


def _create_session() -> str:
    """Cree un nouveau token de session."""
    token = secrets.token_hex(32)
    _sessions[token] = time.time() + _SESSION_TTL
    return token


def _validate_session(token: str) -> bool:
    """Verifie si un token de session est valide."""
    if not token or token not in _sessions:
        return False
    if time.time() > _sessions[token]:
        del _sessions[token]
        return False
    return True


def _cleanup_sessions():
    """Nettoie les sessions expirees."""
    now = time.time()
    expired = [t for t, exp in _sessions.items() if now > exp]
    for t in expired:
        del _sessions[t]


# --- Login brute-force protection ---
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW = 300  # 5 minutes
_rate_lock = None  # Sera partage avec rate_limit.py


def _set_rate_lock(lock):
    """Partage le lock avec rate_limit.py."""
    global _rate_lock
    _rate_lock = lock


def _check_login_rate(ip: str) -> bool:
    """Verifie le rate limiting des tentatives de login."""
    import threading
    if _rate_lock is None:
        _rate_lock = threading.Lock()
    now = time.time()
    with _rate_lock:
        attempts = _login_attempts[ip]
        _login_attempts[ip] = [t for t in attempts if now - t < _LOGIN_WINDOW]
        if len(_login_attempts[ip]) >= _LOGIN_MAX_ATTEMPTS:
            return False
        _login_attempts[ip].append(now)
        return True


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


# --- Admin routes config ---
ADMIN_STATIC_PATHS = [
    "/admin/login.html", "/admin/styles.css", "/admin/utils.js",
    "/admin/vendor", "/admin/img", "/admin/service-worker.js",
    "/admin/manifest.json", "/admin/pwa.css", "/admin/pwa.js",
    "/admin/app.html", "/admin/test-pwa.html", "/admin/diag-pwa.html",
    "/admin/install.html",
]
ADMIN_API_LOGIN = "/admin/api/login"
ADMIN_API_LOGOUT = "/admin/api/logout"
ADMIN_API_CHECK = "/admin/api/auth/check"
