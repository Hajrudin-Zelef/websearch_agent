"""
Conftest pytest — charge le .env AVANT tout import du serveur.
Ceci确保 que ADMIN_PASSWORD_HASH, ADMIN_TOTP_SECRET, etc.
sont dans os.environ quand routes/auth.py est importe.
"""

import os
from pathlib import Path

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env, override=False)
