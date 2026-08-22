"""
Tests de securite pour la protection SSRF.
P6: Validation IP, DNS rebinding, schemas bloques, ranges IPv6.
"""

import os
import socket
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ssrf import (
    BLOCKED_NETWORKS,
    is_safe_ip,
    is_safe_url,
    validate_url_for_fetch,
)


class TestSSRFSchemeBlocking(unittest.TestCase):
    """Verifie que les schemas non-HTTP sont bloques."""

    def test_file_scheme_blocked(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))

    def test_gopher_scheme_blocked(self):
        self.assertFalse(is_safe_url("gopher://localhost:25/"))

    def test_ftp_scheme_blocked(self):
        self.assertFalse(is_safe_url("ftp://example.com/file"))

    def test_ftp_bruteforce_blocked(self):
        self.assertFalse(is_safe_url("ftp://10.0.0.1/internal"))

    def test_http_allowed(self):
        self.assertTrue(is_safe_url("http://example.com"))

    def test_https_allowed(self):
        self.assertTrue(is_safe_url("https://example.com"))

    def test_empty_url_blocked(self):
        self.assertFalse(is_safe_url(""))

    def test_no_scheme_blocked(self):
        self.assertFalse(is_safe_url("example.com/path"))


class TestSSRFPrivateIPv4Blocking(unittest.TestCase):
    """Verifie que les IP privees/reservees IPv4 sont bloques."""

    def test_localhost_loopback(self):
        self.assertFalse(is_safe_ip("127.0.0.1"))

    def test_localhost_loopback_high(self):
        self.assertFalse(is_safe_ip("127.255.255.255"))

    def test_private_10_network(self):
        self.assertFalse(is_safe_ip("10.0.0.1"))
        self.assertFalse(is_safe_ip("10.255.255.255"))
        self.assertFalse(is_safe_ip("10.10.10.10"))

    def test_private_172_network(self):
        self.assertFalse(is_safe_ip("172.16.0.1"))
        self.assertFalse(is_safe_ip("172.31.255.255"))
        self.assertFalse(is_safe_ip("172.20.0.1"))

    def test_private_192_network(self):
        self.assertFalse(is_safe_ip("192.168.1.1"))
        self.assertFalse(is_safe_ip("192.168.255.255"))
        self.assertFalse(is_safe_ip("192.168.0.1"))

    def test_link_local_metadata_cloud(self):
        self.assertFalse(is_safe_ip("169.254.169.254"))
        self.assertFalse(is_safe_ip("169.254.0.1"))

    def test_zero_network(self):
        self.assertFalse(is_safe_ip("0.0.0.0"))

    def test_cgnat_shared_address_space(self):
        self.assertFalse(is_safe_ip("100.64.0.1"))
        self.assertFalse(is_safe_ip("100.127.255.255"))

    def test_public_ip_allowed(self):
        self.assertTrue(is_safe_ip("8.8.8.8"))
        self.assertTrue(is_safe_ip("1.1.1.1"))
        self.assertTrue(is_safe_ip("208.67.222.222"))
        self.assertTrue(is_safe_ip("93.184.216.34"))

    def test_invalid_ip_blocked(self):
        self.assertFalse(is_safe_ip("not-an-ip"))
        self.assertFalse(is_safe_ip("999.999.999.999"))


class TestSSRFPrivateIPv6Blocking(unittest.TestCase):
    """Verifie que les IP privees/reservees IPv6 sont bloques."""

    def test_loopback_ipv6(self):
        self.assertFalse(is_safe_ip("::1"))

    def test_ula_unique_local(self):
        self.assertFalse(is_safe_ip("fd00::1"))
        self.assertFalse(is_safe_ip("fc00::1"))

    def test_link_local_ipv6(self):
        self.assertFalse(is_safe_ip("fe80::1"))
        self.assertFalse(is_safe_ip("fe80::1%eth0"))

    def test_ipv4_mapped_ipv6(self):
        self.assertFalse(is_safe_ip("::ffff:127.0.0.1"))
        self.assertFalse(is_safe_ip("::ffff:10.0.0.1"))

    def test_public_ipv6_allowed(self):
        self.assertTrue(is_safe_ip("2606:4700::1"))
        self.assertTrue(is_safe_ip("2001:4860:4860::8888"))


