"""
Settings runtime — lecture/écriture de settings.json avec cache TTL.
Extrait de agent.py lors du refactoring.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import time
import threading
import logging

logger = logging.getLogger("websearch-agent.settings")

_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "settings.json")
_settings_cache: dict = {}
_settings_mtime: float = 0
_settings_last_check: float = 0
_SETTINGS_CACHE_TTL = 30.0  # 30s entre chaque vérification
_settings_lock = threading.Lock()


def _load_settings() -> dict:
    """Charge les settings depuis settings.json (avec cache TTL 30s). Retourne une copie."""
    global _settings_cache, _settings_mtime, _settings_last_check
    now = time.monotonic()
    with _settings_lock:
        if now - _settings_last_check < _SETTINGS_CACHE_TTL:
            return copy.deepcopy(_settings_cache)
        _settings_last_check = now
        try:
            mtime = os.path.getmtime(_SETTINGS_FILE)
            if mtime != _settings_mtime:
                with open(_SETTINGS_FILE) as f:
                    _settings_cache = json.load(f)
                _settings_mtime = mtime
        except FileNotFoundError:
            _settings_cache = {}
        except json.JSONDecodeError as e:
            logger.error("Failed to parse settings.json: %s", e)
            _settings_cache = {}
        return copy.deepcopy(_settings_cache)


def _save_settings(settings: dict) -> None:
    """Ecrit les settings dans settings.json de maniere atomique et invalide le cache."""
    global _settings_cache, _settings_mtime, _settings_last_check
    # Ensure data directory exists
    data_dir = os.path.dirname(_SETTINGS_FILE)
    os.makedirs(data_dir, exist_ok=True)
    with _settings_lock:
        # Atomic write: temp file + os.replace
        try:
            fd, tmp_path = tempfile.mkstemp(dir=data_dir, suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(fd)
            os.replace(tmp_path, _SETTINGS_FILE)
        except Exception as e:
            logger.error("Failed to save settings: %s", type(e).__name__)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        _settings_cache = copy.deepcopy(settings)
        _settings_mtime = os.path.getmtime(_SETTINGS_FILE)
        _settings_last_check = time.monotonic()


def _update_settings(section: str, data: dict) -> dict:
    """Met a jour une section des settings et ecrit sur disque."""
    settings = _load_settings()
    settings[section] = data
    _save_settings(settings)
    return settings


def _get_setting(section: str, key: str, default=None):
    """Lit un parametre depuis settings.json."""
    settings = _load_settings()
    return settings.get(section, {}).get(key, default)
