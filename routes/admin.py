"""
Routes admin — panneau d'administration.
Extrait de server.py lors du refactoring.
"""

from __future__ import annotations

import os
import asyncio
import re
import secrets
import time
import logging
from pathlib import Path
from fastapi.concurrency import run_in_threadpool
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from agent import MODEL_POOL
from sources import SOURCES
from sources.router import INTENT_INDEX, DOMAIN_INDEX, TOOL_LEVELS
from core.settings import _load_settings, _save_settings
from clients import (
    create_client,
    list_clients,
    get_client,
    deactivate_client,
    activate_client,
    delete_client,
    regenerate_api_key,
    get_client_logs as _get_client_logs,
    get_client_stats as get_global_client_stats,
)

import routes.auth as auth_mod

logger = logging.getLogger("websearch-agent")
router = APIRouter(tags=["Admin"])

# --- Paths ---
BASE_DIR = Path(__file__).parent.parent
ADMIN_DIR = BASE_DIR / "admin"
ENV_FILE = BASE_DIR / ".env"




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
    """Ecrit les cles dans le fichier .env de maniere atomique."""
    import tempfile
    existing = _read_env()
    existing.update(data)
    lines = []
    for key, value in existing.items():
        lines.append(f"{key}={value}")
    content = "\n".join(lines) + "\n"
    # Atomic write: temp file + os.replace
    try:
        fd, tmp_path = tempfile.mkstemp(dir=ENV_FILE.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(fd)
        os.replace(tmp_path, ENV_FILE)
    except Exception as e:
        logger.error("Failed to write .env: %s", type(e).__name__)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@router.post("/admin/api/login", summary="Connexion admin", description="Authentifie l'admin avec username/password et 2FA, cree une session.")
async def login(req: auth_mod.LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"

    if not auth_mod._check_login_rate(client_ip):
        raise HTTPException(status_code=429, detail="Trop de tentatives. Reessayez dans 5 minutes.")

    # Constant-time comparison pour username
    username_ok = secrets.compare_digest(req.username, auth_mod.ADMIN_USER)

    # Vérification du mot de passe: hash prioritaire, fallback legacy
    password_ok = False
    if auth_mod.ADMIN_PASSWORD_HASH:
        from core.password import verify_password
        password_ok = verify_password(req.password, auth_mod.ADMIN_PASSWORD_HASH)
    elif auth_mod.ADMIN_PASSWORD:
        password_ok = secrets.compare_digest(req.password, auth_mod.ADMIN_PASSWORD)

    if not username_ok or not password_ok:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    if auth_mod.ADMIN_TOTP_SECRET:
        if not req.totp_code:
            raise HTTPException(status_code=401, detail="Code 2FA requis")
        import pyotp
        totp = pyotp.TOTP(auth_mod.ADMIN_TOTP_SECRET)
        if not totp.verify(req.totp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Code 2FA invalide")

    token = auth_mod._create_session()
    csrf_token = auth_mod.generate_csrf_token(token)
    response = JSONResponse({"status": "authenticated", "token": token, "csrf_token": csrf_token})
    response.set_cookie(
        "admin_session",
        token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="strict",
        max_age=86400,
    )
    logger.info("Admin connecte")
    return response


@router.post("/admin/api/logout", summary="Deconnexion admin", description="Detruit la session et deconnecte l'admin.")
async def logout(request: Request):
    token = request.cookies.get("admin_session")
    if token and token in auth_mod._sessions:
        del auth_mod._sessions[token]
    response = JSONResponse({"status": "disconnected"})
    response.delete_cookie("admin_session")
    return response


@router.get("/admin/api/auth/check", summary="Verifier authentification", description="Retourne si l'admin est authentifie ou non.")
async def check_auth(request: Request):
    """Verifie si l'admin est authentifie."""
    token = request.cookies.get("admin_session")
    if auth_mod._validate_session(token):
        return {"authenticated": True}
    return {"authenticated": False}


@router.get("/admin/api/2fa/setup")
async def setup_2fa(request: Request):
    """Retourne les informations de setup 2FA (pas de secret exposed)."""
    token = auth_mod.require_admin_session(request)
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifie")
    if not auth_mod.ADMIN_TOTP_SECRET:
        return {"enabled": False, "message": "2FA non configure"}
    import pyotp
    totp = pyotp.TOTP(auth_mod.ADMIN_TOTP_SECRET)
    provisioning_uri = totp.provisioning_uri(
        name=auth_mod.ADMIN_USER,
        issuer_name="WebSearch Agent"
    )
    return {
        "enabled": True,
        "qr_url": provisioning_uri,
    }


# ============================================================================
# ADMIN UI + CONFIG ENDPOINTS
# ============================================================================

@router.get("/admin")
async def admin_ui():
    """Sert le panneau d'administration."""
    index = ADMIN_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return FileResponse(index, media_type="text/html")


@router.get("/admin/env/{key}/reveal")
async def reveal_env_key(key: str, request: Request):
    """Revele la vraie valeur d'une variable d'env (admin auth uniquement)."""
    token = auth_mod.require_admin_session(request)
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifie")
    # Validate key format
    if not re.match(r'^[A-Z][A-Z0-9_]{0,80}$', key):
        raise HTTPException(status_code=400, detail="Nom de cle invalide")
    # Blacklist: ces secrets ne doivent jamais etre revels
    _NEVER_REVEAL = {"ADMIN_PASSWORD_HASH", "ADMIN_PASSWORD", "ADMIN_TOTP_SECRET", "JWT_SECRET"}
    if key in _NEVER_REVEAL:
        raise HTTPException(status_code=403, detail="Cle protegee — revelation interdite")
    env = _read_env()
    return {"key": key, "value": env.get(key, "")}


@router.get("/admin/env", summary="Variables d'environnement", description="Liste les variables d'environnement (valeurs masquees).")
async def get_env():
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


@router.post("/admin/env", summary="Mettre a jour l'environnement", description="Ecrit les variables d'environnement dans le fichier .env.")
async def set_env(request: Request):
    data = await request.json()
    clean = {}
    for key, value in data.items():
        # Validate key format
        if not re.match(r'^[A-Z][A-Z0-9_]{0,80}$', key):
            logger.warning("Invalid env key rejected: %s", key)
            continue
        # Reject masked values
        if value in ("***", "...") or (isinstance(value, str) and "..." in value):
            continue
        # Reject values with dangerous characters
        if isinstance(value, str) and ("\n" in value or "\r" in value or "\x00" in value):
            logger.warning("Env value with dangerous chars rejected for key: %s", key)
            continue
        if value:
            clean[key] = value
    if clean:
        _write_env(clean)
    return {"status": "ok", "saved": list(clean.keys())}


@router.get("/admin/sources")
async def get_sources():
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


@router.post("/admin/sources/{name}")
async def toggle_source(name: str, request: Request):
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


@router.get("/admin/models")
async def get_models():
    return {
        "pool": MODEL_POOL,
        "models_per_request": 3,
        "cache_ttl": 300,
    }


@router.get("/admin/router")
async def get_router():
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


@router.get("/admin/logs", summary="Logs du serveur", description="Retourne les dernieres lignes de log avec statistiques (error, warning, info).")
async def get_logs(lines: int = Query(200, ge=1, le=1000)):
    log_file = BASE_DIR / "data" / "websearch-agent.log"
    if not log_file.exists():
        return {"logs": [], "stats": {"total": 0, "error": 0, "warning": 0, "info": 0}}

    try:
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

        log_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?)\s+\[(\w+)\]\s+(.*)')

        category_keywords = {
            "routing": ["Route", "route_query", "score=", "niveau="],
            "search": ["Search", "search", "Outil", "source", "circuit breaker"],
            "llm": ["Modèle", "modele", "Essai", "Tool calls", "Synthese", "HTTP Request"],
            "cache": ["cache", "Cache"],
            "auth": ["auth", "Admin", "Rate limit", "API key"],
            "thread": ["Thread", "thread"],
            "system": ["startup", "shutdown", "Uvicorn", "Started", "Finished"],
        }

        def _categorize(msg: str) -> str:
            for cat, keywords in category_keywords.items():
                if any(kw.lower() in msg.lower() for kw in keywords):
                    return cat
            return "system"

        def _extract_details(msg: str) -> dict:
            details = {}
            # Extract request ID [xxxxxxxx]
            rid = re.search(r'\[([0-9a-f]{8})\]', msg)
            if rid:
                details["req_id"] = rid.group(1)
            # Extract tool name
            tool = re.search(r'Outil (\w+)', msg)
            if tool:
                details["tool"] = tool.group(1)
            # Extract model name
            model = re.search(r'(?:Modèle|Modele|Essai\S*):\s*(\S+)', msg)
            if model:
                details["model"] = model.group(1)
            # Extract duration
            dur = re.search(r'(\d+\.?\d*)s', msg)
            if dur:
                details["duration"] = f"{dur.group(1)}s"
            # Extract score
            score = re.search(r'score=(\d+)', msg)
            if score:
                details["score"] = score.group(1)
            return details

        for line in raw_lines:
            if not line.strip():
                continue
            match = log_pattern.match(line)
            if match:
                timestamp_str, level, message = match.groups()
                level = level.lower()
                stats["total"] += 1
                if level in stats:
                    stats[level] += 1
                parsed_logs.append({
                    "timestamp": timestamp_str,
                    "level": level,
                    "message": message,
                    "category": _categorize(message),
                    "details": _extract_details(message),
                })

        return {"logs": parsed_logs[-lines:], "stats": stats}
    except Exception as e:
        return {"logs": [], "stats": {"total": 0, "error": 0, "warning": 0, "info": 0}, "error": str(e)}


# ============================================================================
# CLIENTS CRUD
# ============================================================================

@router.get("/admin/clients", summary="Lister les clients API", description="Retourne la liste des clients API avec statistiques.")
async def get_clients():
    clients, stats = await run_in_threadpool(lambda: (list_clients(), get_global_client_stats()))
    return {"clients": clients, "stats": stats}


@router.post("/admin/clients", summary="Creer un client API", description="Cree un nouveau client API avec une cle generee automatiquement.")
async def create_new_client(request: Request):
    data = await request.json()
    name = data.get("name", "Unnamed")
    client = await run_in_threadpool(create_client, name)
    return client


@router.get("/admin/clients/{client_id}")
async def get_client_detail(client_id: str):
    client = await run_in_threadpool(get_client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouve.")
    return client


@router.post("/admin/clients/{client_id}/deactivate")
async def deactivate(client_id: str):
    await run_in_threadpool(deactivate_client, client_id)
    return {"status": "deactivated"}


@router.post("/admin/clients/{client_id}/activate")
async def activate(client_id: str):
    await run_in_threadpool(activate_client, client_id)
    return {"status": "activated"}


@router.delete("/admin/clients/{client_id}")
async def remove_client(client_id: str):
    await run_in_threadpool(delete_client, client_id)
    return {"status": "deleted"}


@router.post("/admin/clients/{client_id}/regenerate")
async def regenerate(client_id: str):
    from clients import get_client
    result = await run_in_threadpool(regenerate_api_key, client_id)
    if not result:
        raise HTTPException(status_code=404, detail="Client non trouve.")
    client = await run_in_threadpool(get_client, client_id)
    return {
        "api_key": result["api_key"],
        "client_secret": result["client_secret"],
        "name": result["name"],
        "scopes": client["scopes"] if client else [],
    }


@router.get("/admin/clients/{client_id}/logs")
async def get_client_logs(client_id: str, limit: int = Query(100, ge=1, le=1000)):
    return await run_in_threadpool(_get_client_logs, client_id, limit=limit)


@router.get("/admin/metrics/history", summary="Historique des metriques", description="Retourne les snapshots de metriques persistes (retention 7 jours).")
async def get_metrics_history(since_seconds: int = Query(3600, ge=60, le=604800)):
    from core.monitoring import get_history
    history = await run_in_threadpool(get_history, since_seconds)
    return {"history": history}


@router.get("/admin/clients/{client_id}/stats")
async def get_single_client_stats(client_id: str):
    from clients import get_client_stats as _get_stats
    return await run_in_threadpool(_get_stats, client_id)


@router.put("/admin/clients/{client_id}/scopes")
async def update_scopes(client_id: str, request: Request):
    """Met à jour les scopes d'un client."""
    from clients import update_client_scopes, AVAILABLE_SCOPES
    body = await request.json()
    scopes = body.get("scopes", [])
    # Validate
    invalid = set(scopes) - set(AVAILABLE_SCOPES.keys())
    if invalid:
        raise HTTPException(status_code=400, detail=f"Scopes invalides: {', '.join(invalid)}")
    try:
        client = update_client_scopes(client_id, scopes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouve.")
    return {"scopes": client["scopes"]}


@router.get("/admin/scopes")
async def list_scopes():
    """Retourne la liste des scopes disponibles."""
    from clients import AVAILABLE_SCOPES
    return {"scopes": AVAILABLE_SCOPES}


@router.put("/admin/clients/{client_id}/rate-limit")
async def update_rate_limit(client_id: str, request: Request):
    """Met à jour le rate limit d'un client (requests par minute)."""
    from clients import update_client_rate_limit
    body = await request.json()
    rate_limit = body.get("rate_limit")
    if not isinstance(rate_limit, int) or rate_limit < 1:
        raise HTTPException(status_code=400, detail="rate_limit doit etre un entier positif.")
    try:
        client = update_client_rate_limit(client_id, rate_limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouve.")
    return {"rate_limit": client["rate_limit"]}


# ============================================================================
# SERVICE CONTROL
# ============================================================================

# Rate limit pour les commandes systemctl dangereuses
SERVICE_RATE_MAX = 3  # max 3 appels
SERVICE_RATE_WINDOW = 300  # par fenêtre de 5 minutes
_service_rate_timestamps: list[float] = []


def _check_service_rate() -> bool:
    """Vérifie le rate limit pour les commandes systemctl."""
    now = time.time()
    # Nettoyer les timestamps expirés
    while _service_rate_timestamps and _service_rate_timestamps[0] < now - SERVICE_RATE_WINDOW:
        _service_rate_timestamps.pop(0)
    if len(_service_rate_timestamps) >= SERVICE_RATE_MAX:
        return False
    _service_rate_timestamps.append(now)
    return True


def _log_service_audit(action: str, request: Request):
    """Écrit un log d'audit pour les commandes systemctl."""
    token = request.cookies.get("admin_session", "")
    token_prefix = token[:8] if token else "unknown"
    client_ip = request.client.host if request.client else "unknown"
    logger.warning(
        "AUDIT: service %s — session=%s ip=%s timestamp=%.0f",
        action, token_prefix, client_ip, time.time()
    )


@router.get("/admin/service/status")
async def service_status():
    """Etat du service systemd."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "is-active", "websearch-agent",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        running = stdout.decode().strip() == "active"
    except Exception:
        running = False
    return {"running": running}


@router.post("/admin/service/restart")
async def service_restart(request: Request):
    """Redemarre le service via systemctl (en background)."""
    if not _check_service_rate():
        raise HTTPException(status_code=429, detail="Trop de redémarrages. Réessayez dans 5 minutes.")
    _log_service_audit("restart", request)
    async def _restart():
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", "restart", "websearch-agent",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=15)
    asyncio.create_task(_restart())
    return {"status": "restarting"}


@router.post("/admin/service/stop")
async def service_stop(request: Request):
    """Arrete le service via systemctl (en background)."""
    if not _check_service_rate():
        raise HTTPException(status_code=429, detail="Trop d'arrêts. Réessayez dans 5 minutes.")
    _log_service_audit("stop", request)
    async def _stop():
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", "stop", "websearch-agent",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=15)
    asyncio.create_task(_stop())
    return {"status": "stopped"}


@router.post("/admin/cache/clear")
async def clear_cache():
    """Vide le cache LRU."""
    from core.cache import _cache, _cache_lock
    with _cache_lock:
        _cache.clear()
    return {"status": "cleared"}


# ============================================================================
# SETTINGS
# ============================================================================

@router.get("/admin/settings", summary="Lire les settings", description="Retourne toutes les settings du panel admin (general, appearance, ai, etc.).")
async def get_settings():
    return _load_settings()


@router.post("/admin/settings", summary="Mettre a jour les settings", description="Ecrit les settings dans data/settings.json.")
async def update_settings(request: Request):
    data = await request.json()
    existing = _load_settings()
    existing.update(data)
    _save_settings(existing)
    return {"status": "ok"}


# ============================================================================
# ACCOUNT
# ============================================================================

@router.get("/admin/account")
async def get_account():
    settings = _load_settings()
    account = settings.get("account", {})
    return {
        "email": account.get("email", "admin@websearch.local"),
    }


@router.post("/admin/account/email")
async def update_account_email(request: Request):
    data = await request.json()
    email = data.get("email", "")
    settings = _load_settings()
    settings.setdefault("account", {})["email"] = email
    _save_settings(settings)
    return {"status": "ok"}


@router.post("/admin/account/password")
async def update_account_password(request: Request):
    data = await request.json()
    current = data.get("current", "")
    new_password = data.get("new", "")
    if not current or not new_password:
        raise HTTPException(status_code=400, detail="Champs manquants")

    # Vérification du mot de passe actuel: hash prioritaire, fallback legacy
    current_ok = False
    if auth_mod.ADMIN_PASSWORD_HASH:
        from core.password import verify_password
        current_ok = verify_password(current, auth_mod.ADMIN_PASSWORD_HASH)
    elif auth_mod.ADMIN_PASSWORD:
        current_ok = secrets.compare_digest(current, auth_mod.ADMIN_PASSWORD)

    if not current_ok:
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 6 caractères")
    # Update .env file — hasher le nouveau mot de passe
    from core.password import hash_password
    new_hash = hash_password(new_password)
    env_file = BASE_DIR / ".env"
    env_lines = env_file.read_text().splitlines() if env_file.exists() else []
    found = False
    for i, line in enumerate(env_lines):
        if line.startswith("ADMIN_PASSWORD="):
            env_lines[i] = f"ADMIN_PASSWORD_HASH={new_hash}"
            found = True
            break
        elif line.startswith("ADMIN_PASSWORD_HASH="):
            env_lines[i] = f"ADMIN_PASSWORD_HASH={new_hash}"
            found = True
            break
    if not found:
        env_lines.append(f"ADMIN_PASSWORD_HASH={new_hash}")
    env_file.write_text("\n".join(env_lines) + "\n")
    # Update in-memory value
    auth_mod.ADMIN_PASSWORD_HASH = new_hash
    auth_mod.ADMIN_PASSWORD = None  # Plus de password en clair
    # Invalidate all other sessions
    current_token = request.cookies.get("admin_session")
    invalidated = auth_mod._invalidate_all_sessions(keep_token=current_token)
    logger.info("Admin password changed, %d sessions invalidated", invalidated)
    return {"status": "ok", "message": "Mot de passe mis à jour. Sessions invalidées: %d" % invalidated}


@router.get("/admin/account/sessions")
async def get_sessions(request: Request):
    current_token = request.cookies.get("admin_session", "")
    sessions = []
    now = time.time()
    for token, expiry in auth_mod._sessions.items():
        remaining = expiry - now
        if remaining <= 0:
            continue
        sessions.append({
            "token_prefix": token[:8],
            "is_current": token == current_token,
            "expires_in_hours": round(remaining / 3600, 1),
        })
    return {"sessions": sessions, "current": current_token[:8]}


@router.delete("/admin/account/sessions/{token_prefix}")
async def disconnect_session(token_prefix: str):
    # Require minimum 8 chars prefix for safety
    if len(token_prefix) < 8:
        raise HTTPException(status_code=400, detail="Token prefix trop court (min 8 caractères)")
    to_remove = [t for t in auth_mod._sessions if t.startswith(token_prefix)]
    for t in to_remove:
        del auth_mod._sessions[t]
    return {"status": "ok"}


# ============================================================================
# SECURITY
# ============================================================================

@router.get("/admin/security")
async def get_security():
    settings = _load_settings()
    security = settings.get("security", {})
    return {
        "two_factor_enabled": security.get("two_factor_enabled", False),
        "active_sessions": len([t for t, exp in auth_mod._sessions.items() if exp > time.time()]),
    }


@router.post("/admin/security/2fa")
async def toggle_2fa(request: Request):
    data = await request.json()
    enabled = data.get("enabled", False)
    settings = _load_settings()
    settings.setdefault("security", {})["two_factor_enabled"] = enabled
    _save_settings(settings)
    if enabled:
        import pyotp
        secret = pyotp.random_base32()
        auth_mod.ADMIN_TOTP_SECRET = secret
        # Persist to .env
        _write_env({"ADMIN_TOTP_SECRET": secret})
        return {"status": "ok"}
    else:
        auth_mod.ADMIN_TOTP_SECRET = ""
        _write_env({"ADMIN_TOTP_SECRET": ""})
        return {"status": "ok"}


# ============================================================================
# PLUGINS (Search Sources)
# ============================================================================

@router.get("/admin/plugins", summary="Lister les plugins", description="Retourne la liste des sources de recherche et modules métier avec etat.")
async def get_plugins():
    from sources import SOURCES
    settings = _load_settings()
    disabled = settings.get("plugins", {}).get("disabled_sources", [])
    enabled_modules = settings.get("plugins", {}).get("enabled_modules", [])
    plugins = []
    for name, info in SOURCES.items():
        plugins.append({
            "name": name,
            "description": info.get("description", ""),
            "enabled": name not in disabled,
        })
    MODULE_NAMES = [
        "productivity", "design", "marketing", "engineering", "data",
        "finance", "product_management", "pdf_viewer", "sales", "operations",
        "legal", "enterprise_search", "small_business", "human_resources",
        "customer_support", "bio_research",
    ]
    modules = [{"name": m, "enabled": m in enabled_modules} for m in MODULE_NAMES]
    return {"plugins": plugins, "modules": modules}


@router.post("/admin/plugins/{name}/toggle", summary="Activer/Desactiver un plugin", description="Bascule l'etat enabled/disabled d'une source ou d'un module metier.")
async def toggle_plugin(name: str, request: Request):
    from sources import SOURCES
    data = await request.json()
    enabled = data.get("enabled", True)
    settings = _load_settings()
    plugins = settings.setdefault("plugins", {})

    # Handle source toggles (existing)
    if name in SOURCES:
        disabled = plugins.setdefault("disabled_sources", [])
        if enabled and name in disabled:
            disabled.remove(name)
        elif not enabled and name not in disabled:
            disabled.append(name)
        _save_settings(settings)
        return {"status": "ok", "enabled": enabled}

    # Handle module toggles
    MODULE_NAMES = [
        "productivity", "design", "marketing", "engineering", "data",
        "finance", "product_management", "pdf_viewer", "sales", "operations",
        "legal", "enterprise_search", "small_business", "human_resources",
        "customer_support", "bio_research",
    ]
    if name in MODULE_NAMES:
        enabled_modules = plugins.setdefault("enabled_modules", [])
        if enabled and name not in enabled_modules:
            enabled_modules.append(name)
        elif not enabled and name in enabled_modules:
            enabled_modules.remove(name)
        _save_settings(settings)
        return {"status": "ok", "enabled": enabled}

    raise HTTPException(status_code=404, detail=f"'{name}' inconnu")


# ============================================================================
# DEVELOPER
# ============================================================================

@router.get("/admin/developer", summary="Settings developpeur", description="Retourne les settings developpeur (webhooks, log level, streaming, RAG).")
async def get_developer():
    settings = _load_settings()
    dev = settings.get("developer", {})
    api_keys = settings.get("api_keys", {})
    return {
        "log_level": dev.get("log_level", "INFO"),
        "webhook_url": dev.get("webhook_url", ""),
        "webhooks_enabled": dev.get("webhooks_enabled", False),
        "streaming": dev.get("streaming", False),
        "rag": dev.get("rag", False),
        "api_keys": {
            "OPENROUTER_API_KEY": bool(api_keys.get("OPENROUTER_API_KEY")),
            "TAVILY_API_KEY": bool(api_keys.get("TAVILY_API_KEY")),
            "BRAVE_API_KEY": bool(api_keys.get("BRAVE_API_KEY")),
        },
    }


@router.post("/admin/developer", summary="Mettre a jour les settings developpeur", description="Ecrit les settings developpeur (webhooks, log level, streaming, RAG).")
async def update_developer(request: Request):
    data = await request.json()
    settings = _load_settings()
    dev = settings.setdefault("developer", {})
    for key in ["log_level", "webhook_url", "webhooks_enabled", "streaming", "rag"]:
        if key in data:
            dev[key] = data[key]
    # Apply log level change
    if "log_level" in data:
        import logging
        level = getattr(logging, data["log_level"].upper(), logging.INFO)
        logging.getLogger().setLevel(level)
    _save_settings(settings)
    return {"status": "ok"}


@router.post("/admin/api-keys")
async def update_api_keys(request: Request):
    data = await request.json()
    settings = _load_settings()
    api_keys = settings.setdefault("api_keys", {})
    for key in ["OPENROUTER_API_KEY", "TAVILY_API_KEY", "BRAVE_API_KEY"]:
        if key in data and data[key]:
            api_keys[key] = data[key]
    _save_settings(settings)
    # Update env vars in memory
    import os
    for key, val in api_keys.items():
        if val:
            os.environ[key] = val
    return {"status": "ok"}


# ============================================================================
# DATA
# ============================================================================

@router.get("/admin/data/export", summary="Exporter les conversations", description="Exporte les conversations en JSON ou CSV.")
async def export_data(format: str = Query("json", enum=["json", "csv"])):
    from threads import _get_db
    import csv
    import io
    from fastapi.responses import StreamingResponse

    db = _get_db()
    cursor = db.execute("SELECT id, title, created_at, updated_at FROM threads ORDER BY created_at DESC")

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["thread_id", "thread_title", "created_at", "updated_at", "role", "content", "metadata"])
        for row in cursor.fetchall():
            tid, title, created, updated = row
            msg_cursor = db.execute(
                "SELECT role, content, metadata FROM messages WHERE thread_id = ? ORDER BY created_at",
                (tid,)
            )
            for mrow in msg_cursor.fetchall():
                role, content, meta = mrow
                writer.writerow([tid, title, created, updated, role, content, meta])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=conversations.csv"},
        )

    threads = []
    for row in cursor.fetchall():
        tid, title, created, updated = row
        msg_cursor = db.execute(
            "SELECT role, content, metadata FROM messages WHERE thread_id = ? ORDER BY created_at",
            (tid,)
        )
        messages = []
        for mrow in msg_cursor.fetchall():
            role, content, meta = mrow
            messages.append({"role": role, "content": content, "metadata": meta})
        threads.append({
            "id": tid,
            "title": title,
            "created_at": created,
            "updated_at": updated,
            "messages": messages,
        })
    return {"threads": threads, "count": len(threads)}


@router.delete("/admin/data/history")
async def delete_history():
    from threads import _get_db
    db = _get_db()
    db.execute("DELETE FROM messages")
    db.execute("DELETE FROM threads")
    db.commit()
    return {"status": "ok", "message": "Historique supprimé"}


# ============================================================================
# DANGER ZONE
# ============================================================================

@router.post("/admin/danger/disconnect-all")
async def disconnect_all(request: Request):
    current_token = request.cookies.get("admin_session", "")
    to_remove = [t for t in auth_mod._sessions if t != current_token]
    for t in to_remove:
        del auth_mod._sessions[t]
    return {"status": "ok", "disconnected": len(to_remove)}


@router.post("/admin/danger/reset")
async def reset_settings():
    import json
    settings_file = BASE_DIR / "data" / "settings.json"
    if settings_file.exists():
        settings_file.unlink()
    return {"status": "ok", "message": "Paramètres réinitialisés"}


@router.get("/admin/docs", summary="Documentation interactive")
async def docs_ui():
    """Sert la documentation interactive."""
    docs = ADMIN_DIR / "docs.html"
    if not docs.exists():
        raise HTTPException(status_code=404, detail="Docs not found")
    return FileResponse(docs, media_type="text/html")


# ============================================================================
# STATIC FILES — doit etre EN DERNIER pour ne pas intercepter les routes API
# ============================================================================

@router.get("/admin/{filename:path}")
async def serve_admin_static(filename: str):
    """Sert les fichiers statiques du dossier admin (CSS, JS, images, etc.)."""
    # Racine /admin → redirect vers login
    if not filename or filename == "/":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login.html", status_code=302)

    # Securite : empecher les traversées de répertoire
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")

    # Try exact path first, then with .html extension
    file_path = ADMIN_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        file_path = ADMIN_DIR / (filename + ".html")
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

    # Determiner le type MIME
    _MIME_TYPES = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".html": "text/html",
    }
    suffix = file_path.suffix.lower()
    media_type = _MIME_TYPES.get(suffix, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type)
