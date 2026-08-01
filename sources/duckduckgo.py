"""
Source DuckDuckGo — recherche web via ddgs (sans API key).
Retourne [{"title", "url", "snippet"}].

Pas de cle API requise.
"""

import logging
from typing import Any

logger = logging.getLogger("websearch-agent.duckduckgo")

_client = None


def _get_client():
    global _client
    if _client is None:
        from ddgs import DDGS
        _client = DDGS()
    return _client


def duckduckgo_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Recherche web via DuckDuckGo et retourne des resultats structures."""
    client = _get_client()

    results: list[dict[str, str]] = []

    try:
        for r in client.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:300],
            })
    except Exception as e:
        logger.warning("Erreur DuckDuckGo: %s", e)
        raise

    return results[:max_results]


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = duckduckgo_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
