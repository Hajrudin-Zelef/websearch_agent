"""
Source Just Scrape — recherche web via ScrapeGraph AI.
Utilise le CLI just-scrape ou l'API directement.

Auth via SGAI_API_KEY.
"""

import json
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

logger = logging.getLogger("websearch-agent.just-scrape")

SGAI_API_URL = "https://v2-api.scrapegraphai.com"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        api_key = os.getenv("SGAI_API_KEY")
        if not api_key:
            raise RuntimeError("SGAI_API_KEY non definie.")
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
def just_scrape_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche web via ScrapeGraph AI."""
    session = _get_session()

    payload: dict[str, Any] = {
        "query": query,
        "num_results": max_results,
    }

    resp = session.post(f"{SGAI_API_URL}/search", json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []

    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", "")[:300],
        })

    return results[:max_results]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def just_scrape_scrape(url: str) -> dict[str, str]:
    """Extrait le contenu d'une page web."""
    session = _get_session()

    payload: dict[str, Any] = {
        "url": url,
        "formats": ["markdown"],
    }

    resp = session.post(f"{SGAI_API_URL}/scrape", json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    return {
        "title": data.get("title", ""),
        "url": url,
        "content": data.get("markdown", "")[:1000],
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python just_scrape.py <query>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    results = just_scrape_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
