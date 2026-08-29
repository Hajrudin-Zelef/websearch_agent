#!/usr/bin/env python3
"""
Script de configuration mcporter avec les credentials depuis settings.json.
Usage: python3 scripts/configure_mcporter.py
"""

import json
import subprocess
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.settings import _get_setting


def get_credential(key: str) -> str:
    """Lit un credential depuis settings.json."""
    return _get_setting("api_keys", key, "") or ""


def configure_mcporter_server(name: str, env_vars: dict) -> bool:
    """
    Configure un serveur mcporter avec les variables d'environnement.
    """
    try:
        # Vérifier si le serveur existe déjà
        result = subprocess.run(
            ["mcporter", "config", "get", name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Si le serveur existe, on le supprime d'abord
        if result.returncode == 0:
            subprocess.run(
                ["mcporter", "config", "remove", name],
                capture_output=True,
                timeout=10,
            )
        
        # Construire les arguments pour ajouter le serveur
        cmd = ["mcporter", "config", "add", name]
        
        # Ajouter les variables d'environnement
        for key, value in env_vars.items():
            if value and value != "***":
                cmd.extend(["--env", f"{key}={value}"])
        
        # Ajouter le serveur
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            print(f"  ✓ {name} configuré")
            return True
        else:
            print(f"  ✗ {name} échoué: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"  ✗ {name} erreur: {e}")
        return False


def main():
    print("Configuration mcporter avec credentials agent-reach...\n")
    
    # Configuration des serveurs
    servers = {
        "exa": {
            "EXA_API_KEY": get_credential("EXA_API_KEY"),
        },
        "xiaohongshu": {
            "XIAOHONGSHU_COOKIES_FILE": get_credential("XIAOHONGSHU_COOKIES_FILE"),
        },
        "linkedin": {
            "LINKEDIN_EMAIL": get_credential("LINKEDIN_EMAIL"),
            "LINKEDIN_PASSWORD": get_credential("LINKEDIN_PASSWORD"),
        },
        "bosszhipin": {
            "BOSSZHIPIN_COOKIES_FILE": get_credential("BOSSZHIPIN_COOKIES_FILE"),
        },
    }
    
    success_count = 0
    total = len(servers)
    
    for name, env_vars in servers.items():
        if configure_mcporter_server(name, env_vars):
            success_count += 1
    
    print(f"\n{success_count}/{total} serveurs configurés")
    
    # Lister les serveurs configurés
    print("\nServeurs mcporter:")
    subprocess.run(["mcporter", "config", "list"], timeout=10)


if __name__ == "__main__":
    main()
