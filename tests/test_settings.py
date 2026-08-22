"""
Tests unitaires pour core/settings.py.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.settings import _get_setting, _load_settings


class TestSettings(unittest.TestCase):

    def setUp(self):
        """Cree un fichier settings.json temporaire."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "settings.json")
        self.test_data = {
            "models": {"tool_timeout": 8.0, "max_tokens_tool_selection": 400},
            "cache": {"ttl": 600, "max_size": 500},
            "agent": {"system_prompt": "Custom prompt"},
        }
        with open(self.test_file, "w") as f:
            json.dump(self.test_data, f)

    def test_get_setting_exists(self):
        """Recupere une cle existante."""
        import core.settings
        core.settings._SETTINGS_FILE = self.test_file
        core.settings._settings_cache = {}
        core.settings._settings_mtime = 0
        core.settings._settings_last_check = 0

        result = _get_setting("models", "tool_timeout")
        self.assertEqual(result, 8.0)

    def test_get_setting_missing_key(self):
        """Retourne default si cle manquante."""
        import core.settings
        core.settings._SETTINGS_FILE = self.test_file
        core.settings._settings_cache = {}
        core.settings._settings_mtime = 0
        core.settings._settings_last_check = 0

        result = _get_setting("models", "nonexistent", default=42)
        self.assertEqual(result, 42)

    def test_get_setting_missing_section(self):
        """Retourne default si section manquante."""
        import core.settings
        core.settings._SETTINGS_FILE = self.test_file
        core.settings._settings_cache = {}
        core.settings._settings_mtime = 0
        core.settings._settings_last_check = 0

        result = _get_setting("nonexistent", "key", default="fallback")
        self.assertEqual(result, "fallback")

    def test_load_settings_file_not_found(self):
        """Gere le cas ou le fichier n'existe pas."""
        import core.settings
        core.settings._SETTINGS_FILE = "/nonexistent/path.json"
        core.settings._settings_cache = {}
        core.settings._settings_mtime = 0
        core.settings._settings_last_check = 0

        result = _load_settings()
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
