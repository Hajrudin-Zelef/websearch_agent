"""
Source GitHub — recherche de repos via l'API officielle.
Auth optionnelle via GITHUB_TOKEN (header Authorization: Bearer ...).
Retourne [{"title": full_name, "url", "snippet": description}].

Optimisations :
- requests.Session() avec connection pooling
- Retry tenacity sur erreurs transitoires
"""

import os
import logging
import requests
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.github")

GITHUB_API = "https://api.github.com/search/repositories"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": "websearch-agent/1.0",
        })
        token = os.getenv("GITHUB_TOKEN")
        if token:
            _session.headers["Authorization"] = f"Bearer {token}"
    return _session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def github_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Recherche GitHub et retourne une liste de repos."""
    session = _get_session()
    params: dict[str, Any] = {
        "q": query,
        "per_page": max_results,
        "sort": "stars",
        "order": "desc",
    }
    resp = session.get(GITHUB_API, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    for item in data.get("items", []):
        results.append({
            "title": item.get("full_name", ""),
            "url": item.get("html_url", ""),
            "snippet": item.get("description") or "",
        })
    return results


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "llm agent framework"
    results = github_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
