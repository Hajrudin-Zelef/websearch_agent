"""
Source Exa — recherche semantique via l'API Exa (exa.ai).
Retourne [{"title", "url", "snippet"}].

Auth via EXA_API_KEY.
"""

import os
import json
import logging
import requests
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.exa")

EXA_API_URL = "https://api.exa.ai/search"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def _get_api_key() -> str:
    key = os.getenv("EXA_API_KEY", "")
    if not key:
        raise RuntimeError("EXA_API_KEY non definie.")
    return key


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def exa_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche semantique via Exa et retourne des resultats structures."""
    session = _get_session()
    api_key = _get_api_key()

    payload: dict[str, Any] = {
        "query": query,
        "numResults": min(max_results, 10),
        "type": "neural",
        "contents": {
            "text": {"maxCharacters": 300},
        },
    }

    if time_range:
        time_map = {"day": "day", "week": "week", "month": "month", "year": "year"}
        payload["livecrawl"] = "auto"
        payload["startPublishedDate"] = None
        payload["endPublishedDate"] = None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = session.post(EXA_API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("text", "")[:300],
        })

    return results[:max_results]


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = exa_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
