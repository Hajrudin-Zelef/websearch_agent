"""
Serveur FastAPI — endpoint POST /chat avec rate limiting et validation.
Écoute sur 127.0.0.1:8000 (interne uniquement).
"""

import time
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent import run_agent, REFUSAL_MARKERS
from sources.datasets import datasets_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("websearch-agent")

app = FastAPI(title="WebSearch Agent")

# --- Rate limiting (sliding window local) ---
_RATE_WINDOW = 60
_RATE_MAX = 30
_rate_history: dict[str, list[float]] = {}

def _check_rate(client_ip: str) -> bool:
    now = time.time()
    window_start = now - _RATE_WINDOW
    hits = [t for t in _rate_history.get(client_ip, []) if t > window_start]
    _rate_history[client_ip] = hits
    if len(hits) >= _RATE_MAX:
        return False
    hits.append(now)
    if len(_rate_history) > 100:
        _rate_history.clear()
    return True


def _is_refusal(text: str) -> bool:
    """Détecte si la réponse est un refus (pas de résultat trouvé)."""
    text_lower = text.lower()
    return any(marker.lower() in text_lower for marker in REFUSAL_MARKERS)


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
        raise HTTPException(status_code=429, detail="Trop de requêtes. Réessaie dans une minute.")

    logger.info("Query (%d chars): %.100s", len(req.message), req.message)
    try:
        answer = run_agent(req.message)
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
    logger.error("Exception non gérée: %s: %s", type(exc).__name__, exc)
    return JSONResponse(status_code=500, content={"error": "Erreur interne du serveur."})
