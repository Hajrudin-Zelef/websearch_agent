"""
Extraction de contenu — fetch URLs → texte lisible pour citations.

Pipeline :
1. Prend les URLs des resultats de recherche
2. Fetch le HTML avec timeout agressif
3. Extrait le texte lisible via trafilatura
4. Retourne [(url, titre, texte), ...] pour le LLM

Graceful degradation : si une page echoue, on la drop et on continue.
"""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests
import trafilatura

logger = logging.getLogger("websearch-agent.content-extractor")

# ============================================================================
# CONFIG
# ============================================================================

_FETCH_TIMEOUT = 8.0  # timeout par page (secondes)
_MAX_PAGES = 6  # nombre max de pages a extraire par requete
_EXTRACT_TIMEOUT = 10.0  # timeout extraction trafilatura
_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Patterns a exclure (pas la peine de fetcher)
_SKIP_PATTERNS = [
    r"\.(pdf|zip|tar\.gz|exe|dmg)$",
    r"youtube\.com/watch",
    r"vimeo\.com",
    r"twitter\.com",
    r"x\.com",
    r"facebook\.com",
    r"instagram\.com",
]

# ============================================================================
# HELPERS
# ============================================================================

def _should_skip(url: str) -> bool:
    """Verifie si une URL doit etre sautee (PDF, video, reseau social...)."""
    return any(re.search(p, url, re.IGNORECASE) for p in _SKIP_PATTERNS)


def _extract_title(html: str) -> str:
    """Extrait le titre de la page HTML."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _fetch_and_extract(url: str) -> Optional[dict]:
    """Fetch une URL et extrait le texte lisible. Retourne None si echec."""
    if _should_skip(url):
        logger.debug("Skip URL (pattern): %s", url)
        return None

    try:
        resp = requests.get(
            url,
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            allow_redirects=True,
            stream=True,
        )
        resp.raise_for_status()

        # Limiter la taille du contenu (1 MB max)
        content_length = 0
        chunks = []
        for chunk in resp.iter_content(chunk_size=8192):
            content_length += len(chunk)
            if content_length > 1_000_000:  # 1 MB
                break
            chunks.append(chunk)

        html = b"".join(chunks).decode("utf-8", errors="replace")

    except requests.exceptions.Timeout:
        logger.warning("Timeout fetching: %s", url)
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("Fetch error for %s: %s", url, e)
        return None
    except Exception as e:
        logger.warning("Unexpected error fetching %s: %s", url, e)
        return None

    try:
        # Extraction du texte lisible
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_images=False,
            favor_precision=True,
        )

        if not extracted or len(extracted.strip()) < 50:
            logger.debug("No meaningful content extracted from: %s", url)
            return None

        title = _extract_title(html) or url.split("/")[-1][:50]

        # Tronquer si trop long (3000 chars max par page)
        text = extracted.strip()
        if len(text) > 3000:
            text = text[:3000] + "..."

        return {
            "url": url,
            "title": title,
            "text": text,
        }

    except Exception as e:
        logger.warning("Extraction error for %s: %s", url, e)
        return None


def extract_content_from_results(urls: list[str]) -> list[dict]:
    """
    Extrait le contenu lisible d'une liste d'URLs.
    Graceful degradation : les pages qui echouent sont droppees.

    Args:
        urls: liste d'URLs a extraire

    Returns:
        liste de dicts {url, title, text} pour les pages extraites avec succes
    """
    if not urls:
        return []

    # Limiter le nombre de pages
    urls = urls[:_MAX_PAGES]

    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_fetch_and_extract, url): url
            for url in urls
        }
        for future in futures:
            url = futures[future]
            try:
                result = future.result(timeout=_EXTRACT_TIMEOUT)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.warning("Extraction timeout/error for %s: %s", url, e)

    logger.info("Content extraction: %d/%d pages extraites", len(results), len(urls))
    return results
