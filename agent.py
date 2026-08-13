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
import threading
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
    firecrawl_search,
    just_scrape_search,
    research_search,
)
from sources.router import route_query
from sources.content_extractor import extract_content_from_results
from threads import get_thread_context

load_dotenv()

logger = logging.getLogger("websearch-agent")

# ============================================================================
# SETTINGS RUNTIME — lit settings.json a chaque appel
# ============================================================================

_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
_settings_cache: dict = {}
_settings_mtime: float = 0


def _load_settings() -> dict:
    """Charge les settings depuis settings.json (avec cache)."""
    global _settings_cache, _settings_mtime
    try:
        mtime = os.path.getmtime(_SETTINGS_FILE)
        if mtime != _settings_mtime:
            with open(_SETTINGS_FILE) as f:
                _settings_cache = json.load(f)
            _settings_mtime = mtime
    except (FileNotFoundError, json.JSONDecodeError):
        _settings_cache = {}
    return _settings_cache


def _get_setting(section: str, key: str, default=None):
    """Lit un parametre depuis settings.json."""
    settings = _load_settings()
    return settings.get(section, {}).get(key, default)


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

_FAST_PATH_TOOL_TIMEOUT = 5.0
_SYNTHESIS_TIMEOUT = 6.0

# Pool de modeles — chacun tourne aleatoirement par requete
MODEL_POOL: list[dict] = [
    {"model": "meta-llama/llama-4-maverick", "timeout": 6.0, "weight": 4},
    {"model": "qwen/qwen-2.5-7b-instruct",   "timeout": 6.0, "weight": 3},
    {"model": "qwen/qwen3-8b",               "timeout": 8.0, "weight": 2},
    {"model": "deepseek/deepseek-chat-v3-0324:free", "timeout": 6.0, "weight": 1},
    {"model": "mistralai/mistral-small-3.1-24b-instruct:free", "timeout": 6.0, "weight": 1},
]


def _get_tool_timeout() -> float:
    return _get_setting("models", "tool_timeout", _FAST_PATH_TOOL_TIMEOUT)


def _get_synthesis_timeout() -> float:
    return _get_setting("models", "synthesis_timeout", _SYNTHESIS_TIMEOUT)


def _get_max_tokens_tool() -> int:
    return _get_setting("models", "max_tokens_tool_selection", 300)


