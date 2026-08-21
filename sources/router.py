"""
Routeur intelligent ultra-performant — version optimisee.

Detection precise de l'intention, du domaine, de la complexite.
Outils minimum pour les requetes simples, maximum pour les complexes.
"""

import re
import logging

logger = logging.getLogger("websearch-agent.router")

# ============================================================================
# NIVEAUX D'OUTILS — plus restrictif pour les requetes simples
# ============================================================================

TOOL_LEVELS: dict[int, list[str]] = {
    1: [
        "perplexity_search",
        "searxng_search",
        "research_search",
        "querit_search",
        "langsearch_search",
        "yacy_search",
    ],
    2: [
        "perplexity_search",
        "tavily_search",
        "searxng_search",
        "firecrawl_search",
        "research_search",
        "wikipedia_search",
        "wikipedia_en_search",
        "agent_reach_web_search",
        "querit_search",
        "langsearch_search",
        "yacy_search",
        "brightdata_search",
    ],
    3: [
        "perplexity_search",
        "tavily_search",
        "duckduckgo_search",
        "searxng_search",
        "firecrawl_search",
        "just_scrape_search",
        "research_search",
        "wikipedia_search",
        "wikipedia_en_search",
        "github_search",
        "news_search",
        "datasets_search",
        "brave_search",
        "agent_reach_web_search",
        "agent_reach_github_search",
        "agent_reach_rss_search",
        "querit_search",
        "langsearch_search",
        "yacy_search",
        "brightdata_search",
    ],
}

# ============================================================================
# INDEX D'INTENT — patterns optimises, poids ajustes
# ============================================================================

