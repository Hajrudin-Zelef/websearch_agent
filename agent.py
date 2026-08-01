"""
Agent IA ultra-rapide avec function-calling via OpenRouter.
Selection aleatoire des modeles par requete, execution parallele des outils.
L'utilisateur ne remarque rien — tout est transparent.
"""

import asyncio
import logging
import os
import json
import re
import sys
import uuid
import random
import hashlib
import time
from functools import lru_cache
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

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
)
from sources.router import route_query

load_dotenv()

logger = logging.getLogger("websearch-agent")

# ============================================================================
# CONFIG — modeles aleatoires avec timeouts agressifs
# ============================================================================

PROVIDER = os.getenv("PROVIDER", "openrouter")

PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}

# Pool de modeles — chacun tourne aleatoirement par requete
MODEL_POOL: list[dict] = [
    {"model": "meta-llama/llama-4-maverick", "timeout": 8.0, "weight": 3},
    {"model": "qwen/qwen-2.5-7b-instruct",   "timeout": 10.0, "weight": 2},
    {"model": "qwen/qwen3-8b",               "timeout": 12.0, "weight": 2},
    {"model": "deepseek/deepseek-chat-v3-0324:free", "timeout": 10.0, "weight": 1},
    {"model": "mistralai/mistral-small-3.1-24b-instruct:free", "timeout": 10.0, "weight": 1},
]

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
}

# ============================================================================
# AUTO-GENERATION
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
# CACHE LRU — resultats en memoire (TTL 5 min)
# ============================================================================

_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cache_key(query: str, tools: list[str]) -> str:
    raw = f"{query}|{'|'.join(sorted(tools))}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(query: str, tools: list[str]) -> str | None:
    key = _cache_key(query, tools)
    if key in _cache:
        ts, result = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            logger.info("Cache HIT: %.50s", query)
            return result
        del _cache[key]
    return None


def _set_cached(query: str, tools: list[str], result: str):
    key = _cache_key(query, tools)
    _cache[key] = (time.time(), result)
    # Nettoyage periodique
    if len(_cache) > 200:
        now = time.time()
        expired = [k for k, (ts, _) in _cache.items() if now - ts > _CACHE_TTL]
        for k in expired:
            del _cache[k]


# ============================================================================
# SELECTION ALEATOIRE DES MODELES
# ============================================================================

def _pick_random_models(count: int = 3) -> list[dict]:
    """Selectionne aleatoirement des modeles avec poids pour une requete."""
    pool = list(MODEL_POOL)
    selected = []
    for _ in range(min(count, len(pool))):
        weights = [m["weight"] for m in pool]
        chosen = random.choices(pool, weights=weights, k=1)[0]
        selected.append(chosen)
        pool.remove(chosen)
    return selected


# ============================================================================
# PROMPTS
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
    "Tu es un assistant de recherche. Tu as acces a dix outils :\n"
    "- perplexity_search : recherche web intelligente via Perplexity, pour des questions generales et des sources web.\n"
    "- tavily_search : recherche web via Tavily, optimisee pour les agents IA.\n"
    "- brave_search : recherche web via Brave Search, moteur prive sans tracking.\n"
    "- duckduckgo_search : recherche web via DuckDuckGo, moteur prive sans tracking, sans cle API.\n"
    "- searxng_search : recherche web via SearXNG, metar moteur open-source decentralise.\n"
    "- wikipedia_search : Wikipedia francais, pour des questions factuelles et encyclopediques.\n"
    "- wikipedia_en_search : Wikipedia anglais, pour des sujets techniques, scientifiques, ou a meilleure couverture en anglais.\n"
    "- github_search : pour trouver des repositories et du code.\n"
    "- news_search : pour les actualites recentes.\n"
    "- datasets_search : pour trouver des jeux de donnees publics (datasets statiques ou flux temps reel).\n\n"
    "REGLES IMPERATIVES :\n"
    "1. Tu DOIS appeler au moins un outil avant de repondre. "
    "Tu n'as PAS LE DROIT de repondre de memoire.\n"
    "2. Si AUCUN outil n'est pertinent, reponds EXACTEMENT : "
    "'Je ne peux pas repondre a cette question. Mes sources couvrent : Wikipedia, GitHub, actualites, datasets, et recherche web (Perplexity, Tavily, Brave, DuckDuckGo, SearXNG).'\n"
    "3. Si les resultats sont vides, dis-le honnetement.\n"
    "4. Si un outil echoue, ne reponds PAS de memoire. Dis que la source est indisponible.\n"
    "5. Synthetise en 5-8 lignes, clair, en francais, avec 2-3 sources sous forme de liens.\n\n"
    "SUJETS HORS SCOPE — refus : meteo, crypto temps reel, traductions longues, code complet, opinions, sante, droit."
)

_SYNTHESIS_PROMPT = (
    "Synthetise les resultats ci-dessus en une reponse courte (3-5 lignes) en francais, "
    "avec 1-2 sources sous forme de liens. "
    "Ne cite QUE les liens presents dans les resultats d'outils."
)

_FALLBACK_RESPONSE = (
    "Je ne peux pas repondre a cette question. "
    "Mes sources couvrent : Wikipedia, GitHub, actualites, datasets, "
    "et recherche web (Perplexity, Tavily, Brave, DuckDuckGo, SearXNG)."
)

_EMPTY_RESPONSE = (
    "Aucun resultat trouve dans mes sources pour cette question."
)

