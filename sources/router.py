"""
Routeur intelligent ultra-performant — version optimisee.

Detection precise de l'intention, du domaine, de la complexite.
Outils minimum pour les requetes simples, maximum pour les complexes.
"""

import re
import logging

from core.circuit_breaker import circuit_breaker

logger = logging.getLogger("websearch-agent.router")

# ============================================================================
# NIVEAUX D'OUTILS — plus restrictif pour les requetes simples
# ============================================================================

TOOL_LEVELS: dict[int, list[str]] = {
    1: [
        "duckduckgo_search",
        "brave_search",
        "searxng_search",
        "research_search",
        "perplexity_search",
        "querit_search",
        "langsearch_search",
        "youtube_search",
        "exa_search",
    ],
    2: [
        "duckduckgo_search",
        "searxng_search",
        "research_search",
        "perplexity_search",
        "tavily_search",
        "firecrawl_search",
        "wikipedia_search",
        "wikipedia_en_search",
        "agent_reach_web_search",
        "querit_search",
        "langsearch_search",
        "brightdata_search",
        "youtube_search",
        "exa_search",
    ],
    3: [
        "duckduckgo_search",
        "searxng_search",
        "research_search",
        "perplexity_search",
        "tavily_search",
        "firecrawl_search",
        "just_scrape_search",
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
        "brightdata_search",
        "youtube_search",
        "exa_search",
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
            "github", "langchain", "ai", "ml", "llm", "gpt", "claude", "gemini", "openai",
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
    "code": {
        "keywords": [
            "programmation", "algorithme", "variable", "fonction", "classe",
            "compil", "debug", "code", "developpeur", "ide", "editor",
            "bug", "refactor", "test", "unitaire", "module", "package",
        ],
        "tools_boost": ["github_search", "searxng_search"],
    },
    "info": {
        "keywords": [
            "information", "c'est quoi", "definition", "definir",
            "expliquer", "fonctionner", "comment marche", "pourquoi",
            "principe", "concept", "notion", "signification",
        ],
        "tools_boost": ["wikipedia_search", "research_search"],
    },
    "actualite": {
        "keywords": [
            "actualite", "news", "breaking", "derniere",
            "dernier", "aujourd'hui", "hier", "ce matin", "ce soir",
            "recent", "nouveau", "nouvelle", "sujet du jour",
        ],
        "tools_boost": ["news_search", "agent_reach_rss_search", "searxng_search"],
    },
    "reseau": {
        "keywords": [
            "internet", "site web", "serveur", "dns", "cloud",
            "vpn", "firewall", "proxy", "ssl", "https",
            "reseau", "network", "bande passante", "latence",
        ],
        "tools_boost": ["searxng_search", "agent_reach_web_search"],
    },
    "finance": {
        "keywords": [
            "bourse", "crypto", "bitcoin", "ethereum", "investissement",
            "trading", "action", "portefeuille", "dividende",
            "marche", "economie", "inflation", "taux", "interet",
        ],
        "tools_boost": ["news_search", "searxng_search", "research_search"],
    },
    "sante": {
        "keywords": [
            "medecine", "sante", "symptome", "traitement", "medicament",
            "maladie", "diagnostic", "docteur", "hopital", "pharmacie",
            "alimentation", "sport", "sommeil", "stress",
        ],
        "tools_boost": ["wikipedia_search", "research_search"],
    },
    "education": {
        "keywords": [
            "cours", "tutoriel", "formation", "apprendre", "etude",
            "ecole", "universite", "diplome", "examen", "exercice",
            "professeur", "eleve", "matiere", "programme",
        ],
        "tools_boost": ["searxng_search", "youtube_search", "research_search"],
    },
    "sport": {
        "keywords": [
            "football", "basketball", "tennis", "match", "score",
            "championnat", "olympique", "joueur", "equipe", "entraineur",
            "coupe", "liga", "premier league", "nba", "atp",
        ],
        "tools_boost": ["news_search", "agent_reach_rss_search", "youtube_search"],
    },
    "cuisine": {
        "keywords": [
            "recette", "cuisson", "ingredient", "plat",
            "four", "cuisine", "mijoter", "griller",
            "dessert", "entree", "menu", "chef",
        ],
        "tools_boost": ["searxng_search", "youtube_search"],
    },
    "mode": {
        "keywords": [
            "vetement", "tendance", "style", "fashion",
            "luxe", "couture", "marque", "collection", "accessoire",
            "chaussure", "montre", "bijou", "sac",
        ],
        "tools_boost": ["searxng_search", "agent_reach_web_search"],
    },
    "musique": {
        "keywords": [
            "chanson", "album", "concert", "artiste", "playlist",
            "guitare", "piano", "batterie", "melodie", "rythme",
            "rap", "rock", "jazz", "classique", "electro",
        ],
        "tools_boost": ["searxng_search", "youtube_search"],
    },
    "cinema": {
        "keywords": [
            "film", "serie", "acteur", "actrice", "realisateur",
            "netflix", "critique", "bande-annonce", "oscar",
            "comedie", "drame", "thriller", "horreur", "documentaire",
        ],
        "tools_boost": ["searxng_search", "wikipedia_search"],
    },
    "jeu_video": {
        "keywords": [
            "jeu", "ps5", "xbox", "nintendo", "steam",
            "rpg", "fps", "mmo", "gaming", "console",
            "joueur", "partie", "niveau", "boss",
        ],
        "tools_boost": ["searxng_search", "youtube_search"],
    },
    "voyage": {
        "keywords": [
            "hotel", "vol", "touristique",
            "visa", "bagage", "reservation", "croisiere",
            "plage", "camping", "road trip",
        ],
        "tools_boost": ["searxng_search", "wikipedia_search"],
    },
    "immobilier": {
        "keywords": [
            "appartement", "maison", "loyer", "achat", "terrain",
            "copropriete", "notaire", "hypothèque", "investissement locatif",
            "surface", "chambre", "salon", "jardin",
        ],
        "tools_boost": ["searxng_search", "research_search"],
    },
    "automobile": {
        "keywords": [
            "voiture", "vehicule", "essence", "electrique",
            "permis", "entretien", "pneu", "moteur", "cote",
            "marque", "conso", "garage",
        ],
        "tools_boost": ["searxng_search", "youtube_search"],
    },
    "juridique": {
        "keywords": [
            "loi", "droit", "contrat", "avocat", "tribunal",
            "juridique", "justice", "reglement", "norme",
            "procedure", "litige", "contentieux", "amende",
        ],
        "tools_boost": ["research_search", "wikipedia_search"],
    },
    "animaux": {
        "keywords": [
            "chien", "chat", "animal", "veterinaire",
            "race", "nourriture",
            "poisson", "oiseau", "hamster", "cheval",
        ],
        "tools_boost": ["searxng_search", "youtube_search"],
    },
    "jardinage": {
        "keywords": [
            "plante", "jardin", "fleur", "arrosage", "terre",
            "potager", "taille", "semis", "recolte", "compost",
            "arbuste", "gazon", "roseraie", "serre",
        ],
        "tools_boost": ["searxng_search", "youtube_search"],
    },
    "maison": {
        "keywords": [
            "decoration", "bricolage", "renovation", "meuble", "design",
            "peinture", "carrelage", "plomberie", "electricite",
            "salle de bain", "salon", "chambre",
        ],
        "tools_boost": ["searxng_search", "youtube_search"],
    },
}

# ============================================================================
# REGEX PRE-COMPILES — detection ultra-rapide des domaines
# ============================================================================

_DOMAIN_PATTERNS: dict[str, re.Pattern] = {}
for _name, _data in DOMAIN_INDEX.items():
    _pattern = "|".join(re.escape(kw) for kw in _data["keywords"])
    _DOMAIN_PATTERNS[_name] = re.compile(r"\b(" + _pattern + r")\b", re.IGNORECASE)


# ============================================================================
# CHARGEMENT DOMAINES CUSTOM — data/custom_domains.json
# ============================================================================

def _load_custom_domains() -> dict[str, dict]:
    """Charge les domaines custom depuis data/custom_domains.json."""
    try:
        import json
        import os
        path = os.path.join(os.path.dirname(__file__), '..', 'data', 'custom_domains.json')
        if os.path.exists(path):
            with open(path) as f:
                custom = json.load(f)
            for name, data in custom.items():
                DOMAIN_INDEX[name] = data
                pattern = "|".join(re.escape(kw) for kw in data.get("keywords", []))
                _DOMAIN_PATTERNS[name] = re.compile(r"\b(" + pattern + r")\b", re.IGNORECASE)
            logger.info("Loaded %d custom domains from custom_domains.json", len(custom))
            return custom
    except Exception as e:
        logger.warning("Failed to load custom domains: %s", e)
    return {}


# Charger au démarrage
CUSTOM_DOMAINS = _load_custom_domains()

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
        "secondary": ["npm", "pip", "cargo", "install", "setup", "open source", "python", "javascript", "typescript"],
        "boost": 20,
    },
    "news_search": {
        "primary": ["actualit", "news", "breaking", "headline"],
        "secondary": ["dernier", "récent", "aujourd'hui", "hier", "sujet du jour", "flash"],
        "boost": 25,
    },
    "datasets_search": {
        "primary": ["dataset", "data", "donnees", "open data"],
        "secondary": ["csv", "json", "excel", "database", "api", "streaming", "climat", "economie"],
        "boost": 20,
    },
    "wikipedia_search": {
        "primary": ["définition", "definition", "concept", "principe", "histoire"],
        "secondary": ["biographie", "qui est", "théorie", "encyclopédie", "origine"],
        "boost": 15,
    },
    "wikipedia_en_search": {
        "primary": ["technical", "scientific", "research", "specification"],
        "secondary": ["academic", "journal", "methodology", "thesis", "algorithm"],
        "boost": 15,
    },
    "perplexity_search": {
        "primary": ["recherche", "search", "information", "récent"],
        "secondary": ["source", "article", "web", "internet", "comparatif", "comparaison", "meilleur"],
        "boost": 15,
    },
    "tavily_search": {
        "primary": ["recherche", "search", "information", "comparatif", "comparaison"],
        "secondary": ["récent", "source", "article", "meilleur", "avis", "review"],
        "boost": 10,
    },
    "brave_search": {
        "primary": ["recherche", "search", "information", "privé", "private"],
        "secondary": ["web", "internet", "rapide", "sans tracking", "sécurisé"],
        "boost": 10,
    },
    "searxng_search": {
        "primary": ["recherche", "search", "trouver", "chercher", "info"],
        "secondary": ["métamoteur", "meta search", "open source", "multi-source", "privacy"],
        "boost": 15,
    },
    "firecrawl_search": {
        "primary": ["contenu complet", "full content", "extraction", "scrape"],
        "secondary": ["page", "article", "contenu", "markdown", "documentation"],
        "boost": 10,
    },
    "just_scrape_search": {
        "primary": ["données structurées", "structured data", "extraction", "scrape", "scraping"],
        "secondary": ["graph", "intelligent", "structuré", "contenu", "page", "données"],
        "boost": 15,
    },
    "research_search": {
        "primary": ["recherche approfondie", "deep research", "analyse", "comparatif", "comparaison"],
        "secondary": ["académique", "scientifique", "encyclopédique", "étude", "étude de cas"],
        "boost": 15,
    },
    "agent_reach_web_search": {
        "primary": ["jina", "markdown extraction", "web content"],
        "secondary": ["page content", "article extraction", "contenu web"],
        "boost": 5,
    },
    "agent_reach_github_search": {
        "primary": ["github", "repo", "repository", "code", "library", "framework"],
        "secondary": ["npm", "pip", "open source", "python", "javascript", "typescript"],
        "boost": 15,
    },
    "agent_reach_rss_search": {
        "primary": ["rss", "feed", "hacker news", "actualités tech"],
        "secondary": ["flux", "articles", "blog", "tech", "numérique"],
        "boost": 10,
    },
    "exa_search": {
        "primary": ["recherche", "search", "sémantique", "semantic", "intelligent"],
        "secondary": ["web", "internet", "contenu", "articles", "documents"],
        "boost": 10,
    },
    "duckduckgo_search": {
        "primary": ["recherche", "search", "trouver", "chercher", "info"],
        "secondary": ["moteur", "privé", "gratuit", "rapide"],
        "boost": 10,
    },
    "youtube_search": {
        "primary": ["video", "youtube", "tutoriel", "tutorial", "démonstration"],
        "secondary": ["apprendre", "cours", "formation", "vidéo", "watch"],
        "boost": 20,
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
        1 for name, pat in _DOMAIN_PATTERNS.items()
        if pat.search(q)
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
    """Détecte les domaines d'une requête using pre-compiled regex (ultra-rapide)."""
    return [name for name, pat in _DOMAIN_PATTERNS.items() if pat.search(query)]


# ============================================================================
# SIGNAUX DE FRAICHEUR — pour les requêtes événementielles récentes
# ============================================================================

_FRESHNESS_SIGNALS: list[tuple[re.Pattern, str]] = [
    # Année récente + événement
    (r"\b(20\d{2})\b.*\b(coupe|championnat|élection|election|oscar|oscars|nobel|grammy|olympique|olympic|finale|gagnant|winner|vainqueur)\b", "event_year"),
    (r"\b(coupe|championnat|élection|election|oscar|oscars|nobel|grammy|olympique|olympic|finale|gagnant|winner|vainqueur)\b.*\b(20\d{2})\b", "event_year"),
    # "qui a gagné" style
    (r"\b(qui[a-z\s]*a?\s*gagn[ée]r|who won|which team won|quel est le gagnant)\b", "who_won"),
    # Dernière actualité
    (r"\b(derni[eè]re?s?\s+(nouvelle|r[ée]sultat|score|info|break|update)|latest |most recent )", "latest"),
    # Score / match
    (r"\b(score|r[és]ultat)\s+(du|de|d')\s+(match|jeu|partie)\b", "score"),
    # Breaking / aujourd'hui
    (r"\b(breaking|flash info|urgence|breaking news|live update|en direct)\b", "breaking"),
    # Qui est le/la actuel(le) / champion
    (r"\b(qui ?est ?le ?(actuel|champion|leader|roi)|who is the current)\b", "current_leader"),
]

_COMPILED_FRESHNESS: list[tuple[re.Pattern, str]] = [
    (re.compile(p), label) for p, label in _FRESHNESS_SIGNALS
]

# Sources prioritaires pour les requêtes fraîches
_FRESH_SOURCES: list[str] = [
    "duckduckgo_search",
    "searxng_search",
    "news_search",
    "agent_reach_web_search",
    "agent_reach_rss_search",
    "youtube_search",
]


def _detect_temporal_query(query: str) -> list[str]:
    """Détecte si une requête nécessite des résultats frais/temps réel.
    Retourne la liste des signaux temporels détectés."""
    q = query.lower()
    signals = []
    for pattern, label in _COMPILED_FRESHNESS:
        if pattern.search(q):
            signals.append(label)
    return signals


def _boost_fresh_sources(tools: list[str]) -> list[str]:
    """Décale les sources temps-réel en tête de liste pour les requêtes fraîches.
    Préserve l'ordre relatif des autres outils."""
    boosted = []
    inserted = False
    for tool in tools:
        if not inserted and tool in _FRESH_SOURCES:
            # Insérer les sources fraîches en premier
            for fs in _FRESH_SOURCES:
                if fs in tools and fs not in boosted:
                    boosted.append(fs)
            inserted = True
    if inserted:
        # Ajouter les outils non-fraîches dans l'ordre original
        for t in tools:
            if t not in _FRESH_SOURCES and t not in boosted:
                boosted.append(t)
        return boosted
    return tools


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


# ============================================================================
# MoE (MIXTURE OF EXPERTS) — scoring dynamique par source
# ============================================================================

# Mapping tool -> type de source (pour la diversité)
_SOURCE_TYPE_MAP: dict[str, str] = {
    "yacy_search": "web",
    "searxng_search": "web",
    "duckduckgo_search": "web",
    "perplexity_search": "web",
    "tavily_search": "web",
    "brave_search": "web",
    "firecrawl_search": "web",
    "just_scrape_search": "web",
    "agent_reach_web_search": "web",
    "querit_search": "web",
    "langsearch_search": "web",
    "brightdata_search": "web",
    "exa_search": "web",
    "research_search": "research",
    "wikipedia_search": "encyclopedie",
    "wikipedia_en_search": "encyclopedie",
    "github_search": "code",
    "agent_reach_github_search": "code",
    "news_search": "news",
    "agent_reach_rss_search": "news",
    "datasets_search": "data",
    "youtube_search": "video",
}


def _get_source_type(tool: str) -> str:
    """Retourne le type d'une source (web, research, code, news, etc.)."""
    return _SOURCE_TYPE_MAP.get(tool, "web")


def _score_source(
    query: str,
    tool: str,
    intents: list[str],
    domains: list[str],
    temporal_signals: list[str],
) -> float:
    """
    Score une source pour une requête donnée.
    Plus le score est élevé, plus la source est pertinente.
    Score < -50 = source exclue (clé API manquante ou circuit breaker).
    """
    score = 0.0
    q = query.lower()

    # 0. Base priority for general-purpose sources (0-20 points)
    _GENERAL_PRIORITY: dict[str, int] = {
        "duckduckgo_search": 50,
        "searxng_search": 40,
        "research_search": 10,
        "agent_reach_web_search": 10,
    }
    score += _GENERAL_PRIORITY.get(tool, 0)

    # 1. Keyword match (0-50 points)
    if tool in TOOL_KEYWORD_INDEX:
        idx = TOOL_KEYWORD_INDEX[tool]
        for kw in idx["primary"]:
            if kw in q:
                score += idx["boost"] * 2
        for kw in idx["secondary"]:
            if kw in q:
                score += idx["boost"]

    # 2. Intent match (0-30 points)
    for intent in intents:
        if tool in INTENT_INDEX.get(intent, {}).get("tools_boost", []):
            score += 30

    # 3. Domain match (0-20 points)
    for domain in domains:
        if tool in DOMAIN_INDEX.get(domain, {}).get("tools_boost", []):
            score += 20

    # 4. Temporal match (0-40 points)
    if temporal_signals and tool in _FRESH_SOURCES:
        score += 40

    # 5. Has valid API key (0 or -100)
    if not _has_valid_key(tool):
        score -= 100

    # 6. Circuit breaker (0 or -100)
    if circuit_breaker.is_open(tool):
        score -= 100

    # 7. Base score for free sources (0-10)
    if not _SOURCE_API_KEYS.get(tool):
        score += 10

    return score


def _select_moe_sources(
    query: str,
    intents: list[str],
    domains: list[str],
    temporal_signals: list[str],
    max_sources: int = 3,
) -> list[str]:
    """
    Sélectionne dynamiquement les N meilleures sources pour une requête.
    Approche MoE : chaque source est scorée individuellement, puis les N
    meilleures sont sélectionnées avec diversité de type.
    """
    from sources import SOURCES

    # 1. Scorer toutes les sources
    scores: dict[str, float] = {}
    for source_name in SOURCES:
        tool = f"{source_name}_search" if source_name != "datasets" else "datasets_search"
        scores[tool] = _score_source(query, tool, intents, domains, temporal_signals)

    # 2. Filtrer les sources exclues (score < -50)
    valid = {t: s for t, s in scores.items() if s > -50}

    # 3. Trier par score décroissant
    ranked = sorted(valid.items(), key=lambda x: x[1], reverse=True)

    # 4. Sélectionner avec diversité de type
    selected: list[str] = []
    types_used: set[str] = set()

    for tool, score in ranked:
        if len(selected) >= max_sources:
            break
        source_type = _get_source_type(tool)

        # Prioriser la diversité : 1er du même type OK, 2ème du même type seulement si < max
        if source_type not in types_used or len(selected) < 2:
            selected.append(tool)
            types_used.add(source_type)

    # 5. Si pas assez de sources (toutes exclues), fallback sur les sources gratuites
    if len(selected) < max_sources:
        for source_name in SOURCES:
            tool = f"{source_name}_search" if source_name != "datasets" else "datasets_search"
            if tool not in selected and _has_valid_key(tool) and not circuit_breaker.is_open(tool):
                selected.append(tool)
                if len(selected) >= max_sources:
                    break

    logger.info(
        "MoE selected %d sources: %s (scores: %s)",
        len(selected),
        selected,
        {t: scores.get(t, 0) for t in selected},
    )

    return selected


def route_query(query: str) -> dict:
    """
    Route intelligemment — MoE scoring dynamique pour chaque requête.
    Sélectionne les 3 sources les plus pertinentes via scoring.
    """
    score = _compute_complexity(query)
    intents = _detect_intent(query)
    domains = _detect_domain(query)
    specific = _detect_specific_tools(query)
    temporal_signals = _detect_temporal_query(query)

    if score < 40:
        level = 1
    elif score < 65:
        level = 2
    else:
        level = 3

    # MoE : scoring dynamique pour sélectionner les 3 meilleures sources
    max_sources = _TOP_N_BY_LEVEL.get(level, 3)
    moe_sources = _select_moe_sources(query, intents, domains, temporal_signals, max_sources)

    # Garder la liste complète pour fallback (utilisé par _select_top_sources)
    tools = list(TOOL_LEVELS[level])

    for tool in specific:
        if tool not in tools:
            tools.append(tool)

    boosted = _get_boosted_tools(intents, domains)
    for tool in boosted:
        if tool not in tools:
            tools.append(tool)

    module_boosted = _get_module_boosted_tools()
    for tool in module_boosted:
        if tool not in tools:
            tools.append(tool)

    if temporal_signals:
        for fs in _FRESH_SOURCES:
            if fs not in tools:
                tools.append(fs)
        tools = _boost_fresh_sources(tools)

    logger.info(
        "Route: score=%d, level=%d, intents=%s, domains=%s, temporal=%s, moe=%s",
        score, level, intents, domains, temporal_signals, moe_sources,
    )

    return {
        "complexity_score": score,
        "level": level,
        "tools": moe_sources,
        "all_tools": tools,
        "specific": specific,
        "intents": intents,
        "domains": domains,
        "temporal_signals": temporal_signals,
    }


_TOP_N_BY_LEVEL: dict[int, int] = {1: 4, 2: 5, 3: 6}

# Mapping source -> variable d'env requise (None = pas de cle requise)
_SOURCE_API_KEYS: dict[str, str | None] = {
    "perplexity_search": "PERPLEXITY_API_KEY",
    "brave_search": "BRAVE_API_KEY",
    "firecrawl_search": "FIRECRAWL_API_KEY",
    "just_scrape_search": "SGAI_API_KEY",
    "tavily_search": "TAVILY_API_KEY",
    "github_search": "GITHUB_TOKEN",
    "querit_search": "QUERIT_API_KEY",
    "langsearch_search": "LANGSEARCH_API_KEY",
    "brightdata_search": "BRIGHTDATA_API_KEY",
    "exa_search": "EXA_API_KEY",
    "yacy_search": "YACY_URL",
}


def _has_valid_key(source: str) -> bool:
    """Verifie si une source a une cle API valide (presente et non vide)."""
    import os
    env_var = _SOURCE_API_KEYS.get(source)
    if env_var is None:
        return True  # Pas de cle requise
    val = os.getenv(env_var, "")
    return bool(val) and val not in ("***", "your-key-here")


def _select_top_sources(tools: list[str], level: int) -> list[str]:
    """Garde les N sources les plus pertinentes selon le niveau de complexite,
    en excluant celles dont le circuit breaker est ouvert ou la cle API invalide."""
    available = [
        t for t in tools
        if not circuit_breaker.is_open(t) and _has_valid_key(t)
    ]
    if not available:
        # Fallback: ignore circuit breaker mais garde les clés valides
        available = [t for t in tools if _has_valid_key(t)][:3]
    if not available:
        # Dernier recours: sources sans clé requise depuis SOURCES
        from sources import SOURCES
        available = []
        for name, meta in SOURCES.items():
            if not meta.get("requires_key", False):
                tool_name = f"{name}_search" if name != "datasets" else "datasets_search"
                available.append(tool_name)
                if len(available) >= 3:
                    break
    n = _TOP_N_BY_LEVEL.get(level, len(available))
    result = available[:n]
    logger.info("Select sources: %d -> %d (level %d): %s", len(tools), len(result), level, result)
    return result


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
