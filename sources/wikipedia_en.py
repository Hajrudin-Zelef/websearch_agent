"""
Source Wikipedia EN — recherche via l'API officielle (en.wikipedia.org).
Pas de cle requise. Retourne [{"title", "url", "snippet"}].
"""

import requests
from typing import Any
from urllib.parse import quote

WIKIPEDIA_EN_API = "https://en.wikipedia.org/w/api.php"


def wikipedia_en_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Recherche Wikipedia EN et retourne une liste de resultats."""
    params: dict[str, Any] = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": max_results,
    }
    headers = {"User-Agent": "websearch-agent/1.0 (research bot; contact@example.com)"}
    resp = requests.get(WIKIPEDIA_EN_API, params=params, headers=headers, timeout=15)
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
