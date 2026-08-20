"""
Serveur FastAPI — bootstrap et montage des routes.
Ecoute sur 127.0.0.1:4500 (interne uniquement).

Refactore : les routes ont ete extraites dans routes/
- routes/auth.py : authentification, sessions, 2FA
- routes/rate_limit.py : rate limiting
- routes/api.py : endpoints /chat, /search, /datasets, /health, /threads
- routes/admin.py : endpoints /admin/*
"""

import os
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ADMIN_ALLOW_DOCS = os.getenv("ADMIN_ALLOW_DOCS", "false").lower() == "true"
ADMIN_ALLOW_LOCAL_CORS = os.getenv("ADMIN_ALLOW_LOCAL_CORS", "false").lower() == "true"

# Routes extraites
from routes.api import router as api_router
from routes.admin import router as admin_router
from routes.oauth import router as oauth_router
from routes.rate_limit import _cleanup_rate_history
from routes.auth import _cleanup_sessions

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_FILE = Path(__file__).parent / "data" / "websearch-agent.log"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
logging.getLogger().addHandler(file_handler)
logger = logging.getLogger("websearch-agent")

_docs_url = "/docs"
_redoc_url = "/redoc"
if ENVIRONMENT == "production" and not ADMIN_ALLOW_DOCS:
    _docs_url = None
    _redoc_url = None

app = FastAPI(
    title="WebSearch Agent",
    description="Agent de recherche web multi-sources avec interface admin.",
    version="1.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# --- GZip compression ---
app.add_middleware(GZipMiddleware, minimum_size=2048)

# --- CORS ---
_cors_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:4500", "http://127.0.0.1:4500",
    "http://localhost:3080", "http://127.0.0.1:3080",
]
if ENVIRONMENT == "production" and not ADMIN_ALLOW_LOCAL_CORS:
    _cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
    _cors_origins = [o.strip() for o in _cors_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-CSRF-Token"],
)

# --- Body size limit (10 KB max) ---
MAX_BODY_SIZE = 10 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_SIZE:
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Request body too large."},
                    )
            except (ValueError, TypeError):
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid Content-Length header."},
                )
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)


# --- Security headers ---
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if ENVIRONMENT == "production":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'"
        )
    return response


# --- Block API docs in production ---
@app.middleware("http")
async def block_docs_in_production(request: Request, call_next):
    path = request.url.path
    if ENVIRONMENT == "production" and not ADMIN_ALLOW_DOCS:
        if path in ("/docs", "/redoc", "/openapi.json"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
    return await call_next(request)


# --- Admin auth middleware ---
from routes.auth import (
    _validate_session,
    ADMIN_STATIC_PATHS,
    ADMIN_API_LOGIN,
    ADMIN_API_LOGOUT,
    ADMIN_API_CHECK,
)


@app.middleware("http")
async def admin_auth(request: Request, call_next):
    """Protege les routes admin avec authentification."""
    path = request.url.path

    if not path.startswith("/admin"):
        return await call_next(request)

    # Endpoints auth (login/logout/check) — toujours accessibles
    if path in (ADMIN_API_LOGIN, ADMIN_API_LOGOUT, ADMIN_API_CHECK):
        return await call_next(request)

    # Fichiers statiques — toujours accessibles (CSS, JS, images, etc.)
    # Check strict: path == prefix ou path.startswith(prefix + "/")
    if any(path == p or path.startswith(p + "/") for p in ADMIN_STATIC_PATHS):
        return await call_next(request)

    # Racine /admin — redirect vers login
    if path in ("/admin", "/admin/"):
        return RedirectResponse(url="/admin/login.html", status_code=302)

    # Documentation — protégée en production
    if path == "/admin/docs":
        if ENVIRONMENT == "production" and not ADMIN_ALLOW_DOCS:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        token = request.cookies.get("admin_session")
        if not _validate_session(token):
            return RedirectResponse(url="/admin/login.html", status_code=302)
        return await call_next(request)

    # Verification session pour toutes les autres routes admin
    token = request.cookies.get("admin_session")
    if not _validate_session(token):
        # Si c'est une page HTML → redirect vers login
        if path.endswith(".html") or path == "/admin":
            return RedirectResponse(url="/admin/login.html", status_code=302)
        # Sinon (API JSON) → retourner 401
        return JSONResponse(status_code=401, content={"detail": "Non authentifie"})

    return await call_next(request)


# --- CSRF protection middleware ---
from routes.auth import validate_csrf_token


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    """Vérifie le token CSRF sur les routes admin mutantes (POST/PUT/DELETE)."""
    path = request.url.path
    method = request.method

    # Only check mutating methods on admin routes
    if path.startswith("/admin") and method in ("POST", "PUT", "DELETE"):
        # Exclude login/logout/check (token not yet available or being destroyed)
        if path not in (ADMIN_API_LOGIN, ADMIN_API_LOGOUT, ADMIN_API_CHECK):
            # Exclude static files and non-API routes
            if not any(path == p or path.startswith(p + "/") for p in ADMIN_STATIC_PATHS):
                token = request.cookies.get("admin_session")
                csrf_token = request.headers.get("X-CSRF-Token")
                if not token or not csrf_token or not validate_csrf_token(token, csrf_token):
                    return JSONResponse(status_code=403, content={"detail": "CSRF token invalide"})

    return await call_next(request)


# --- Montage des routes ---
app.include_router(api_router)
app.include_router(admin_router)
app.include_router(oauth_router)


# --- Root redirect ---
@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin/login.html", status_code=302)


@app.get("/admin/")
async def admin_root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin/login.html", status_code=302)


# --- Lifecycle events ---
@app.on_event("shutdown")
async def shutdown_event():
    global _cleanup_running
    _cleanup_running = False
    from sources.content_extractor import close_session
    await close_session()
    # Don't close SQLite connections here — background threads may still
    # be writing.  The connections are cleaned up automatically on process exit.


_cleanup_running = True


@app.on_event("startup")
async def startup_event():
    """Start background cleanup task."""
    async def _periodic_cleanup():
        while _cleanup_running:
            try:
                await asyncio.sleep(60)
                _cleanup_rate_history()
                _cleanup_sessions()
            except Exception as e:
                logger.error("Cleanup error: %s", e)
    asyncio.create_task(_periodic_cleanup())

    from core.monitoring import start_snapshot_thread
    start_snapshot_thread()


# --- Main ---
if __name__ == "__main__":
    import uvicorn
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "4500"))
    uvicorn.run(app, host=HOST, port=PORT)