class TestSSRFURLValidation(unittest.TestCase):
    """Verifie la validation complete d'URL."""

    def test_safe_url_for_fetch(self):
        result = validate_url_for_fetch("https://example.com/article")
        self.assertTrue(result["safe"])

    def test_unsafe_url_localhost(self):
        result = validate_url_for_fetch("http://127.0.0.1/admin")
        self.assertFalse(result["safe"])

    def test_unsafe_url_metadata(self):
        result = validate_url_for_fetch("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(result["safe"])

    def test_unsafe_url_private(self):
        result = validate_url_for_fetch("http://192.168.1.1/admin")
        self.assertFalse(result["safe"])

    def test_unsafe_url_file_scheme(self):
        result = validate_url_for_fetch("file:///etc/passwd")
        self.assertFalse(result["safe"])

    def test_hostname_manquant(self):
        result = validate_url_for_fetch("http://")
        self.assertFalse(result["safe"])

    def test_resolved_ips_returned(self):
        result = validate_url_for_fetch("https://example.com")
        self.assertTrue(result["safe"])
        self.assertIsInstance(result["resolved_ips"], list)

    def test_dns_resolution_failure(self):
        result = validate_url_for_fetch("http://this-host-does-not-exist-xyz123.example")
        self.assertFalse(result["safe"])


class TestSSRFDNSRebindingProtection(unittest.TestCase):
    """Verifie que la resolution DNS est faite une seule fois (anti-TOCTOU)."""

    def test_validate_returns_resolved_ips(self):
        result = validate_url_for_fetch("https://example.com")
        self.assertTrue(result["safe"])
        self.assertTrue(len(result["resolved_ips"]) > 0)

    def test_single_resolution_per_call(self):
        with patch("socket.getaddrinfo") as mock_resolve:
            mock_resolve.return_value = [
                (socket.AF_INET, 0, 0, "", ("93.184.216.34", 0))
            ]
            result = validate_url_for_fetch("https://example.com")
            self.assertTrue(result["safe"])
            self.assertEqual(mock_resolve.call_count, 1)

    def test_blocked_ip_in_resolved_list(self):
        with patch("socket.getaddrinfo") as mock_resolve:
            mock_resolve.return_value = [
                (socket.AF_INET, 0, 0, "", ("8.8.8.8", 0)),
                (socket.AF_INET, 0, 0, "", ("127.0.0.1", 0)),
            ]
            result = validate_url_for_fetch("https://example.com")
            self.assertFalse(result["safe"])


class TestSSRFAllowedNetworks(unittest.TestCase):
    """Verifie que les reseaux bloques couvrent bien les plages attendues."""

    def test_blocked_networks_count(self):
        self.assertGreaterEqual(len(BLOCKED_NETWORKS), 11)

    def test_all_networks_are_ip_network(self):
        import ipaddress
        for net in BLOCKED_NETWORKS:
            self.assertIsInstance(net, ipaddress.IPv4Network | ipaddress.IPv6Network)


class TestSSRFRSSFeedProtection(unittest.TestCase):
    """Verifie que agent_reach_rss_search valide le feed_url."""

    def test_rss_feed_blocked_private_ip(self):
        from sources.agent_reach import agent_reach_rss_search
        results = agent_reach_rss_search("test", feed_url="http://192.168.1.1/feed")
        self.assertEqual(results, [])

    def test_rss_feed_blocked_loopback(self):
        from sources.agent_reach import agent_reach_rss_search
        results = agent_reach_rss_search("test", feed_url="http://127.0.0.1/rss")
        self.assertEqual(results, [])

    def test_rss_feed_blocked_metadata(self):
        from sources.agent_reach import agent_reach_rss_search
        results = agent_reach_rss_search("test", feed_url="http://169.254.169.254/metadata")
        self.assertEqual(results, [])

    def test_rss_feed_blocked_file_scheme(self):
        from sources.agent_reach import agent_reach_rss_search
        results = agent_reach_rss_search("test", feed_url="file:///etc/passwd")
        self.assertEqual(results, [])


class TestSSRFRedirectBypass(unittest.TestCase):
    """Verifie que les redirections vers des IPs privees sont bloquees."""

    def test_redirect_to_localhost_blocked(self):
        """Une URL safe qui redirige vers 127.0.0.1 doit etre bloquee."""
        from core.ssrf import validate_url_for_fetch
        redirect_url = "http://127.0.0.1/admin"
        result = validate_url_for_fetch(redirect_url)
        self.assertFalse(result["safe"])

    def test_redirect_to_private_ip_blocked(self):
        """Une URL safe qui redirige vers 10.0.0.1 doit etre bloquee."""
        from core.ssrf import validate_url_for_fetch
        redirect_url = "http://10.0.0.1/secret"
        result = validate_url_for_fetch(redirect_url)
        self.assertFalse(result["safe"])

    def test_redirect_to_metadata_blocked(self):
        """Une URL safe qui redirige vers 169.254.169.254 doit etre bloquee."""
        from core.ssrf import validate_url_for_fetch
        redirect_url = "http://169.254.169.254/latest/meta-data/"
        result = validate_url_for_fetch(redirect_url)
        self.assertFalse(result["safe"])

    def test_redirect_to_ipv6_loopback_blocked(self):
        """Une URL safe qui redirige vers ::1 doit etre bloquee."""
        from core.ssrf import validate_url_for_fetch
        redirect_url = "http://[::1]/admin"
        result = validate_url_for_fetch(redirect_url)
        self.assertFalse(result["safe"])

    def test_redirect_to_ipv4_mapped_blocked(self):
        """Une URL safe qui redirige vers ::ffff:127.0.0.1 doit etre bloquee."""
        from core.ssrf import validate_url_for_fetch
        redirect_url = "http://[::ffff:127.0.0.1]/admin"
        result = validate_url_for_fetch(redirect_url)
        self.assertFalse(result["safe"])

    def test_redirect_to_private_range_blocked(self):
        """Une URL safe qui redirige vers 172.16.0.1 doit etre bloquee."""
        from core.ssrf import validate_url_for_fetch
        redirect_url = "http://172.16.0.1/admin"
        result = validate_url_for_fetch(redirect_url)
        self.assertFalse(result["safe"])

    def test_redirect_to_link_local_blocked(self):
        """Une URL safe qui redirige vers fe80::1 doit etre bloquee."""
        from core.ssrf import validate_url_for_fetch
        redirect_url = "http://[fe80::1]/admin"
        result = validate_url_for_fetch(redirect_url)
        self.assertFalse(result["safe"])

    def test_redirect_to_public_ip_allowed(self):
        """Une URL safe qui redirige vers une IP publique est autorisee."""
        from core.ssrf import validate_url_for_fetch
        with patch("socket.getaddrinfo") as mock_resolve:
            mock_resolve.return_value = [
                (socket.AF_INET, 0, 0, "", ("93.184.216.34", 0))
            ]
            redirect_url = "https://example.com/article"
            result = validate_url_for_fetch(redirect_url)
            self.assertTrue(result["safe"])


if __name__ == "__main__":
    unittest.main()
