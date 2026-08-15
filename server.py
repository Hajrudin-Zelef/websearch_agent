"""
Serveur FastAPI — endpoint POST /chat avec rate limiting et validation.
Ecoute sur 127.0.0.1:4500 (interne uniquement).

Optimisations :
- run_agent_async (ne bloque pas l'event loop)
- Rate limiter sans memory leak (deque borné)
- Validation Pydantic stricte
- Threads SQLite pour l'historique et les follow-ups
- Panneau d'administration web
"""

import os
import re
import time
import asyncio
import logging
import secrets
import threading
import unicodedata
from pathlib import Path
from collections import defaultdict, deque, OrderedDict
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

from agent import run_agent_async, REFUSAL_MARKERS, MODEL_POOL, _get_refusal_markers
from sources.datasets import datasets_search
from sources import SOURCES
from sources.router import INTENT_INDEX, DOMAIN_INDEX, TOOL_LEVELS
from threads import (
    create_thread,
    add_message,
    get_thread,
    list_threads,
    delete_thread,
    get_thread_context,
)
from clients import (
    get_client_by_api_key,
    log_request,
    create_client,
    list_clients,
    get_client,
    deactivate_client,
    activate_client,
    delete_client,
    regenerate_api_key,
    get_client_logs,
    get_client_stats,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("websearch-agent")

app = FastAPI(title="WebSearch Agent")

# --- GZip compression (responses > 2KB — skip small responses) ---
app.add_middleware(GZipMiddleware, minimum_size=2048)


@app.on_event("shutdown")
async def shutdown_event():
    from sources.content_extractor import close_session
    await close_session()
    # Close SQLite connections gracefully
    try:
        from threads import _db as threads_db
        if threads_db:
            threads_db.close()
    except Exception:
        pass
    try:
        from clients import _db as clients_db
        if clients_db:
            clients_db.close()
    except Exception:
        pass


@app.on_event("startup")
async def startup_event():
    """Start background cleanup task."""
    async def _periodic_cleanup():
        while True:
            try:
                await asyncio.sleep(60)
                _cleanup_rate_history()
                _cleanup_sessions()
            except Exception as e:
                logger.error("Cleanup error: %s", e)
    asyncio.create_task(_periodic_cleanup())

# --- Paths ---
BASE_DIR = Path(__file__).parent
ADMIN_DIR = BASE_DIR / "admin"
ENV_FILE = BASE_DIR / ".env"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "4500"))

# --- Authentication ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_TOTP_SECRET = os.getenv("ADMIN_TOTP_SECRET", "")
_sessions: dict[str, float] = {}  # token -> expiry timestamp
_SESSION_TTL = 86400  # 24 hours


def _create_session() -> str:
    """Crée un nouveau token de session."""
    token = secrets.token_hex(32)
    _sessions[token] = time.time() + _SESSION_TTL
    return token


def _validate_session(token: str) -> bool:
    """Vérifie si un token de session est valide."""
    if not token or token not in _sessions:
        return False
    if time.time() > _sessions[token]:
        del _sessions[token]
        return False
    return True


def _cleanup_sessions():
    """Nettoie les sessions expirées."""
    now = time.time()
    expired = [t for t, exp in _sessions.items() if now > exp]
    for t in expired:
        del _sessions[t]

# --- CORS (origines explicites uniquement) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:4500", "http://127.0.0.1:4500", "http://localhost:3080", "http://127.0.0.1:3080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# --- Body size limit (10 KB max) ---
MAX_BODY_SIZE = 10 * 1024  # 10 KB


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"error": "Request body too large."},
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
    return response


# --- Admin Authentication ---
ADMIN_STATIC_PATHS = ["/admin/login.html", "/admin/styles.css", "/admin/utils.js", "/admin/vendor", "/admin/img", "/admin/service-worker.js", "/admin/manifest.json", "/admin/pwa.css", "/admin/pwa.js", "/admin/app.html", "/admin/test-pwa.html", "/admin/diag-pwa.html", "/admin/install.html"]
ADMIN_API_LOGIN = "/admin/api/login"
ADMIN_API_LOGOUT = "/admin/api/logout"
ADMIN_API_CHECK = "/admin/api/auth/check"


