"""
Protection SSRF centralisee.

Module unique pour la validation d'URLs, la verification d'IPs privees
et la protection contre le DNS rebinding (TOCTOU).

Utilise par :
- sources/content_extractor.py (fetch async)
- sources/agent_reach.py (feed_url RSS)
- core/events.py (webhook URL)
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger("websearch-agent.ssrf")

# ============================================================================
# RESEAUX BLOQUES
# ============================================================================

BLOCKED_NETWORKS = [
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network
    ipaddress.ip_network("10.0.0.0/8"),          # Privé RFC1918
    ipaddress.ip_network("100.64.0.0/10"),       # CGNAT / Shared Address Space
    ipaddress.ip_network("127.0.0.0/8"),         # Loopback
    ipaddress.ip_network("169.254.0.0/16"),      # Link-local (metadata cloud)
    ipaddress.ip_network("172.16.0.0/12"),       # Privé RFC1918
    ipaddress.ip_network("192.168.0.0/16"),      # Privé RFC1918
    # IPv6
    ipaddress.ip_network("::1/128"),             # Loopback IPv6
    ipaddress.ip_network("::ffff:0:0/96"),       # IPv4-mapped IPv6
    ipaddress.ip_network("fc00::/7"),            # IPv6 ULA (Unique Local)
    ipaddress.ip_network("fe80::/10"),           # IPv6 link-local
]

ALLOWED_SCHEMAS = {"http", "https"}


def is_safe_ip(ip_str: str) -> bool:
    """Verifie qu'une IP n'appartient a aucune plage privee/reservee."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not any(ip in net for net in BLOCKED_NETWORKS)


def is_safe_url(url: str) -> bool:
    """Verifie qu'une URL a un schema autorise."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme.lower() in ALLOWED_SCHEMAS


def validate_url_for_fetch(url: str) -> dict:
    """
    Validation complete d'une URL avant fetch.
    Retourne {"safe": bool, "reason": str, "resolved_ips": list[str]}
    """
    # 1. Schema
    if not is_safe_url(url):
        return {"safe": False, "reason": "schema non autorise", "resolved_ips": []}

    # 2. Hostname
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return {"safe": False, "reason": "hostname manquant", "resolved_ips": []}
    except Exception:
        return {"safe": False, "reason": "URL invalide", "resolved_ips": []}

    # 3. Resolution DNS + verification IPs
    resolved_ips = []
    try:
        addrinfos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
    except socket.gaierror:
        return {"safe": False, "reason": "resolution DNS echouee", "resolved_ips": []}

    for family, _, _, _, sockaddr in addrinfos:
        ip_str = sockaddr[0]
        resolved_ips.append(ip_str)
        if not is_safe_ip(ip_str):
            return {"safe": False, "reason": f"IP privee/reservee: {ip_str}", "resolved_ips": resolved_ips}

    return {"safe": True, "reason": "", "resolved_ips": resolved_ips}


def resolve_and_validate(url: str) -> tuple[bool, str, list[str]]:
    """
    Resolution DNS + validation IP pour une URL.
    Retourne (is_safe, reason, resolved_ips).

    Usage:
        safe, reason, ips = resolve_and_validate("http://evil.com/steal")
        if not safe:
            raise ValueError(reason)
    """
    result = validate_url_for_fetch(url)
    return result["safe"], result["reason"], result["resolved_ips"]
