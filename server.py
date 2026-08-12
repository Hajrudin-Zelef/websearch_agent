"""
Serveur FastAPI — endpoint POST /chat avec rate limiting et validation.
Ecoute sur 127.0.0.1:8000 (interne uniquement).

Optimisations :
- run_agent_async (ne bloque pas l'event loop)
- Rate limiter sans memory leak (deque borné)
- Validation Pydantic stricte
- Threads SQLite pour l'historique et les follow-ups
"""

import time
import logging
import threading
import unicodedata
from collections import defaultdict, deque
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

from agent import run_agent_async, REFUSAL_MARKERS
from sources.datasets import datasets_search
from threads import (
    create_thread,
    add_message,
    get_thread,
    list_threads,
    delete_thread,
    get_thread_context,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("websearch-agent")

app = FastAPI(title="WebSearch Agent")

# --- CORS (origines explicites uniquement) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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

# --- Rate limiting (sliding window, borné, sans memory leak) ---
_RATE_WINDOW = 60
_RATE_MAX = 30
_rate_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_RATE_MAX + 1))
_rate_lock = threading.Lock()


def _check_rate(client_ip: str) -> bool:
    now = time.time()
    window_start = now - _RATE_WINDOW
    with _rate_lock:
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
    with _rate_lock:
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

    # Nettoyage periodique (1 chance sur 100 a chaque requete)
    if time.time() % 100 < 1:
        _cleanup_rate_history()

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
        answer = await run_agent_async(req.message, thread_id=thread_id)
        refused = _is_refusal(answer)

        # Sauvegarder la reponse dans le thread
        add_message(thread_id, "assistant", answer, metadata={"refused": refused})

        return ChatResponse(response=answer, refused=refused, thread_id=thread_id)
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
    return {"status": "ok"}


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
