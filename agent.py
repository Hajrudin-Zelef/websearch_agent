"""
Agent IA avec function-calling — DeepSeek ou OpenRouter.
Déclare 3 tools (wikipedia_search, github_search, news_search) et
laisse le modèle décider lequel appeler selon la question.
"""

import os
import json
import sys
from dotenv import load_dotenv
from openai import OpenAI

from sources.wikipedia import wikipedia_search
from sources.wikipedia_en import wikipedia_en_search
from sources.github import github_search
from sources.news_rss import news_search
from sources.datasets import datasets_search

load_dotenv()

PROVIDER = os.getenv("PROVIDER", "deepseek")

PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}

# --- Tool definitions (OpenAI function-calling format) ---

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "wikipedia_search",
            "description": (
                "Recherche sur Wikipedia (encyclopédie). "
                "À utiliser pour des questions factuelles, définitions, "
                "biographies, événements historiques, concepts scientifiques."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La requête de recherche (mots-clés en français de préférence).",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wikipedia_en_search",
            "description": (
                "Search English Wikipedia (encyclopedia). "
                "Use for factual questions, definitions, biographies, "
                "historical events, scientific concepts — especially "
                "when the topic is technical/specialized or likely to "
                "have better coverage in English than French."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords, preferably in English).",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_search",
            "description": (
                "Recherche des repositories GitHub. "
                "À utiliser pour trouver du code, des bibliothèques, "
                "des frameworks, des outils open-source."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La requête de recherche (mots-clés en anglais de préférence).",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_search",
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
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Mots-clés pour filtrer les articles. "
                            "Laisser vide pour avoir les derniers articles sans filtre."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "datasets_search",
            "description": (
                "Recherche des jeux de donnees publics (datasets) parmi ~1000 references. "
                "Couvre les datasets statiques (fichiers CSV, bases de donnees) "
                "en climat, sante, economie, biologie, NLP, computer vision, transport... "
                "ET les flux temps reel (WebSocket, API streaming) "
                "en finance/crypto, meteo,transport, cybersecurite, IoT. "
                "A utiliser pour trouver des sources de donnees sur un sujet donne."
            ),
            "parameters": {
                "type": "object",
                "properties": {
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
            },
        },
    },
]

# --- Dispatch functions ---

TOOL_FUNCTIONS: dict[str, callable] = {
    "wikipedia_search": lambda **kwargs: wikipedia_search(
        query=kwargs.get("query", ""), max_results=kwargs.get("max_results", 5)
    ),
    "wikipedia_en_search": lambda **kwargs: wikipedia_en_search(
        query=kwargs.get("query", ""), max_results=kwargs.get("max_results", 5)
    ),
    "github_search": lambda **kwargs: github_search(
        query=kwargs.get("query", ""), max_results=kwargs.get("max_results", 5)
    ),
    "news_search": lambda **kwargs: news_search(
        query=kwargs.get("query", ""),
        max_results_per_feed=kwargs.get("max_results_per_feed", 2),
    ),
    "datasets_search": lambda **kwargs: datasets_search(
        query=kwargs.get("query", ""), max_results=kwargs.get("max_results", 10)
    ),
}

# Marqueurs de refus — utilisés par server.py pour tagger les réponses
REFUSAL_MARKERS: list[str] = [
    "Je ne peux pas répondre",
    "Je ne peux pas repondre",
    "Aucun résultat trouvé",
    "Aucun resultat trouvé",
    "pas trouver",
    "n'ai pas trouvé",
]

