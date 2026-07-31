"""
Source GitHub — recherche de repos via l'API officielle.
Auth optionnelle via GITHUB_TOKEN (header Authorization: Bearer ...).
Retourne [{"title": full_name, "url", "snippet": description}].
"""

import os
import requests
from typing import Any

GITHUB_API = "https://api.github.com/search/repositories"


def github_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Recherche GitHub et retourne une liste de repos."""
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "websearch-agent/1.0",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params: dict[str, Any] = {
        "q": query,
        "per_page": max_results,
        "sort": "stars",
        "order": "desc",
    }
    resp = requests.get(GITHUB_API, headers=headers, params=params, timeout=15)
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
    print(f"\n→ {len(results)} résultat(s)")
