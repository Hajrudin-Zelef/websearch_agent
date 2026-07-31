"""
Source Actualités — 5 flux RSS.
Pas d'API de recherche par mot-clé : on récupère les derniers articles
de chaque flux, et on filtre par mot-clé (titre + résumé) si query non vide.
Chaque flux est dans un try/except individuel.
"""

import requests
import feedparser
from typing import Any

FEEDS: dict[str, str] = {
    "bbc": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "techcrunch": "https://techcrunch.com/feed/",
    "theverge": "https://www.theverge.com/rss/index.xml",
    "arstechnica": "https://feeds.arstechnica.com/arstechnica/index",
    "mit_tech_review": "https://www.technologyreview.com/feed/",
}

HEADERS: dict[str, str] = {
    "User-Agent": "websearch-agent/1.0 (news reader; contact@example.com)",
}


def news_search(
    query: str = "", max_results_per_feed: int = 5
) -> list[dict[str, str]]:
    """Récupère les derniers articles de chaque flux RSS et filtre par query."""
    all_articles: list[dict[str, str]] = []
    query_lower = query.lower().strip() if query else ""

    for source, url in FEEDS.items():
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            count = 0
            for entry in feed.entries:
                if count >= max_results_per_feed:
                    break
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                combined = f"{title} {summary}"

                if query_lower and query_lower not in combined.lower():
                    continue

                all_articles.append({
                    "title": title,
                    "url": entry.get("link", ""),
                    "snippet": summary,
                    "source": source,
                })
                count += 1

        except requests.RequestException as e:
            # Un flux mort ne doit pas casser les autres
            print(f"[news_rss] ⚠ Flux {source} indisponible : {e}")

    return all_articles


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else ""
    results = news_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n→ {len(results)} article(s)")