def _get_max_tokens_synthesis() -> int:
    return _get_setting("models", "max_tokens_synthesis", 500)

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
    "just_scrape_search": {
        "func": just_scrape_search,
        "description": (
            "Recherche web via ScrapeGraph AI, intelligente et structuree. "
            "Extrait les informations ciblees des pages trouvees. "
            "A utiliser pour des recherches necessitant des donnees structurees."
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
# CACHE LRU — resultats en memoire (TTL 5 min, max 200 entrees)
# ============================================================================

_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 300  # 5 minutes
_CACHE_MAX_SIZE = 200
_cache_lock = threading.Lock()


def _get_cache_ttl() -> int:
    return _get_setting("cache", "ttl", _CACHE_TTL)


def _get_cache_max_size() -> int:
    return _get_setting("cache", "max_size", _CACHE_MAX_SIZE)


def _cache_key(query: str, tools: list[str]) -> str:
    raw = f"{query}|{'|'.join(sorted(tools))}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(query: str, tools: list[str]) -> str | None:
    key = _cache_key(query, tools)
    with _cache_lock:
        if key in _cache:
            ts, result = _cache[key]
            if time.time() - ts < _get_cache_ttl():
                logger.info("Cache HIT: %.50s", query)
                return result
            del _cache[key]
    return None


def _set_cached(query: str, tools: list[str], result: str):
    key = _cache_key(query, tools)
    with _cache_lock:
        _cache[key] = (time.time(), result)
        # Nettoyage : eviction des expirees + LRU si limite atteinte
        now = time.time()
        expired = [k for k, (ts, _) in _cache.items() if now - ts > _get_cache_ttl()]
        for k in expired:
            del _cache[k]
        # Si toujours au-dessus de la limite, eviction des plus anciennes
        if len(_cache) > _get_cache_max_size():
            sorted_entries = sorted(_cache.items(), key=lambda x: x[1][0])
            excess = len(_cache) - _get_cache_max_size()
            for k, _ in sorted_entries[:excess]:
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

_REFUSAL_MARKERS_DEFAULT = [
    "je ne peux pas",
    "je ne peux pas repondre",
    "aucun resultat",
    "n'ai pas trouve",
    "n'a pas trouve",
    "pas trouver",
]


def _get_refusal_markers() -> list[str]:
    markers_str = _get_setting("agent", "refusal_markers", "")
    if markers_str:
        return [m.strip().lower() for m in markers_str.split(",") if m.strip()]
    return _REFUSAL_MARKERS_DEFAULT


REFUSAL_MARKERS: list[str] = _REFUSAL_MARKERS_DEFAULT

_SYSTEM_PROMPT_DEFAULT = (
    "Tu es un assistant de recherche. Tu as acces a treize outils :\n"
    "- perplexity_search : recherche web intelligente via Perplexity\n"
    "- tavily_search : recherche web via Tavily\n"
    "- brave_search : recherche web via Brave Search\n"
    "- duckduckgo_search : recherche web via DuckDuckGo\n"
    "- searxng_search : recherche web via SearXNG\n"
    "- firecrawl_search : recherche web avancee avec extraction de contenu complet\n"
    "- just_scrape_search : recherche web intelligente ScrapeGraph AI\n"
    "- research_search : recherche approfondie Wikipedia FR/EN\n"
    "- wikipedia_search : Wikipedia francais\n"
    "- wikipedia_en_search : Wikipedia anglais\n"
    "- github_search : repositories et code\n"
    "- news_search : actualites (112 flux RSS)\n"
    "- datasets_search : jeux de donnees publics\n\n"
    "REGLES IMPERATIVES :\n"
    "1. Tu DOIS appeler au moins un outil avant de repondre.\n"
    "2. Si AUCUN outil n'est pertinent, reponds : "
    "'Je ne peux pas repondre a cette question.'\n"
    "3. Si les resultats sont vides, dis-le honnetement.\n"
    "4. Si un outil echoue, ne reponds PAS de memoire.\n"
    "5. Synthetise en 3-5 lignes, clair, en francais, avec 1-2 sources.\n"
    "6. CITE tes sources avec des numeros entre crochets [1], [2], etc. "
    "Chaque numero correspond a une source dans les resultats d'outils.\n"
    "7. Ne cite JAMAIS une source que tu n'as pas dans les resultats.\n\n"
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

_ALL_MODELS_FAILED = (
    "Mes sources sont temporairement indisponibles. "
    "Reessaie dans un instant."
)

_EMPTY_RESPONSE = (
    "Aucun resultat trouve dans mes sources pour cette question."
)

# ============================================================================
# CLIENT SINGLETON — connection pooling agressif
# ============================================================================

_clients: dict[str, OpenAI] = {}
_async_clients: dict[str, AsyncOpenAI] = {}


def _get_client(model: str, timeout: float = 30.0) -> OpenAI:
    if model not in _clients:
        provider_cfg = PROVIDER_CONFIG[PROVIDER]
        api_key = os.getenv(provider_cfg["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Variable {provider_cfg['api_key_env']} non definie.")
        _clients[model] = OpenAI(
            base_url=provider_cfg["base_url"],
            api_key=api_key,
            timeout=timeout,
            max_retries=0,
        )
    return _clients[model]


def _get_async_client(model: str, timeout: float = 30.0) -> AsyncOpenAI:
    if model not in _async_clients:
        provider_cfg = PROVIDER_CONFIG[PROVIDER]
        api_key = os.getenv(provider_cfg["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Variable {provider_cfg['api_key_env']} non definie.")
        _async_clients[model] = AsyncOpenAI(
            base_url=provider_cfg["base_url"],
            api_key=api_key,
            timeout=timeout,
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
# JSON RECOVERY — capte les tool-calls emis en JSON brut
# ============================================================================

def _parse_json_tool_calls(text: str) -> list[dict]:
    """Detecte les tool-calls emis en JSON brut par un modele
    qui ne supporte pas le function-calling natif.

    Ex: {"name": "perplexity_search", "arguments": {"query": "taux euro FCFA"}}
    """
    if not text:
        return []

    tool_calls: list[dict] = []
    decoder = json.JSONDecoder()
    known_tools = set(TOOLS_REGISTRY.keys())

    idx = 0
    while idx < len(text):
        brace_idx = text.find("{", idx)
        if brace_idx == -1:
            break

        try:
            obj, end = decoder.raw_decode(text[brace_idx:])
        except json.JSONDecodeError:
            idx = brace_idx + 1
            continue

        if (
            isinstance(obj, dict)
            and "name" in obj
            and "arguments" in obj
            and obj["name"] in known_tools
        ):
            func_name = obj["name"]
            args = obj["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"query": args}
            if not isinstance(args, dict):
                args = {"query": str(args)}

            tool_calls.append({
                "id": f"json_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": func_name,
                    "arguments": json.dumps(args, ensure_ascii=False),
                },
            })

        idx = brace_idx + end

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


def _handle_json_recovery(message) -> bool:
    """Recovery pour les tool-calls emis en JSON brut (sans <DSML>)."""
    if message.tool_calls:
        return False

    json_calls = _parse_json_tool_calls(message.content or "")
    if not json_calls:
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
        for tc in json_calls
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
        client = _get_client(model, timeout=timeout)

        tools_to_use = _filter_tools(routed_tools) if routed_tools else TOOLS

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_to_use,
            max_tokens=_get_max_tokens_tool(),
        )

        message = response.choices[0].message

        if not message.tool_calls:
            if not _handle_dsml_recovery(message):
                if not _handle_json_recovery(message):
                    if message.content and "DSML" not in message.content:
                        return message.content
                    return _FALLBACK_RESPONSE

        messages.append(_build_tool_call_message(message))
        messages.extend(_execute_tools(message.tool_calls))
        messages.append({"role": "user", "content": _SYNTHESIS_PROMPT})

        final_response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=_get_max_tokens_synthesis(),
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
        {"role": "system", "content": _get_system_prompt()},
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

    return _ALL_MODELS_FAILED


async def _try_model_async(
    model_info: dict,
    messages: list[dict],
    routed_tools: list[str] | None = None,
) -> str | None:
    """Essaie un modele en async avec timeout agressif."""
    model = model_info["model"]
    timeout = model_info["timeout"]

    try:
        client = _get_async_client(model, timeout=timeout)

        tools_to_use = _filter_tools(routed_tools) if routed_tools else TOOLS

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_to_use,
            max_tokens=_get_max_tokens_tool(),
        )

        message = response.choices[0].message

        if not message.tool_calls:
            if not _handle_dsml_recovery(message):
                if not _handle_json_recovery(message):
                    if message.content and "DSML" not in message.content:
                        return message.content
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
            max_tokens=_get_max_tokens_synthesis(),
        )

        final_content = final_response.choices[0].message.content or ""

        if "DSML" in final_content and "invoke" in final_content:
            return _EMPTY_RESPONSE

        return final_content

    except Exception as e:
        logger.warning("Modele %s echoue (%.1fs): %s", model, timeout, e)
        return None


async def run_agent_async(user_message: str, thread_id: str | None = None) -> dict:
    """Version async — fast path (1 appel LLM) + fallback agent complet (2 appels).
    Retourne un dict avec 'response' et 'metadata'."""
    route = route_query(user_message)
    routed_tools = route["tools"]

    metadata = {
        "query": user_message[:200],
        "complexity_score": route["complexity_score"],
        "level": route["level"],
        "tools_routed": routed_tools,
        "tools_used": [],
        "path": None,
        "models_used": [],
        "response_time_ms": 0,
        "cached": False,
    }

    import time
    start_time = time.time()

    # Cache check (seulement si pas de thread — les follow-ups ne cachent pas)
    if not thread_id:
        cached = _get_cached(user_message, routed_tools)
        if cached:
            metadata["cached"] = True
            metadata["response_time_ms"] = int((time.time() - start_time) * 1000)
            return {"response": cached, "metadata": metadata}

    logger.info(
        "Route: score=%d, niveau=%d, outils=%s",
        route["complexity_score"], route["level"], routed_tools,
    )

    # Construire les messages avec contexte de thread si present
    messages: list[dict] = [
        {"role": "system", "content": _get_system_prompt()},
    ]

    if thread_id:
        context = get_thread_context(thread_id, max_messages=10)
        messages.extend(context)

    messages.append({"role": "user", "content": user_message})

    # --- Fast path: outils en parallele + extraction contenu + 1 synthese LLM ---
    fast_result = await _fast_path_async(user_message, routed_tools, messages)
    if fast_result is not None:
        metadata["path"] = "fast"
        metadata["tools_used"] = routed_tools[:3]
        metadata["response_time_ms"] = int((time.time() - start_time) * 1000)
        if not thread_id:
            _set_cached(user_message, routed_tools, fast_result)
        return {"response": fast_result, "metadata": metadata}

    # --- Fallback: agent complet (2 appels LLM: selection d'outils + synthese) ---
    logger.info("Fallback: agent complet (2 round-trips LLM)")
    metadata["path"] = "full"

    # Selection aleatoire des modeles
    models = _pick_random_models(count=3)
    metadata["models_used"] = [m["model"] for m in models]

    # Race: tous les modeles demarrent en meme temps, le premier qui repond gagne
    tasks = [
        asyncio.create_task(
            asyncio.wait_for(
                _try_model_async(m, list(messages), routed_tools),
                timeout=m["timeout"] + 2,
            )
        )
        for m in models
    ]

    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                result = task.result()
            except (asyncio.TimeoutError, Exception):
                continue
            if result is not None:
                for t in pending:
                    t.cancel()
                metadata["response_time_ms"] = int((time.time() - start_time) * 1000)
                if not thread_id:
                    _set_cached(user_message, routed_tools, result)
                return {"response": result, "metadata": metadata}

    metadata["response_time_ms"] = int((time.time() - start_time) * 1000)
    return {"response": _ALL_MODELS_FAILED, "metadata": metadata}


# ============================================================================
# FAST PATH — outils en parallele + 1 synthese LLM (1 round-trip au lieu de 2)
# ============================================================================

async def _exec_tool_timed(
    name: str, query: str, timeout: float = None
):
    """Execute un outil avec timeout individuel."""
    if timeout is None:
        timeout = _get_tool_timeout()
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(TOOL_FUNCTIONS[name], query=query),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("Fast path outil %s timeout (%.0fs)", name, timeout)
        return None
    except Exception as e:
        logger.warning("Fast path outil %s echoue: %s", name, e)
        return None


async def _try_synthesis_only(model_info: dict, messages: list[dict]) -> str | None:
    """Appel LLM de synthese uniquement (sans tools)."""
    model = model_info["model"]
    try:
        client = _get_async_client(model, timeout=_get_synthesis_timeout())
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=_get_max_tokens_synthesis(),
        )
        content = response.choices[0].message.content or ""
        if not content or ("DSML" in content and "invoke" in content):
            return None
        return content
    except Exception as e:
        logger.warning("Synthese %s echouee: %s", model, e)
        return None


async def _synthesis_race(messages: list[dict]) -> str | None:
    """Race tous les modeles pour la synthese — premier qui repond gagne."""
    models = _pick_random_models(count=len(MODEL_POOL))

    tasks = [
        asyncio.create_task(
            asyncio.wait_for(
                _try_synthesis_only(m, messages),
                timeout=_get_synthesis_timeout() + 2,
            )
        )
        for m in models
    ]

    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            try:
                result = task.result()
            except (asyncio.TimeoutError, Exception):
                continue
            if result is not None:
                for t in pending:
                    t.cancel()
                return result

    return None


async def _fast_path_async(
    user_message: str, routed_tools: list[str], messages: list[dict] | None = None
) -> str | None:
    """Chemin rapide: execute les outils directement avec la requete utilisateur,
    extrait le contenu des pages trouvees, puis synthese en un seul appel LLM.

    Pipeline :
    1. Execute les outils en parallele
    2. Extrait le contenu lisible des URLs trouvees
    3. Passe les extraits numerotes au LLM pour synthese avec citations [1][2]

    Elimine le premier round-trip LLM (selection d'outil) car le routeur
    a deja choisi les outils pertinents. Les outils ont des timeouts
    individuels pour eviter qu'un outil lent bloque les autres.
    """
    top_tools = routed_tools[:3]
    logger.info("Fast path: outils=%s", top_tools)

    tool_results = await asyncio.gather(*[
        _exec_tool_timed(name, user_message)
        for name in top_tools
    ])

    valid = []
    for name, result in zip(top_tools, tool_results):
        if result:
            valid.append({"tool": name, "results": result})

    if not valid:
        logger.info("Fast path: aucun resultat valide, fallback agent complet")
        return None

    # --- Extraction de contenu : fetch URLs -> texte lisible ---
    urls_to_fetch = []
    for item in valid:
        for r in item["results"]:
            if isinstance(r, dict) and "url" in r and r["url"]:
                urls_to_fetch.append(r["url"])

    # Dedupliquer et limiter
    urls_to_fetch = list(dict.fromkeys(urls_to_fetch))[:6]

    extracted_content = []
    if urls_to_fetch:
        logger.info("Fast path: extraction de %d URLs", len(urls_to_fetch))
        extracted_content = await asyncio.to_thread(
            extract_content_from_results, urls_to_fetch
        )

    # Construire le contexte avec extraits numerotes
    context_parts = []

    # Ajouter les extraits de contenu numerotes
    for i, ext in enumerate(extracted_content, 1):
        context_parts.append(
            f"[{i}] {ext['title']}\nURL: {ext['url']}\n{ext['text']}"
        )

    # Ajouter les resultats bruts des outils (snippets)
    context_parts.append("\n--- Snippets de recherche ---\n")
    for item in valid:
        for r in item["results"]:
            if isinstance(r, dict):
                title = r.get("title", "")
                url = r.get("url", "")
                snippet = r.get("snippet", r.get("content", ""))
                if snippet:
                    context_parts.append(f"Titre: {title}\nURL: {url}\n{snippet}\n")

    context = "\n".join(context_parts)
    if len(context) > 6000:
        context = context[:6000]

    synthesis_messages = [
        {"role": "system", "content": _get_system_prompt()},
    ]

    # Ajouter le contexte de thread si present
    if messages:
        # messages contient deja le system prompt + contexte thread + user message
        # On remplace le system prompt et on garde le reste
        synthesis_messages = messages[:-1]  # tout sauf le dernier user message
        synthesis_messages[0] = {"role": "system", "content": _get_system_prompt()}

    synthesis_messages.append({"role": "user", "content": user_message})
    synthesis_messages.append({"role": "assistant", "content": f"Resultats de recherche:\n{context}"})
    synthesis_messages.append({"role": "user", "content": _SYNTHESIS_PROMPT})

    result = await _synthesis_race(synthesis_messages)
    if result is None:
        logger.warning("Fast path: synthese echouee pour tous les modeles")

    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>")
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    print(f"Question : {question}\n")
    answer = run_agent(question)
    print(answer)
