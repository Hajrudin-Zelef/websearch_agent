"""
Source Brave Search — recherche web via l'API Brave Search.
Retourne [{"title", "url", "snippet"}].

Auth via BRAVE_API_KEY.
"""

import os
import logging
import requests
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.brave")

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            raise RuntimeError("BRAVE_API_KEY non definie.")
        _session = requests.Session()
        _session.headers.update({
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        })
    return _session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def brave_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Recherche web via Brave Search et retourne des resultats structures."""
    session = _get_session()

    params: dict[str, Any] = {
        "q": query,
        "count": max_results,
    }

    resp = session.get(BRAVE_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []

    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", "")[:300],
        })

    return results[:max_results]


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = brave_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