@app.middleware("http")
async def admin_auth(request: Request, call_next):
    """Protège les routes admin avec authentification."""
    path = request.url.path

    # Skip si ce n'est pas une route admin
    if not path.startswith("/admin"):
        return await call_next(request)

    # Skip les endpoints de login et les assets statiques
    if path == ADMIN_API_LOGIN or path == ADMIN_API_LOGOUT or path == ADMIN_API_CHECK:
        return await call_next(request)

    # Skip les fichiers statiques (CSS, JS, images, vendor)
    if any(path.startswith(p) for p in ADMIN_STATIC_PATHS):
        return await call_next(request)

    # Skip la racine /admin (redirige vers login)
    if path == "/admin":
        return await call_next(request)

    # Vérifier le token de session
    token = request.cookies.get("admin_session")
    if not _validate_session(token):
        return RedirectResponse(url="/admin/login.html", status_code=302)

    return await call_next(request)


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


# --- Login brute-force protection ---
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW = 300  # 5 minutes


def _check_login_rate(ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        attempts = _login_attempts[ip]
        # Remove old attempts
        _login_attempts[ip] = [t for t in attempts if now - t < _LOGIN_WINDOW]
        if len(_login_attempts[ip]) >= _LOGIN_MAX_ATTEMPTS:
            return False
        _login_attempts[ip].append(now)
        return True


@app.post("/admin/api/login")
async def login(req: LoginRequest, request: Request):
    """Authentifie l'admin et crée une session."""
    client_ip = request.client.host if request.client else "unknown"

    if not _check_login_rate(client_ip):
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessayez dans 5 minutes.")

    if req.username != ADMIN_USER or req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    # Vérifier le 2FA si configuré
    if ADMIN_TOTP_SECRET:
        if not req.totp_code:
            raise HTTPException(status_code=401, detail="Code 2FA requis")

        import pyotp
        totp = pyotp.TOTP(ADMIN_TOTP_SECRET)
        if not totp.verify(req.totp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Code 2FA invalide")

    token = _create_session()
    response = JSONResponse({"status": "authenticated", "token": token})
    response.set_cookie(
        "admin_session",
        token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="strict",
        max_age=_SESSION_TTL,
    )
    logger.info("Admin connecté")
    return response


@app.post("/admin/api/logout")
async def logout(request: Request):
    """Déconnecte l'admin."""
    token = request.cookies.get("admin_session")
    if token and token in _sessions:
        del _sessions[token]
    response = JSONResponse({"status": "disconnected"})
    response.delete_cookie("admin_session")
    return response


@app.get("/admin/api/auth/check")
async def check_auth(request: Request):
    """Vérifie si l'admin est authentifié."""
    token = request.cookies.get("admin_session")
    if _validate_session(token):
        return {"authenticated": True}
    return {"authenticated": False}


@app.get("/admin/api/2fa/setup")
async def setup_2fa():
    """Retourne les informations de setup 2FA (QR code URL et secret)."""
    if not ADMIN_TOTP_SECRET:
        return {"enabled": False, "message": "2FA non configuré"}

    import pyotp
    totp = pyotp.TOTP(ADMIN_TOTP_SECRET)
    provisioning_uri = totp.provisioning_uri(
        name=ADMIN_USER,
        issuer_name="WebSearch Agent"
    )

    return {
        "enabled": True,
        "secret": ADMIN_TOTP_SECRET,
        "qr_url": provisioning_uri,
    }


# --- API Key verification (optionnel, backward compatible) ---
# Les routes qui nécessitent une API key
PROTECTED_ROUTES = ["/chat", "/datasets"]
# Les routes admin qui ne nécessitent pas de clé API
ADMIN_ROUTES = ["/admin"]


@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    """Vérifie la clé d'API pour les routes protégées (optionnel)."""
    path = request.url.path

    # Skip si ce n'est pas une route protégée
    if not any(path.startswith(route) for route in PROTECTED_ROUTES):
        return await call_next(request)

    # Extraire la clé d'API du header
    api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")

    logger.info("[API-Key] Route: %s, Key present: %s", path, bool(api_key))

    # Si pas de clé, laisser passer (backward compatible)
    if not api_key:
        return await call_next(request)

    # Vérifier la clé
    client = get_client_by_api_key(api_key)
    if not client:
        logger.warning("[API-Key] Invalid key for route %s", path)
        return JSONResponse(
            status_code=401,
            content={"error": "Clé d'API invalide ou désactivée."},
        )

    # Attacher le client à la request pour logging
    request.state.client = client

    # Exécuter la requête
    response = await call_next(request)

    # Logger la requête en background (ne bloque pas)
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "")
    agent_metadata = getattr(request.state, "agent_metadata", None)
    asyncio.create_task(asyncio.to_thread(
        log_request,
        client_id=client["id"],
        endpoint=path,
        method=request.method,
        status_code=response.status_code,
        ip_address=client_ip,
        user_agent=user_agent,
        metadata=agent_metadata,
    ))

    return response

# --- Rate limiting (sliding window, borné, sans memory leak) ---
_RATE_WINDOW = 60
_RATE_MAX = 30
_RATE_MAX_IPS = 10000
_rate_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_RATE_MAX + 1))
_rate_lock = threading.Lock()


