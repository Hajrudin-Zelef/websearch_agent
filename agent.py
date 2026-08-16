"""
Agent IA ultra-rapide avec function-calling via OpenRouter.
Selection aleatoire des modeles par requete, execution parallele des outils.
L'utilisateur ne remarque rien — tout est transparent.

Refactore : les modules suivants ont ete extraits :
- settings.py : lecture de settings.json
- cache.py : cache LRU
- prompts.py : prompts et detection de refus
- models.py : pool de modeles et clients OpenAI
- parser.py : parsing DSML et JSON
- tools.py : registry des outils de recherche
"""

import asyncio
import logging
import json
import re
import uuid
import time
import threading
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

# Imports des modules extraits (core/)
from core.settings import _get_setting
from core.cache import _get_cached, _set_cached
from core.prompts import (
    _get_system_prompt,
    _get_refusal_markers,
    REFUSAL_MARKERS,
    _get_synthesis_prompt,
    _FALLBACK_RESPONSE,
)
from core.models import (
    MODEL_POOL,
    _pick_random_models,
    _get_client,
    _get_async_client,
    _get_tool_timeout,
    _get_synthesis_timeout,
    _get_max_tokens_tool,
    _get_max_tokens_synthesis,
    _get_search_speed_config,
)
from core.parser import _parse_dsml_tool_calls, _parse_json_tool_calls
from core.tools import (
    TOOLS_REGISTRY,
    TOOLS,
    TOOL_FUNCTIONS,
    _filter_tools,
)
from sources.router import route_query
from sources.content_extractor import extract_content_async
from threads import get_thread_context

load_dotenv()

logger = logging.getLogger("websearch-agent")

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


def _deduplicate_tool_calls(tool_calls: list) -> list:
    """Supprime les tool calls en double (meme outil + meme query)."""
    seen = set()
    unique = []
    for tc in tool_calls:
        key = f"{tc.function.name}:{tc.function.arguments}"
        if key not in seen:
            seen.add(key)
            unique.append(tc)
    return unique


def _execute_single_tool(tc, request_id: str = "") -> dict:
    from core.monitoring import source_stats
    func_name = tc.function.name
    func = TOOL_FUNCTIONS.get(func_name)
    if func is None:
        tool_result = json.dumps({"error": f"Fonction inconnue: {func_name}"})
    else:
        tool_start = time.time()
        try:
            args = json.loads(tc.function.arguments)
            logger.info("[%s] Outil %s lancé", request_id, func_name)
            result = func(**args)
            tool_duration = time.time() - tool_start
            logger.info("[%s] Outil %s terminé en %.1fs", request_id, func_name, tool_duration)
            tool_result = json.dumps(result, ensure_ascii=False, default=str)
            source_stats.record(func_name, True, tool_duration, origin="chat")
        except Exception as e:
            tool_duration = time.time() - tool_start
            logger.warning("[%s] Outil %s échoué: %s", request_id, func_name, e)
            tool_result = json.dumps({"error": str(e)})
            source_stats.record(func_name, False, tool_duration, origin="chat")

    return {
        "role": "tool",
        "tool_call_id": tc.id,
        "content": tool_result,
    }


def _execute_tools_parallel(tool_calls: list, request_id: str = "") -> list[dict]:
    """Execute les tool calls en parallele."""
    import concurrent.futures

    tool_names = [tc.function.name for tc in tool_calls]
    logger.info("[%s] Exécution %d outils: %s", request_id, len(tool_calls), tool_names)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_execute_single_tool, tc, request_id): tc for tc in tool_calls}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logger.error("[%s] Erreur execution outil: %s", request_id, e)
    return results


# ============================================================================
# MODEL CALL — un seul appel LLM
# ============================================================================

