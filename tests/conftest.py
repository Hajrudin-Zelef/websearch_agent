"""
Configuration des tests CI — variables d'env pour l'authentification.
setdefault ne ecrase pas les vraies valeurs si un .env local est charge.
"""

import os

os.environ.setdefault("ADMIN_USER", "admin")
os.environ.setdefault("ADMIN_TOTP_SECRET", "VEUJD46PMPRPWXDLHILDF2GMI7BWAXV7")

if not os.environ.get("ADMIN_PASSWORD_HASH"):
    from argon2 import PasswordHasher

    ph = PasswordHasher()
    os.environ["ADMIN_PASSWORD_HASH"] = ph.hash("admin123")
