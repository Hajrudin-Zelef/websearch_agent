"""
Modeles LLM — pool, selection aleatoire, clients OpenAI.
Extrait de agent.py lors du refactoring.
"""

import os
import time
import random
import threading
from openai import AsyncOpenAI, OpenAI
from core.settings import _get_setting

# ============================================================================
# CONFIG — provider et pool de modeles
# ============================================================================

PROVIDER = os.getenv("PROVIDER", "openrouter")

PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
}

_FAST_PATH_TOOL_TIMEOUT = 5.0
_SYNTHESIS_TIMEOUT = 6.0

# Pool de modeles — 3 tiers + special, selectionnes par complexite de la requete
MODEL_POOL: list[dict] = [
    # Tier 1 : Rapide (ultra-economiques, infERENCE tres rapide) —requete simple
    {"model": "inclusionai/ling-2.6-flash:exacto",          "timeout": 8.0,  "weight": 4, "tier": 1},
    {"model": "ibm-granite/granite-4.1-8b:exacto",         "timeout": 8.0,  "weight": 3, "tier": 1},
    {"model": "poolside/laguna-xs-2.1:exacto",             "timeout": 8.0,  "weight": 3, "tier": 1},

    # Tier 2 : Standard (bon equilibre performance/prix) —requete moyenne
    {"model": "qwen/qwen3.7-flash:exacto",                 "timeout": 10.0, "weight": 4, "tier": 2},
    {"model": "deepseek/deepseek-v4-flash-latest:exacto",  "timeout": 10.0, "weight": 4, "tier": 2},
    {"model": "mistralai/ministral-14b-2512:exacto",       "timeout": 10.0, "weight": 3, "tier": 2},
    {"model": "nvidia/nemotron-3.5-lightning:exacto",      "timeout": 10.0, "weight": 3, "tier": 2},

    # Tier 3 : Elite (plus puissants) —requete complexe
    {"model": "meta-llama/llama-4-scout:exacto",           "timeout": 12.0, "weight": 5, "tier": 3},
    {"model": "xiaomi/mimo-v2-flash:exacto",               "timeout": 12.0, "weight": 4, "tier": 3},
    {"model": "stepfun/step-3.5-flash:exacto",             "timeout": 12.0, "weight": 3, "tier": 3},

    # Special : Le plus puissant —requete tres complexe
    {"model": "meta-llama/llama-4-scout:exacto",           "timeout": 15.0, "weight": 5, "tier": "special"},
]


def _get_tool_timeout() -> float:
    return _get_setting("models", "tool_timeout", _FAST_PATH_TOOL_TIMEOUT)


def _get_synthesis_timeout() -> float:
    return _get_setting("models", "synthesis_timeout", _SYNTHESIS_TIMEOUT)


def _get_max_tokens_tool() -> int:
    return _get_setting("models", "max_tokens_tool_selection", 300)


def _get_max_tokens_synthesis() -> int:
    return _get_setting("models", "max_tokens_synthesis", 500)


def _get_search_speed_config() -> dict:
    """Retourne la config basée sur search_speed (fast/normal/deep)."""
    speed = _get_setting("ai", "search_speed", "normal")
    configs = {
        "fast": {"model_count": 1, "timeout_multiplier": 0.7},
        "normal": {"model_count": 2, "timeout_multiplier": 1.0},
        "deep": {"model_count": 3, "timeout_multiplier": 1.5},
    }
    return configs.get(speed, configs["normal"])


# ============================================================================
# SELECTION PAR TIER — basee sur la complexite de la requete
# ============================================================================

def _pick_random_models(count: int = 3, tier: int = None) -> list[dict]:
    """Selectionne des modeles aleatoirement avec poids, filtre par tier.

    - tier=None : melange de tous les tiers (fallback)
    - tier=1,2,3 : modeles du tier specifie
    - tier="special" : uniquement le special
    """
    if tier is not None:
        pool = [m for m in MODEL_POOL if m["tier"] == tier]
    else:
        pool = list(MODEL_POOL)

    if not pool:
        pool = list(MODEL_POOL)  # Fallback sur tout le pool

    selected = []
    for _ in range(min(count, len(pool))):
        weights = [m["weight"] for m in pool]
        chosen = random.choices(pool, weights=weights, k=1)[0]
        selected.append(chosen)
        pool.remove(chosen)
    return selected


# ============================================================================
# CLIENT SINGLETON — connection pooling agressif
# ============================================================================

_clients: dict[str, tuple[OpenAI, float]] = {}
_async_clients: dict[str, tuple[AsyncOpenAI, float]] = {}
_client_lock = threading.Lock()
_CLIENT_TTL = 3600  # Recreate clients every hour


def _get_client(model: str, timeout: float = 30.0, provider: str = None) -> OpenAI:
    """Cree ou reutilise un client OpenAI pour un model/provider donne."""
    provider = provider or PROVIDER
    cache_key = f"{provider}:{model}"
    now = time.time()
    with _client_lock:
        if cache_key in _clients:
            client, created_at = _clients[cache_key]
            if now - created_at < _CLIENT_TTL:
                return client
        provider_cfg = PROVIDER_CONFIG.get(provider, PROVIDER_CONFIG[PROVIDER])
        api_key = os.getenv(provider_cfg["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Variable {provider_cfg['api_key_env']} non definie.")
        client = OpenAI(
            base_url=provider_cfg["base_url"],
            api_key=api_key,
            timeout=timeout,
            max_retries=0,
        )
        _clients[cache_key] = (client, now)
        if len(_clients) > 20:
            oldest_key = min(_clients, key=lambda k: _clients[k][1])
            del _clients[oldest_key]
        return client


def _get_async_client(model: str, timeout: float = 30.0, provider: str = None) -> AsyncOpenAI:
    """Cree ou reutilise un client AsyncOpenAI pour un model/provider donne."""
    provider = provider or PROVIDER
    cache_key = f"{provider}:{model}"
    now = time.time()
    with _client_lock:
        if cache_key in _async_clients:
            client, created_at = _async_clients[cache_key]
            if now - created_at < _CLIENT_TTL:
                return client
        provider_cfg = PROVIDER_CONFIG.get(provider, PROVIDER_CONFIG[PROVIDER])
        api_key = os.getenv(provider_cfg["api_key_env"])
        if not api_key:
            raise RuntimeError(f"Variable {provider_cfg['api_key_env']} non definie.")
        client = AsyncOpenAI(
            base_url=provider_cfg["base_url"],
            api_key=api_key,
            timeout=timeout,
            max_retries=0,
        )
        _async_clients[cache_key] = (client, now)
        if len(_async_clients) > 20:
            oldest_key = min(_async_clients, key=lambda k: _async_clients[k][1])
            del _async_clients[oldest_key]
        return client