INTENT_INDEX: dict[str, dict] = {
    "search_general": {
        "patterns": [
            r"\b(cherche|recherche|trouve|find|search|lookup|google)\b",
            r"\b(info|information|details?|detaille)\b",
        ],
        "weight": 0,
        "tools_boost": ["perplexity_search", "tavily_search"],
    },

    "explain": {
        "patterns": [
            r"\b(explique|expliquer|explain|comprendre|understand)\b",
            r"\b(comment (ça|cela|ca) (marche|fonctionne|works))\b",
        ],
        "weight": 15,
        "tools_boost": ["perplexity_search", "wikipedia_search", "wikipedia_en_search"],
    },

    "compare": {
        "patterns": [
            r"\b(compar|compare|comparison|vs|versus)\b",
            r"\b(diff[ée]rence|differ)\b",
            r"\b(quel est (le|la) meilleur|which is better)\b",
            r"\b(avantages?|inconv[ée]nients?|pros?|cons?)\b",
            r"\b(prefer|choisir entre|choose between)\b",
        ],
        "weight": 25,
        "tools_boost": ["perplexity_search", "tavily_search", "wikipedia_search"],
    },

    "news": {
        "patterns": [
            r"\b(actualit|actualité|news)\b",
            r"\b(dernier|dernière|recent|récent)\b",
            r"\b(aujourd'hui|hier|ce matin|cette semaine)\b",
            r"\b(breaking|actualit[ée]s?|sujet du jour|derni[èe]res?\s+nouvelles?)\b",
            r"\b(que se passe|what happening|what's new)\b",
        ],
        "weight": 20,
        "tools_boost": ["news_search", "perplexity_search", "agent_reach_rss_search"],
    },

    "code": {
        "patterns": [
            r"\b(github|repo|repository|code|coding|program)\b",
            r"\b(library|framework|package|sdk|npm|pip|cargo)\b",
            r"\b(installer|install|setup|configurer|configure)\b",
            r"\b(exemple|example|template|boilerplate)\b",
        ],
        "weight": 15,
        "tools_boost": ["github_search", "perplexity_search", "agent_reach_github_search"],
    },

    "data": {
        "patterns": [
            r"\b(dataset|data|donnees|données|open data)\b",
            r"\b(csv|json|excel|database|base de données)\b",
            r"\b(api|endpoint|streaming|temps r[ée]el|real-time)\b",
        ],
        "weight": 15,
        "tools_boost": ["datasets_search", "github_search"],
    },

    "recommend": {
        "patterns": [
            r"\b(recommand|recommend|conseille|advise)\b",
            r"\b(meilleur|best|optimal|ideal|top)\b",
            r"\b(quoi utiliser|what to use|which tool)\b",
        ],
        "weight": 20,
        "tools_boost": ["perplexity_search", "tavily_search"],
    },

    "howto": {
        "patterns": [
            r"\b(comment|how to|how do I|how can I)\b",
            r"\b(tutoriel|tutorial|guide|step by step|étape)\b",
        ],
        "weight": 15,
        "tools_boost": ["perplexity_search", "tavily_search"],
    },

    "definition": {
        "patterns": [
            r"\b(d[ée]finition|definition|signification|meaning)\b",
            r"\b(concept|principe|principle|notion)\b",
            r"\b(qu'est-ce que|what is|what are)\b",
        ],
        "weight": 10,
        "tools_boost": ["wikipedia_search", "wikipedia_en_search", "perplexity_search"],
    },

    "history": {
        "patterns": [
            r"\b(histoire|history|origine|origin)\b",
            r"\b([ée]volution|evolution|developpement|development)\b",
            r"\b(depuis quand|since when|when was|quand)\b",
        ],
        "weight": 10,
        "tools_boost": ["wikipedia_search", "wikipedia_en_search"],
    },

    "technical": {
        "patterns": [
            r"\b(architecture|infrastructure|deploy|deployment)\b",
            r"\b(s[ée]curit[ée]|security|vuln[ée]rabilit[ée])\b",
            r"\b(performance|optimisation|scale|scalability)\b",
            r"\b(microservice|api|rest|graphql|grpc)\b",
        ],
        "weight": 20,
        "tools_boost": ["perplexity_search", "github_search"],
    },

    "finance": {
        "patterns": [
            r"\b(finance|bourse|stock|crypto|bitcoin|ethereum)\b",
            r"\b(cours|price|market|march[ée]|trading)\b",
        ],
        "weight": 15,
        "tools_boost": ["perplexity_search", "news_search"],
    },

    "science": {
        "patterns": [
            r"\b(science|scientifique|scientific|research)\b",
            r"\b([ée]tude|study|paper|article|journal)\b",
            r"\b(exp[ée]riment|experiment|th[ée]orie|theory)\b",
        ],
        "weight": 15,
        "tools_boost": ["perplexity_search", "wikipedia_en_search"],
    },
}

# ============================================================================
# INDEX DE DOMAINES
# ============================================================================

DOMAIN_INDEX: dict[str, dict] = {
    "tech": {
        "keywords": [
            "python", "javascript", "typescript", "react", "vue", "angular",
            "node", "django", "fastapi", "flask", "rust", "golang", "java",
            "docker", "kubernetes", "aws", "gcp", "azure", "linux", "git",
            "ai", "ml", "llm", "gpt", "claude", "gemini", "openai",
            "html", "css", "sql", "nosql", "mongodb", "postgres",
            "redis", "kafka", "nginx", "apache", "webpack", "vite",
        ],
        "tools_boost": ["github_search"],
    },
    "science": {
        "keywords": [
            "physique", "chimie", "biologie", "astronomie", "mathematiques",
            "physics", "chemistry", "biology", "astronomy",
            "quantum", "evolution", "genetique", "adn",
            "neuroscience", "ecologie", "climat",
        ],
        "tools_boost": ["wikipedia_search", "wikipedia_en_search"],
    },
    "history": {
        "keywords": [
            "histoire", "guerre", "revolution", "empire", "civilisation",
            "history", "war", "civilization",
            "medieval", "antiquite", "renaissance",
        ],
        "tools_boost": ["wikipedia_search", "wikipedia_en_search"],
    },
    "geography": {
        "keywords": [
            "pays", "ville", "continent", "ocean", "montagne", "fleuve",
            "country", "city", "mountain", "river",
            "carte", "geographie",
        ],
        "tools_boost": ["wikipedia_search"],
    },
    "philosophy": {
        "keywords": [
            "philosophie", "philosophy", "ethique", "ethics",
            "existence", "conscience", "pensee",
        ],
        "tools_boost": ["wikipedia_search", "wikipedia_en_search"],
    },
    "art": {
        "keywords": [
            "art", "peinture", "musique", "cinema",
            "litterature", "theatre", "danse", "sculpture",
        ],
        "tools_boost": ["wikipedia_search"],
    },
}

