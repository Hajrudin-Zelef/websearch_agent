#!/bin/bash
# ============================================================================
# restore.sh — Restauration complète de WebSearch Agent
# Usage: ./restore.sh /chemin/vers/backup.tar.gz
# ============================================================================

set -euo pipefail

BACKUP="${1:?Usage: ./restore.sh /chemin/vers/backup.tar.gz}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════╗"
echo "║   WebSearch Agent — Restore              ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Archive: $BACKUP"
echo "Destination: $APP_DIR"
echo ""

# 1. Extraire l'archive
echo "📦 Extraction de l'archive..."
TEMP_DIR=$(mktemp -d)
tar -xzf "$BACKUP" -C "$TEMP_DIR"
# Trouver le dossier extrait (peut avoir un nom timestampé)
EXTRACTED=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "websearch-backup*" | head -1)
if [ -z "$EXTRACTED" ]; then
    EXTRACTED="$TEMP_DIR"
fi
echo "  ✅ Extrait dans $EXTRACTED"

# 2. Arrêter le service s'il tourne
echo ""
echo "🛑 Arrêt du service..."
if systemctl is-active --quiet websearch-agent 2>/dev/null; then
    sudo systemctl stop websearch-agent
    echo "  ✅ Service arrêté"
else
    echo "  ℹ️  Service déjà arrêté"
fi

# 3. Sauvegarder l'ancien .env s'il existe
if [ -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env" "$APP_DIR/.env.bak.$(date +%Y%m%d)"
    echo "  ✅ Ancien .env sauvegardé"
fi

# 4. Copier les fichiers
echo ""
echo "📋 Restauration des fichiers..."
for f in .env docker-compose.yml Dockerfile requirements.txt websearch-agent.service install.sh backup.sh restore.sh docker-entrypoint.sh; do
    if [ -f "$EXTRACTED/$f" ]; then
        cp "$EXTRACTED/$f" "$APP_DIR/$f"
        chmod +x "$APP_DIR/$f" 2>/dev/null || true
        echo "  ✅ $f"
    fi
done

# 5. Restaurer les bases de données
echo ""
echo "🗄️  Restauration des bases de données..."
mkdir -p "$APP_DIR/data"
for db in threads.db metrics.db; do
    if [ -f "$EXTRACTED/data/$db" ]; then
        cp "$EXTRACTED/data/$db" "$APP_DIR/data/$db"
        echo "  ✅ $db ($(du -h "$EXTRACTED/data/$db" | cut -f1))"
    fi
done

# 6. Restaurer settings.json et custom_domains.json
if [ -f "$EXTRACTED/data/settings.json" ]; then
    cp "$EXTRACTED/data/settings.json" "$APP_DIR/data/settings.json"
    echo "  ✅ settings.json"
fi
if [ -f "$EXTRACTED/data/custom_domains.json" ]; then
    cp "$EXTRACTED/data/custom_domains.json" "$APP_DIR/data/custom_domains.json"
    echo "  ✅ custom_domains.json"
elif [ ! -f "$APP_DIR/data/custom_domains.json" ]; then
    echo '{}' > "$APP_DIR/data/custom_domains.json"
    echo "  ✅ custom_domains.json créé (vide)"
fi

# 7. Restaurer config SearXNG
if [ -d "$EXTRACTED/data/searxng" ]; then
    cp -r "$EXTRACTED/data/searxng" "$APP_DIR/data/searxng"
    echo "  ✅ config SearXNG"
fi

# 8. Recréer le venv Python
echo ""
echo "🐍 Création du virtualenv Python..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt 2>&1 | tail -3
echo "  ✅ venv créé avec $(pip list 2>/dev/null | wc -l) packages"

# 9. Installer le service systemd
echo ""
echo "⚙️  Installation du service systemd..."
if [ -f "$APP_DIR/websearch-agent.service" ]; then
    sudo cp "$APP_DIR/websearch-agent.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    echo "  ✅ Service systemd installé"
fi

# 10. Démarrer SearXNG (Docker)
echo ""
echo "🐳 Démarrage de SearXNG..."
if command -v docker &> /dev/null; then
    docker compose up -d searxng 2>/dev/null && echo "  ✅ SearXNG démarré" || echo "  ⚠️  SearXNG non démarré (vérifier docker-compose.yml)"
else
    echo "  ⚠️  Docker non installé — SearXNG non démarré"
fi

# 11. Démarrer le service
echo ""
echo "🚀 Démarrage du service..."
sudo systemctl start websearch-agent 2>/dev/null && echo "  ✅ Service démarré" || echo "  ⚠️  Service non démarré"

# 12. Vérification
echo ""
echo "🔍 Vérification..."
sleep 3
if curl -s http://127.0.0.1:4500/health 2>/dev/null | grep -q "ok"; then
    echo "  ✅ Serveur OK — http://127.0.0.1:4500"
else
    echo "  ⚠️  Serveur pas encore prêt (vérifier les logs)"
fi

# 13. Nettoyer
rm -rf "$TEMP_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ✅ Restore terminé                     ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Fichiers restaurés dans: $APP_DIR"
echo ""
echo "Prochaines étapes:"
echo "  1. Vérifier le .env: cat $APP_DIR/.env"
echo "  2. Vérifier le service: sudo systemctl status websearch-agent"
echo "  3. Vérifier les logs: journalctl -u websearch-agent -f"
echo "  4. Tester: curl http://127.0.0.1:4500/health"
echo "  5. Admin: http://$(hostname -I | awk '{print $1}'):4500/admin"
echo ""
