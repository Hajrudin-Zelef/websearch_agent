"""
Source Actualites - 112 flux RSS organises par categorie.
Chaque flux est dans un try/except individuel pour qu'un flux mort
ne casse pas les autres.

Optimisations :
- Cache TTL 10 min par flux (evite de re-fetch les 112 flux a chaque requete)
- requests.Session() pour le connection pooling (keep-alive)
- Retry tenacity sur les erreurs transitoires
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import threading
import time
import requests
import feedparser
from typing import Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("websearch-agent.news")

# --- TTL Cache ---
_FEED_CACHE_TTL = 600  # 10 minutes
_feed_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
_feed_cache_lock = threading.Lock()

# --- Shared ThreadPoolExecutor ---
_feed_executor = ThreadPoolExecutor(max_workers=30)

# --- Session partagee avec connection pooling + retry ---
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.3, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=20,
            pool_maxsize=20,
        )
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
        _session.headers.update(HEADERS)
    return _session


FEEDS: dict[str, str] = {
    # =================================================================
    # Francophone (prioritaires - l'agent repond en francais)
    # =================================================================
    "france24": "https://www.france24.com/en/rss",
    "lemonde_une": "https://www.lemonde.fr/rss/une.xml",
    "francetvinfo": "https://www.francetvinfo.fr/titres.rss",
    "nouvelobs": "https://www.nouvelobs.com/a-la-une/rss.xml",
    "huffpost_fr": "https://www.huffingtonpost.fr/feeds/index.xml",
    "ladepeche": "https://www.ladepeche.fr/rss.xml",
    "sudouest": "https://www.sudouest.fr/essentiel/rss.xml",
    "ouest_france": "https://www.ouest-france.fr/rss-en-continu.xml",
    "mediapart": "https://www.mediapart.fr/articles/feed",
    "ansm": "https://ansm.sante.fr/rss/actualites",

    # =================================================================
    # Actualite generale & internationale
    # =================================================================
    "bbc_world": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "bbc_tech": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "bbc_business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "bbc_science": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "cnn_top": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "cnn_world": "http://rss.cnn.com/rss/cnn_world.rss",
    "cnn_business": "http://rss.cnn.com/rss/money_latest.rss",
    "guardian_world": "https://www.theguardian.com/world/rss",
    "guardian_tech": "https://www.theguardian.com/technology/rss",
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "npr": "https://feeds.npr.org/1001/rss.xml",
    "foxnews": "https://m.foxnews.com/feed",

    # =================================================================
    # Technologie & startups
    # =================================================================
    "techcrunch": "https://techcrunch.com/feed/",
    "theverge": "https://www.theverge.com/rss/index.xml",
    "wired": "https://www.wired.com/feed/rss",
    "arstechnica": "https://feeds.arstechnica.com/arstechnica/index",
    "mit_tech_review": "https://www.technologyreview.com/feed/",
    "zdnet": "https://www.zdnet.com/news/rss.xml",
    "hackernews": "https://news.ycombinator.com/rss",
    "producthunt": "https://www.producthunt.com/feed",
    "slashdot": "http://rss.slashdot.org/Slashdot/slashdotMain",
    "engadget": "https://www.engadget.com/rss.xml",
    "cnet": "https://www.cnet.com/rss/news/",
    "daringfireball": "https://daringfireball.net/feeds/main",
    "stratechery": "http://stratechery.com/feed/",
    "macstories": "https://www.macstories.net/feed",
    "lifehacker": "https://lifehacker.com/rss",
    "feld": "https://feld.com/feed",
    "inc": "https://www.inc.com/rss/",
    "bothsides": "https://bothsidesofthetable.com/feed",

    # =================================================================
    # Intelligence Artificielle
    # =================================================================
    "openai": "https://openai.com/news/rss.xml",
    "deepmind": "https://deepmind.google/blog/rss.xml",
    "google_ai": "https://blog.google/technology/ai/rss/",
    "huggingface": "https://huggingface.co/blog/feed.xml",
    "stability_ai": "https://stability.ai/news?format=rss",
    "simonwillison": "https://simonwillison.net/atom/everything/",
    "arxiv_cs_ai": "https://rss.arxiv.org/rss/cs.AI",
    "arxiv_cs_lg": "https://rss.arxiv.org/rss/cs.LG",
    "arxiv_cs_cl": "https://rss.arxiv.org/rss/cs.CL",
    "arxiv_cs_cv": "https://rss.arxiv.org/rss/cs.CV",

    # =================================================================
    # Cybersecurite
    # =================================================================
    "krebs": "https://krebsonsecurity.com/feed/",
    "schneier": "https://www.schneier.com/feed/",
    "thehackernews": "https://feeds.feedburner.com/TheHackersNews",
    "bleepingcomputer": "https://www.bleepingcomputer.com/feed/",
    "darkreading": "https://www.darkreading.com/rss.xml",
    "ms_security": "https://www.microsoft.com/en-us/security/blog/feed/",
    "google_security": "https://security.googleblog.com/atom.xml",
    "unit42": "https://unit42.paloaltonetworks.com/feed/?v=2",
    "securelist": "https://securelist.com/feed/",
    "securityaffairs": "https://securityaffairs.com/feed",

    # =================================================================
    # Programmation
    # =================================================================
    "codinghorror": "http://feeds.feedburner.com/codinghorror",
    "overreacted": "https://overreacted.io/rss.xml",
    "hackernoon": "https://medium.com/feed/hackernoon",
    "infoq": "https://feed.infoq.com",
    "martinfowler": "https://martinfowler.com/feed.atom",
    "scott_hanselman": "http://feeds.hanselman.com/ScottHanselman",
    "stackoverflow_blog": "https://stackoverflow.blog/feed/",
    "joelonsoftware": "https://www.joelonsoftware.com/feed/",
    "reddit_programming": "https://www.reddit.com/r/programming/.rss",
    "codeascraft": "https://codeascraft.com/feed/atom/",

    # =================================================================
    # Langages de programmation
    # =================================================================
    "python": "https://blog.python.org/feeds/posts/default",
    "rust": "https://blog.rust-lang.org/feed.xml",
    "go": "https://go.dev/blog/feed.atom",
    "nodejs": "https://nodejs.org/en/feed/blog.xml",
    "deno": "https://deno.com/blog/feed.xml",
    "react": "https://react.dev/rss.xml",
    "vue": "https://blog.vuejs.org/feed.rss",
    "typescript": "https://devblogs.microsoft.com/typescript/feed/",
    "swift": "https://www.swift.org/atom.xml",
    "kotlin": "https://blog.jetbrains.com/kotlin/feed/",

    # =================================================================
    # Newsletters
    # =================================================================
    "javascript_weekly": "https://javascriptweekly.com/rss/",
    "rust_weekly": "https://this-week-in-rust.org/atom.xml",
    "golang_weekly": "https://golangweekly.com/rss/",
    "bytebytego": "https://blog.bytebytego.com/feed",

    # =================================================================
    # Frontend & design
    # =================================================================
    "smashing": "https://www.smashingmagazine.com/feed/",
    "css_tricks": "https://css-tricks.com/feed/",
    "astro": "https://astro.build/rss.xml",
    "svelte": "https://svelte.dev/blog/rss.xml",
    "nextjs": "https://nextjs.org/feed.xml",
    "tailwind": "https://tailwindcss.com/feeds/feed.xml",
    "devto": "https://dev.to/feed",
    "chrome_dev": "https://developer.chrome.com/blog/feed.xml",

    # =================================================================
    # Sciences & espace
    # =================================================================
    "nature": "https://www.nature.com/nature.rss",
    "nasa": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "space_com": "https://www.space.com/feeds/all",
    "phys_org": "https://phys.org/rss-feed/",
    "sciam": "http://rss.sciam.com/ScientificAmerican-Global",
    "newscientist_space": "https://www.newscientist.com/subject/space/feed/",
    "sky_telescope": "https://www.skyandtelescope.com/feed/",
    "flowingdata": "https://flowingdata.com/feed",

    # =================================================================
    # Entreprise & blogs techniques
    # =================================================================
    "aws": "https://aws.amazon.com/blogs/aws/feed/",
    "cloudflare": "https://blog.cloudflare.com/rss/",
    "github_blog": "https://github.blog/feed/",
    "netflix_tech": "https://netflixtechblog.com/feed",
    "meta_engineering": "https://engineering.fb.com/feed/",
    "spotify_engineering": "https://engineering.atspotify.com/feed/",
    "google_dev": "https://developers.googleblog.com/feeds/posts/default/",
    "google_research": "https://research.google/blog/rss/",
    "mozilla": "https://hacks.mozilla.org/feed/",
    "vercel": "https://vercel.com/atom",
    "supabase": "https://supabase.com/rss.xml",
    "stripe": "https://stripe.com/blog/feed.rss",
}

HEADERS: dict[str, str] = {
    "User-Agent": "websearch-agent/1.0 (news reader; contact@example.com)",
}


def _fetch_feed(source: str, url: str, query_lower: str, max_results_per_feed: int) -> list[dict[str, str]]:
    now = time.monotonic()

    # Verifier le cache
    with _feed_cache_lock:
        if source in _feed_cache:
            cached_time, cached_articles = _feed_cache[source]
            if now - cached_time < _FEED_CACHE_TTL:
                # Cache hit : filtrer directement depuis le cache
                if not query_lower:
                    return cached_articles[:max_results_per_feed]
                filtered = [
                    a for a in cached_articles
                    if query_lower in f"{a['title']} {a['snippet']}".lower()
                ]
                return filtered[:max_results_per_feed]

    # Cache miss : fetch depuis le reseau
    articles: list[dict[str, str]] = []
    try:
        session = _get_session()
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        all_articles: list[dict[str, str]] = []
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            all_articles.append({
                "title": title,
                "url": entry.get("link", ""),
                "snippet": summary,
                "source": source,
            })

        # Mettre en cache toutes les articles du flux
        with _feed_cache_lock:
            _feed_cache[source] = (now, all_articles)

        # Filtrer par query
        if query_lower:
            articles = [
                a for a in all_articles
                if query_lower in f"{a['title']} {a['snippet']}".lower()
            ][:max_results_per_feed]
        else:
            articles = all_articles[:max_results_per_feed]

    except requests.RequestException as e:
        logger.warning("Flux %s indisponible : %s", source, e)
    return articles


def news_search(
    query: str = "", max_results_per_feed: int = 1
) -> list[dict[str, str]]:
    """Recupere les articles RSS et filtre par query (parallelise + cache)."""
    all_articles: list[dict[str, str]] = []
    query_lower = query.lower().strip() if query else ""

    # Calculer quels flux necessitent un refresh (hors TTL)
    now = time.monotonic()
    feeds_to_fetch: list[tuple[str, str]] = []
    with _feed_cache_lock:
        for source, url in FEEDS.items():
            if source in _feed_cache:
                cached_time, cached_articles = _feed_cache[source]
                if now - cached_time < _FEED_CACHE_TTL:
                    # Cache hit : traiter sans thread
                    if query_lower:
                        filtered = [
                            a for a in cached_articles
                            if query_lower in f"{a['title']} {a['snippet']}".lower()
                        ]
                        all_articles.extend(filtered[:max_results_per_feed])
                    else:
                        all_articles.extend(cached_articles[:max_results_per_feed])
                    continue
            feeds_to_fetch.append((source, url))

    # Fetch les flux hors cache en parallele
    if feeds_to_fetch:
        futures = [
            _feed_executor.submit(_fetch_feed, source, url, query_lower, max_results_per_feed)
            for source, url in feeds_to_fetch
        ]
        for future in as_completed(futures):
            all_articles.extend(future.result())

    # Fallback : si le filtre ne donne rien, chercher sans filtre
    # (utile quand le mot-cle est en francais mais les flux en anglais)
    if query_lower and not all_articles:
        now = time.monotonic()
        with _feed_cache_lock:
            for source, (cached_time, cached_articles) in _feed_cache.items():
                if now - cached_time < _FEED_CACHE_TTL:
                    all_articles.extend(cached_articles[:max_results_per_feed])

    return all_articles


def invalidate_cache():
    """Invalide tout le cache (utile pour les tests)."""
    with _feed_cache_lock:
        _feed_cache.clear()


if __name__ == "__main__":
    import sys
    import json

    query = sys.argv[1] if len(sys.argv) > 1 else ""
    results = news_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n-> {len(results)} article(s)")
