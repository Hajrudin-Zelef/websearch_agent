"""
Agent IA avec function-calling via OpenRouter (qwen/qwen3-coder-next).
Expose 5 tools et laisse le modele decider lequel appeler.

Architecture registry :
- Chaque outil est defini UNE SEULE FOIS dans TOOLS_REGISTRY
- TOOLS (format OpenAI) et TOOL_FUNCTIONS (dispatch) sont auto-generes
- Ajouter un outil = ajouter 1 entree dans TOOLS_REGISTRY
"""

import asyncio
import logging
import os
import json
import re
import sys
import uuid
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

from sources import (
    wikipedia_search,
    wikipedia_en_search,
    github_search,
    news_search,
    datasets_search,
)

load_dotenv()

logger = logging.getLogger("websearch-agent")

# ============================================================================
# CONFIG
# ============================================================================

PROVIDER = os.getenv("PROVIDER", "openrouter")

PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}

AGENT_MODEL = "meta-llama/llama-4-maverick"

# --- Fallback chain : chaque modele avec son timeout ---
# Si le premier echoue (timeout, erreur), on passe au suivant
MODEL_CHAIN: list[dict] = [
    {"model": "meta-llama/llama-4-maverick", "timeout": 15.0},
    {"model": "qwen/qwen-2.5-7b-instruct",   "timeout": 25.0},
    {"model": "qwen/qwen3-8b",               "timeout": 30.0},
]

# ============================================================================
# TOOLS REGISTRY — source unique de verite
# Pour ajouter un outil, il suffit d'ajouter une entree ici.
# ============================================================================

TOOLS_REGISTRY: dict[str, dict] = {
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
}

# ============================================================================
# AUTO-GENERATION — ne pas modifier manuellement
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
    """Cree une fonction dispatch qui applique les defaults."""
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

# ============================================================================
# PROMPTS & CONSTANTS
# ============================================================================

REFUSAL_MARKERS: list[str] = [
    "je ne peux pas",
    "je ne peux pas repondre",
    "aucun resultat",
    "n'ai pas trouve",
    "n'a pas trouve",
    "pas trouver",
]

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
    "(5-8 lignes max), claire, en francais, avec 2-3 sources max sous forme de liens.\n\n"
    "SUJETS HORS SCOPE — tu DOIS refuser et repondre exactement la regle 2 :\n"
    "- Meteo, previsions, temperatures, conditions climatiques en temps reel\n"
    "- Cours boursiers, taux de change, crypto en temps reel\n"
    "- Traductions de textes longs\n"
    "- Generation de code complet / programmes\n"
    "- Conversations generales, conseil personnel, opinions\n"
    "- Calculs mathematiques complexes\n"
    "- Sante, diagnostics medicaux\n"
    "- Droit, conseils juridiques"
)

_FALLBACK_RESPONSE = (
    "Je ne peux pas repondre a cette question. "
    "Mes sources couvrent : Wikipedia (faits, encyclopedie), "
    "GitHub (code, repositories), actualites recentes (112 flux RSS), "
    "et datasets publics. "
    "Reformule ta question pour qu'elle corresponde a l'une de ces sources."
)

_EMPTY_RESPONSE = (
    "Aucun resultat trouve dans mes sources pour cette question. "
    "Mes sources couvrent : Wikipedia (faits, encyclopedie), "
    "GitHub (code, repositories), actualites recentes (112 flux RSS), "
    "et datasets publics."
)

# ============================================================================
# CLIENT SINGLETON
# ============================================================================

_clients: dict[str, OpenAI] = {}
_async_clients: dict[str, AsyncOpenAI] = {}


