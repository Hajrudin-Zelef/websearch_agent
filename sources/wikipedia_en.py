"""
Source Wikipedia EN — recherche via l'API officielle (en.wikipedia.org).
Pas de cle requise. Retourne [{"title", "url", "snippet"}].

Optimisations :
- requests.Session() avec connection pooling
- Retry tenacity sur erreurs transitoires
"""

import logging
import requests
from typing import Any
from urllib.parse import quote
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.wikipedia_en")

WIKIPEDIA_EN_API = "https://en.wikipedia.org/w/api.php"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "websearch-agent/1.0 (research bot; contact@example.com)",
        })
    return _session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def wikipedia_en_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Recherche Wikipedia EN et retourne une liste de resultats."""
    session = _get_session()
    params: dict[str, Any] = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": max_results,
    }
    resp = session.get(WIKIPEDIA_EN_API, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        results.append({
            "title": title,
            "url": f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}",
            "snippet": item.get("snippet", ""),
        })
    return results


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "artificial intelligence"
    results = wikipedia_en_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
