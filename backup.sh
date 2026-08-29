#!/bin/bash
# ============================================================================
# backup.sh — Sauvegarde complète de WebSearch Agent
# Usage: ./backup.sh [destination_path]
# Exemple: ./backup.sh /tmp/websearch-backup
# ============================================================================

set -euo pipefail

DEST="${1:-/tmp/websearch-backup-$(date +%Y%m%d-%H%M%S)}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "╔══════════════════════════════════════════╗"
echo "║   WebSearch Agent — Backup               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Source: $APP_DIR"
echo "Destination: $DEST"
echo ""

# 1. Créer la structure
echo "📁 Création de la structure..."
mkdir -p "$DEST/data" "$DEST/logs"

# 2. Sauvegarder les fichiers critiques
echo "📋 Sauvegarde des fichiers..."
cp "$APP_DIR/.env" "$DEST/.env" 2>/dev/null && echo "  ✅ .env" || echo "  ⚠️  .env non trouvé"
cp "$APP_DIR/websearch-agent.service" "$DEST/websearch-agent.service" 2>/dev/null && echo "  ✅ service systemd" || echo "  ⚠️  service non trouvé"
cp "$APP_DIR/docker-compose.yml" "$DEST/docker-compose.yml" 2>/dev/null && echo "  ✅ docker-compose.yml" || echo "  ⚠️  docker-compose non trouvé"
cp "$APP_DIR/Dockerfile" "$DEST/Dockerfile" 2>/dev/null && echo "  ✅ Dockerfile" || echo "  ⚠️  Dockerfile non trouvé"
cp "$APP_DIR/requirements.txt" "$DEST/requirements.txt" 2>/dev/null && echo "  ✅ requirements.txt" || echo "  ⚠️  requirements.txt non trouvé"
cp "$APP_DIR/install.sh" "$DEST/install.sh" 2>/dev/null && echo "  ✅ install.sh" || echo "  ⚠️  install.sh non trouvé"
cp "$APP_DIR/backup.sh" "$DEST/backup.sh" 2>/dev/null && echo "  ✅ backup.sh" || echo "  ⚠️  backup.sh non trouvé"
cp "$APP_DIR/restore.sh" "$DEST/restore.sh" 2>/dev/null && echo "  ✅ restore.sh" || echo "  ⚠️  restore.sh non trouvé"
cp "$APP_DIR/docker-entrypoint.sh" "$DEST/docker-entrypoint.sh" 2>/dev/null && echo "  ✅ docker-entrypoint.sh" || echo "  ⚠️  docker-entrypoint.sh non trouvé"

# 3. Sauvegarder les bases de données
echo ""
echo "🗄️  Sauvegarde des bases de données..."
for db in threads.db metrics.db; do
    if [ -f "$APP_DIR/data/$db" ]; then
        # VACUUM pour optimiser avant copie
        sqlite3 "$APP_DIR/data/$db" "VACUUM;" 2>/dev/null || true
        cp "$APP_DIR/data/$db" "$DEST/data/$db"
        echo "  ✅ $db ($(du -h "$APP_DIR/data/$db" | cut -f1))"
    fi
done

# 4. Sauvegarder settings.json et custom_domains.json
if [ -f "$APP_DIR/data/settings.json" ]; then
    cp "$APP_DIR/data/settings.json" "$DEST/data/settings.json"
    echo "  ✅ settings.json"
fi
if [ -f "$APP_DIR/data/custom_domains.json" ]; then
    cp "$APP_DIR/data/custom_domains.json" "$DEST/data/custom_domains.json"
    echo "  ✅ custom_domains.json"
fi

# 5. Sauvegarder les logs (optionnel)
if [ -f "$APP_DIR/data/websearch-agent.log" ]; then
    cp "$APP_DIR/data/websearch-agent.log" "$DEST/logs/websearch-agent.log"
    echo "  ✅ logs websearch-agent"
fi
if [ -f "$APP_DIR/data/audit.log" ]; then
    cp "$APP_DIR/data/audit.log" "$DEST/logs/audit.log"
    echo "  ✅ logs audit"
fi

# 6. Sauvegarder la config SearXNG
if [ -d "$APP_DIR/data/searxng" ]; then
    cp -r "$APP_DIR/data/searxng" "$DEST/data/searxng"
    echo "  ✅ config SearXNG"
fi

# 7. Créer un manifest
echo ""
echo "📝 Création du manifest..."
cat > "$DEST/MANIFEST.txt" << EOF
WebSearch Agent — Backup
========================
Date: $(date)
Hostname: $(hostname)
User: $(whoami)

Fichiers sauvegardés:
- .env (variables d'environnement — SENSIBLE)
- data/threads.db (conversations)
- data/metrics.db (métriques)
- data/settings.json (configuration)
- data/custom_domains.json (domaines custom)
- data/searxng/ (config SearXNG)
- websearch-agent.service (systemd)
- docker-compose.yml
- Dockerfile
- docker-entrypoint.sh
- requirements.txt
- install.sh
- backup.sh
- restore.sh
- logs/ (logs serveur)

Pour restaurer:
1. git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
2. cd websearch_agent
3. tar -xzf /chemin/vers/backup.tar.gz -C .
4. ./restore.sh /chemin/vers/backup.tar.gz
EOF
echo "  ✅ MANIFEST.txt"

# 8. Créer l'archive tar.gz
echo ""
echo "📦 Création de l'archive..."
ARCHIVE="${DEST}.tar.gz"
tar -czf "$ARCHIVE" -C "$(dirname "$DEST")" "$(basename "$DEST")"
echo "  ✅ $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ✅ Backup terminé                      ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Archive: $ARCHIVE"
echo ""
echo "⚠️  ATTENTION: Ce backup contient vos clés API (.env)"
echo "   Ne partagez JAMAIS cette archive publiquement."
echo ""
echo "Pour transférer vers le nouveau VPS:"
echo "  scp $ARCHIVE user@nouveau-vps:/tmp/"
echo ""
