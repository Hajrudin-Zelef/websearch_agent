#!/bin/bash
# ============================================================================
# docker-entrypoint.sh — Initialisation au démarrage du conteneur
# ============================================================================

set -e

echo "╔══════════════════════════════════════════╗"
echo "║   WebSearch Agent — Starting             ║"
echo "╚══════════════════════════════════════════╝"

# 1. Créer les dossiers de données si absents
mkdir -p /app/data/logs

# 2. Initialiser settings.json si absent
if [ ! -f /app/data/settings.json ]; then
    echo '{}' > /app/data/settings.json
    echo "  ✅ settings.json created"
fi

# 3. Initialiser la base de données si absente
if [ ! -f /app/data/threads.db ]; then
    touch /app/data/threads.db
    echo "  ✅ threads.db created"
fi

if [ ! -f /app/data/metrics.db ]; then
    touch /app/data/metrics.db
    echo "  ✅ metrics.db created"
fi

# 4. Fixer les permissions pour appuser (uid 1000)
chown -R 1000:1000 /app/data 2>/dev/null || true

# 5. Vérifier les variables d'environnement critiques
if [ -z "$PROVIDER" ]; then
    echo "  ⚠️  PROVIDER not set, defaulting to openrouter"
    export PROVIDER=openrouter
fi

if [ -z "$OPENROUTER_API_KEY" ] && [ "$PROVIDER" = "openrouter" ]; then
    echo "  ❌ OPENROUTER_API_KEY is required"
    exit 1
fi

echo "  ✅ Provider: $PROVIDER"
echo "  ✅ Data dir: /app/data"
echo ""

# 6. Lancer l'application
exec "$@"
