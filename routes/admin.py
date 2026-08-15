"""
Routes admin — panneau d'administration.
Extrait de server.py lors du refactoring.
"""

import os
import asyncio
import re
import time
import logging
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from agent import MODEL_POOL
from sources import SOURCES
from sources.router import INTENT_INDEX, DOMAIN_INDEX, TOOL_LEVELS
from clients import (
    create_client,
    list_clients,
    get_client,
    deactivate_client,
    activate_client,
    delete_client,
    regenerate_api_key,
    get_client_logs,
    get_client_stats as get_global_client_stats,
)
from routes.auth import (
    ADMIN_USER,
    ADMIN_PASSWORD,
    ADMIN_TOTP_SECRET,
    _sessions,
    _validate_session,
    _create_session,
    _check_login_rate,
    LoginRequest,
    ADMIN_STATIC_PATHS,
    ADMIN_API_LOGIN,
    ADMIN_API_LOGOUT,
    ADMIN_API_CHECK,
)

logger = logging.getLogger("websearch-agent")
router = APIRouter()

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
    """Ecrit les cles dans le fichier .env."""
    existing = _read_env()
    existing.update(data)
    lines = []
    for key, value in existing.items():
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n")


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@router.post("/admin/api/login")
async def login(req: LoginRequest, request: Request):
    """Authentifie l'admin et cree une session."""
    client_ip = request.client.host if request.client else "unknown"

    if not _check_login_rate(client_ip):
        raise HTTPException(status_code=429, detail="Trop de tentatives. Reessayez dans 5 minutes.")

    if req.username != ADMIN_USER or req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

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
        max_age=86400,
    )
    logger.info("Admin connecte")
    return response


@router.post("/admin/api/logout")
async def logout(request: Request):
    """Deconnecte l'admin."""
    token = request.cookies.get("admin_session")
    if token and token in _sessions:
        del _sessions[token]
    response = JSONResponse({"status": "disconnected"})
    response.delete_cookie("admin_session")
    return response


@router.get("/admin/api/auth/check")
async def check_auth(request: Request):
    """Verifie si l'admin est authentifie."""
    token = request.cookies.get("admin_session")
    if _validate_session(token):
        return {"authenticated": True}
    return {"authenticated": False}


@router.get("/admin/api/2fa/setup")
async def setup_2fa():
    """Retourne les informations de setup 2FA."""
    if not ADMIN_TOTP_SECRET:
        return {"enabled": False, "message": "2FA non configure"}
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
async def reveal_env_key(key: str):
    env = _read_env()
    return {"key": key, "value": env.get(key, "")}


@router.get("/admin/env")
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


@router.post("/admin/env")
async def set_env(request: Request):
    data = await request.json()
    clean = {}
    for key, value in data.items():
        if value and "..." not in value and value != "***":
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


@router.get("/admin/logs")
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

@router.get("/admin/clients")
async def get_clients():
    return {"clients": list_clients(), "stats": get_global_client_stats()}


@router.post("/admin/clients")
async def create_new_client(request: Request):
    data = await request.json()
    name = data.get("name", "Unnamed")
    client = create_client(name)
    return client


@router.get("/admin/clients/{client_id}")
async def get_client_detail(client_id: str):
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouve.")
    return client


@router.post("/admin/clients/{client_id}/deactivate")
async def deactivate(client_id: str):
    deactivate_client(client_id)
    return {"status": "deactivated"}


@router.post("/admin/clients/{client_id}/activate")
async def activate(client_id: str):
    activate_client(client_id)
    return {"status": "activated"}


@router.delete("/admin/clients/{client_id}")
async def remove_client(client_id: str):
    delete_client(client_id)
    return {"status": "deleted"}


@router.post("/admin/clients/{client_id}/regenerate")
async def regenerate(client_id: str):
    new_key = regenerate_api_key(client_id)
    return {"api_key": new_key}


