"""
Settings runtime — lecture de settings.json avec cache TTL.
Extrait de agent.py lors du refactoring.
"""

import os
import json
import time
import threading

_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
_settings_cache: dict = {}
_settings_mtime: float = 0
_settings_last_check: float = 0
_SETTINGS_CACHE_TTL = 30.0  # 30s entre chaque vérification
_settings_lock = threading.Lock()


def _load_settings() -> dict:
    """Charge les settings depuis settings.json (avec cache TTL 30s)."""
    global _settings_cache, _settings_mtime, _settings_last_check
    now = time.monotonic()
    with _settings_lock:
        if now - _settings_last_check < _SETTINGS_CACHE_TTL:
            return _settings_cache
        _settings_last_check = now
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
