"""
Source Wikipedia — recherche via l'API officielle (fr.wikipedia.org).
Pas de clé requise. Retourne [{"title", "url", "snippet"}].
"""

import requests
from typing import Any
from urllib.parse import quote

WIKIPEDIA_API = "https://fr.wikipedia.org/w/api.php"


def wikipedia_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Recherche Wikipedia et retourne une liste de résultats."""
    params: dict[str, Any] = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": max_results,
    }
    headers = {"User-Agent": "websearch-agent/1.0 (research bot; contact@example.com)"}
    resp = requests.get(WIKIPEDIA_API, params=params, headers=headers, timeout=15)
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
    print(f"\n→ {len(results)} résultat(s)")
