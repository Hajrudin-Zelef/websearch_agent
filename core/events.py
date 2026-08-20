"""
Events system — dispatch webhook asynchrone.
Envoie des POST JSON a l'URL configuree dans settings.json (section developer).
"""

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlparse

import aiohttp

from core.settings import _get_setting
from core.ssrf import validate_url_for_fetch, PinnedResolver

logger = logging.getLogger("websearch-agent")

_WEBHOOK_TIMEOUT = 5.0
_MAX_REDIRECTS = 3


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

    # SSRF guard: valider l'URL avant envoi (DNS + IP check)
    validation = validate_url_for_fetch(url)
    if not validation["safe"]:
        logger.warning(
            "Webhook %s blocked (SSRF): %s — %s",
            event_type, url, validation.get("reason", "unsafe URL"),
        )
        return

    payload = {
        "event": event_type,
        "timestamp": time.time(),
        "data": data,
    }

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    try:
        # Anti-DNS-rebinding: resolver pinné sur les IPs pré-validées
        resolver = PinnedResolver({hostname: validation["resolved_ips"]})
        timeout = aiohttp.ClientTimeout(total=_WEBHOOK_TIMEOUT)
        connector = aiohttp.TCPConnector(
            limit=1,
            resolver=resolver,
            enable_cleanup_closed=True,
        )
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
        ) as session:
            current_url = url
            for _ in range(_MAX_REDIRECTS + 1):
                async with session.post(
                    current_url,
                    json=payload,
                    allow_redirects=False,
                    ssl=(urlparse(current_url).scheme == "https"),
                ) as resp:
                    if resp.status in (301, 302, 303, 307, 308):
                        redirect_url = resp.headers.get("Location", "")
                        if not redirect_url:
                            break
                        # Valider la redirection (SSRF)
                        redirect_validation = validate_url_for_fetch(redirect_url)
                        if not redirect_validation["safe"]:
                            logger.warning(
                                "Webhook %s blocked redirect: %s -> %s — %s",
                                event_type, current_url, redirect_url,
                                redirect_validation.get("reason", "unsafe URL"),
                            )
                            return
                        r_parsed = urlparse(redirect_url)
                        r_hostname = r_parsed.hostname or ""
                        r_resolver = PinnedResolver(
                            {r_hostname: redirect_validation["resolved_ips"]}
                        )
                        r_connector = aiohttp.TCPConnector(
                            limit=1, resolver=r_resolver,
                            enable_cleanup_closed=True,
                        )
                        # Recréer la session avec le nouveau resolver
                        await session.close()
                        session = aiohttp.ClientSession(
                            timeout=timeout,
                            connector=r_connector,
                        )
                        current_url = redirect_url
                        continue

                    if resp.status >= 400:
                        logger.warning(
                            "Webhook %s -> %s returned %d",
                            event_type, current_url, resp.status,
                        )
                    break
    except asyncio.TimeoutError:
        logger.warning("Webhook %s -> %s timed out", event_type, url)
    except Exception as e:
        logger.warning("Webhook %s -> %s failed: %s", event_type, url, e)
