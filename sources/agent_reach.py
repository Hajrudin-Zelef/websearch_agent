"""
Sources agent-reach — Web (Jina), GitHub (gh CLI), RSS (feedparser).

Integre les canaux sans authentification du skill agent-reach.
"""

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger("websearch-agent.agent-reach")


def _get_credential(key: str) -> str:
    """Lit un credential depuis settings.json (section api_keys)."""
    try:
        from core.settings import _get_setting
        return _get_setting("api_keys", key, "") or ""
    except Exception:
        return ""


def agent_reach_web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Recherche web via Jina Reader (r.jina.ai).
    Extrait le contenu markdown des pages trouvees.
    Necessite la cle JINA_API_KEY dans settings.json (api_keys).
    """
    import urllib.request
    import urllib.parse

    results = []
    api_key = _get_credential("JINA_API_KEY")

    if not api_key or api_key == "***":
        logger.info("JINA_API_KEY non configure — skip agent_reach_web_search")
        return results

    try:
        search_url = f"https://s.jina.ai/{urllib.parse.quote(query)}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        if isinstance(data, dict) and "data" in data:
            items = data["data"][:max_results]
        elif isinstance(data, list):
            items = data[:max_results]
        else:
            items = []

        for item in items:
            if isinstance(item, dict):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", item.get("link", "")),
                    "snippet": item.get("content", item.get("description", ""))[:500],
                    "source": "agent_reach_web",
                })
    except Exception as e:
        logger.warning("agent_reach_web_search echoue: %s", e)

    return results


def agent_reach_github_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Recherche GitHub via gh CLI.
    Trouve des repositories, code, frameworks.
    """
    results = []
    try:
        cmd = ["gh", "search", "repos", query, "--sort", "stars", "--limit", str(max_results), "--json", "name,owner,description,url,stargazersCount"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if proc.returncode != 0:
            logger.warning("gh search echoue: %s", proc.stderr)
            return results

        repos = json.loads(proc.stdout)
        for repo in repos:
            owner = repo.get("owner", {})
            owner_login = owner.get("login", "") if isinstance(owner, dict) else str(owner)
            results.append({
                "title": f"{owner_login}/{repo.get('name', '')}",
                "url": repo.get("url", ""),
                "snippet": repo.get("description", "") or "",
                "source": "agent_reach_github",
                "stars": repo.get("stargazersCount", 0),
            })
    except FileNotFoundError:
        logger.warning("gh CLI non installe")
    except Exception as e:
        logger.warning("agent_reach_github_search echoue: %s", e)

    return results


def agent_reach_rss_search(query: str, feed_url: str = "https://hnrss.org/frontpage", max_results: int = 5) -> list[dict]:
    """
    Recherche dans un flux RSS via feedparser.
    Par defaut : Hacker News frontpage.
    """
    results = []
    try:
        import feedparser

        feed = feedparser.parse(feed_url)
        query_lower = query.lower()

        for entry in feed.entries[:50]:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            link = entry.get("link", "")

            if query_lower and query_lower not in title.lower() and query_lower not in summary.lower():
                continue

            results.append({
                "title": title,
                "url": link,
                "snippet": summary[:500] if summary else "",
                "source": "agent_reach_rss",
            })

            if len(results) >= max_results:
                break
    except ImportError:
        logger.warning("feedparser non installe")
    except Exception as e:
        logger.warning("agent_reach_rss_search echoue: %s", e)

    return results
