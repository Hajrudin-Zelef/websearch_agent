"""
Source Actualites - 34 flux RSS couvrant actualite generale, tech, IA,
cybersecurite, entreprise et sources francophones.
Chaque flux est dans un try/except individuel pour qu'un flux mort
ne casse pas les autres.
"""

import requests
import feedparser
from typing import Any

FEEDS: dict[str, str] = {
    # === Actualite generale & internationale ===
    "bbc_world": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "bbc_tech": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "bbc_business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "cnn_top": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "cnn_world": "http://rss.cnn.com/rss/cnn_world.rss",
    "cnn_business": "http://rss.cnn.com/rss/money_latest.rss",
    "guardian_world": "https://www.theguardian.com/world/rss",
    "guardian_tech": "https://www.theguardian.com/technology/rss",
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "npr": "https://feeds.npr.org/1001/rss.xml",
    "foxnews": "https://m.foxnews.com/feed",

    # === Technologie & startups ===
    "techcrunch": "https://techcrunch.com/feed/",
    "theverge": "https://www.theverge.com/rss/index.xml",
    "wired": "https://www.wired.com/feed/rss",
    "arstechnica": "https://feeds.arstechnica.com/arstechnica/index",
    "mit_tech_review": "https://www.technologyreview.com/feed/",
    "zdnet": "https://www.zdnet.com/news/rss.xml",
    "hackernews": "https://news.ycombinator.com/rss",

    # === Intelligence Artificielle ===
    "openai": "https://openai.com/news/rss.xml",
    "huggingface": "https://huggingface.co/blog/feed.xml",
    "arxiv_cs_ai": "https://export.arxiv.org/rss/cs.AI",

    # === Cybersecurite ===
    "krebs": "https://krebsonsecurity.com/feed/",
    "thehackernews": "https://feeds.feedburner.com/TheHackersNews",
    "bleepingcomputer": "https://www.bleepingcomputer.com/feed/",
    "darkreading": "https://www.darkreading.com/rss.xml",
    "ms_security": "https://www.microsoft.com/en-us/security/blog/feed/",
    "unit42": "https://unit42.paloaltonetworks.com/feed/?v=2",
    "securelist": "https://securelist.com/feed/",
    "securityaffairs": "https://securityaffairs.com/feed",

    # === Entreprise & blogs techniques ===
    "aws": "https://aws.amazon.com/blogs/aws/feed/",
    "cloudflare": "https://blog.cloudflare.com/rss/",
    "github_blog": "https://github.blog/feed/",
    "netflix_tech": "https://netflixtechblog.com/feed",

    # === Francophone ===
    "ansm": "https://ansm.sante.fr/rss/actualites",
}

HEADERS: dict[str, str] = {
    "User-Agent": "websearch-agent/1.0 (news reader; contact@example.com)",
}


def news_search(
    query: str = "", max_results_per_feed: int = 3
) -> list[dict[str, str]]:
    """Recupere les derniers articles de chaque flux RSS et filtre par query."""
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
            print(f"[news_rss] ⚠ Flux {source} indisponible : {e}")

    return all_articles


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else ""
    results = news_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n→ {len(results)} article(s)")
