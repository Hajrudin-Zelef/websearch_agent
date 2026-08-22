"""
Source Research — recherche approfondie via sources primaires.
Combine plusieurs sources pour des reponses completes.
"""

import logging

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("websearch-agent.research")

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "websearch-agent/1.0 (https://github.com/Hajrudin-Zelef/websearch_agent)",
            "Accept": "application/json",
        })
    return _session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def research_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """
    Recherche approfondie — combine Wikipedia + web search.
    Utile pour les questions qui necessitent une analyse complete.
    """
    results: list[dict[str, str]] = []
    session = _get_session()

    # 1. Wikipedia comme source primaire (avec headers corrects)
    try:
        wiki_url = "https://fr.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json",
        }
        resp = session.get(wiki_url, params=params, timeout=10)
        if resp.ok:
            data = resp.json()
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                results.append({
                    "title": title,
                    "url": f"https://fr.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    "snippet": item.get("snippet", "")[:300],
                })
    except Exception as e:
        logger.debug("Wikipedia FR error: %s", e)

    # 2. Wikipedia anglais
    try:
        wiki_en_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 2,
            "format": "json",
        }
        resp = session.get(wiki_en_url, params=params, timeout=10)
        if resp.ok:
            data = resp.json()
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                results.append({
                    "title": title,
                    "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    "snippet": item.get("snippet", "")[:300],
                })
    except Exception as e:
        logger.debug("Wikipedia EN error: %s", e)

    return results[:max_results]


if __name__ == "__main__":
    import json
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "artificial intelligence"
    results = research_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
