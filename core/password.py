"""
Gestion sécurisée des mots de passe — Argon2id + migration legacy.
"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger("websearch-agent")

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    """Hash un mot de passe avec Argon2id."""
    return _ph.hash(plain)


def verify_password(plain: str, stored: str) -> bool:
    """Vérifie un mot de passe contre un hash Argon2id."""
    try:
        _ph.verify(stored, plain)
        return True
    except VerifyMismatchError:
        return False


def migrate_legacy_password(env_path: Path) -> dict:
    """
    Migration rétrocompatible: ADMIN_PASSWORD (clair) → ADMIN_PASSWORD_HASH.
    - Si ADMIN_PASSWORD existe et ADMIN_PASSWORD_HASH absent → hash + écrire + supprimer l'ancien
    - Sinon → rien
    Retourne {"migrated": bool, "password": str | None}
    """
    if not env_path.exists():
        return {"migrated": False, "password": None}

    lines = env_path.read_text().splitlines()
    env = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()

    legacy_password = env.get("ADMIN_PASSWORD")
    existing_hash = env.get("ADMIN_PASSWORD_HASH")

    if not legacy_password or existing_hash:
        # Si le hash existe mais le password en clair aussi, nettoyer le password en clair
        if existing_hash and legacy_password:
            new_lines = []
            for l in lines:
                stripped = l.strip()
                # Garder ADMIN_PASSWORD_HASH, supprimer ADMIN_PASSWORD (sans HASH)
                if stripped.startswith("ADMIN_PASSWORD=") and not stripped.startswith("ADMIN_PASSWORD_HASH="):
                    continue
                new_lines.append(l)
            env_path.write_text("\n".join(new_lines) + "\n")
        return {"migrated": False, "password": legacy_password}

    # Hasher le mot de passe legacy
    password_hash = hash_password(legacy_password)
    logger.warning("ADMIN_PASSWORD legacy migré vers ADMIN_PASSWORD_HASH")

    # Réécrire le fichier .env
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("ADMIN_PASSWORD="):
            new_lines.append(f"ADMIN_PASSWORD_HASH={password_hash}")
        elif stripped.startswith("ADMIN_PASSWORD_HASH="):
            pass  # Skip, on vient de l'ajouter
        else:
            new_lines.append(line)

    # Si ADMIN_PASSWORD_HASH n'était pas dans le fichier, l'ajouter
    content_after = "\n".join(new_lines)
    if "ADMIN_PASSWORD_HASH=" not in content_after:
        # Insérer après ADMIN_PASSWORD ou à la fin
        inserted = False
        final_lines = []
        for line in new_lines:
            final_lines.append(line)
            if line.strip().startswith("ADMIN_PASSWORD=") and not inserted:
                final_lines.append(f"ADMIN_PASSWORD_HASH={password_hash}")
                inserted = True
        if not inserted:
            final_lines.append(f"ADMIN_PASSWORD_HASH={password_hash}")
        new_lines = final_lines

    env_path.write_text("\n".join(new_lines) + "\n")
    return {"migrated": True, "password": legacy_password}
