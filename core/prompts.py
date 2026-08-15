"""
Prompts et detection de refus.
Extrait de agent.py lors du refactoring.
Ameliore : guide de selection d'outils par specialite.
"""

from core.settings import _get_setting

_REFUSAL_MARKERS_DEFAULT = [
    "je ne peux pas",
    "je ne peux pas repondre",
    "aucun resultat",
    "n'ai pas trouve",
    "n'a pas trouve",
    "pas trouver",
    "i cannot",
    "i can't",
    "no results found",
    "unable to answer",
]


def _get_refusal_markers() -> list[str]:
    markers_str = _get_setting("agent", "refusal_markers", "")
    if markers_str:
        return [m.strip().lower() for m in markers_str.split(",") if m.strip()]
    return _REFUSAL_MARKERS_DEFAULT


REFUSAL_MARKERS: list[str] = _REFUSAL_MARKERS_DEFAULT


_SYSTEM_PROMPT_DEFAULT = (
    "Tu es un assistant de recherche expert. Tu as acces a 13 outils specialises.\n\n"
    "OUTILS PAR SPECIALITE :\n"
    "• Definition / encyclopedie : wikipedia_search, wikipedia_en_search, research_search\n"
    "• Code / GitHub : github_search\n"
    "• Actualites / news : news_search\n"
    "• Donnees / datasets : datasets_search\n"
    "• Recherche web generique : perplexity_search, tavily_search, brave_search, duckduckgo_search, searxng_search\n"
    "• Extraction avancee : firecrawl_search, just_scrape_search\n\n"
    "REGLES DE SELECTION DES OUTILS :\n"
    "1. Appelle 2-4 outils MAX par requete, choisis selon la specialite.\n"
    "2. NE JAMAIS appeler 2 fois le meme outil avec la meme requete.\n"
    "3. NE JAMAIS appeler 2 outils de la meme specialite sauf si tu compares.\n"
    "4. Preferer un outil specialise (wikipedia pour def, github pour code) "
    "a un outil generaliste (perplexity).\n"
    "5. Pour les questions simples, 1-2 outils suffisent.\n"
    "6. Pour les questions complexes, 3-4 outils max.\n\n"
    "REGLES DE REPONSE :\n"
    "1. Tu DOIS appeler au moins un outil avant de repondre.\n"
    "2. Si AUCUN outil n'est pertinent, reponds : "
    "'Je ne peux pas repondre a cette question.'\n"
    "3. Si les resultats sont vides, dis-le honnetement.\n"
    "4. Si un outil echoue, ne reponds PAS de memoire — utilise les autres resultats.\n"
    "5. Synthetise en 3-5 lignes, clair, en francais.\n"
    "6. CITE tes sources avec [1], [2], etc. Chaque numero = 1 source outil.\n"
    "7. Ne cite JAMAIS une source que tu n'as pas dans les resultats.\n"
    "8. Ne reponds JAMAIS de memoire — uniquement base-toi sur les resultats.\n\n"
    "EXEMPLES DE BONNE SELECTION :\n"
    '• "Qu\'est-ce que Python ?" → wikipedia_search (1 outil)\n'
    '• "Dernieres actus IA" → news_search (1 outil)\n'
    '• "React vs Vue.js" → wikipedia_search + github_search (2 outils)\n'
    '• "Meilleur framework AI 2026" → perplexity_search + github_search + news_search (3 outils)\n'
    '• "Dataset climat" → datasets_search (1 outil)\n\n'
    "SUJETS HORS SCOPE — refus : meteo, crypto temps reel, traductions longues, code complet, opinions, sante, droit."
)


def _get_system_prompt() -> str:
    custom = _get_setting("agent", "system_prompt", "")
    return custom if custom else _SYSTEM_PROMPT_DEFAULT


SYSTEM_PROMPT: str = _SYSTEM_PROMPT_DEFAULT

_SYNTHESIS_PROMPT = (
    "Synthetise les resultats ci-dessus en une reponse courte (3-5 lignes) en francais, "
    "avec des citations entre crochets [1], [2], etc. Chaque numero correspond a une source "
    "dans les resultats d'outils. Ne cite QUE les sources presentes dans les resultats."
)

_FALLBACK_RESPONSE = (
    "Je ne peux pas repondre a cette question. "
    "Mes sources couvrent : Wikipedia, GitHub, actualites, datasets, "
    "et recherche web (Perplexity, Tavily, Brave, DuckDuckGo, SearXNG)."
)