# ============================================================================
# SIGNAUX DE COMPLEXITE — calibres pour un scoring precis
# ============================================================================

COMPLEXITY_SIGNALS: dict[str, list[tuple[str, int]]] = {
    "structure": [
        (r"^(pourquoi|comment) ", 15),
        (r"^(quel|quelle|quels|quelles) ", 5),
        (r"^(est-ce que|is it) ", 5),
        (r"\?$", 2),
    ],
    "length": [
        (r"^.{1,15}$", -15),
        (r"^.{16,30}$", -5),
        (r"^.{31,60}$", 5),
        (r"^.{61,}$", 15),
    ],
    "connectors": [
        (r"\b(et|and)\b", 2),
        (r"\b(mais|but|however)\b", 5),
        (r"\b(donc|so|therefore)\b", 5),
        (r"\b(bien que|although)\b", 8),
    ],
    "cognitive": [
        (r"\b(analyser|analyse|analyze)\b", 15),
        (r"\b(evaluer|evaluate)\b", 15),
        (r"\b(comparer|compare|comparison)\b", 20),
        (r"\b(synthetiser|synthetize)\b", 15),
        (r"\b(debattre|debate)\b", 15),
    ],
    "temporal": [
        (r"\b(aujourd'hui|today|maintenant)\b", 5),
        (r"\b(en 20\d{2}|in 20\d{2})\b", 8),
        (r"\b(depuis|since|pendant|during)\b", 5),
    ],
    "quantification": [
        (r"\b(combien|how much|how many)\b", 10),
        (r"\b(statistique|statistics|stats)\b", 10),
        (r"\b(pourcentage|percent|%)\b", 5),
    ],
}

# Pre-compiled patterns for performance
_COMPILED_COMPLEXITY: dict[str, list[tuple[re.Pattern, int]]] = {
    cat: [(re.compile(p), w) for p, w in signals]
    for cat, signals in COMPLEXITY_SIGNALS.items()
}

SIMPLIFICATION_SIGNALS: list[tuple[str, int]] = [
    (r"^[a-z]{1,15}$", -20),
    (r"^[a-z]+ [a-z]{1,10}$", -10),
    (r"^(qui a|who is|qui est)\b", -10),
    (r"^(combien|quel age)\b", -5),
    (r"^(ou se trouve|where is)\b", -10),
]

_COMPILED_SIMPLIFICATION: list[tuple[re.Pattern, int]] = [
    (re.compile(p), w) for p, w in SIMPLIFICATION_SIGNALS
]

# ============================================================================
# INDEX DE MOTS-CLES PAR OUTIL — scoring differentiel
# ============================================================================