def _get_client(model: str | None = None) -> OpenAI:
    model = model or AGENT_MODEL
    if model not in _clients:
        provider_cfg = PROVIDER_CONFIG.get(PROVIDER)
        if not provider_cfg:
            raise RuntimeError(f"Provider '{PROVIDER}' inconnu.")
        api_key = os.getenv(provider_cfg["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Variable {provider_cfg['api_key_env']} non definie.")
        _clients[model] = OpenAI(
            base_url=provider_cfg["base_url"],
            api_key=api_key,
            timeout=30.0,
            max_retries=0,  # on gere nous-memes les retries via MODEL_CHAIN
        )
    return _clients[model]


def _get_async_client(model: str | None = None) -> AsyncOpenAI:
    model = model or AGENT_MODEL
    if model not in _async_clients:
        provider_cfg = PROVIDER_CONFIG.get(PROVIDER)
        if not provider_cfg:
            raise RuntimeError(f"Provider '{PROVIDER}' inconnu.")
        api_key = os.getenv(provider_cfg["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Variable {provider_cfg['api_key_env']} non definie.")
        _async_clients[model] = AsyncOpenAI(
            base_url=provider_cfg["base_url"],
            api_key=api_key,
            timeout=30.0,
            max_retries=0,
        )
    return _async_clients[model]


# ============================================================================
# DSML RECOVERY (bug DeepSeek connu)
# ============================================================================

def _parse_dsml_tool_calls(text: str) -> list[dict]:
    if not text or "DSML" not in text:
        return []

    tool_calls: list[dict] = []

    invoke_pattern = re.compile(
        r"<.DSML..>invoke\s+name=\"(\w+)\">(.*?)</.DSML..>invoke>",
        re.DOTALL,
    )
    param_pattern = re.compile(
        r"<.DSML..>parameter\s+name=\"(\w+)\"[^>]*>(.*?)</.DSML..>parameter>",
        re.DOTALL,
    )

    for invoke_match in invoke_pattern.finditer(text):
        func_name = invoke_match.group(1)
        params_block = invoke_match.group(2)

        arguments: dict[str, str] = {}
        for param_match in param_pattern.finditer(params_block):
            param_name = param_match.group(1)
            param_value = param_match.group(2).strip()
            arguments[param_name] = param_value

        tool_calls.append({
            "id": f"dsml_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": func_name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        })

    return tool_calls


# ============================================================================
# TOOL EXECUTION
# ============================================================================

def _build_tool_call_message(message) -> dict:
    msg_dict: dict = {"role": message.role}
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
    return msg_dict


def _execute_single_tool(tc) -> dict:
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

    return {
        "role": "tool",
        "tool_call_id": tc.id,
        "content": tool_result,
    }


def _execute_tools(tool_calls) -> list[dict]:
    return [_execute_single_tool(tc) for tc in tool_calls]


def _handle_dsml_recovery(message) -> bool:
    """Tente le recovery DSML. Retourne True si des tool calls ont ete injectes."""
    if message.tool_calls:
        return False

    dsml_calls = _parse_dsml_tool_calls(message.content or "")
    if not dsml_calls:
        return False

    message.tool_calls = [
        type("ToolCall", (), {
            "id": tc["id"],
            "type": tc["type"],
            "function": type("Function", (), {
                "name": tc["function"]["name"],
                "arguments": tc["function"]["arguments"],
            }),
        })
        for tc in dsml_calls
    ]
    return True


# ============================================================================
# AGENT SYNC & ASYNC
# ============================================================================

_SYNTHESIS_PROMPT = (
    "Synthetise les resultats ci-dessus en une reponse courte (5-8 lignes) en francais, "
    "avec 2-3 sources sous forme de liens. "
    "Si les resultats sont vraiment vides, dis 'Aucun resultat trouve dans mes sources.' "
    "Ne cite QUE les liens presents dans les resultats d'outils."
)


def _try_model_sync(client: OpenAI, model: str, messages: list[dict]) -> str | None:
    """Essaie un modele. Retourne la reponse ou None si echec."""
    try:
        client_with_timeout = OpenAI(
            base_url=client.base_url,
            api_key=client.api_key,
            timeout=_get_model_timeout(model),
            max_retries=0,
        )

        response = client_with_timeout.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            max_tokens=300,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            if not _handle_dsml_recovery(message):
                return _FALLBACK_RESPONSE

        messages.append(_build_tool_call_message(message))
        messages.extend(_execute_tools(message.tool_calls))

        messages.append({"role": "user", "content": _SYNTHESIS_PROMPT})

        final_response = client_with_timeout.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
        )

        final_content = final_response.choices[0].message.content or ""

        if "DSML" in final_content and "invoke" in final_content:
            return _EMPTY_RESPONSE

        return final_content

    except Exception as e:
        logger.warning("Modele %s echoue: %s: %s", model, type(e).__name__, e)
        return None


def _get_model_timeout(model: str) -> float:
    """Retourne le timeout Configure pour un modele."""
    for entry in MODEL_CHAIN:
        if entry["model"] == model:
            return entry["timeout"]
    return 15.0


def run_agent(user_message: str) -> str:
    """Version synchrone — fallback chain sur les modeles."""
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for entry in MODEL_CHAIN:
        model = entry["model"]
        logger.info("Essai modele: %s (timeout: %ds)", model, entry["timeout"])

        client = _get_client(model)
        result = _try_model_sync(client, model, list(messages))
        if result is not None:
            logger.info("Reussi avec: %s", model)
            return result
        logger.warning("Echec: %s — passage au suivant", model)

    return _FALLBACK_RESPONSE


async def _try_model_async(client: AsyncOpenAI, model: str, messages: list[dict]) -> str | None:
    """Essaie un modele en async. Retourne la reponse ou None si echec."""
    try:
        client_with_timeout = AsyncOpenAI(
            base_url=client.base_url,
            api_key=client.api_key,
            timeout=_get_model_timeout(model),
            max_retries=0,
        )

        response = await client_with_timeout.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            max_tokens=300,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            if not _handle_dsml_recovery(message):
                return _FALLBACK_RESPONSE

        messages.append(_build_tool_call_message(message))

        tool_messages = await asyncio.gather(*[
            asyncio.to_thread(_execute_single_tool, tc)
            for tc in message.tool_calls
        ])
        messages.extend(tool_messages)

        messages.append({"role": "user", "content": _SYNTHESIS_PROMPT})

        final_response = await client_with_timeout.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
        )

        final_content = final_response.choices[0].message.content or ""

        if "DSML" in final_content and "invoke" in final_content:
            return _EMPTY_RESPONSE

        return final_content

    except Exception as e:
        logger.warning("Modele %s echoue: %s: %s", model, type(e).__name__, e)
        return None


async def run_agent_async(user_message: str) -> str:
    """Version async — fallback chain sur les modeles."""
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for entry in MODEL_CHAIN:
        model = entry["model"]
        logger.info("Essai modele: %s (timeout: %ds)", model, entry["timeout"])

        client = _get_async_client(model)
        result = await _try_model_async(client, model, list(messages))
        if result is not None:
            logger.info("Reussi avec: %s", model)
            return result
        logger.warning("Echec: %s — passage au suivant", model)

    return _FALLBACK_RESPONSE


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>")
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    print(f"Question : {question}\n")
    answer = run_agent(question)
    print(answer)
