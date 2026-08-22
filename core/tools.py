"""
Registry des outils de recherche — definitions, dispatch, filtres.
Extrait de agent.py lors du refactoring.
"""

from sources import (
    wikipedia_search,
    wikipedia_en_search,
    github_search,
    news_search,
    datasets_search,
    perplexity_search,
    tavily_search,
    brave_search,
    duckduckgo_search,
    searxng_search,
    firecrawl_search,
    research_search,
    agent_reach_web_search,
    agent_reach_github_search,
    agent_reach_rss_search,
    querit_search,
    langsearch_search,
    yacy_search,
    brightdata_search,
    youtube_search,
    exa_search,
)

# ============================================================================
# TOOLS REGISTRY
# ============================================================================

TOOLS_REGISTRY: dict[str, dict] = {
    "perplexity_search": {
        "func": perplexity_search,
        "description": (
            "Recherche web intelligente via Perplexity (sonar). "
            "Repond a des questions generales, trouve des informations recentes, "
            "des sources web, des articles, de la documentation. "
            "Renvoie des citations avec les URLs source. "
            "A utiliser en PREMIER pour toute question necessitant une recherche web."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "tavily_search": {
        "func": tavily_search,
        "description": (
            "Recherche web via Tavily, optimisee pour les agents IA. "
            "Trouve des informations recentes, des articles, de la documentation. "
            "Renvoie des titres, URLs et extraits de contenu. "
            "A utiliser en PREMIER pour toute question necessitant une recherche web."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "brave_search": {
        "func": brave_search,
        "description": (
            "Recherche web via Brave Search, moteur prive sans tracking. "
            "Trouve des informations recentes, des articles, de la documentation. "
            "Renvoie des titres, URLs et extraits de contenu. "
            "A utiliser en PREMIER pour toute question necessitant une recherche web."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "duckduckgo_search": {
        "func": duckduckgo_search,
        "description": (
            "Recherche web via DuckDuckGo, moteur prive sans tracking, sans cle API. "
            "Trouve des informations recentes, des articles, de la documentation. "
            "Renvoie des titres, URLs et extraits de contenu. "
            "A utiliser en PREMIER pour toute question necessitant une recherche web."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "searxng_search": {
        "func": searxng_search,
        "description": (
            "Recherche web via SearXNG, metar moteur open-source decentralise. "
            "Agregresultats de multiples moteurs de recherche. "
            "Renvoie des titres, URLs et extraits de contenu. "
            "A utiliser en PREMIER pour toute question necessitant une recherche web."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "wikipedia_search": {
        "func": wikipedia_search,
        "description": (
            "Recherche sur Wikipedia (encyclopedie). "
            "A utiliser pour des questions factuelles, definitions, "
            "biographies, evenements historiques, concepts scientifiques."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (mots-cles en francais de preference).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "wikipedia_en_search": {
        "func": wikipedia_en_search,
        "description": (
            "Search English Wikipedia (encyclopedia). "
            "Use for factual questions, definitions, biographies, "
            "historical events, scientific concepts — especially "
            "when the topic is technical/specialized or likely to "
            "have better coverage in English than French."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "Search query (keywords, preferably in English).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "github_search": {
        "func": github_search,
        "description": (
            "Recherche des repositories GitHub. "
            "A utiliser pour trouver du code, des bibliotheques, "
            "des frameworks, des outils open-source."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (mots-cles en anglais de preference).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "news_search": {
        "func": news_search,
        "description": (
            "Recherche dans les articles d'actualite recents via 112 flux RSS "
            "couvrant: actualite generale (BBC, CNN, Guardian, Al Jazeera...), "
            "tech (TechCrunch, The Verge, Wired, Ars Technica, Hacker News...), "
            "IA (OpenAI, DeepMind, HuggingFace, arXiv...), "
            "cybersecurite (Krebs, Schneier, BleepingComputer, Dark Reading...), "
            "blogs entreprise (AWS, Cloudflare, GitHub, Netflix, Meta, Spotify...), "
            "langages (Python, Rust, Go, React, Vue, TypeScript...), "
            "newsletters (JavaScript Weekly, Rust Weekly, ByteByteGo...), "
            "frontend (Smashing, CSS-Tricks, Astro, Svelte, Tailwind...), "
            "sciences (Nature). "
            "A utiliser pour des questions sur l'actualite recente."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": (
                    "Mots-cles pour filtrer les articles. "
                    "Laisser vide pour avoir les derniers articles sans filtre."
                ),
            }
        },
        "required": [],
        "defaults": {"max_results_per_feed": 1},
    },
    "datasets_search": {
        "func": datasets_search,
        "description": (
            "Recherche des jeux de donnees publics (datasets) parmi ~1000 references. "
            "Couvre les datasets statiques (fichiers CSV, bases de donnees) "
            "en climat, sante, economie, biologie, NLP, computer vision, transport... "
            "ET les flux temps reel (WebSocket, API streaming) "
            "en finance/crypto, meteo, transport, cybersecurite, IoT. "
            "A utiliser pour trouver des sources de donnees sur un sujet donne."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": (
                    "Mots-cles pour filtrer les datasets (ex: 'climat', "
                    "'NLP francais', 'finance temps reel'). "
                    "Laisser vide pour voir un echantillon par categorie."
                ),
            }
        },
        "required": [],
        "defaults": {"max_results": 10},
    },
    "firecrawl_search": {
        "func": firecrawl_search,
        "description": (
            "Recherche web avancee via Firecrawl avec extraction de contenu complet. "
            "Retourne le contenu markdown des pages trouvees. "
            "A utiliser pour des recherches approfondies necessitant le contenu complet."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "research_search": {
        "func": research_search,
        "description": (
            "Recherche approfondie combinant Wikipedia FR/EN. "
            "Utile pour les questions necessitant une analyse complete "
            "avec des sources encyclopediques fiables. "
            "A utiliser pour les sujets academiques, historiques, scientifiques."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "agent_reach_web_search": {
        "func": agent_reach_web_search,
        "description": (
            "Recherche web via Jina Reader (agent-reach). "
            "Extrait le contenu markdown des pages trouvees. "
            "Necessite la variable d'environnement JINA_API_KEY. "
            "A utiliser pour des recherches generales ou when Jina is preferred."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "agent_reach_github_search": {
        "func": agent_reach_github_search,
        "description": (
            "Recherche GitHub via gh CLI (agent-reach). "
            "Trouve des repositories, code, frameworks open-source. "
            "A utiliser pour trouver des outils, bibliotheques, exemples de code."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (mots-cles en anglais).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "agent_reach_rss_search": {
        "func": agent_reach_rss_search,
        "description": (
            "Recherche dans les flux RSS via feedparser (agent-reach). "
            "Par defaut: Hacker News frontpage. "
            "A utiliser pour des questions sur l'actualite tech, programmation, open-source."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "Mots-cles pour filtrer les articles.",
            },
            "feed_url": {
                "type": "string",
                "description": "URL du flux RSS (defaut: Hacker News).",
            },
        },
        "required": ["query"],
        "defaults": {"max_results": 5, "feed_url": "https://hnrss.org/frontpage"},
    },
    "querit_search": {
        "func": querit_search,
        "description": (
            "Recherche web via Querit, moteur intelligent avec extraction de contenu. "
            "Repond a des questions generales, trouve des informations recentes, "
            "des sources web, des articles. "
            "A utiliser pour toute question necessitant une recherche web."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "langsearch_search": {
        "func": langsearch_search,
        "description": (
            "Recherche web via LangSearch avec reranking semantique. "
            "Trouve des informations recentes, des articles, de la documentation. "
            "Renvoie des titres, URLs et extraits de contenu. "
            "A utiliser pour toute question necessitant une recherche web."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "yacy_search": {
        "func": yacy_search,
        "description": (
            "Recherche web via YaCy, moteur open-source decentralise heberge en local. "
            "Trouve des informations, articles, documentations. "
            "A utiliser pour toute question necessitant une recherche web."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "brightdata_search": {
        "func": brightdata_search,
        "description": (
            "Recherche web via Brightdata MCP avec proxy anti-bot. "
            "Bypass la detection bot, CAPTCHA, rate limiting. "
            "A utiliser pour des recherches sur des sites proteges ou pour un taux de reussite maximal."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "youtube_search": {
        "func": youtube_search,
        "description": (
            "Recherche de videos YouTube via yt-dlp. "
            "Trouve des videos, tutoriels, conferences, documentaires. "
            "Renvoie les titres, URLs et descriptions des videos. "
            "A utiliser pour des questions necessitant des videos ou tutoriels."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
    "exa_search": {
        "func": exa_search,
        "description": (
            "Recherche semantique intelligente via Exa AI. "
            "Comprend le sens de la question, retourne les sources les plus pertinentes. "
            "Ideal pour la recherche approfondie et la decouverte de contenu."
        ),
        "params": {
            "query": {
                "type": "string",
                "description": "La requete de recherche (question ou mots-cles).",
            }
        },
        "required": ["query"],
        "defaults": {"max_results": 5},
    },
}

# ============================================================================
# AUTO-GENERATION — schema OpenAI + dispatch
# ============================================================================

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": entry["description"],
            "parameters": {
                "type": "object",
                "properties": entry["params"],
                "required": entry["required"],
            },
        },
    }
    for name, entry in TOOLS_REGISTRY.items()
]


def _make_dispatch(name: str, entry: dict):
    func = entry["func"]
    defaults = entry["defaults"]

    def dispatch(**kwargs):
        merged = {**defaults, **{k: v for k, v in kwargs.items() if v is not None}}
        return func(**merged)

    dispatch.__name__ = name
    return dispatch


TOOL_FUNCTIONS: dict[str, callable] = {
    name: _make_dispatch(name, entry)
    for name, entry in TOOLS_REGISTRY.items()
}


def _filter_tools(allowed_names: list[str]) -> list[dict]:
    return [t for t in TOOLS if t["function"]["name"] in allowed_names]


# ============================================================================
# SCORING DES RESULTATS — priorise les sources fiables
# ============================================================================

# Poids de fiabilite par source (plus haut = plus fiable)
SOURCE_RELIABILITY: dict[str, float] = {
    "wikipedia_search": 1.0,      # Encyclopedie, tres fiable
    "wikipedia_en_search": 1.0,
    "research_search": 0.95,      # Combine Wikipedia FR/EN
    "github_search": 0.9,         # Code source officiel
    "perplexity_search": 0.85,    # Bonne qualite generale
    "tavily_search": 0.85,
    "brave_search": 0.8,
    "duckduckgo_search": 0.75,
    "searxng_search": 0.75,
    "news_search": 0.8,           # Actualites verifiees
    "datasets_search": 0.9,       # Donnees officielles
    "firecrawl_search": 0.7,      # Extraction brute
    "agent_reach_web_search": 0.75,   # Jina Reader, extraction markdown
    "agent_reach_github_search": 0.9, # GitHub officiel via gh CLI
    "agent_reach_rss_search": 0.7,    # Flux RSS, qualite variable
    "querit_search": 0.85,            # Recherche intelligente avec extraction
    "langsearch_search": 0.85,        # Reranking semantique
    "yacy_search": 0.75,              # Moteur open-source local
    "brightdata_search": 0.9,         # Proxy anti-bot, tres fiable
    "youtube_search": 0.8,            # Videos YouTube via yt-dlp
    "exa_search": 0.9,                # Recherche semantique IA
}


def _score_result(result: dict, source_name: str = "") -> float:
    """Score un resultat de 0 a 1 base sur la fiabilite de la source."""
    base_score = SOURCE_RELIABILITY.get(source_name, 0.5)

    # Bonus si le resultat a un titre et un snippet
    has_title = bool(result.get("title"))
    has_snippet = bool(result.get("snippet"))
    has_url = bool(result.get("url"))

    content_bonus = 0.0
    if has_url:
        content_bonus += 0.1
    if has_title:
        content_bonus += 0.1
    if has_snippet and len(result.get("snippet", "")) > 50:
        content_bonus += 0.1

    return min(base_score + content_bonus, 1.0)


def _sort_results_by_relevance(results: list[dict], source_name: str = "") -> list[dict]:
    """Trie les resultats par pertinence (score decroissant)."""
    return sorted(results, key=lambda r: _score_result(r, source_name), reverse=True)


# ============================================================================
# FILTRAGE PAR DOMAINE — post-filtrage centralise pour /search
# ============================================================================

def _filter_by_domains(
    results: list[dict],
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[dict]:
    """Filtre les resultats par domaine (include/exclude).

    Utilise urllib.parse.urlparse(url).netloc pour extraire le domaine.
    Correspondance par suffixe : "docs.github.com" matche "github.com".

    Args:
        results: Liste de resultats (dict avec clé "url").
        include: Domaines autorises (None = tous autorises).
        exclude: Domaines interdits (None = aucun interdit).

    Returns:
        Liste filtree.
    """
    if not include and not exclude:
        return results

    from urllib.parse import urlparse

    def _get_domain(url: str) -> str:
        """Extrait le netloc ( domaine ) d'une URL."""
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def _matches(domain: str, pattern: str) -> bool:
        """Verifie si domain se termine par pattern (gestion sous-domaines)."""
        pattern = pattern.lower().strip()
        return domain == pattern or domain.endswith("." + pattern)

    filtered: list[dict] = []
    for r in results:
        url = r.get("url", "")
        if not url:
            filtered.append(r)
            continue

        domain = _get_domain(url)
        if not domain:
            filtered.append(r)
            continue

        # Exclude : rejeter si le domaine matche un pattern exclude
        if exclude and any(_matches(domain, ex) for ex in exclude):
            continue

        # Include : accepter uniquement si include est None ou domaine matche
        if include and not any(_matches(domain, inc) for inc in include):
            continue

        filtered.append(r)

    return filtered
