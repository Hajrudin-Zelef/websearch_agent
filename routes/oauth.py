"""
OAuth2 Token Endpoint — authentification client_credentials avec JWT.
"""

import logging
import os
import time
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("websearch-agent.oauth")
router = APIRouter(tags=["OAuth2"])

# ============================================================================
# CONFIG
# ============================================================================

_JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_SECONDS = 3600  # 1 hour

# ============================================================================
# JWT HELPERS
# ============================================================================


def create_access_token(client_id: str, client_name: str = "") -> str:
    """Crée un JWT access token pour un client."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": client_id,
        "name": client_name,
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
            client = get_client(payload["sub"])
            if client and client["active"]:
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


# ============================================================================
# TOKEN ENDPOINT
# ============================================================================


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    client_id: str


@router.post("/oauth/token", response_model=TokenResponse, summary="Obtenir un access token",
             description="Authentifie un client via client_id + client_secret et retourne un JWT access token (valide 1h).")
async def token(req: TokenRequest) -> TokenResponse:
    from clients import authenticate_client

    client = authenticate_client(req.client_id, req.client_secret)
    if not client:
        raise HTTPException(
            status_code=401,
            detail="Identifiants invalides ou client desactive.",
        )

    access_token = create_access_token(client["id"], client["name"])

    logger.info("Token issued for client: %s (%s)", client["name"], client["id"])

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=_JWT_EXPIRY_SECONDS,
        client_id=client["id"],
    )