def _check_rate(client_ip: str) -> bool:
    now = time.time()
    window_start = now - _RATE_WINDOW
    with _rate_lock:
        # Si trop d'IPs, nettoyer d'abord
        if len(_rate_history) > _RATE_MAX_IPS:
            _cleanup_rate_history_locked(now)

        hits = _rate_history[client_ip]

        # Supprimer les timestamps expires
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


def _is_refusal(text: str) -> bool:
    """Detecte si la réponse est un refus."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    markers = _get_refusal_markers()
    return any(marker.lower() in normalized for marker in markers)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    thread_id: str | None = None  # pour les follow-ups dans un thread existant


class ChatResponse(BaseModel):
    response: str
    refused: bool = False
    thread_id: str  # ID du thread (nouveau ou existant)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate(client_ip):
        logger.warning("Rate limit atteint pour %s", client_ip)
        raise HTTPException(status_code=429, detail="Trop de requetes. Reessaie dans une minute.")

    logger.info("Query (%d chars): %.100s", len(req.message), req.message)

    # Determiner le thread_id (nouveau ou existant)
    thread_id = req.thread_id
    if not thread_id:
        # Nouveau thread
        thread_id = create_thread(req.message)
    else:
        # Verifier que le thread existe
        existing = get_thread(thread_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Thread non trouve.")

    try:
        result = await run_agent_async(req.message, thread_id=thread_id)
        answer = result["response"]
        agent_metadata = result["metadata"]
        refused = _is_refusal(answer)

        # Stocker les métadonnées pour le middleware de logging
        request.state.agent_metadata = agent_metadata

        # Sauvegarder la reponse en background (ne bloque pas la réponse)
        asyncio.create_task(asyncio.to_thread(
            add_message, thread_id, "assistant", answer, {"refused": refused}
        ))

        return {"response": answer, "refused": refused, "thread_id": thread_id}
    except Exception as e:
        logger.error("Erreur agent: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur.")


@app.get("/datasets")
async def list_datasets(
    query: str = "",
    max_results: int = Query(10, ge=1, le=100),
    request: Request = None,
):
    client_ip = request.client.host if request and request.client else "unknown"

    if not _check_rate(client_ip):
        logger.warning("Rate limit atteint pour %s", client_ip)
        raise HTTPException(status_code=429, detail="Trop de requetes. Reessaie dans une minute.")

    logger.info("Datasets query: %.100s", query)
    try:
        results = datasets_search(query=query, max_results=max_results)
        return {"query": query, "count": len(results), "datasets": results}
    except Exception as e:
        logger.error("Erreur datasets: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur.")


@app.get("/health")
async def health():
    """Health check vérifie DB + mémoire."""
    checks = {"status": "ok", "db": "ok"}
    try:
        from threads import _get_db
        db = _get_db()
        db.execute("SELECT 1")
    except Exception as e:
        checks["status"] = "degraded"
        checks["db"] = f"error: {type(e).__name__}"
    return checks


# ============================================================================
# SEARCH — endpoint structuré pour les providers externes (DSH, etc.)
# ============================================================================

class SearchSource(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""


class SearchResponse(BaseModel):
    sources: list[SearchSource]
    query: str
    count: int
    truncated: bool = False


@app.get("/search", response_model=SearchResponse)
async def search(
    q: str,
    max_results: int = Query(10, ge=1, le=30),
    request: Request = None,
):
    """
    Endpoint de recherche structurée — retourne des résultats au format
    compatible avec les providers de recherche (DeepSeek Harness, etc.).

    Utilise le routeur intelligent pour sélectionner les sources pertinentes,
    exécute la recherche en parallèle, et déduplique les résultats par URL.
    """
    client_ip = request.client.host if request and request.client else "unknown"

    if not _check_rate(client_ip):
        raise HTTPException(status_code=429, detail="Trop de requetes. Reessaie dans une minute.")

    logger.info("Search query (%d chars): %.100s", len(q), q)

    try:
        from sources.router import route_query
        from sources import get_source
        import concurrent.futures

        routing = route_query(q)
        tools = routing["tools"]

        # Exécuter les sources en parallèle
        all_results: list[dict] = []

        def _run_source(tool_name: str) -> list[dict]:
            try:
                func = get_source(tool_name.replace("_search", "") if tool_name.endswith("_search") else tool_name)
                return func(query=q, max_results=min(max_results, 5))
            except Exception as e:
                logger.warning("Search source %s failed: %s", tool_name, e)
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(_run_source, t): t for t in tools}
            for future in concurrent.futures.as_completed(futures):
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception:
                    pass

        # Dédupliquer par URL
        seen_urls: set[str] = set()
        unique_results: list[dict] = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        # Limiter et formater
        sources = [
            SearchSource(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("snippet", "")[:300],
            )
            for r in unique_results[:max_results]
        ]

        return SearchResponse(
            sources=sources,
            query=q,
            count=len(sources),
            truncated=len(unique_results) > max_results,
        )
    except Exception as e:
        logger.error("Search error: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur.")


# ============================================================================
# THREADS — historique et follow-ups
# ============================================================================

class ThreadSummary(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float


class ThreadDetail(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float
    messages: list[dict]


@app.get("/threads", response_model=list[ThreadSummary])
async def get_threads(limit: int = Query(50, ge=1, le=200)):
    """Liste les threads tries par derniere activite."""
    return list_threads(limit=limit)


@app.get("/threads/{thread_id}", response_model=ThreadDetail)
async def get_thread_detail(thread_id: str):
    """Detail d'un thread avec tous ses messages."""
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread non trouve.")
    return thread