@router.get("/admin/clients/{client_id}/logs")
async def get_client_logs(client_id: str, limit: int = Query(100, ge=1, le=1000)):
    return get_client_logs(client_id, limit=limit)


@router.get("/admin/clients/{client_id}/stats")
async def get_single_client_stats(client_id: str):
    from clients import get_client_stats as _get_stats
    return _get_stats(client_id)


# ============================================================================
# SERVICE CONTROL
# ============================================================================

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
async def service_restart():
    """Redemarre le service via systemctl (en background)."""
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
async def service_stop():
    """Arrete le service via systemctl (en background)."""
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

@router.get("/admin/settings")
async def get_settings():
    import json
    settings_file = BASE_DIR / "data" / "settings.json"
    if settings_file.exists():
        return json.loads(settings_file.read_text())
    return {}


@router.post("/admin/settings")
async def update_settings(request: Request):
    import json
    data = await request.json()
    settings_file = BASE_DIR / "data" / "settings.json"
    existing = {}
    if settings_file.exists():
        existing = json.loads(settings_file.read_text())
    existing.update(data)
    settings_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    return {"status": "ok"}


# ============================================================================
# ACCOUNT
# ============================================================================

@router.get("/admin/account")
async def get_account():
    import json
    settings_file = BASE_DIR / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    account = settings.get("account", {})
    return {
        "email": account.get("email", "admin@websearch.local"),
    }


@router.post("/admin/account/email")
async def update_account_email(request: Request):
    import json
    data = await request.json()
    email = data.get("email", "")
    settings_file = BASE_DIR / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    settings.setdefault("account", {})["email"] = email
    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
    return {"status": "ok"}


@router.post("/admin/account/password")
async def update_account_password(request: Request):
    data = await request.json()
    current = data.get("current", "")
    new_password = data.get("new", "")
    if not current or not new_password:
        raise HTTPException(status_code=400, detail="Champs manquants")
    from routes.auth import ADMIN_PASSWORD
    if current != ADMIN_PASSWORD:
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 6 caractères")
    # Update .env file
    env_file = BASE_DIR / ".env"
    env_lines = env_file.read_text().splitlines() if env_file.exists() else []
    found = False
    for i, line in enumerate(env_lines):
        if line.startswith("ADMIN_PASSWORD="):
            env_lines[i] = f"ADMIN_PASSWORD={new_password}"
            found = True
            break
    if not found:
        env_lines.append(f"ADMIN_PASSWORD={new_password}")
    env_file.write_text("\n".join(env_lines) + "\n")
    return {"status": "ok", "message": "Mot de passe mis à jour. Redémarrez le service."}


@router.get("/admin/account/sessions")
async def get_sessions(request: Request):
    from routes.auth import _sessions, _SESSION_TTL
    current_token = request.cookies.get("admin_session", "")
    sessions = []
    now = time.time()
    for token, expiry in _sessions.items():
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
    from routes.auth import _sessions
    to_remove = [t for t in _sessions if t.startswith(token_prefix)]
    for t in to_remove:
        del _sessions[t]
    return {"status": "ok"}


# ============================================================================
# SECURITY
# ============================================================================

@router.get("/admin/security")
async def get_security():
    import json
    from routes.auth import ADMIN_TOTP_SECRET, _sessions
    settings_file = BASE_DIR / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    security = settings.get("security", {})
    return {
        "two_factor_enabled": bool(ADMIN_TOTP_SECRET),
        "active_sessions": len([t for t, exp in _sessions.items() if exp > time.time()]),
    }