# System prompt
SYSTEM_PROMPT: str = (
    "Tu es un assistant de recherche. Tu as acces a cinq outils :\n"
    "- wikipedia_search : Wikipedia francais, pour des questions factuelles et encyclopediques.\n"
    "- wikipedia_en_search : Wikipedia anglais, pour des sujets techniques, scientifiques, ou a meilleure couverture en anglais.\n"
    "- github_search : pour trouver des repositories et du code.\n"
    "- news_search : pour les actualites recentes.\n"
    "- datasets_search : pour trouver des jeux de donnees publics (datasets statiques ou flux temps reel).\n\n"
    "REGLES IMPERATIVES :\n"
    "1. Tu DOIS appeler au moins un outil avant de repondre. "
    "Tu n'as PAS LE DROIT de repondre de memoire, de tes connaissances internes, "
    "ou d'inventer une reponse sans etre passe par un outil.\n"
    "2. Si AUCUN de tes cinq outils n'est pertinent pour la question, "
    "reponds EXACTEMENT : "
    "'Je ne peux pas repondre a cette question. Mes sources couvrent : Wikipedia (faits, encyclopedie), GitHub (code, repositories), actualites recentes (112 flux RSS), et datasets publics. Reformule ta question pour qu'elle corresponde a l'une de ces sources.'\n"
    "3. Si les outils retournent des resultats vides, dis-le honnetement : "
    "'Aucun resultat trouve dans mes sources pour cette question.'\n"
    "4. Si un outil retourne une erreur technique, ne reponds PAS de memoire. "
    "Dis : 'La source X est momentanement indisponible, reessaie dans quelques instants.'\n"
    "5. Si les outils trouvent des resultats, synthetise-les en une reponse COURTE "
    "(5-8 lignes max), claire, en francais, avec 2-3 sources max sous forme de liens."
)


def run_agent(user_message: str) -> str:
    """Exécute l'agent avec function-calling et retourne la réponse finale."""

    provider_cfg = PROVIDER_CONFIG.get(PROVIDER)
    if not provider_cfg:
        return f"Erreur : provider '{PROVIDER}' inconnu. Utilise 'deepseek' ou 'openrouter'."

    api_key = os.getenv(provider_cfg["api_key_env"])
    if not api_key:
        return (
            f"Erreur : variable d'environnement {provider_cfg['api_key_env']} "
            f"non définie. Vérifie ton fichier .env."
        )

    client = OpenAI(base_url=provider_cfg["base_url"], api_key=api_key)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Premier appel : le modèle décide si/quels tools appeler
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=TOOLS,
    )

    message = response.choices[0].message

    # Si pas de tool_calls, le modèle a ignoré les règles → refuser
    if not message.tool_calls:
        return (
            "Je ne peux pas repondre a cette question. "
            "Mes sources couvrent : Wikipedia (faits, encyclopedie), "
            "GitHub (code, repositories), actualites recentes (112 flux RSS), "
            "et datasets publics. "
            "Reformule ta question pour qu'elle corresponde a l'une de ces sources."
        )

    # Ajouter la réponse du modèle aux messages
    # Conversion en dict compatible selon version du SDK
    if hasattr(message, "model_dump"):
        messages.append(message.model_dump(exclude_none=True))
    elif isinstance(message, dict):
        messages.append(message)
    else:
        # Fallback manuel
        msg_dict = {"role": message.role}
        if message.content:
            msg_dict["content"] = message.content
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        messages.append(msg_dict)

    # Exécuter chaque tool call
    for tc in message.tool_calls:
        func_name = tc.function.name
        func = TOOL_FUNCTIONS.get(func_name)
        if func is None:
            tool_result = json.dumps({"error": f"Fonction inconnue: {func_name}"})
        else:
            try:
                args = json.loads(tc.function.arguments)
                result = func(**args)
                tool_result = json.dumps(result, ensure_ascii=False)
            except Exception as e:
                tool_result = json.dumps({"error": str(e)})

        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": tool_result,
        })

    # Deuxième appel : le modèle synthétise les résultats
    # Instruction renforcée après les tool results
    messages.append({
        "role": "system",
        "content": (
            "IMPERATIF : Synthetise UNIQUEMENT a partir des resultats d'outils ci-dessus. "
            "Si les resultats sont vides ou contiennent une erreur, reponds EXACTEMENT : "
            "'Aucun resultat trouve dans mes sources pour cette question.' "
            "N'invente JAMAIS de reponse. "
            "N'utilise PAS tes connaissances internes. "
            "Ne cite que des liens obtenus via les outils."
        ),
    })
    final_response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
    )

    return final_response.choices[0].message.content or ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>")
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    print(f"🤖 Question : {question}\n")
    answer = run_agent(question)
    print(answer)