@app.delete("/threads/{thread_id}")
async def delete_thread_endpoint(thread_id: str):
    """Supprime un thread et ses messages."""
    if not delete_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread non trouve.")
    return {"status": "deleted", "thread_id": thread_id}


@app.get("/threads/{thread_id}/context")
async def get_thread_context_endpoint(
    thread_id: str,
    max_messages: int = Query(10, ge=1, le=50),
):
    """Contexte d'un thread pour follow-up (derniers messages)."""
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread non trouve.")
    return {
        "thread_id": thread_id,
        "messages": get_thread_context(thread_id, max_messages=max_messages),
    }


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.error("Exception non geree: %s: %s", type(exc).__name__, exc)
    return JSONResponse(status_code=500, content={"error": "Erreur interne du serveur."})


# ============================================================================
# ADMIN — panneau d'administration
# ============================================================================

def _read_env() -> dict[str, str]:
    """Lit le fichier .env et retourne un dict."""
    if not ENV_FILE.exists():
        return {}
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def _write_env(data: dict[str, str]):
    """Ecrit les cles dans le fichier .env."""
    existing = _read_env()
    existing.update(data)
    lines = []
    for key, value in existing.items():
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n")


@app.get("/admin")
async def admin_ui():
    """Sert le panneau d'administration."""
    index = ADMIN_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return FileResponse(index, media_type="text/html")


@app.get("/admin/env/{key}/reveal")
async def reveal_env_key(key: str):
    """Retourne la valeur reelle d'une seule cle (pour reveal/copy)."""
    env = _read_env()
    return {"key": key, "value": env.get(key, "")}


@app.get("/admin/env")
async def get_env():
    """Retourne les variables d'environnement (sans les secrets masques)."""
    env = _read_env()
    masked = {}
    for key, value in env.items():
        if key.endswith("_ENABLED"):
            masked[key] = value
        elif "KEY" in key or "TOKEN" in key or "SECRET" in key:
            if value and len(value) > 8:
                masked[key] = value[:4] + "..." + value[-4:]
            else:
                masked[key] = "***" if value else ""
        else:
            masked[key] = value
    return masked


@app.post("/admin/env")
async def set_env(request: Request):
    """Sauvegarde les variables d'environnement."""
    data = await request.json()
    # Ne pas sauvegarder les valeurs masquees
    clean = {}
    for key, value in data.items():
        if value and "..." not in value and value != "***":
            clean[key] = value
    if clean:
        _write_env(clean)
    return {"status": "ok", "saved": list(clean.keys())}


