"""
Routes API principales — /chat, /search, /datasets, /health, /threads.
Extrait de server.py lors du refactoring.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
import unicodedata
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent import run_agent_async
from core.events import fire_webhook
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
from core.monitoring import agent_stats, rate_limit_stats
from routes.oauth import extract_and_verify_client, require_scope

logger = logging.getLogger("websearch-agent")
router = APIRouter(tags=["API"])

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
PUBLIC_API_ANONYMOUS = os.getenv("PUBLIC_API_ANONYMOUS", "true").lower() == "true"


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


@router.post("/chat", response_model=ChatResponse, summary="Envoyer un message", description="Envoie un message a l'agent et retourne la reponse. Cree automatiquement un thread.")
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    req_id = uuid.uuid4().hex[:8]
    client_ip = request.client.host if request.client else "unknown"

    # Auth centralisée (JWT ou API key)
    has_credentials = (
        request.headers.get("Authorization", "").startswith("Bearer ")
        or request.headers.get("X-API-Key")
    )
    client = extract_and_verify_client(request)
    if client:
        require_scope("write")(client)
        client_id = client["id"]
        client_rate_limit = client.get("rate_limit", 30)
        rate_limit_ok, retry_after = _check_rate(f"client:{client_id}", max_requests=client_rate_limit)
        if not rate_limit_ok:
            rate_limit_stats.record(f"client:{client_id}")
            logger.warning("[%s] Rate limit atteint pour client %s (limite: %d)", req_id, client_id, client_rate_limit)
            raise HTTPException(status_code=429, detail=f"Trop de requetes. Limite: {client_rate_limit}/min. Retry dans {retry_after}s.")
        request.state.client = client
    elif has_credentials:
        raise HTTPException(status_code=401, detail="Cle d'API ou token invalide.")
    else:
        # Pas de credentials — rate limit par IP (backward compatible)
        rate_limit_ok, retry_after = _check_rate(f"ip:{client_ip}")
        if not rate_limit_ok:
            rate_limit_stats.record(client_ip)
            logger.warning("[%s] Rate limit atteint pour %s", req_id, client_ip)
            raise HTTPException(status_code=429, detail=f"Trop de requetes. Retry dans {retry_after}s.")

    logger.info("[%s] Requête reçue: %d chars", req_id, len(req.message[:100]))

    thread_id = req.thread_id
    if not thread_id:
        thread_id = create_thread(req.message)
    else:
        existing = get_thread(thread_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Thread non trouve.")

    start = time.time()
    try:
        result = await run_agent_async(req.message, thread_id=thread_id, request_id=req_id)
        answer = result["response"]
        agent_metadata = result["metadata"]
        refused = _is_refusal(answer)
        duration = time.time() - start

        request.state.agent_metadata = agent_metadata

        asyncio.create_task(asyncio.to_thread(
            add_message, thread_id, "assistant", answer, {"refused": refused}
        ))

        model_used = agent_metadata.get("model", "unknown")
        logger.info("[%s] Réponse envoyée en %.1fs (modèle: %s, refusé: %s)", req_id, duration, model_used, refused)
        agent_stats.record(True, duration)
        asyncio.create_task(fire_webhook("chat.completed", {
            "request_id": req_id,
            "thread_id": thread_id,
            "model": model_used,
            "duration": round(duration, 2),
            "refused": refused,
            "message_length": len(req.message),
        }))
        return {"response": answer, "refused": refused, "thread_id": thread_id}
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start
        agent_stats.record(False, duration)
        logger.error("[%s] Erreur après %.1fs: %s: %s", req_id, duration, type(e).__name__, e)
        asyncio.create_task(fire_webhook("chat.error", {
            "request_id": req_id,
            "thread_id": thread_id,
            "error": type(e).__name__,
            "duration": round(duration, 2),
        }))
        raise HTTPException(status_code=500, detail="Erreur interne du serveur.")


# ============================================================================
# DATASETS
# ============================================================================

@router.get("/datasets", summary="Rechercher des datasets", description="Recherche dans ~1000 datasets publics (statiques + temps reel).")
async def list_datasets(
    query: str = Query("", max_length=500),
    max_results: int = Query(10, ge=1, le=100),
    request: Request = None,
):
    """Recherche datasets. En production: admin ou scope 'read' requis."""
    client_ip = request.client.host if request and request.client else "unknown"

    if ENVIRONMENT == "production":
        from routes.auth import _validate_session
        token = request.cookies.get("admin_session") if request else None
        is_admin = _validate_session(token)
        if not is_admin:
            client = extract_and_verify_client(request) if request else None
            if not client or "read" not in client.get("scopes", []):
                raise HTTPException(status_code=401, detail="Non autorisé")

    rate_limit_ok, retry_after = _check_rate(client_ip)
    if not rate_limit_ok:
        raise HTTPException(status_code=429, detail=f"Trop de requetes. Retry dans {retry_after}s.")

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

@router.get("/health", summary="Health check", description="Verifie l'etat de la base de donnees et de la memoire.")
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


@router.get("/metrics", summary="Metriques detaillees", description="Retourne les metriques : sources, cache, agent, circuit breaker.")
async def metrics(request: Request):
    """Metriques detaillees — protection admin ou scope admin/read en production."""
    if ENVIRONMENT == "production":
        from routes.auth import _validate_session
        token = request.cookies.get("admin_session")
        is_admin = _validate_session(token)
        if not is_admin:
            client = extract_and_verify_client(request)
            if not client or "admin/read" not in client.get("scopes", []):
                raise HTTPException(status_code=401, detail="Non autorisé")
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


@router.get("/search", response_model=SearchResponse, summary="Recherche web", description="Recherche web multi-sources avec deduplication et tri par pertinence.")
async def search(
    q: str = Query(..., min_length=1, max_length=500),
    max_results: int = Query(10, ge=1, le=30),
    time_range: str | None = Query(None, description="Filtrer par fraicheur: day, week, month, year"),
    include_domains: str | None = Query(None, description="Domaines a inclure (separes par virgule)"),
    exclude_domains: str | None = Query(None, description="Domaines a exclure (separes par virgule)"),
    request: Request = None,
):
    """Endpoint de recherche structuree pour providers externes (DSH)."""
    # Parser les domaines avec validation
    def _parse_domains(raw: str | None, max_count: int = 20) -> list[str] | None:
        if not raw:
            return None
        domains = [d.strip().lower() for d in raw.split(",") if d.strip()]
        if len(domains) > max_count:
            domains = domains[:max_count]
        return domains if domains else None

    parsed_include = _parse_domains(include_domains)
    parsed_exclude = _parse_domains(exclude_domains)

    client_ip = request.client.host if request and request.client else "unknown"

    # Auth centralisée (JWT ou API key)
    has_credentials = (
        request and (
            request.headers.get("Authorization", "").startswith("Bearer ")
            or request.headers.get("X-API-Key")
        )
    )
    client = extract_and_verify_client(request) if request else None
    if client:
        require_scope("read")(client)
        client_id = client["id"]
        client_rate_limit = client.get("rate_limit", 30)
        rate_limit_ok, retry_after = _check_rate(f"client:{client_id}", max_requests=client_rate_limit)
        if not rate_limit_ok:
            rate_limit_stats.record(f"client:{client_id}")
            logger.warning("Rate limit atteint pour client %s (limite: %d)", client_id, client_rate_limit)
            raise HTTPException(status_code=429, detail=f"Trop de requetes. Limite: {client_rate_limit}/min. Retry dans {retry_after}s.")
    elif has_credentials:
        raise HTTPException(status_code=401, detail="Cle d'API ou token invalide.")
    else:
        rate_limit_ok, retry_after = _check_rate(f"ip:{client_ip}")
        if not rate_limit_ok:
            rate_limit_stats.record(client_ip)
            raise HTTPException(status_code=429, detail=f"Trop de requetes. Retry dans {retry_after}s.")

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
                # Params de base pour toutes les sources
                call_kwargs: dict = {"query": q, "max_results": min(max_results, 5)}
                if time_range:
                    call_kwargs["time_range"] = time_range
                # Tavily : support natif des filtres domaine
                if tool_name == "tavily_search":
                    if parsed_include:
                        call_kwargs["include_domains"] = parsed_include
                    if parsed_exclude:
                        call_kwargs["exclude_domains"] = parsed_exclude
                result = func(**call_kwargs)
                duration = time.time() - start
                source_stats.record(tool_name, True, duration, origin="search")
                circuit_breaker.record_success(tool_name)
                return result
            except Exception as e:
                duration = time.time() - start
                source_stats.record(tool_name, False, duration, origin="search")
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

        # Filtrage par domaine (centralise, avant dedoublonnage)
        from core.tools import _filter_by_domains, _sort_results_by_relevance
        all_results = _filter_by_domains(all_results, parsed_include, parsed_exclude)

        seen_urls: set[str] = set()
        unique_results: list[dict] = []
        for r in all_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        # Trier par pertinence (score decroissant)
        unique_results = _sort_results_by_relevance(unique_results)

        sources = [
            SearchSource(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("snippet", "")[:300],
            )
            for r in unique_results[:max_results]
        ]

        asyncio.create_task(fire_webhook("search.completed", {
            "query": q,
            "result_count": len(sources),
            "truncated": len(unique_results) > max_results,
        }))

        return SearchResponse(
            sources=sources,
            query=q,
            count=len(sources),
            truncated=len(unique_results) > max_results,
        )
    except HTTPException:
        raise
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


@router.get("/threads", response_model=list[ThreadSummary], summary="Lister les threads", description="Retourne la liste de tous les threads de conversation.")
async def get_threads(request: Request):
    """Liste les threads. En production: admin ou scope 'read' requis."""
    if ENVIRONMENT == "production":
        from routes.auth import _validate_session
        token = request.cookies.get("admin_session")
        is_admin = _validate_session(token)
        if not is_admin:
            client = extract_and_verify_client(request)
            if not client or "read" not in client.get("scopes", []):
                raise HTTPException(status_code=401, detail="Non autorisé")
    return list_threads()


@router.get("/threads/{thread_id}", response_model=ThreadDetail, summary="Detail d'un thread", description="Retourne un thread avec tous ses messages.")
async def get_thread_detail(thread_id: str, request: Request):
    """Detail d'un thread. En production: admin ou scope 'read' requis."""
    if len(thread_id) > 128:
        raise HTTPException(status_code=400, detail="thread_id trop long")
    if ENVIRONMENT == "production":
        from routes.auth import _validate_session
        token = request.cookies.get("admin_session")
        is_admin = _validate_session(token)
        if not is_admin:
            client = extract_and_verify_client(request)
            if not client or "read" not in client.get("scopes", []):
                raise HTTPException(status_code=401, detail="Non autorisé")
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread non trouve.")
    return thread


