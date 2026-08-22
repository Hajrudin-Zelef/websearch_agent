"""
Source Wikipedia — recherche via l'API officielle (fr.wikipedia.org).
Pas de clé requise. Retourne [{"title", "url", "snippet"}].

Optimisations :
- requests.Session() avec connection pooling
- Retry tenacity sur erreurs transitoires
"""

import logging
import time
from typing import Any
from urllib.parse import quote

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger("websearch-agent.wikipedia")

WIKIPEDIA_API = "https://fr.wikipedia.org/w/api.php"

_session: requests.Session | None = None
_last_request_time: float = 0.0
_MIN_INTERVAL = 0.5


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "websearch-agent/1.0 (research bot; contact@example.com)",
        })
    return _session


def _is_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, requests.exceptions.HTTPError):
        return exc.response is not None and exc.response.status_code == 429
    return False


def _get_retry_after(exc: Exception) -> float:
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
    return 0.0


def _wait_for_retry(retry_state):
    exc = retry_state.outcome.exception()
    if exc and _is_rate_limited(exc):
        wait = _get_retry_after(exc)
        if wait > 0:
            return wait
    return wait_exponential(multiplier=2.0, min=2.0, max=15)(retry_state)


@retry(
    stop=stop_after_attempt(4),
    wait=_wait_for_retry,
    retry=retry_if_exception(lambda exc: isinstance(exc, (requests.ConnectionError, requests.Timeout)) or _is_rate_limited(exc)),
    reraise=True,
)
def wikipedia_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche Wikipedia et retourne une liste de résultats."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    session = _get_session()
    params: dict[str, Any] = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": max_results,
    }
    resp = session.get(WIKIPEDIA_API, params=params, timeout=15)
    _last_request_time = time.monotonic()
    resp.raise_for_status()
    data = resp.json()

    results: list[dict[str, str]] = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        results.append({
            "title": title,
            "url": f"https://fr.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='/_')}",
            "snippet": item.get("snippet", ""),
        })
    return results


if __name__ == "__main__":
    import json
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "intelligence artificielle"
    results = wikipedia_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} résultat(s)")
