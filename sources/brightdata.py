"""
Source Brightdata — recherche web via Brightdata MCP (search_engine tool).
Retourne [{"title", "url", "snippet"}].

Auth via BRIGHTDATA_API_TOKEN.
Protocol: MCP over HTTP avec SSE (Server-Sent Events).
"""

import json
import logging
import os

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("websearch-agent.brightdata")

BRIGHTDATA_MCP_URL = "https://mcp.brightdata.com/mcp"

_session: requests.Session | None = None
_session_id: str | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })
    return _session


def _get_mcp_url() -> str:
    token = os.getenv("BRIGHTDATA_API_TOKEN", "")
    if not token:
        raise RuntimeError("BRIGHTDATA_API_TOKEN non definie.")
    return f"{BRIGHTDATA_MCP_URL}?token={token}"


def _parse_sse_response(text: str) -> dict | None:
    """Parse une reponse SSE et retourne le JSON data."""
    for line in text.strip().split("\n"):
        if line.startswith("data: "):
            try:
                return json.loads(line[6:])
            except json.JSONDecodeError:
                continue
    return None


def _mcp_call(method: str, params: dict = None) -> dict:
    """Appel MCP generique avec gestion SSE."""
    global _session_id
    session = _get_session()
    mcp_url = _get_mcp_url()

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
    }
    if params:
        payload["params"] = params

    headers = {}
    if _session_id:
        headers["mcp-session-id"] = _session_id

    resp = session.post(mcp_url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()

    _session_id = resp.headers.get("mcp-session-id", _session_id)

    data = _parse_sse_response(resp.text)
    return data or {}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def brightdata_search(query: str, max_results: int = 5, time_range: str | None = None) -> list[dict[str, str]]:
    """Recherche web via Brightdata MCP search_engine tool."""
    try:
        _mcp_call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "websearch-agent", "version": "1.0"},
        })
    except Exception:
        pass

    result = _mcp_call("tools/call", {
        "name": "search_engine",
        "arguments": {
            "query": query,
            "engine": "google",
            "num_results": min(max_results, 10),
        },
    })

    results: list[dict[str, str]] = []
    content = result.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            text = item.get("text", "")

            import re
            json_match = re.search(r'\{.*"organic".*\}', text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    for organic in data.get("organic", []):
                        results.append({
                            "title": organic.get("title", ""),
                            "url": organic.get("link", ""),
                            "snippet": organic.get("description", "")[:300],
                        })
                except json.JSONDecodeError:
                    pass

            if not results:
                current: dict[str, str] = {}
                for line in text.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("Title:"):
                        current["title"] = line[6:].strip()
                    elif line.startswith("URL:") or line.startswith("Link:"):
                        current["url"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Description:") or line.startswith("Snippet:"):
                        current["snippet"] = line.split(":", 1)[1].strip()[:300]
                    elif (line == "---" or line == "") and current.get("url"):
                        results.append(current)
                        current = {}
                if current.get("url"):
                    results.append(current)

    return results[:max_results]


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI news"
    results = brightdata_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} resultat(s)")
