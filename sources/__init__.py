"""
Package sources — point d'entree unique pour toutes les sources de donnees.

Lazy loading : les modules sources ne sont charges que lors du premier appel.
Le chargement de `from sources import wikipedia_search` ne charge PAS
tous les 13 modules — juste celui demandé.

Utilisation :
    from sources import wikipedia_search, github_search, news_search
    from sources import SOURCES  # registry (pas de lazy loading)
    from sources import get_source  # accès par nom (lazy)
    from sources import list_sources  # liste les sources (pas de lazy)
    from sources import smart_search  # routing automatique (lazy)

Pour ajouter une source :
    1. Creer sources/ma_source.py avec une fonction ma_source_search(query) -> list[dict]
    2. L'ajouter dans SOURCES ci-dessous
    3. L'ajouter dans _LAZY_IMPORTS
"""

import concurrent.futures
import importlib
from typing import Any

# Shared ThreadPoolExecutor for parallel source search
_search_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

# ============================================================================
# LAZY IMPORTS — mapping nom -> (module, function_name)
# ============================================================================

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "wikipedia_search": ("sources.wikipedia", "wikipedia_search"),
    "wikipedia_en_search": ("sources.wikipedia_en", "wikipedia_en_search"),
    "github_search": ("sources.github", "github_search"),
    "news_search": ("sources.news_rss", "news_search"),
    "datasets_search": ("sources.datasets", "datasets_search"),
    "perplexity_search": ("sources.perplexity", "perplexity_search"),
    "tavily_search": ("sources.tavily", "tavily_search"),
    "brave_search": ("sources.brave", "brave_search"),
    "duckduckgo_search": ("sources.duckduckgo", "duckduckgo_search"),
    "searxng_search": ("sources.searxng", "searxng_search"),
    "firecrawl_search": ("sources.firecrawl_search", "firecrawl_search"),
    "just_scrape_search": ("sources.just_scrape", "just_scrape_search"),
    "research_search": ("sources.research", "research_search"),
    "agent_reach_web_search": ("sources.agent_reach", "agent_reach_web_search"),
    "agent_reach_github_search": ("sources.agent_reach", "agent_reach_github_search"),
    "agent_reach_rss_search": ("sources.agent_reach", "agent_reach_rss_search"),
    "querit_search": ("sources.querit", "querit_search"),
    "langsearch_search": ("sources.langsearch", "langsearch_search"),
    "yacy_search": ("sources.yacy", "yacy_search"),
    "brightdata_search": ("sources.brightdata", "brightdata_search"),
    "youtube_search": ("sources.youtube", "youtube_search"),
    "exa_search": ("sources.exa", "exa_search"),
}

# Cache des fonctions deja importees
_loaded: dict[str, Any] = {}


def __getattr__(name: str):
    """Lazy import : charge le module source uniquement lors du premier acces."""
    if name in _LAZY_IMPORTS:
        if name not in _loaded:
            module_path, func_name = _LAZY_IMPORTS[name]
            module = importlib.import_module(module_path)
            _loaded[name] = getattr(module, func_name)
        return _loaded[name]
    raise AttributeError(f"module 'sources' has no attribute {name!r}")


# ============================================================================
# REGISTRY — source unique de verite pour les sources disponibles
# (chargé eager car c'est juste des dicts, pas de lourds imports)
# ============================================================================

SOURCES: dict[str, dict] = {
    "wikipedia": {
        "lang": "fr",
        "type": "encyclopedie",
        "description": "Wikipedia francais — questions factuelles, definitions, biographies",
        "requires_key": False,
    },
    "wikipedia_en": {
        "lang": "en",
        "type": "encyclopedie",
        "description": "Wikipedia anglais — sujets techniques, scientifiques",
        "requires_key": False,
    },
    "github": {
        "lang": "en",
        "type": "code",
        "description": "GitHub — repositories, code, frameworks, outils open-source",
        "requires_key": False,
    },
    "news": {
        "lang": "multi",
        "type": "actualites",
        "description": "112 flux RSS — actu, tech, IA, cybersec, prog, sciences",
        "requires_key": False,
    },
    "datasets": {
        "lang": "multi",
        "type": "donnees",
        "description": "~1000 datasets publics — statiques + temps reel",
        "requires_key": False,
    },
    "perplexity": {
        "lang": "multi",
        "type": "web",
        "description": "Perplexity sonar — recherche web intelligente avec citations",
        "requires_key": True,
    },
    "tavily": {
        "lang": "multi",
        "type": "web",
        "description": "Tavily — recherche web optimisee pour les agents IA",
        "requires_key": True,
    },
    "brave": {
        "lang": "multi",
        "type": "web",
        "description": "Brave Search — recherche web privee et rapide",
        "requires_key": True,
    },
    "duckduckgo": {
        "lang": "multi",
        "type": "web",
        "description": "DuckDuckGo — recherche web privee sans tracking",
        "requires_key": False,
    },
    "searxng": {
        "lang": "multi",
        "type": "web",
        "description": "SearXNG — metar moteur open-source decentralise",
        "requires_key": False,
    },
    "firecrawl": {
        "lang": "multi",
        "type": "web",
        "description": "Firecrawl — recherche web avec extraction de contenu complet",
        "requires_key": True,
    },
    "just_scrape": {
        "lang": "multi",
        "type": "web",
        "description": "ScrapeGraph AI — recherche web intelligente avec extraction",
        "requires_key": True,
    },
    "research": {
        "lang": "multi",
        "type": "research",
        "description": "Recherche approfondie — combine Wikipedia + sources primaires",
        "requires_key": False,
    },
    "agent_reach_web": {
        "lang": "multi",
        "type": "web",
        "description": "Agent Reach Web — Jina Reader, extraction markdown",
        "requires_key": False,
    },
    "agent_reach_github": {
        "lang": "en",
        "type": "code",
        "description": "Agent Reach GitHub — repositories via gh CLI",
        "requires_key": False,
    },
    "agent_reach_rss": {
        "lang": "multi",
        "type": "news",
        "description": "Agent Reach RSS — flux RSS via feedparser",
        "requires_key": False,
    },
    "querit": {
        "lang": "multi",
        "type": "web",
        "description": "Querit — recherche web intelligente avec extraction de contenu",
        "requires_key": True,
    },
    "langsearch": {
        "lang": "multi",
        "type": "web",
        "description": "LangSearch — recherche web avec reranking semantique",
        "requires_key": True,
    },
    "yacy": {
        "lang": "multi",
        "type": "web",
        "description": "YaCy — moteur de recherche open-source decentralise, heberge en local",
        "requires_key": False,
        "optional": True,
    },
    "brightdata": {
        "lang": "multi",
        "type": "web",
        "description": "Brightdata — recherche web via MCP avec proxy anti-bot",
        "requires_key": True,
    },
    "youtube": {
        "lang": "multi",
        "type": "video",
        "description": "YouTube — recherche de videos via yt-dlp",
        "requires_key": False,
    },
    "exa": {
        "lang": "multi",
        "type": "web",
        "description": "Exa — recherche semantique intelligente par IA",
        "requires_key": True,
    },
}