def _try_model_sync(model_info: dict, messages: list[dict], routed_tools: list[str], request_id: str = "") -> str | None:
    """Essaie un modele synchrone avec tool-calling. Retourne la reponse ou None."""
    model = model_info["model"]
    timeout = model_info["timeout"]
    provider = model_info.get("provider")  # None = provider global
    tools = _filter_tools(routed_tools)

    try:
        client = _get_client(model, timeout=timeout, provider=provider)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools if tools else None,
            max_tokens=_get_max_tokens_tool(),
        )

        choice = response.choices[0]
        message = choice.message

        # Si pas de tool calls, retourner directement
        if not message.tool_calls:
            content = message.content or ""
            # Verifier si c'est un DSML
            if "DSML" in content:
                dsml_calls = _parse_dsml_tool_calls(content)
                if dsml_calls:
                    # Executer les tool calls DSML (dedoublonnes)
                    messages.append({"role": "assistant", "content": content})
                    dsml_tc = [type("TC", (), {"id": tc["id"], "type": "function",
                     "function": type("F", (), {"name": tc["function"]["name"],
                     "arguments": tc["function"]["arguments"]})()})() for tc in dsml_calls]
                    dsml_tc = _deduplicate_tool_calls(dsml_tc)
                    tool_results = _execute_tools_parallel(dsml_tc, request_id)
                    messages.extend(tool_results)
                    return _synthesize(client, model, messages, timeout)
            # Verifier JSON brut
            json_calls = _parse_json_tool_calls(content, set(TOOLS_REGISTRY.keys()))
            if json_calls:
                messages.append({"role": "assistant", "content": content})
                json_tc = [type("TC", (), {"id": tc["id"], "type": "function",
                 "function": type("F", (), {"name": tc["function"]["name"],
                 "arguments": tc["function"]["arguments"]})()})() for tc in json_calls]
                json_tc = _deduplicate_tool_calls(json_tc)
                tool_results = _execute_tools_parallel(json_tc, request_id)
                messages.extend(tool_results)
                return _synthesize(client, model, messages, timeout)
            return content

        # Executer les tool calls (dedoublonne)
        messages.append(_build_tool_call_message(message))
        tool_calls = _deduplicate_tool_calls(message.tool_calls)
        logger.info("[%s] Tool calls: %d → %d après dédoublonnage", request_id, len(message.tool_calls), len(tool_calls))
        tool_results = _execute_tools_parallel(tool_calls, request_id)
        messages.extend(tool_results)

        # Synthese finale
        return _synthesize(client, model, messages, timeout)

    except Exception as e:
        logger.warning("[%s] Modèle %s échoué (%.1fs): %s", request_id, model, timeout, e)
        return None


def _synthesize(client, model: str, messages: list[dict], timeout: float) -> str | None:
    """Synthetise les resultats d'outils en une reponse finale."""
    try:
        messages.append({"role": "user", "content": _get_synthesis_prompt()})
        final_response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=_get_max_tokens_synthesis(),
        )
        final_content = final_response.choices[0].message.content or ""
        if "DSML" in final_content and "invoke" in final_content:
            return None
        return final_content
    except Exception as e:
        logger.warning("Synthese echoue: %s", e)
        return None


# ============================================================================
# AGENT SYNCHRONE — fast path
# ============================================================================

_ALL_MODELS_FAILED = (
    "Tous les modeles ont echoue. Reessayez plus tard."
)

_EMPTY_RESPONSE = ""


def run_agent(user_message: str, request_id: str = "") -> str:
    """Version synchrone — selection aleatoire + fallback rapide."""
    route = route_query(user_message)
    routed_tools = route["tools"]

    # Cache check
    cached = _get_cached(user_message, routed_tools)
    if cached:
        logger.info("[%s] Réponse depuis le cache", request_id)
        return cached

    logger.info(
        "[%s] Route: score=%d, niveau=%d, outils=%s",
        request_id, route["complexity_score"], route["level"], routed_tools,
    )

    messages: list[dict] = [
        {"role": "system", "content": _get_system_prompt()},
        {"role": "user", "content": user_message},
    ]

    # Selection des modeles selon le tier de complexite
    tier = route["level"]  # 1=simple, 2=moyen, 3=complexe
    speed_config = _get_search_speed_config()
    models = _pick_random_models(count=speed_config["model_count"], tier=tier)
    logger.info("[%s] Tier %d sélectionné, %d modèles à essayer (vitesse: %s)", request_id, tier, len(models), _get_setting("ai", "search_speed", "normal"))

    for model_info in models:
        adjusted_timeout = model_info["timeout"] * speed_config["timeout_multiplier"]
        adjusted_info = {**model_info, "timeout": adjusted_timeout}
        logger.info("[%s] Essai: %s (timeout: %.0fs, tier: %s)", request_id, adjusted_info["model"], adjusted_timeout, adjusted_info["tier"])
        result = _try_model_sync(adjusted_info, list(messages), routed_tools, request_id)
        if result is not None:
            logger.info("[%s] Modèle gagnant: %s (tier %s)", request_id, model_info["model"], model_info["tier"])
            _set_cached(user_message, routed_tools, result)
            return result

    logger.warning("[%s] Tous les modèles ont échoué", request_id)
    return _ALL_MODELS_FAILED


# ============================================================================
# AGENT ASYNC — version async pour FastAPI
# ============================================================================

