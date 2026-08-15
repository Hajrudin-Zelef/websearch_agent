"""
Routes API principales — /chat, /search, /datasets, /health, /threads.
Extrait de server.py lors du refactoring.
"""

import asyncio
import logging
import time
import unicodedata
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent import run_agent_async
from core.prompts import _get_refusal_markers
from sources.datasets import datasets_search
from sources import SOURCES
from threads import (
    create_thread,
    add_message,
    get_thread,
    list_threads,
    delete_thread,
    get_thread_context,
)
from routes.rate_limit import _check_rate

logger = logging.getLogger("websearch-agent")
router = APIRouter()


def _is_refusal(text: str) -> bool:
    """Detecte si la reponse est un refus — markers + heuristiques."""
    if not text or len(text.strip()) < 10:
        return True  # Trop court = refus implicite

    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))

    # 1. Check markers de refus
    markers = _get_refusal_markers()
    if any(marker.lower() in normalized for marker in markers):
        return True

    # 2. Heuristiques
    # Pas de source citee ([1], [2], etc.)
    import re
    has_citation = bool(re.search(r'\[\d+\]', text))
    word_count = len(text.split())

    # Reponse tres courte sans citation = probable refus
    if word_count < 15 and not has_citation:
        return True

    # Reponse qui commence par des mots de refus implicite
    refusal_starts = [
        "desole", "desolé", "pardonnez", "excusez",
        "sorry", "apologies", "unfortunately",
        "je n'ai pas", "je ne trouve pas", "impossible",
    ]
    if any(normalized.startswith(start) for start in refusal_starts):
        return True

    return False


# ============================================================================
# CHAT
# ============================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    thread_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    refused: bool = False
    thread_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    client_ip = request.client.host if request.client else "unknown"

    # Verification API key (optionnelle — backward compatible)
    api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if api_key:
        from clients import get_client_by_api_key
        client = get_client_by_api_key(api_key)
        if not client:
            raise HTTPException(status_code=401, detail="Cle d'API invalide ou desactivee.")
        # Rate limit par cle API (plus generoux que par IP)
        client_id = client["id"]
        if not _check_rate(f"apikey:{client_id}"):
            logger.warning("Rate limit atteint pour API key %s", client_id)
            raise HTTPException(status_code=429, detail="Trop de requetes pour cette cle API.")
        request.state.client = client
    else:
        # Pas de cle API — rate limit par IP (backward compatible)
        if not _check_rate(client_ip):
            logger.warning("Rate limit atteint pour %s", client_ip)
            raise HTTPException(status_code=429, detail="Trop de requetes. Reessaie dans une minute.")

    logger.info("Query (%d chars): %.100s", len(req.message), req.message)

    thread_id = req.thread_id
    if not thread_id:
        thread_id = create_thread(req.message)
    else:
        existing = get_thread(thread_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Thread non trouve.")

    try:
        result = await run_agent_async(req.message, thread_id=thread_id)
        answer = result["response"]
        agent_metadata = result["metadata"]
        refused = _is_refusal(answer)

        request.state.agent_metadata = agent_metadata

        asyncio.create_task(asyncio.to_thread(
            add_message, thread_id, "assistant", answer, {"refused": refused}
        ))

        return {"response": answer, "refused": refused, "thread_id": thread_id}
    except Exception as e:
        logger.error("Erreur agent: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur.")


# ============================================================================
# DATASETS
# ============================================================================

@router.get("/datasets")
async def list_datasets(
    query: str = "",
    max_results: int = Query(10, ge=1, le=100),
    request: Request = None,
):
    client_ip = request.client.host if request and request.client else "unknown"

    if not _check_rate(client_ip):
        raise HTTPException(status_code=429, detail="Trop de requetes. Reessaie dans une minute.")

    logger.info("Datasets query: %.100s", query)
    try:
        results = datasets_search(query=query, max_results=max_results)
        return {"query": query, "count": len(results), "datasets": results}
    except Exception as e:
        logger.error("Erreur datasets: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur.")


# ============================================================================
# HEALTH
# ============================================================================

@router.get("/health")
async def health():
    """Health check verifie DB + memoire."""
    checks = {"status": "ok", "db": "ok"}
    try:
        from threads import _get_db
        db = _get_db()
        db.execute("SELECT 1")
    except Exception as e:
        checks["status"] = "degraded"
        checks["db"] = f"error: {type(e).__name__}"
    return checks


@router.get("/metrics")
async def metrics():
    """Metriques detaillees — sources, cache, agent, circuit breaker."""
    from core.monitoring import get_all_metrics
    from core.cache import _cache_stats
    from core.circuit_breaker import circuit_breaker

    all_metrics = get_all_metrics()
    all_metrics["cache"]["size"] = _cache_stats()["size"]
    all_metrics["cache"]["max_size"] = _cache_stats()["max_size"]
    all_metrics["circuit_breaker"] = circuit_breaker.stats()
    return all_metrics


# ============================================================================
# SEARCH — endpoint structure pour DSH
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


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str,
    max_results: int = Query(10, ge=1, le=30),
    request: Request = None,
):
    """Endpoint de recherche structuree pour providers externes (DSH)."""
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

        all_results: list[dict] = []
        from core.monitoring import source_stats
        from core.circuit_breaker import circuit_breaker

        def _run_source(tool_name: str) -> list[dict]:
            # Circuit breaker : skip si trop d'echecs recents
            if not circuit_breaker.allow_request(tool_name):
                logger.info("Circuit breaker: %s skip (trop d'echecs)", tool_name)
                return []

            start = time.time()
            try:
                func = get_source(tool_name.replace("_search", "") if tool_name.endswith("_search") else tool_name)
                result = func(query=q, max_results=min(max_results, 5))
                duration = time.time() - start
                source_stats.record(tool_name, True, duration)
                circuit_breaker.record_success(tool_name)
                return result
            except Exception as e:
                duration = time.time() - start
                source_stats.record(tool_name, False, duration)
                circuit_breaker.record_failure(tool_name)
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

        seen_urls: set[str] = set()
        unique_results: list[dict] = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        # Trier par pertinence (score decroissant)
        from core.tools import _sort_results_by_relevance
        unique_results = _sort_results_by_relevance(unique_results)

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
# THREADS
# ============================================================================

class ThreadSummary(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float


class ThreadDetail(BaseModel):
    id: str
    title: str
    messages: list[dict]
    created_at: float
    updated_at: float


@router.get("/threads", response_model=list[ThreadSummary])
async def get_threads():
    return list_threads()


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
async def get_thread_detail(thread_id: str):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread non trouve.")
    return thread


@router.delete("/threads/{thread_id}")
async def remove_thread(thread_id: str):
    delete_thread(thread_id)
    return {"status": "deleted"}


@router.get("/threads/{thread_id}/context")
async def get_thread_ctx(thread_id: str):
    context = get_thread_context(thread_id)
    return {"thread_id": thread_id, "context": context}
