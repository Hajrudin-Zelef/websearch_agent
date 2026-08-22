"""
Source LangSearch — recherche web via l'API LangSearch (langsearch.com).
Retourne [{"title", "url", "snippet"}].

Auth via LANGSEARCH_API_KEY.
"""

import os
import logging
import requests
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.langsearch")

LANGSEARCH_API_URL = "https://api.langsearch.com/v1/web-search"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        api_key = os.getenv("LANGSEARCH_API_KEY")
        if not api_key:
            raise RuntimeError("LANGSEARCH_API_KEY non definie.")
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
def langsearch_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche web via LangSearch et retourne des resultats structures."""
    session = _get_session()

    payload: dict[str, Any] = {
        "query": query,
        "count": min(max_results, 10),
        "summary": False,
    }

    if time_range:
        time_map = {"day": "oneDay", "week": "oneWeek", "month": "oneMonth", "year": "oneYear"}
        payload["freshness"] = time_map.get(time_range, "noLimit")
    else:
        payload["freshness"] = "noLimit"

    resp = session.post(LANGSEARCH_API_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    pages = data.get("data", {}).get("webPages", {}).get("value", [])
    for item in pages:
        results.append({
            "title": item.get("name", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", "")[:300],
        })

    return results[:max_results]


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = langsearch_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