TOOL_KEYWORD_INDEX: dict[str, dict] = {
    "github_search": {
        "primary": ["github", "repo", "repository", "code", "library", "framework", "package"],
        "secondary": ["npm", "pip", "cargo", "install", "setup", "open source"],
        "boost": 20,
    },
    "news_search": {
        "primary": ["actualit", "news", "breaking", "headline"],
        "secondary": ["dernier", "récent", "aujourd'hui", "hier", "sujet du jour"],
        "boost": 25,
    },
    "datasets_search": {
        "primary": ["dataset", "data", "donnees", "open data"],
        "secondary": ["csv", "json", "excel", "database", "api", "streaming"],
        "boost": 20,
    },
    "wikipedia_search": {
        "primary": ["définition", "definition", "concept", "principe", "histoire"],
        "secondary": ["biographie", "qui est", "théorie", "encyclopédie"],
        "boost": 15,
    },
    "wikipedia_en_search": {
        "primary": ["technical", "scientific", "research", "specification"],
        "secondary": ["academic", "journal", "methodology", "thesis"],
        "boost": 15,
    },
    "perplexity_search": {
        "primary": ["recherche", "search", "information", "récent"],
        "secondary": ["source", "article", "web", "internet"],
        "boost": 5,
    },
    "tavily_search": {
        "primary": ["recherche", "search", "information"],
        "secondary": ["récent", "source", "article"],
        "boost": 5,
    },
    "searxng_search": {
        "primary": ["métamoteur", "meta search", "open source"],
        "secondary": ["multi-source", "privacy", "décentralisé"],
        "boost": 5,
    },
    "firecrawl_search": {
        "primary": ["contenu complet", "full content", "extraction", "scrape"],
        "secondary": ["page", "article", "contenu", "markdown"],
        "boost": 10,
    },
    "just_scrape_search": {
        "primary": ["données structurées", "structured data", "extraction"],
        "secondary": ["scrape", "graph", "intelligent"],
        "boost": 10,
    },
    "research_search": {
        "primary": ["recherche approfondie", "deep research", "analyse"],
        "secondary": ["académique", "scientifique", "encyclopédique"],
        "boost": 10,
    },
    "agent_reach_web_search": {
        "primary": ["jina", "markdown extraction", "web content"],
        "secondary": ["page content", "article extraction"],
        "boost": 5,
    },
    "agent_reach_github_search": {
        "primary": ["github", "repo", "repository", "code", "library"],
        "secondary": ["npm", "pip", "open source", "framework"],
        "boost": 15,
    },
    "agent_reach_rss_search": {
        "primary": ["rss", "feed", "hacker news", "actualités tech"],
        "secondary": ["flux", "articles", "blog"],
        "boost": 10,
    },
}


def _compute_complexity(query: str) -> int:
    """Score de complexite optimise (0-100)."""
    score = 25
    q = query.lower().strip()

    for category, signals in _COMPILED_COMPLEXITY.items():
        for pattern, weight in signals:
            if pattern.search(q):
                score += weight

    for pattern, weight in _COMPILED_SIMPLIFICATION:
        if pattern.search(q):
            score += weight

    for intent_data in INTENT_INDEX.values():
        for pattern in intent_data["patterns"]:
            if re.search(pattern, q):
                score += intent_data["weight"]
                break

    domain_count = sum(
        1 for d in DOMAIN_INDEX.values()
        if any(kw in q for kw in d["keywords"])
    )
    if domain_count > 1:
        score += domain_count * 5

    return max(0, min(100, score))


def _detect_intent(query: str) -> list[str]:
    q = query.lower()
    intents = []
    for name, data in INTENT_INDEX.items():
        for pattern in data["patterns"]:
            if re.search(pattern, q):
                intents.append(name)
                break
    return intents


def _detect_domain(query: str) -> list[str]:
    q = query.lower()
    domains = []
    for name, data in DOMAIN_INDEX.items():
        if any(kw in q for kw in data["keywords"]):
            domains.append(name)
    return domains


# ============================================================================
# MODULE-BASED SOURCE BOOSTS — sources privilegiees par module metier
# ============================================================================

MODULE_SOURCE_BOOSTS: dict[str, list[str]] = {
    "productivity": ["perplexity_search", "searxng_search"],
    "design": ["perplexity_search", "firecrawl_search", "research_search"],
    "marketing": ["perplexity_search", "news_search", "searxng_search", "tavily_search"],
    "engineering": ["github_search", "perplexity_search", "searxng_search"],
    "data": ["datasets_search", "perplexity_search", "github_search"],
    "finance": ["perplexity_search", "news_search", "tavily_search"],
    "product_management": ["perplexity_search", "tavily_search", "research_search"],
    "pdf_viewer": ["perplexity_search", "searxng_search"],
    "sales": ["perplexity_search", "tavily_search", "news_search"],
    "operations": ["perplexity_search", "searxng_search", "research_search"],
    "legal": ["perplexity_search", "research_search", "wikipedia_search"],
    "enterprise_search": ["perplexity_search", "searxng_search", "tavily_search"],
    "small_business": ["perplexity_search", "news_search", "tavily_search"],
    "human_resources": ["perplexity_search", "news_search", "research_search"],
    "customer_support": ["perplexity_search", "searxng_search", "research_search"],
    "bio_research": ["perplexity_search", "research_search", "wikipedia_search", "wikipedia_en_search"],
}


