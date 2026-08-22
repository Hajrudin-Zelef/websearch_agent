"""
Source Firecrawl Search — recherche web avec extraction de contenu complet.
Utilise l'API Firecrawl pour des resultats riches.

Auth via FIRECRAWL_API_KEY.
"""

import logging
import os
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("websearch-agent.firecrawl")

FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            raise RuntimeError("FIRECRAWL_API_KEY non definie.")
        _session = requests.Session()
        _session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
    return _session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def firecrawl_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche web via Firecrawl avec extraction de contenu."""
    session = _get_session()

    payload: dict[str, Any] = {
        "query": query,
        "limit": max_results,
        "scrapeOptions": {
            "formats": ["markdown"],
        },
    }

    resp = session.post(FIRECRAWL_SEARCH_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []

    for item in data.get("data", []):
        content = item.get("markdown", "")[:500]
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": content,
        })

    return results[:max_results]


if __name__ == "__main__":
    import json
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = firecrawl_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
