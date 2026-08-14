"""
Extraction de contenu — fetch URLs → texte lisible pour citations.

Pipeline 100% async :
1. Prend les URLs des resultats de recherche
2. Fetch le HTML en async (aiohttp, 6 pages en parallele)
3. Extrait le texte lisible via trafilatura (thread pool, CPU-bound)
4. Retourne [(url, titre, texte), ...] pour le LLM

Graceful degradation : si une page echoue, on la drop et on continue.
"""

import asyncio
import logging
import re
from typing import Optional

import aiohttp
import trafilatura

logger = logging.getLogger("websearch-agent.content-extractor")

# ============================================================================
# CONFIG
# ============================================================================

_FETCH_TIMEOUT = 8.0
_MAX_PAGES = 6
_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_MAX_CONTENT_BYTES = 1_000_000  # 1 MB
_MAX_TEXT_LENGTH = 3000
_MIN_TEXT_LENGTH = 50

_SKIP_PATTERNS = [
    r"\.(pdf|zip|tar\.gz|exe|dmg)$",
    r"youtube\.com/watch",
    r"vimeo\.com",
    r"twitter\.com",
    r"x\.com",
    r"facebook\.com",
    r"instagram\.com",
]

# Session aiohttp partagee (connection pooling)
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=_FETCH_TIMEOUT)
        connector = aiohttp.TCPConnector(
            limit=10,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        _session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": _USER_AGENT},
        )
    return _session


# ============================================================================
# HELPERS
# ============================================================================

def _should_skip(url: str) -> bool:
    return any(re.search(p, url, re.IGNORECASE) for p in _SKIP_PATTERNS)


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _extract_text(html: str, url: str) -> Optional[dict]:
    """Extraction CPU-bound : trafilatura dans un thread pool."""
    try:
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_images=False,
            favor_precision=True,
        )

        if not extracted or len(extracted.strip()) < _MIN_TEXT_LENGTH:
            return None

        title = _extract_title(html) or url.split("/")[-1][:50]
        text = extracted.strip()
        if len(text) > _MAX_TEXT_LENGTH:
            text = text[:_MAX_TEXT_LENGTH] + "..."

        return {"url": url, "title": title, "text": text}

    except Exception as e:
        logger.warning("Extraction error for %s: %s", url, e)
        return None


async def _fetch_and_extract(url: str) -> Optional[dict]:
    """Fetch async + extraction thread pool."""
    if _should_skip(url):
        return None

    try:
        session = await _get_session()
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                logger.warning("HTTP %d for %s", resp.status, url)
                return None

            # Lire avec limite de taille
            content_length = 0
            chunks = []
            async for chunk in resp.content.iter_chunked(8192):
                content_length += len(chunk)
                if content_length > _MAX_CONTENT_BYTES:
                    break
                chunks.append(chunk)

            html = b"".join(chunks).decode("utf-8", errors="replace")

    except asyncio.TimeoutError:
        logger.warning("Timeout fetching: %s", url)
        return None
    except Exception as e:
        logger.warning("Fetch error for %s: %s", url, e)
        return None

    # Extraction CPU-bound en thread pool
    return await asyncio.to_thread(_extract_text, html, url)


# ============================================================================
# API PUBLIQUE
# ============================================================================

async def extract_content_async(urls: list[str]) -> list[dict]:
    """
    Extrait le contenu lisible d'une liste d'URLs (100% async).
    6 pages fetchees en parallele, graceful degradation.
    """
    if not urls:
        return []

    urls = urls[:_MAX_PAGES]

    tasks = [asyncio.create_task(_fetch_and_extract(url)) for url in urls]
    results = []

    for task in asyncio.as_completed(tasks):
        try:
            result = await asyncio.wait_for(task, timeout=_FETCH_TIMEOUT + 2)
            if result is not None:
                results.append(result)
        except Exception as e:
            logger.warning("Extraction error: %s", e)

    logger.info("Content extraction: %d/%d pages extraites", len(results), len(urls))
    return results


def extract_content_from_results(urls: list[str]) -> list[dict]:
    """
    Version sync pour backward compatibility.
    Utilise asyncio.run() si pas de loop en cours.
    """
    if not urls:
        return []

    try:
        loop = asyncio.get_running_loop()
        # On est deja dans un loop → lancer en thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, extract_content_async(urls))
            return future.result(timeout=_FETCH_TIMEOUT + 5)
    except RuntimeError:
        # Pas de loop → asyncio.run direct
        return asyncio.run(extract_content_async(urls))


async def close_session():
    """Ferme la session aiohttp (a appeler a l'arret du serveur)."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