def _get_module_boosted_tools() -> list[str]:
    """Retourne les outils boostes par les modules actifs."""
    try:
        from core.settings import _get_setting
        enabled = _get_setting("plugins", "enabled_modules", [])
        boosted = []
        for mod in enabled:
            if mod in MODULE_SOURCE_BOOSTS:
                for tool in MODULE_SOURCE_BOOSTS[mod]:
                    if tool not in boosted:
                        boosted.append(tool)
        return boosted
    except Exception:
        return []


def _detect_specific_tools(query: str) -> list[str]:
    q = query.lower()
    scores = {}

    for tool, idx in TOOL_KEYWORD_INDEX.items():
        s = 0
        for kw in idx["primary"]:
            if kw in q:
                s += idx["boost"] * 2
        for kw in idx["secondary"]:
            if kw in q:
                s += idx["boost"]
        if s > 0:
            scores[tool] = s

    return [t for t, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def _get_boosted_tools(intents: list[str], domains: list[str]) -> list[str]:
    boosted = []
    for intent in intents:
        for tool in INTENT_INDEX.get(intent, {}).get("tools_boost", []):
            if tool not in boosted:
                boosted.append(tool)
    for domain in domains:
        for tool in DOMAIN_INDEX.get(domain, {}).get("tools_boost", []):
            if tool not in boosted:
                boosted.append(tool)
    return boosted


def route_query(query: str) -> dict:
    """
    Route intelligemment — outils minimum pour simples, maximum pour complexes.
    """
    score = _compute_complexity(query)
    intents = _detect_intent(query)
    domains = _detect_domain(query)
    specific = _detect_specific_tools(query)

    if score < 40:
        level = 1
    elif score < 65:
        level = 2
    else:
        level = 3

    tools = list(TOOL_LEVELS[level])

    for tool in specific:
        if tool not in tools:
            tools.append(tool)

    boosted = _get_boosted_tools(intents, domains)
    for tool in boosted:
        if tool not in tools:
            tools.append(tool)

    # Module-based boosts
    module_boosted = _get_module_boosted_tools()
    for tool in module_boosted:
        if tool not in tools:
            tools.append(tool)

    # Limiter le nombre d'outils pour les requetes simples
    if level == 1 and len(tools) > 8:
        # Garder les 8 plus pertinents
        tools = tools[:8]

    logger.info(
        "Route: score=%d, level=%d, intents=%s, domains=%s, tools=%s",
        score, level, intents, domains, tools,
    )

    return {
        "complexity_score": score,
        "level": level,
        "tools": tools,
        "specific": specific,
        "intents": intents,
        "domains": domains,
    }


if __name__ == "__main__":
    queries = [
        "python",
        "qu'est-ce que le W3C",
        "comparaison entre React et Vue.js pour un projet SPA",
        "quel est le meilleur framework AI en 2026 et pourquoi",
        "github langchain",
        "actualites IA",
        "dataset climat",
        "difference entre SQL et NoSQL",
        "comment installer Docker sur Ubuntu",
        "histoire de la philosophie grecque",
        "recherche sur la securite des APIs REST",
        "bonjour",
    ]

    for q in queries:
        r = route_query(q)
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        print(f"  Score: {r['complexity_score']}, Niveau: {r['level']}")
        print(f"  Intentions: {r['intents']}")
        print(f"  Domaines: {r['domains']}")
        print(f"  Tools ({len(r['tools'])}): {r['tools']}")