@app.get("/admin/sources")
async def get_sources():
    """Liste les sources avec leur etat."""
    enabled = os.getenv("DISABLED_SOURCES", "").split(",")
    return [
        {
            "name": name,
            "description": meta["description"],
            "requires_key": meta["requires_key"],
            "enabled": name not in enabled,
        }
        for name, meta in SOURCES.items()
    ]


@app.post("/admin/sources/{name}")
async def toggle_source(name: str, request: Request):
    """Active/desactive une source."""
    if name not in SOURCES:
        raise HTTPException(status_code=404, detail=f"Source '{name}' inconnue")
    data = await request.json()
    enabled = data.get("enabled", True)
    current = os.getenv("DISABLED_SOURCES", "").split(",")
    current = [s for s in current if s]
    if enabled and name in current:
        current.remove(name)
    elif not enabled and name not in current:
        current.append(name)
    _write_env({"DISABLED_SOURCES": ",".join(current)})
    return {"name": name, "enabled": enabled}


@app.get("/admin/models")
async def get_models():
    """Configuration du pool de modeles."""
    return {
        "pool": MODEL_POOL,
        "models_per_request": 3,
        "cache_ttl": 300,
    }


@app.get("/admin/router")
async def get_router():
    """Configuration du routeur."""
    intents = {}
    for name, data in INTENT_INDEX.items():
        intents[name] = {
            "weight": data["weight"],
            "patterns": data["patterns"][:2],
            "tools_boost": data["tools_boost"],
        }
    domains = {}
    for name, data in DOMAIN_INDEX.items():
        domains[name] = {
            "keywords": data["keywords"][:8],
            "tools_boost": data["tools_boost"],
        }
    levels = []
    for level, tools in TOOL_LEVELS.items():
        score_map = {1: "0-39", 2: "40-64", 3: "65-100"}
        levels.append({
            "level": level,
            "score_range": score_map.get(level, "?"),
            "max_tools": len(tools),
        })
    return {"intents": intents, "domains": domains, "levels": levels}


@app.get("/admin/logs")
async def get_logs(lines: int = Query(200, ge=1, le=1000)):
    """Retourne les logs structurés avec métadonnées."""
    log_file = BASE_DIR / "websearch-agent.log"
    if not log_file.exists():
        return {"logs": [], "stats": {"total": 0, "error": 0, "warning": 0, "info": 0}}

    try:
        # Read only the tail of the file efficiently
        raw_lines = []
        try:
            with open(log_file, 'rb') as f:
                f.seek(0, 2)
                file_size = f.tell()
                block_size = min(file_size, lines * 200)
                f.seek(max(0, file_size - block_size))
                tail = f.read().decode('utf-8', errors='replace')
                raw_lines = tail.split('\n')[-lines:]
        except Exception:
            content = log_file.read_text()
            raw_lines = content.strip().split('\n')[-lines:]

        parsed_logs = []
        stats = {"total": 0, "error": 0, "warning": 0, "info": 0}

        # Pre-compiled patterns for log parsing
        log_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+(.*)')
        tools_pattern = re.compile(r'outils=\[([^\]]*)\]')
        score_pattern = re.compile(r'score=(\d+)')
        level_pattern = re.compile(r'niveau=(\d+)')
        urls_pattern = re.compile(r'extraction de (\d+) URLs')
        model_pattern = re.compile(r'(?:modele|essai|synthese)\s+(\S+)', re.IGNORECASE)

        for line in raw_lines:
            if not line.strip():
                continue

            # Parser le format: 2024-01-15 10:30:45 [LEVEL] message
            match = log_pattern.match(line)
            if match:
                timestamp_str, level, message = match.groups()
                level = level.lower()

                # Extraire des métadonnées du message
                category = "system"
                details = {}

                if "route:" in message.lower() or "outils=" in message:
                    category = "routing"
                    # Extraire les outils
                    tools_match = tools_pattern.search(message)
                    if tools_match:
                        details["tools"] = [t.strip().strip("'") for t in tools_match.group(1).split(",")]
                    score_match = score_pattern.search(message)
                    if score_match:
                        details["score"] = int(score_match.group(1))
                    level_match = level_pattern.search(message)
                    if level_match:
                        details["level"] = int(level_match.group(1))

                elif "fast path" in message.lower():
                    category = "search"
                    tools_match = tools_pattern.search(message)
                    if tools_match:
                        details["tools"] = [t.strip().strip("'") for t in tools_match.group(1).split(",")]
                    urls_match = urls_pattern.search(message)
                    if urls_match:
                        details["urls_fetched"] = int(urls_match.group(1))

                elif "cache" in message.lower():
                    category = "cache"

                elif "model" in message.lower() or "synth" in message.lower():
                    category = "llm"
                    model_match = model_pattern.search(message)
                    if model_match:
                        details["model"] = model_match.group(1)

                elif "thread" in message.lower():
                    category = "thread"

                elif "client" in message.lower() or "api-key" in message.lower():
                    category = "auth"

                elif "error" in message.lower() or "erreur" in message.lower():
                    category = "error"

                elif "rate limit" in message.lower():
                    category = "security"

                stats["total"] += 1
                if level in stats:
                    stats[level] += 1

                parsed_logs.append({
                    "timestamp": timestamp_str,
                    "level": level,
                    "message": message,
                    "category": category,
                    "details": details,
                    "raw": line,
                })
            else:
                # Ligne sans format standard
                parsed_logs.append({
                    "timestamp": "",
                    "level": "info",
                    "message": line,
                    "category": "system",
                    "details": {},
                    "raw": line,
                })

        # Inverser pour avoir les plus récents en premier
        parsed_logs.reverse()

        return {"logs": parsed_logs, "stats": stats}
    except Exception as e:
        return {"logs": [], "stats": {"total": 0, "error": 0, "warning": 0, "info": 0}, "error": str(e)}


