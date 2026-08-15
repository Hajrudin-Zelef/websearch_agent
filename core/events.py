"""
Events system — dispatch webhook asynchrone.
Envoie des POST JSON a l'URL configuree dans settings.json (section developer).
"""

import asyncio
import logging
import time
from typing import Any

import aiohttp

from core.settings import _get_setting

logger = logging.getLogger("websearch-agent")

_WEBHOOK_TIMEOUT = 5.0


def _is_webhook_enabled() -> bool:
    return bool(_get_setting("developer", "webhooks_enabled", False))


def _get_webhook_url() -> str:
    return _get_setting("developer", "webhook_url", "")


async def fire_webhook(event_type: str, data: dict[str, Any]) -> None:
    """Envoie un evenement webhook de maniere asynchrone.

    Ne bloque jamais le caller. En cas d'echec, log et retourne.
    """
    if not _is_webhook_enabled():
        return

    url = _get_webhook_url()
    if not url:
        return

    payload = {
        "event": event_type,
        "timestamp": time.time(),
        "data": data,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=_WEBHOOK_TIMEOUT),
            ) as resp:
                if resp.status >= 400:
                    logger.warning(
                        "Webhook %s -> %s returned %d",
                        event_type, url, resp.status,
                    )
    except asyncio.TimeoutError:
        logger.warning("Webhook %s -> %s timed out", event_type, url)
    except Exception as e:
        logger.warning("Webhook %s -> %s failed: %s", event_type, url, e)