@router.post("/admin/security/2fa")
async def toggle_2fa(request: Request):
    import json
    data = await request.json()
    enabled = data.get("enabled", False)
    settings_file = BASE_DIR / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    settings.setdefault("security", {})["two_factor_enabled"] = enabled
    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
    if enabled:
        import secrets
        secret = secrets.token_hex(20)
        env_file = BASE_DIR / ".env"
        env_lines = env_file.read_text().splitlines() if env_file.exists() else []
        found = False
        for i, line in enumerate(env_lines):
            if line.startswith("ADMIN_TOTP_SECRET="):
                env_lines[i] = f"ADMIN_TOTP_SECRET={secret}"
                found = True
                break
        if not found:
            env_lines.append(f"ADMIN_TOTP_SECRET={secret}")
        env_file.write_text("\n".join(env_lines) + "\n")
        return {"status": "ok", "secret": secret}
    return {"status": "ok"}


# ============================================================================
# PLUGINS (Search Sources)
# ============================================================================

@router.get("/admin/plugins")
async def get_plugins():
    import json
    from sources import SOURCES
    settings_file = BASE_DIR / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    disabled = settings.get("plugins", {}).get("disabled_sources", [])
    plugins = []
    for name, info in SOURCES.items():
        plugins.append({
            "name": name,
            "description": info.get("description", ""),
            "enabled": name not in disabled,
        })
    return {"plugins": plugins}


@router.post("/admin/plugins/{name}/toggle")
async def toggle_plugin(name: str, request: Request):
    import json
    from sources import SOURCES
    if name not in SOURCES:
        raise HTTPException(status_code=404, detail=f"Source '{name}' inconnue")
    data = await request.json()
    enabled = data.get("enabled", True)
    settings_file = BASE_DIR / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    disabled = settings.setdefault("plugins", {}).setdefault("disabled_sources", [])
    if enabled and name in disabled:
        disabled.remove(name)
    elif not enabled and name not in disabled:
        disabled.append(name)
    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
    return {"status": "ok", "enabled": enabled}


# ============================================================================
# DEVELOPER
# ============================================================================

@router.get("/admin/developer")
async def get_developer():
    import json
    settings_file = BASE_DIR / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    dev = settings.get("developer", {})
    return {
        "log_level": dev.get("log_level", "INFO"),
        "webhook_url": dev.get("webhook_url", ""),
        "webhooks_enabled": dev.get("webhooks_enabled", False),
        "streaming": dev.get("streaming", False),
        "rag": dev.get("rag", False),
    }


@router.post("/admin/developer")
async def update_developer(request: Request):
    import json
    data = await request.json()
    settings_file = BASE_DIR / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    dev = settings.setdefault("developer", {})
    for key in ["log_level", "webhook_url", "webhooks_enabled", "streaming", "rag"]:
        if key in data:
            dev[key] = data[key]
    # Apply log level change
    if "log_level" in data:
        import logging
        level = getattr(logging, data["log_level"].upper(), logging.INFO)
        logging.getLogger().setLevel(level)
    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
    return {"status": "ok"}


# ============================================================================
# DATA
# ============================================================================

@router.get("/admin/data/export")
async def export_data():
    from threads import list_threads, _get_db
    db = _get_db()
    cursor = db.execute("SELECT id, title, created_at, updated_at FROM threads ORDER BY created_at DESC")
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
    from routes.auth import _sessions
    current_token = request.cookies.get("admin_session", "")
    to_remove = [t for t in _sessions if t != current_token]
    for t in to_remove:
        del _sessions[t]
    return {"status": "ok", "disconnected": len(to_remove)}


@router.post("/admin/danger/reset")
async def reset_settings():
    import json
    settings_file = BASE_DIR / "data" / "settings.json"
    if settings_file.exists():
        settings_file.unlink()
    return {"status": "ok", "message": "Paramètres réinitialisés"}


# ============================================================================
# STATIC FILES — doit etre EN DERNIER pour ne pas intercepter les routes API
# ============================================================================

@router.get("/admin/{filename:path}")
async def serve_admin_static(filename: str):
    """Sert les fichiers statiques du dossier admin (CSS, JS, images, etc.)."""
    # Securite : empecher les traversées de répertoire
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")

    file_path = ADMIN_DIR / filename
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
