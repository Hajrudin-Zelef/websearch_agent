"""
Routes admin — panneau d'administration.
Extrait de server.py lors du refactoring.
"""

import os
import re
import logging
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse

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
    get_client_stats,
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
    log_file = BASE_DIR / "websearch-agent.log"
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

        log_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(\w+)\]\s+(.*)')

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
                })

        return {"logs": parsed_logs[-lines:], "stats": stats}
    except Exception as e:
        return {"logs": [], "stats": {"total": 0, "error": 0, "warning": 0, "info": 0}, "error": str(e)}


# ============================================================================
# CLIENTS CRUD
# ============================================================================

@router.get("/admin/clients")
async def get_clients():
    return list_clients()


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
async def get_client_stats(client_id: str):
    return get_client_stats(client_id)


# ============================================================================
# SETTINGS
# ============================================================================

@router.get("/admin/settings")
async def get_settings():
    import json
    settings_file = BASE_DIR / "settings.json"
    if settings_file.exists():
        return json.loads(settings_file.read_text())
    return {}


@router.post("/admin/settings")
async def update_settings(request: Request):
    import json
    data = await request.json()
    settings_file = BASE_DIR / "settings.json"
    existing = {}
    if settings_file.exists():
        existing = json.loads(settings_file.read_text())
    existing.update(data)
    settings_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    return {"status": "ok"}
