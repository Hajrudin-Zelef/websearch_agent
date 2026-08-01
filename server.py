"""
Serveur FastAPI — endpoint POST /chat avec rate limiting et validation.
Ecoute sur 127.0.0.1:8000 (interne uniquement).

Optimisations :
- run_agent_async (ne bloque pas l'event loop)
- Rate limiter sans memory leak (deque borné)
- Validation Pydantic stricte
"""

import time
import logging
import unicodedata
from collections import defaultdict, deque
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent import run_agent_async, REFUSAL_MARKERS
from sources.datasets import datasets_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("websearch-agent")

app = FastAPI(title="WebSearch Agent")

# --- Rate limiting (sliding window, borné, sans memory leak) ---
_RATE_WINDOW = 60
_RATE_MAX = 30
_rate_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_RATE_MAX + 1))


def _check_rate(client_ip: str) -> bool:
    now = time.time()
    window_start = now - _RATE_WINDOW
    hits = _rate_history[client_ip]

    # Supprimer les timestamps expires
    while hits and hits[0] < window_start:
        hits.popleft()

    if len(hits) >= _RATE_MAX:
        return False

    hits.append(now)
    return True


def _cleanup_rate_history():
    """Nettoyage periodique des IPs inactives."""
    now = time.time()
    window_start = now - _RATE_WINDOW
    empty_ips = [
        ip for ip, hits in _rate_history.items()
        if not hits or hits[-1] < window_start
    ]
    for ip in empty_ips:
        del _rate_history[ip]


def _is_refusal(text: str) -> bool:
    """Detecte si la réponse est un refus."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return any(marker.lower() in normalized for marker in REFUSAL_MARKERS)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)


class ChatResponse(BaseModel):
    response: str
    refused: bool = False


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate(client_ip):
        logger.warning("Rate limit atteint pour %s", client_ip)
        raise HTTPException(status_code=429, detail="Trop de requetes. Reessaie dans une minute.")

    # Nettoyage periodique (1 chance sur 100 a chaque requete)
    if time.time() % 100 < 1:
        _cleanup_rate_history()

    logger.info("Query (%d chars): %.100s", len(req.message), req.message)
    try:
        answer = await run_agent_async(req.message)
        refused = _is_refusal(answer)
        return ChatResponse(response=answer, refused=refused)
    except Exception as e:
        logger.error("Erreur agent: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Erreur interne lors de la recherche.")


@app.get("/datasets")
async def list_datasets(query: str = "", max_results: int = 10, request: Request = None):
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
        raise HTTPException(status_code=500, detail="Erreur interne lors de la recherche de datasets.")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.error("Exception non geree: %s: %s", type(exc).__name__, exc)
    return JSONResponse(status_code=500, content={"error": "Erreur interne du serveur."})