# ============================================================================
# CLIENT SINGLETON — connection pooling agressif
# ============================================================================

_clients: dict[str, OpenAI] = {}
_async_clients: dict[str, AsyncOpenAI] = {}


def _get_client(model: str) -> OpenAI:
    if model not in _clients:
        provider_cfg = PROVIDER_CONFIG[PROVIDER]
        api_key = os.getenv(provider_cfg["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Variable {provider_cfg['api_key_env']} non definie.")
        _clients[model] = OpenAI(
            base_url=provider_cfg["base_url"],
            api_key=api_key,
            timeout=30.0,
            max_retries=0,
        )
    return _clients[model]


def _get_async_client(model: str) -> AsyncOpenAI:
    if model not in _async_clients:
        provider_cfg = PROVIDER_CONFIG[PROVIDER]
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
# DSML RECOVERY
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
# TOOL EXECUTION — parallele
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
# AGENT — VERSION ULTRA-RAPIDE
# ============================================================================

def _try_model_sync(
    model_info: dict,
    messages: list[dict],
    routed_tools: list[str] | None = None,
) -> str | None:
    """Essaie un modele avec timeout agressif. Retourne la reponse ou None."""
    model = model_info["model"]
    timeout = model_info["timeout"]

    try:
        client = OpenAI(
            base_url=PROVIDER_CONFIG[PROVIDER]["base_url"],
            api_key=os.getenv(PROVIDER_CONFIG[PROVIDER]["api_key_env"]),
            timeout=timeout,
            max_retries=0,
        )

        tools_to_use = _filter_tools(routed_tools) if routed_tools else TOOLS

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_to_use,
            max_tokens=300,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            if not _handle_dsml_recovery(message):
                return _FALLBACK_RESPONSE

        messages.append(_build_tool_call_message(message))
        messages.extend(_execute_tools(message.tool_calls))
        messages.append({"role": "user", "content": _SYNTHESIS_PROMPT})

        final_response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
        )

        final_content = final_response.choices[0].message.content or ""

        if "DSML" in final_content and "invoke" in final_content:
            return _EMPTY_RESPONSE

        return final_content

    except Exception as e:
        logger.warning("Modele %s echoue (%.1fs): %s", model, timeout, e)
        return None


def run_agent(user_message: str) -> str:
    """Version synchrone — selection aleatoire + fallback rapide."""
    route = route_query(user_message)
    routed_tools = route["tools"]

    # Cache check
    cached = _get_cached(user_message, routed_tools)
    if cached:
        return cached

    logger.info(
        "Route: score=%d, niveau=%d, outils=%s",
        route["complexity_score"], route["level"], routed_tools,
    )

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Selection aleatoire des modeles pour cette requete
    models = _pick_random_models(count=3)

    for model_info in models:
        logger.info("Essai: %s (timeout: %.0fs)", model_info["model"], model_info["timeout"])
        result = _try_model_sync(model_info, list(messages), routed_tools)
        if result is not None:
            _set_cached(user_message, routed_tools, result)
            return result

    return _FALLBACK_RESPONSE


async def _try_model_async(
    model_info: dict,
    messages: list[dict],
    routed_tools: list[str] | None = None,
) -> str | None:
    """Essaie un modele en async avec timeout agressif."""
    model = model_info["model"]
    timeout = model_info["timeout"]

    try:
        client = AsyncOpenAI(
            base_url=PROVIDER_CONFIG[PROVIDER]["base_url"],
            api_key=os.getenv(PROVIDER_CONFIG[PROVIDER]["api_key_env"]),
            timeout=timeout,
            max_retries=0,
        )

        tools_to_use = _filter_tools(routed_tools) if routed_tools else TOOLS

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_to_use,
            max_tokens=300,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            if not _handle_dsml_recovery(message):
                return _FALLBACK_RESPONSE

        messages.append(_build_tool_call_message(message))

        # Execution parallele des outils
        tool_messages = await asyncio.gather(*[
            asyncio.to_thread(_execute_single_tool, tc)
            for tc in message.tool_calls
        ])
        messages.extend(tool_messages)

        messages.append({"role": "user", "content": _SYNTHESIS_PROMPT})

        final_response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
        )

        final_content = final_response.choices[0].message.content or ""

        if "DSML" in final_content and "invoke" in final_content:
            return _EMPTY_RESPONSE

        return final_content

    except Exception as e:
        logger.warning("Modele %s echoue (%.1fs): %s", model, timeout, e)
        return None


async def run_agent_async(user_message: str) -> str:
    """Version async — selection aleatoire + fallback rapide + outils paralleles."""
    route = route_query(user_message)
    routed_tools = route["tools"]

    # Cache check
    cached = _get_cached(user_message, routed_tools)
    if cached:
        return cached

    logger.info(
        "Route: score=%d, niveau=%d, outils=%s",
        route["complexity_score"], route["level"], routed_tools,
    )

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Selection aleatoire des modeles
    models = _pick_random_models(count=3)

    # Race condition — le premier qui repond gagne
    for model_info in models:
        try:
            result = await asyncio.wait_for(
                _try_model_async(model_info, list(messages), routed_tools),
                timeout=model_info["timeout"] + 2,
            )
            if result is not None:
                _set_cached(user_message, routed_tools, result)
                return result
        except asyncio.TimeoutError:
            logger.warning("Timeout: %s", model_info["model"])
            continue

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