@app.get("/admin/service/status")
async def service_status():
    """Etat du service."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pgrep", "-f", "uvicorn server:app",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)
        running = proc.returncode == 0
    except Exception:
        running = False
    return {"running": running}


@app.post("/admin/service/restart")
async def service_restart():
    """Redémarre le service en background."""
    async def _restart():
        await asyncio.sleep(1)
        log_path = str(BASE_DIR / "websearch-agent.log")
        with open(log_path, "a") as log_file:
            proc = await asyncio.create_subprocess_exec(
                "nohup", "uvicorn", "server:app",
                "--host", "127.0.0.1", "--port", str(PORT),
                "--loop", "uvloop", "--http", "httptools",
                cwd=str(BASE_DIR),
                stdout=log_file,
                stderr=asyncio.subprocess.STDOUT,
            )
        await asyncio.sleep(0.5)
        kill_proc = await asyncio.create_subprocess_exec(
            "pkill", "-f", "uvicorn server:app",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(kill_proc.communicate(), timeout=5)

    asyncio.create_task(_restart())
    return {"status": "restarting"}


@app.post("/admin/service/stop")
async def service_stop():
    """Arrête le service en background."""
    async def _stop():
        await asyncio.sleep(1)
        proc = await asyncio.create_subprocess_exec(
            "pkill", "-f", "uvicorn server:app",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)

    asyncio.create_task(_stop())
    return {"status": "stopped"}


@app.post("/admin/cache/clear")
async def clear_cache():
    """Vide le cache LRU."""
    from agent import _cache, _cache_lock
    with _cache_lock:
        _cache.clear()
    return {"status": "cleared"}


# --- Settings ---
SETTINGS_FILE = BASE_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "general": {
        "fullname": "",
        "displayname": "",
        "language": "fr",
        "timezone": "Europe/Paris",
    },
    "appearance": {
        "theme": "dark",
        "font_size": "medium",
        "animations": True,
        "wide_messages": False,
    },
    "ai": {
        "name": "WebSearch Agent",
        "system_prompt": "",
        "refusal_markers": "je ne peux pas,je ne suis pas en mesure,hors sujet,je refuse,non autorise,pas possible",
        "response_style": "balanced",
        "search_speed": "normal",
    },
    "agent": {
        "system_prompt": "",
        "refusal_markers": "je ne peux pas,je ne suis pas en mesure,hors sujet,je refuse,non autorise,pas possible",
        "max_context_length": 6000,
    },
    "models": {
        "models_per_request": 3,
        "max_tokens_tool_selection": 300,
        "max_tokens_synthesis": 500,
        "synthesis_timeout": 6.0,
        "tool_timeout": 5.0,
    },
    "cache": {
        "ttl": 300,
        "max_size": 200,
    },
    "rate_limit": {
        "window": 60,
        "max_requests": 30,
    },
    "server": {
        "host": "127.0.0.1",
        "port": 4500,
    },
}


def _read_settings() -> dict:
    """Lit les settings depuis le fichier JSON."""
    if SETTINGS_FILE.exists():
        try:
            import json
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            for section, values in saved.items():
                if section in merged and isinstance(merged[section], dict):
                    merged[section].update(values)
                else:
                    merged[section] = values
            return merged
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def _write_settings(settings: dict):
    """Ecrit les settings dans le fichier JSON."""
    import json
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


@app.get("/admin/settings")
async def get_settings():
    """Retourne les parametres de l'application."""
    return _read_settings()