async def _try_model_async(model_info: dict, messages: list[dict], routed_tools: list[str], request_id: str = "") -> str | None:
    """Essaie un modele asynchrone avec tool-calling."""
    model = model_info["model"]
    timeout = model_info["timeout"]
    provider = model_info.get("provider")  # None = provider global
    tools = _filter_tools(routed_tools)

    try:
        client = _get_async_client(model, timeout=timeout, provider=provider)

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools if tools else None,
            max_tokens=_get_max_tokens_tool(),
        )

        choice = response.choices[0]
        message = choice.message

        if not message.tool_calls:
            content = message.content or ""
            # Verifier DSML
            if "DSML" in content:
                dsml_calls = _parse_dsml_tool_calls(content)
                if dsml_calls:
                    messages.append({"role": "assistant", "content": content})
                    tool_results = _execute_tools_parallel(
                        [type("TC", (), {"id": tc["id"], "type": "function",
                         "function": type("F", (), {"name": tc["function"]["name"],
                         "arguments": tc["function"]["arguments"]})()})() for tc in dsml_calls],
                        request_id,
                    )
                    messages.extend(tool_results)
                    return await _synthesize_async(client, model, messages, timeout)
            # Verifier JSON brut
            json_calls = _parse_json_tool_calls(content, set(TOOLS_REGISTRY.keys()))
            if json_calls:
                messages.append({"role": "assistant", "content": content})
                tool_results = _execute_tools_parallel(
                    [type("TC", (), {"id": tc["id"], "type": "function",
                     "function": type("F", (), {"name": tc["function"]["name"],
                     "arguments": tc["function"]["arguments"]})()})() for tc in json_calls],
                    request_id,
                )
                messages.extend(tool_results)
                return await _synthesize_async(client, model, messages, timeout)
            return content

        # Executer les tool calls (dedoublonne)
        messages.append(_build_tool_call_message(message))
        tool_calls = _deduplicate_tool_calls(message.tool_calls)
        logger.info("[%s] Tool calls: %d → %d après dédoublonnage", request_id, len(message.tool_calls), len(tool_calls))
        tool_results = _execute_tools_parallel(tool_calls, request_id)
        messages.extend(tool_results)

        return await _synthesize_async(client, model, messages, timeout)

    except Exception as e:
        logger.warning("[%s] Modèle %s échoué async (%.1fs): %s", request_id, model, timeout, e)
        return None


async def _synthesize_async(client, model: str, messages: list[dict], timeout: float) -> str | None:
    """Synthese asynchrone."""
    try:
        messages.append({"role": "user", "content": _get_synthesis_prompt()})
        final_response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=_get_max_tokens_synthesis(),
        )
        final_content = final_response.choices[0].message.content or ""
        if "DSML" in final_content and "invoke" in final_content:
            return None
        return final_content
    except Exception as e:
        logger.warning("Synthese async echoue: %s", e)
        return None


async def run_agent_async(user_message: str, thread_id: str = None, request_id: str = "") -> dict:
    """Version async — fast path (1 appel LLM) + fallback agent complet (2 appels)."""
    route = route_query(user_message)
    routed_tools = route["tools"]

    # Cache check
    cached = _get_cached(user_message, routed_tools)
    if cached:
        logger.info("[%s] Réponse depuis le cache", request_id)
        return {"response": cached, "metadata": {"cached": True}}

    logger.info(
        "[%s] Route async: score=%d, niveau=%d, outils=%s",
        request_id, route["complexity_score"], route["level"], routed_tools,
    )

    # Construire le contexte avec thread
    thread_context = ""
    if thread_id:
        try:
            thread_context = get_thread_context(thread_id)
        except Exception:
            pass

    messages: list[dict] = [
        {"role": "system", "content": _get_system_prompt()},
    ]
    if thread_context:
        messages.append({"role": "user", "content": f"Contexte de la conversation precedente:\n{thread_context}"})
    messages.append({"role": "user", "content": user_message})

    # Selection des modeles selon le tier de complexite
    tier = route["level"]  # 1=simple, 2=moyen, 3=complexe
    speed_config = _get_search_speed_config()
    models = _pick_random_models(count=speed_config["model_count"], tier=tier)
    logger.info("[%s] Tier %d sélectionné, %d modèles à essayer (vitesse: %s)", request_id, tier, len(models), _get_setting("ai", "search_speed", "normal"))

    for model_info in models:
        adjusted_timeout = model_info["timeout"] * speed_config["timeout_multiplier"]
        adjusted_info = {**model_info, "timeout": adjusted_timeout}
        logger.info("[%s] Essai async: %s (timeout: %.0fs, tier: %s)", request_id, adjusted_info["model"], adjusted_timeout, adjusted_info["tier"])
        result = await _try_model_async(adjusted_info, list(messages), routed_tools, request_id)
        if result is not None:
            logger.info("[%s] Modèle gagnant: %s (tier %s)", request_id, model_info["model"], model_info["tier"])
            _set_cached(user_message, routed_tools, result)
            return {
                "response": result,
                "metadata": {
                    "model": model_info["model"],
                    "cached": False,
                    "route": {
                        "level": route["level"],
                        "intents": route["intents"],
                        "domains": route["domains"],
                    },
                },
            }

    logger.warning("[%s] Tous les modèles ont échoué (async)", request_id)
    return {"response": _ALL_MODELS_FAILED, "metadata": {"error": "all_models_failed"}}
