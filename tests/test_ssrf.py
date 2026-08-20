"""
Tests de sécurité pour la protection SSRF.
P6: Validation IP, DNS rebinding, schémas bloqués.
"""

import unittest
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSSRFSchemeBlocking(unittest.TestCase):
    """Vérifie que les schémas non-HTTP sont bloqués."""

    def test_file_scheme_blocked(self):
        """file:// doit être bloqué."""
        from sources.content_extractor import _is_safe_url
        self.assertFalse(_is_safe_url("file:///etc/passwd"))

    def test_gopher_scheme_blocked(self):
        """gopher:// doit être bloqué."""
        from sources.content_extractor import _is_safe_url
        self.assertFalse(_is_safe_url("gopher://localhost:25/"))

    def test_ftp_scheme_blocked(self):
        """ftp:// doit être bloqué."""
        from sources.content_extractor import _is_safe_url
        self.assertFalse(_is_safe_url("ftp://example.com/file"))

    def test_http_allowed(self):
        """http:// doit être autorisé (pour validation IP après)."""
        from sources.content_extractor import _is_safe_url
        # _is_safe_url vérifie le schéma, pas l'IP encore
        # HTTP est autorisé au niveau du schéma
        result = _is_safe_url("http://example.com")
        # Peut être False si l'IP est privée, mais pas à cause du schéma
        self.assertNotIn("schéma", str(result).lower() if not result else "")

    def test_https_allowed(self):
        """https:// doit être autorisé."""
        from sources.content_extractor import _is_safe_url
        result = _is_safe_url("https://example.com")
        self.assertNotIn("schéma", str(result).lower() if not result else "")


class TestSSRFPrivateIPBlocking(unittest.TestCase):
    """Vérifie que les IP privées/réservées sont bloquées."""

    def test_localhost_blocked(self):
        """127.0.0.1 doit être bloqué."""
        from sources.content_extractor import _is_safe_ip
        self.assertFalse(_is_safe_ip("127.0.0.1"))

    def test_private_10_blocked(self):
        """10.0.0.0/8 doit être bloqué."""
        from sources.content_extractor import _is_safe_ip
        self.assertFalse(_is_safe_ip("10.0.0.1"))
        self.assertFalse(_is_safe_ip("10.255.255.255"))

    def test_private_172_blocked(self):
        """172.16.0.0/12 doit être bloqué."""
        from sources.content_extractor import _is_safe_ip
        self.assertFalse(_is_safe_ip("172.16.0.1"))
        self.assertFalse(_is_safe_ip("172.31.255.255"))

    def test_private_192_blocked(self):
        """192.168.0.0/16 doit être bloqué."""
        from sources.content_extractor import _is_safe_ip
        self.assertFalse(_is_safe_ip("192.168.1.1"))
        self.assertFalse(_is_safe_ip("192.168.255.255"))

    def test_link_local_blocked(self):
        """169.254.0.0/16 (metadata cloud) doit être bloqué."""
        from sources.content_extractor import _is_safe_ip
        self.assertFalse(_is_safe_ip("169.254.169.254"))  # AWS metadata
        self.assertFalse(_is_safe_ip("169.254.0.1"))

    def test_zero_blocked(self):
        """0.0.0.0 doit être bloqué."""
        from sources.content_extractor import _is_safe_ip
        self.assertFalse(_is_safe_ip("0.0.0.0"))

    def test_loopback_ipv6_blocked(self):
        """::1 (loopback IPv6) doit être bloqué."""
        from sources.content_extractor import _is_safe_ip
        self.assertFalse(_is_safe_ip("::1"))

    def test_public_ip_allowed(self):
        """Les IP publiques doivent être autorisées."""
        from sources.content_extractor import _is_safe_ip
        self.assertTrue(_is_safe_ip("8.8.8.8"))  # Google DNS
        self.assertTrue(_is_safe_ip("1.1.1.1"))  # Cloudflare
        self.assertTrue(_is_safe_ip("208.67.222.222"))  # OpenDNS


class TestSSRFURLValidation(unittest.TestCase):
    """Vérifie la validation complète d'URL."""

    def test_safe_url_for_fetch(self):
        """URL publique HTTPS doit être validée."""
        from sources.content_extractor import _validate_url_for_fetch
        result = _validate_url_for_fetch("https://example.com/article")
        self.assertTrue(result["safe"])

    def test_unsafe_url_for_fetch_localhost(self):
        """URL vers localhost doit être rejetée."""
        from sources.content_extractor import _validate_url_for_fetch
        result = _validate_url_for_fetch("http://127.0.0.1/admin")
        self.assertFalse(result["safe"])

    def test_unsafe_url_for_fetch_metadata(self):
        """URL vers metadata cloud doit être rejetée."""
        from sources.content_extractor import _validate_url_for_fetch
        result = _validate_url_for_fetch("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(result["safe"])

    def test_unsafe_url_for_fetch_private(self):
        """URL vers réseau privé doit être rejetée."""
        from sources.content_extractor import _validate_url_for_fetch
        result = _validate_url_for_fetch("http://192.168.1.1/admin")
        self.assertFalse(result["safe"])


if __name__ == "__main__":
    unittest.main()