@app.post("/admin/settings")
async def save_settings(request: Request):
    """Sauvegarde les parametres de l'application."""
    try:
        body = await request.json()
        current = _read_settings()
        for section, values in body.items():
            if section in current and isinstance(current[section], dict) and isinstance(values, dict):
                current[section].update(values)
            else:
                current[section] = values
        _write_settings(current)
        return {"status": "saved", "settings": current}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/settings/reset")
async def reset_settings():
    """Reinitialise les parametres aux valeurs par defaut."""
    _write_settings(DEFAULT_SETTINGS)
    return {"status": "reset", "settings": DEFAULT_SETTINGS}


# ============================================================================
# ADMIN — Gestion des clients (apps connectées)
# ============================================================================

class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)


@app.get("/admin/clients")
async def get_clients():
    """Liste tous les clients avec leurs stats."""
    clients = list_clients(include_inactive=True)
    stats = get_client_stats()
    return {"clients": clients, "stats": stats}


@app.post("/admin/clients")
async def create_new_client(req: ClientCreate):
    """Crée un nouveau client avec une clé d'API."""
    client = create_client(name=req.name, description=req.description)
    return client


@app.get("/admin/clients/{client_id}")
async def get_client_detail(client_id: str):
    """Détails d'un client avec ses logs récents."""
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé.")
    logs = get_client_logs(client_id, limit=20)
    return {**client, "logs": logs}


@app.post("/admin/clients/{client_id}/deactivate")
async def deactivate_client_endpoint(client_id: str):
    """Désactive un client (révoque sa clé)."""
    if not deactivate_client(client_id):
        raise HTTPException(status_code=404, detail="Client non trouvé.")
    return {"status": "deactivated", "client_id": client_id}


@app.post("/admin/clients/{client_id}/activate")
async def activate_client_endpoint(client_id: str):
    """Réactive un client."""
    if not activate_client(client_id):
        raise HTTPException(status_code=404, detail="Client non trouvé.")
    return {"status": "activated", "client_id": client_id}


@app.delete("/admin/clients/{client_id}")
async def delete_client_endpoint(client_id: str):
    """Supprime un client et ses logs."""
    if not delete_client(client_id):
        raise HTTPException(status_code=404, detail="Client non trouvé.")
    return {"status": "deleted", "client_id": client_id}


@app.post("/admin/clients/{client_id}/regenerate")
async def regenerate_client_key(client_id: str):
    """Régénère la clé d'API d'un client."""
    result = regenerate_api_key(client_id)
    if not result:
        raise HTTPException(status_code=404, detail="Client non trouvé.")
    return result


@app.get("/admin/clients/{client_id}/logs")
async def get_client_logs_endpoint(
    client_id: str,
    limit: int = Query(50, ge=1, le=200),
):
    """Logs récents d'un client."""
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé.")
    logs = get_client_logs(client_id, limit=limit)
    return {"client_id": client_id, "logs": logs}


@app.get("/admin/{filename:path}")
async def admin_static(filename: str):
    """Sert les fichiers statiques du dossier admin (CSS, JS, etc.)."""
    # Skip API routes (they should be caught by specific routes above)
    api_prefixes = ["clients", "env", "sources", "models", "router", "logs", "service/", "cache", "settings"]
    if any(filename.startswith(prefix) for prefix in api_prefixes):
        raise HTTPException(status_code=404, detail="API route not found")

    # Path traversal protection
    if ".." in filename or filename.startswith("/") or "\\" in filename:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = (ADMIN_DIR / filename).resolve()
    if not str(file_path).startswith(str(ADMIN_DIR.resolve())):
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    media_types = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }
    media_type = media_types.get(file_path.suffix.lower(), "application/octet-stream")
    response = FileResponse(file_path, media_type=media_type)
    # Pas de cache sur les pages HTML (login, etc.)
    if file_path.suffix.lower() == ".html":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response
