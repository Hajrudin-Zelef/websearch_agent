"""
Source Querit — recherche web via l'API Querit (querit.ai).
Retourne [{"title", "url", "snippet"}].

Auth via QUERIT_API_KEY.
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

logger = logging.getLogger("websearch-agent.querit")

QUERIT_API_URL = "https://api.querit.ai/v1/search"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        api_key = os.getenv("QUERIT_API_KEY")
        if not api_key:
            raise RuntimeError("QUERIT_API_KEY non definie.")
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
def querit_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche web via Querit et retourne des resultats structures."""
    session = _get_session()

    payload: dict[str, Any] = {
        "query": query,
        "count": max_results,
        "include_content": False,
    }

    if time_range:
        time_map = {"day": "d7", "week": "w2", "month": "m3", "year": "y1"}
        payload["date_range"] = time_map.get(time_range, time_range)

    resp = session.post(QUERIT_API_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    for item in data.get("results", {}).get("result", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", "")[:300],
        })

    return results[:max_results]


if __name__ == "__main__":
    import json
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = querit_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
