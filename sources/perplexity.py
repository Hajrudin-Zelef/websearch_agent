"""
Source Perplexity — recherche web via l'API Perplexity (sonar).
Retourne [{"title", "url", "snippet"}].

Auth via PERPLEXITY_API_KEY.
"""

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

logger = logging.getLogger("websearch-agent.perplexity")

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise RuntimeError("PERPLEXITY_API_KEY non definie.")
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
def perplexity_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche web via Perplexity sonar et retourne des resultats structures."""
    session = _get_session()

    payload: dict[str, Any] = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a search assistant. Return the top results with titles, URLs, and brief snippets. "
                    "Format each result as a separate item."
                ),
            },
            {"role": "user", "content": query},
        ],
        "max_tokens": 1024,
    }

    resp = session.post(PERPLEXITY_API_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # Perplexity renvoie la reponse dans choices[0].message.content
    # On parse le texte pour en extraire des resultats
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    # Les citations sont dans data["citations"] si disponibles
    citations = data.get("citations", [])

    results: list[dict[str, str]] = []

    # D'abord, utiliser les citations si disponibles
    for url in citations[:max_results]:
        results.append({
            "title": query,
            "url": url,
            "snippet": "",
        })

    # Si pas de citations, parser le contenu texte
    if not results and content:
        # Extraire les URLs du contenu
        import re
        urls = re.findall(r'https?://[^\s\)\"]+', content)
        for url in urls[:max_results]:
            results.append({
                "title": query,
                "url": url,
                "snippet": "",
            })

        # Si toujours rien, mettre le contenu comme snippet
        if not results:
            results.append({
                "title": "Perplexity Search",
                "url": "",
                "snippet": content[:500],
            })

    return results[:max_results]


if __name__ == "__main__":
    import json
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = perplexity_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
