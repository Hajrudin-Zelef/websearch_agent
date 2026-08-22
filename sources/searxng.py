"""
Source SearXNG — recherche web via une instance SearXNG self-hosted ou publique.
Retourne [{"title", "url", "snippet"}].

Config via SEARXNG_URL (defaut: https://search.inetol.net).
Pas de cle API requise (instance publique) ou SEARXNG_API_KEY (instance privee).
"""

import os
import logging
import requests
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.searxng")

DEFAULT_SEARXNG_URL = "https://search.inetol.net"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Accept": "application/json",
            "User-Agent": "websearch-agent/1.0",
        })
        api_key = os.getenv("SEARXNG_API_KEY")
        if api_key:
            _session.headers["Authorization"] = f"Bearer {api_key}"
    return _session


def _get_base_url() -> str:
    return os.getenv("SEARXNG_URL", DEFAULT_SEARXNG_URL).rstrip("/")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def searxng_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche web via SearXNG et retourne des resultats structures."""
    session = _get_session()
    base_url = _get_base_url()

    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "categories": "general",
    }

    resp = session.get(f"{base_url}/search", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []

    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:300],
        })

    return results[:max_results]


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = searxng_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
