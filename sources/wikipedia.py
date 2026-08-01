"""
Source Wikipedia — recherche via l'API officielle (fr.wikipedia.org).
Pas de clé requise. Retourne [{"title", "url", "snippet"}].

Optimisations :
- requests.Session() avec connection pooling
- Retry tenacity sur erreurs transitoires
"""

import logging
import requests
from typing import Any
from urllib.parse import quote
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.wikipedia")

WIKIPEDIA_API = "https://fr.wikipedia.org/w/api.php"

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
def wikipedia_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Recherche Wikipedia et retourne une liste de résultats."""
    session = _get_session()
    params: dict[str, Any] = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": max_results,
    }
    resp = session.get(WIKIPEDIA_API, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        results.append({
            "title": title,
            "url": f"https://fr.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}",
            "snippet": item.get("snippet", ""),
        })
    return results


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "intelligence artificielle"
    results = wikipedia_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} résultat(s)")
