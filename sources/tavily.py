"""
Source Tavily — recherche web via l'API Tavily.
Retourne [{"title", "url", "snippet"}].

Auth via TAVILY_API_KEY.
"""

import os
import logging
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("websearch-agent.tavily")

_session = None


def _get_client():
    global _session
    if _session is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY non definie.")
        from tavily import TavilyClient
        _session = TavilyClient(api_key=api_key)
    return _session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
def tavily_search(
    query: str,
    max_results: int = 5,
    time_range: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[dict[str, str]]:
    """Recherche web via Tavily et retourne des resultats structures."""
    client = _get_client()

    kwargs: dict[str, Any] = {
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": True,
    }
    if time_range:
        kwargs["time_range"] = time_range
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains

    response = client.search(**kwargs)

    results: list[dict[str, str]] = []

    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:300],
        })

    # Si pas de resultats mais qu'il y a une reponse directe
    if not results and response.get("answer"):
        results.append({
            "title": "Tavily Answer",
            "url": "",
            "snippet": response["answer"][:500],
        })

    return results[:max_results]


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = tavily_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
