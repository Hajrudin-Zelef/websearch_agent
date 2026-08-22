"""
Source Yacy — recherche web via une instance Yacy self-hosted.
Retourne [{"title", "url", "snippet"}].

Config via YACY_URL (defaut: http://localhost:8090).
Pas de cle API requise.
"""

import os
import logging
import requests
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.yacy")

DEFAULT_YACY_URL = "http://localhost:8090"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Accept": "application/json",
            "User-Agent": "websearch-agent/1.0",
        })
    return _session


def _get_base_url() -> str:
    return os.getenv("YACY_URL", DEFAULT_YACY_URL).rstrip("/")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def yacy_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche web via Yacy et retourne des resultats structures."""
    session = _get_session()
    base_url = _get_base_url()

    params: dict[str, Any] = {
        "query": query,
        "resource": "global",
        "maximumRecords": min(max_results, 10),
        "format": "json",
    }

    resp = session.get(f"{base_url}/yacysearch.json", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    channels = data.get("channels", [])
    if channels:
        for item in channels[0].get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("description", "")[:300],
            })

    return results[:max_results]


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = yacy_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
