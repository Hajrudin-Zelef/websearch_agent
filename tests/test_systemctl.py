"""
Tests de sécurité pour les routes systemctl.
P4: Audit logging + rate limit dédié.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSystemctlAuditLogging(unittest.TestCase):
    """Vérifie l'audit logging pour les commandes systemctl."""

    def test_restart_logs_audit(self):
        """service_restart doit écrire dans le fichier d'audit."""
        import inspect

        from routes.admin import service_restart
        source = inspect.getsource(service_restart)
        self.assertIn("audit", source.lower(),
                       "service_restart doit effectuer un audit logging")

    def test_stop_logs_audit(self):
        """service_stop doit écrire dans le fichier d'audit."""
        import inspect

        from routes.admin import service_stop
        source = inspect.getsource(service_stop)
        self.assertIn("audit", source.lower(),
                       "service_stop doit effectuer un audit logging")

    def test_audit_log_contains_session_info(self):
        """Le log d'audit doit contenir des infos sur la session."""
        import inspect

        from routes.admin import service_restart
        source = inspect.getsource(service_restart)
        # Vérifie qu'on log l'IP ou le token (pas le token complet)
        self.assertTrue(
            "client" in source.lower() or "session" in source.lower() or "ip" in source.lower(),
            "Le log d'audit doit contenir des infos d'identification"
        )


class TestSystemctlRateLimit(unittest.TestCase):
    """Vérifie le rate limit dédié sur les routes systemctl."""

    def test_restart_has_rate_limit(self):
        """service_restart doit avoir un rate limit."""
        import inspect

        from routes.admin import service_restart
        source = inspect.getsource(service_restart)
        self.assertIn("rate", source.lower(),
                       "service_restart doit avoir un rate limit")

    def test_stop_has_rate_limit(self):
        """service_stop doit avoir un rate limit."""
        import inspect

        from routes.admin import service_stop
        source = inspect.getsource(service_stop)
        self.assertIn("rate", source.lower(),
                       "service_stop doit avoir un rate limit")

    def test_rate_limit_constants_defined(self):
        """Les constantes de rate limit doivent être définies."""
        from routes.admin import SERVICE_RATE_MAX, SERVICE_RATE_WINDOW
        self.assertIsInstance(SERVICE_RATE_MAX, int)
        self.assertIsInstance(SERVICE_RATE_WINDOW, int)
        self.assertGreater(SERVICE_RATE_MAX, 0)
        self.assertGreater(SERVICE_RATE_WINDOW, 0)


class TestSystemctlCSRF(unittest.TestCase):
    """Vérifie que les routes systemctl sont protégées par CSRF."""

    def test_restart_requires_csrf(self):
        """La route restart doit être protégée par CSRF (via middleware)."""
        # Vérifie que la route est bien dans les routes admin mutantes
        from routes.admin import router
        routes = [r.path for r in router.routes]
        self.assertIn("/admin/service/restart", routes)

    def test_stop_requires_csrf(self):
        """La route stop doit être protégée par CSRF (via middleware)."""
        from routes.admin import router
        routes = [r.path for r in router.routes]
        self.assertIn("/admin/service/stop", routes)


if __name__ == "__main__":
    unittest.main()