@router.delete("/threads/{thread_id}", summary="Supprimer un thread", description="Supprime un thread et tous ses messages.")
async def remove_thread(thread_id: str, request: Request):
    """Supprime un thread. En production: admin ou scope 'write' requis."""
    if len(thread_id) > 128:
        raise HTTPException(status_code=400, detail="thread_id trop long")
    if ENVIRONMENT == "production":
        from routes.auth import _validate_session
        token = request.cookies.get("admin_session")
        is_admin = _validate_session(token)
        if not is_admin:
            client = extract_and_verify_client(request)
            if not client or "write" not in client.get("scopes", []):
                raise HTTPException(status_code=401, detail="Non autorisé")
    delete_thread(thread_id)
    return {"status": "deleted"}


@router.get("/threads/{thread_id}/context", summary="Contexte d'un thread", description="Retourne le contexte resume d'un thread pour les LLMs.")
async def get_thread_ctx(thread_id: str, request: Request):
    """Contexte d'un thread. En production: admin ou scope 'read' requis."""
    if len(thread_id) > 128:
        raise HTTPException(status_code=400, detail="thread_id trop long")
    if ENVIRONMENT == "production":
        from routes.auth import _validate_session
        token = request.cookies.get("admin_session")
        is_admin = _validate_session(token)
        if not is_admin:
            client = extract_and_verify_client(request)
            if not client or "read" not in client.get("scopes", []):
                raise HTTPException(status_code=401, detail="Non autorisé")
    context = get_thread_context(thread_id)
    return {"thread_id": thread_id, "context": context}
