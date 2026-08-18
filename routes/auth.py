"""
Authentification admin — sessions, 2FA, middleware.
Extrait de server.py lors du refactoring.
"""

from __future__ import annotations

import os
import time
import secrets
import threading
import logging
from collections import defaultdict
from pydantic import BaseModel

logger = logging.getLogger("websearch-agent")

# --- Authentication ---
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_TOTP_SECRET = os.getenv("ADMIN_TOTP_SECRET", "")

if ENVIRONMENT == "production" and (not ADMIN_PASSWORD or ADMIN_PASSWORD in ("admin123", "password", "changeme")):
    raise RuntimeError(
        "ADMIN_PASSWORD must be set to a strong value in production. "
        "Refusing to start with default/empty password."
    )

_sessions: dict[str, float] = {}  # token -> expiry timestamp
_SESSION_TTL = 86400  # 24 hours
_rate_lock = threading.Lock()  # Initialized at module level to avoid race condition


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


def _invalidate_all_sessions(keep_token: str | None = None) -> int:
    """Invalide toutes les sessions sauf keep_token. Retourne le nombre invalidé."""
    global _sessions
    now = time.time()
    to_remove = [t for t, exp in _sessions.items() if t != keep_token and now <= exp]
    for t in to_remove:
        del _sessions[t]
    return len(to_remove)


def _cleanup_sessions():
    """Nettoie les sessions expirees."""
    now = time.time()
    expired = [t for t, exp in _sessions.items() if now > exp]
    for t in expired:
        del _sessions[t]


def _set_rate_lock(lock: threading.Lock):
    """Partage le lock avec rate_limit.py."""
    global _rate_lock
    _rate_lock = lock


# --- Login brute-force protection ---
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW = 300  # 5 minutes


def _check_login_rate(ip: str) -> bool:
    """Verifie le rate limiting des tentatives de login."""
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


# --- CSRF protection ---
_csrf_tokens: dict[str, float] = {}  # token -> expiry
_CSRF_TTL = 3600  # 1 hour


def generate_csrf_token(session_token: str) -> str:
    """Genere un token CSRF lie a la session."""
    token = secrets.token_hex(16)
    _csrf_tokens[f"{session_token}:{token}"] = time.time() + _CSRF_TTL
    return token


def validate_csrf_token(session_token: str, csrf_token: str) -> bool:
    """Valide un token CSRF pour une session donnee."""
    key = f"{session_token}:{csrf_token}"
    if key not in _csrf_tokens:
        return False
    if time.time() > _csrf_tokens[key]:
        del _csrf_tokens[key]
        return False
    del _csrf_tokens[key]  # Single use
    return True


def require_admin_session(request) -> str | None:
    """Exige une session admin valide. Retourne le token ou None."""
    token = request.cookies.get("admin_session")
    if _validate_session(token):
        return token
    return None


# --- Admin routes config ---
ADMIN_STATIC_PATHS = [
    "/admin/login.html", "/admin/styles.css", "/admin/utils.js",
    "/admin/vendor", "/admin/img", "/admin/js",
    "/admin/service-worker.js", "/admin/manifest.json",
    "/admin/pwa.css", "/admin/pwa.js",
    "/admin/app.html", "/admin/test-pwa.html", "/admin/diag-pwa.html",
    "/admin/install.html",
]
ADMIN_API_LOGIN = "/admin/api/login"
ADMIN_API_LOGOUT = "/admin/api/logout"
ADMIN_API_CHECK = "/admin/api/auth/check"