def get_source(name: str):
    """Retourne la fonction de recherche d'une source par son nom (lazy)."""
    if name not in SOURCES:
        available = ", ".join(SOURCES.keys())
        raise KeyError(f"Source '{name}' inconnue. Sources disponibles : {available}")
    # Lazy import via __getattr__
    func_name = f"{name}_search" if name != "datasets" else "datasets_search"
    # Mapping special pour les noms qui ne suivent pas le pattern
    special = {
        "wikipedia_en": "wikipedia_en_search",
        "duckduckgo": "duckduckgo_search",
        "searxng": "searxng_search",
        "firecrawl": "firecrawl_search",
        "just_scrape": "just_scrape_search",
    }
    func_name = special.get(name, func_name)
    return __getattr__(func_name)


def list_sources() -> list[dict]:
    """Retourne la liste des sources avec leurs metadonnees."""
    return [
        {"name": name, **meta}
        for name, meta in SOURCES.items()
    ]


def search(source_name: str, query: str, **kwargs):
    """Recherche unifiee — appelle la bonne source par son nom (lazy)."""
    func = get_source(source_name)
    return func(query=query, **kwargs)


# ============================================================================
# SMART SEARCH — routing automatique par mots-cles
# ============================================================================

# Mots-cles -> sources pertinentes (ordre de pertinence)
_KEYWORD_ROUTING: dict[str, list[str]] = {
    "github": ["github"],
    "repo": ["github"],
    "library": ["github"],
    "framework": ["github"],
    "open source": ["github"],
    "npm": ["github"],
    "pip": ["github"],
    "crate": ["github"],
    "dataset": ["datasets"],
    "data": ["datasets"],
    "csv": ["datasets"],
    "api": ["datasets"],
    "real time": ["datasets"],
    "streaming": ["datasets"],
    "qui": ["wikipedia", "wikipedia_en"],
    "quoi": ["wikipedia", "wikipedia_en"],
    "comment": ["wikipedia", "wikipedia_en"],
    "definition": ["wikipedia", "wikipedia_en"],
    "histoire": ["wikipedia", "wikipedia_en"],
    "biographie": ["wikipedia", "wikipedia_en"],
    "who": ["wikipedia_en"],
    "what": ["wikipedia_en"],
    "how": ["wikipedia_en"],
    "actualite": ["news"],
    "news": ["news"],
    "derniere": ["news"],
    "recent": ["news"],
    "aujourd": ["news"],
    "hier": ["news"],
    "breaking": ["news"],
}


def smart_search(query: str, max_results: int = 5) -> dict[str, list]:
    """
    Recherche intelligente — route automatiquement vers les sources pertinentes.
    Utilise le lazy loading : seules les sources pertinentes sont chargees.
    """
    query_lower = query.lower()

    matched_sources: dict[str, int] = {}
    for keyword, sources in _KEYWORD_ROUTING.items():
        if keyword in query_lower:
            for i, src in enumerate(sources):
                score = len(sources) - i
                matched_sources[src] = matched_sources.get(src, 0) + score

    if not matched_sources:
        matched_sources = {name: 1 for name in SOURCES}

    import concurrent.futures

    results: dict[str, list] = {}

    def _search_source(name: str):
        try:
            func = get_source(name)
            return name, func(query=query, max_results=max_results)
        except Exception:
            return name, []

    futures = [
        _search_executor.submit(_search_source, name)
        for name in matched_sources
    ]
    for future in concurrent.futures.as_completed(futures):
        name, source_results = future.result()
        if source_results:
            results[name] = source_results

    return results


__all__ = [
    "SOURCES",
    "agent_reach_github_search",
    "agent_reach_rss_search",
    "agent_reach_web_search",
    "brave_search",
    "brightdata_search",
    "datasets_search",
    "duckduckgo_search",
    "exa_search",
    "firecrawl_search",
    "get_source",
    "github_search",
    "just_scrape_search",
    "langsearch_search",
    "list_sources",
    "news_search",
    "perplexity_search",
    "querit_search",
    "research_search",
    "search",
    "searxng_search",
    "smart_search",
    "tavily_search",
    "wikipedia_en_search",
    "wikipedia_search",
    "yacy_search",
    "youtube_search",
]
