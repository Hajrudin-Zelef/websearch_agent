"""
Package sources — point d'entree unique pour toutes les sources de donnees.

Utilisation :
    from sources import wikipedia_search, github_search, news_search
    from sources import SOURCES  # registry de toutes les sources
    from sources import get_source  # accès par nom
    from sources import list_sources  # liste les sources disponibles

Pour ajouter une source :
    1. Creer sources/ma_source.py avec une fonction ma_source_search(query) -> list[dict]
    2. L'ajouter dans SOURCES ci-dessous
    3. L'ajouter dans __all__
"""

from sources.wikipedia import wikipedia_search
from sources.wikipedia_en import wikipedia_en_search
from sources.github import github_search
from sources.news_rss import news_search
from sources.datasets import datasets_search
from sources.perplexity import perplexity_search
from sources.tavily import tavily_search
from sources.brave import brave_search
from sources.duckduckgo import duckduckgo_search
from sources.searxng import searxng_search

# ============================================================================
# REGISTRY — source unique de verite pour les sources disponibles
# ============================================================================

SOURCES: dict[str, dict] = {
    "wikipedia": {
        "func": wikipedia_search,
        "lang": "fr",
        "type": "encyclopedie",
        "description": "Wikipedia francais — questions factuelles, definitions, biographies",
        "requires_key": False,
    },
    "wikipedia_en": {
        "func": wikipedia_en_search,
        "lang": "en",
        "type": "encyclopedie",
        "description": "Wikipedia anglais — sujets techniques, scientifiques",
        "requires_key": False,
    },
    "github": {
        "func": github_search,
        "lang": "en",
        "type": "code",
        "description": "GitHub — repositories, code, frameworks, outils open-source",
        "requires_key": False,  # GITHUB_TOKEN optionnel (5000 req/h au lieu de 60)
    },
    "news": {
        "func": news_search,
        "lang": "multi",
        "type": "actualites",
        "description": "112 flux RSS — actu, tech, IA, cybersec, prog, sciences",
        "requires_key": False,
    },
    "datasets": {
        "func": datasets_search,
        "lang": "multi",
        "type": "donnees",
        "description": "~1000 datasets publics — statiques + temps reel",
        "requires_key": False,
    },
    "perplexity": {
        "func": perplexity_search,
        "lang": "multi",
        "type": "web",
        "description": "Perplexity sonar — recherche web intelligente avec citations",
        "requires_key": True,
    },
    "tavily": {
        "func": tavily_search,
        "lang": "multi",
        "type": "web",
        "description": "Tavily — recherche web optimisee pour les agents IA",
        "requires_key": True,
    },
    "brave": {
        "func": brave_search,
        "lang": "multi",
        "type": "web",
        "description": "Brave Search — recherche web privee et rapide",
        "requires_key": True,
    },
    "duckduckgo": {
        "func": duckduckgo_search,
        "lang": "multi",
        "type": "web",
        "description": "DuckDuckGo — recherche web privee sans tracking",
        "requires_key": False,
    },
    "searxng": {
        "func": searxng_search,
        "lang": "multi",
        "type": "web",
        "description": "SearXNG — metar moteur open-source decentralise",
        "requires_key": False,
    },
}


def get_source(name: str):
    """Retourne la fonction de recherche d'une source par son nom."""
    if name not in SOURCES:
        available = ", ".join(SOURCES.keys())
        raise KeyError(f"Source '{name}' inconnue. Sources disponibles : {available}")
    return SOURCES[name]["func"]


def list_sources() -> list[dict]:
    """Retourne la liste des sources avec leurs metadonnees."""
    return [
        {"name": name, **meta}
        for name, meta in SOURCES.items()
    ]


def search(source_name: str, query: str, **kwargs):
    """Recherche unifiee — appelle la bonne source par son nom."""
    func = get_source(source_name)
    return func(query=query, **kwargs)


# ============================================================================
# SMART SEARCH — routing automatique par mots-cles
# ============================================================================

# Mots-cles -> sources pertinentes (ordre de pertinence)
_KEYWORD_ROUTING: dict[str, list[str]] = {
    # Code & outils
    "github": ["github"],
    "repo": ["github"],
    "library": ["github"],
    "framework": ["github"],
    "open source": ["github"],
    "npm": ["github"],
    "pip": ["github"],
    "crate": ["github"],
    # Datasets
    "dataset": ["datasets"],
    "data": ["datasets"],
    "csv": ["datasets"],
    "api": ["datasets"],
    "real time": ["datasets"],
    "streaming": ["datasets"],
    # Wikipedia
    "qui": ["wikipedia", "wikipedia_en"],
    "quoi": ["wikipedia", "wikipedia_en"],
    "comment": ["wikipedia", "wikipedia_en"],
    "definition": ["wikipedia", "wikipedia_en"],
    "histoire": ["wikipedia", "wikipedia_en"],
    "biographie": ["wikipedia", "wikipedia_en"],
    "who": ["wikipedia_en"],
    "what": ["wikipedia_en"],
    "how": ["wikipedia_en"],
    # Actualites
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

    Retourne un dict {source_name: [resultats]} pour chaque source adaptee.

    Exemple :
        results = smart_search("framework python")
        # -> {"github": [...], "news": [...]}
    """
    query_lower = query.lower()

    # Detecter les sources pertinentes par mots-cles
    matched_sources: dict[str, int] = {}  # source -> score
    for keyword, sources in _KEYWORD_ROUTING.items():
        if keyword in query_lower:
            for i, src in enumerate(sources):
                score = len(sources) - i  # bonus pour les premieres sources
                matched_sources[src] = matched_sources.get(src, 0) + score

    # Si aucun mot-cle specifique, interroger toutes les sources
    if not matched_sources:
        matched_sources = {name: 1 for name in SOURCES}

    # Executer les recherches en parallele
    import concurrent.futures

    results: dict[str, list] = {}

    def _search_source(name: str):
        try:
            func = SOURCES[name]["func"]
            return name, func(query=query, max_results=max_results)
        except Exception:
            return name, []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(_search_source, name)
            for name in matched_sources
        ]
        for future in concurrent.futures.as_completed(futures):
            name, source_results = future.result()
            if source_results:
                results[name] = source_results

    return results


__all__ = [
    "wikipedia_search",
    "wikipedia_en_search",
    "github_search",
    "news_search",
    "datasets_search",
    "perplexity_search",
    "tavily_search",
    "brave_search",
    "duckduckgo_search",
    "searxng_search",
    "SOURCES",
    "get_source",
    "list_sources",
    "search",
    "smart_search",
]
