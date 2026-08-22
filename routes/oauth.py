"""
OAuth2 Token Endpoint — authentification client_credentials avec JWT + scopes.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("websearch-agent.oauth")
router = APIRouter(tags=["OAuth2"])

# ============================================================================
# CONFIG
# ============================================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
_OAUTH_ALLOW_ACCESS_TOKEN_REFRESH = os.getenv("OAUTH_ALLOW_ACCESS_TOKEN_REFRESH", "true").lower() == "true"

_JWT_SECRET = os.getenv("JWT_SECRET", "")
if not _JWT_SECRET:
    if ENVIRONMENT == "production":
        raise RuntimeError(
            "JWT_SECRET must be set in production. "
            "Refusing to start without a stable JWT secret."
        )
    _JWT_SECRET = secrets.token_hex(32)
    logger.warning("JWT_SECRET not set — using random secret (tokens invalid on restart)")

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_SECONDS = 3600  # 1 hour
_JWT_REFRESH_GRACE_SECONDS = 900  # 15 min grace period for refresh

# ============================================================================
# JWT HELPERS
# ============================================================================


def create_access_token(client_id: str, client_name: str = "", scopes: list[str] | None = None) -> str:
    """Crée un JWT access token pour un client avec ses scopes."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": client_id,
        "name": client_name,
        "scopes": scopes or [],
        "iat": now,
        "exp": now + timedelta(seconds=_JWT_EXPIRY_SECONDS),
        "iss": "websearch-agent",
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_access_token(token: str) -> dict | None:
    """Décode et valide un JWT. Retourne le payload ou None si invalide."""
    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
            issuer="websearch-agent",
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid token: %s", e)
        return None


def decode_expired_token(token: str) -> dict | None:
    """Décode un JWT même expiré (pour le refresh). Retourne le payload ou None."""
    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
            issuer="websearch-agent",
            options={"verify_exp": False},
        )
        # Check if within grace period
        exp = payload.get("exp")
        if exp:
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            if (now - exp_dt).total_seconds() > _JWT_REFRESH_GRACE_SECONDS:
                logger.debug("Token too old for refresh (expired > %ds ago)", _JWT_REFRESH_GRACE_SECONDS)
                return None
        return payload
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid token for refresh: %s", e)
        return None


def extract_and_verify_client(request: Request) -> dict | None:
    """Extrait et vérifie l'identité du client via JWT ou API key.
    Retourne le dict client ou None."""
    # 1. Try JWT from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # First try JWT
        payload = verify_access_token(token)
        if payload:
            from clients import get_client
            client_id = payload.get("sub")
            if not client_id:
                return None
            client = get_client(client_id)
            if client and client["active"]:
                # Attach JWT scopes to client for downstream checks
                client["_jwt_scopes"] = payload.get("scopes", [])
                return client
        # Then try API key (ws_...) in Bearer
        if token.startswith("ws_"):
            from clients import get_client_by_api_key
            client = get_client_by_api_key(token)
            if client:
                return client

    # 2. Try X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        from clients import get_client_by_api_key
        client = get_client_by_api_key(api_key)
        if client:
            return client

    return None


def get_client_scopes(client: dict) -> list[str]:
    """Retourne les scopes d'un client. DB = source de verite (ignore JWT scopes)."""
    return client.get("scopes", [])


def require_scope(required_scope: str):
    """Decorator pour vérifier qu'un client a un scope donné."""
    def checker(client: dict | None):
        if not client:
            raise HTTPException(status_code=401, detail="Non authentifie.")
        scopes = get_client_scopes(client)
        if required_scope not in scopes:
            raise HTTPException(
                status_code=403,
                detail="Scope insuffisant.",
            )
        return True
    return checker


# ============================================================================
# TOKEN ENDPOINT
# ============================================================================


class TokenRequest(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=128)
    client_secret: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    client_id: str
    scopes: list[str]


@router.post("/oauth/token", response_model=TokenResponse, summary="Obtenir un access token",
             description="Authentifie un client via client_id + client_secret et retourne un JWT access token.")
async def token(req: TokenRequest, request: Request) -> TokenResponse:
    from clients import authenticate_client
    from routes.rate_limit import _check_rate

    # Rate limit per IP on token endpoint
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_ok, retry_after = _check_rate(f"oauth_token:{client_ip}", max_requests=10)
    if not rate_limit_ok:
        raise HTTPException(status_code=429, detail=f"Trop de tentatives. Retry dans {retry_after}s.")

    client = authenticate_client(req.client_id, req.client_secret)
    if not client:
        raise HTTPException(
            status_code=401,
            detail="Identifiants invalides ou client desactive.",
        )

    scopes = client.get("scopes", [])
    access_token = create_access_token(client["id"], client["name"], scopes)

    logger.info("Token issued for client: %s (%s)", client["name"], client["id"])

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=_JWT_EXPIRY_SECONDS,
        client_id=client["id"],
        scopes=scopes,
    )


# ============================================================================
# TOKEN REFRESH
# ============================================================================


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=2048)


@router.post("/oauth/token/refresh", response_model=TokenResponse, summary="Rafraichir un access token",
             description="Échange un access token (valide ou récemment expiré) contre un nouveau token.")
async def refresh_token(req: RefreshRequest) -> TokenResponse:
    from clients import get_client

    if not _OAUTH_ALLOW_ACCESS_TOKEN_REFRESH:
        raise HTTPException(status_code=404, detail="Endpoint desactive.")

    # Try to decode the token (valid or within grace period)
    payload = decode_expired_token(req.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou trop ancien pour etre rafraichi.",
        )

    client_id = payload.get("sub")
    if not client_id:
        raise HTTPException(status_code=401, detail="Token invalide.")

    client = get_client(client_id)
    if not client or not client["active"]:
        raise HTTPException(
            status_code=401,
            detail="Client introuvable ou desactive.",
        )

    # Use DB scopes (client may have been updated since token was issued)
    scopes = client.get("scopes", [])
    new_token = create_access_token(client["id"], client["name"], scopes)

    logger.info("Token refreshed for client: %s (%s)", client["name"], client["id"])

    return TokenResponse(
        access_token=new_token,
        token_type="Bearer",
        expires_in=_JWT_EXPIRY_SECONDS,
        client_id=client["id"],
        scopes=scopes,
    )
