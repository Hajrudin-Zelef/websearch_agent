# DEPLOYMENT — Déploiement et maintenance

> Voir aussi : [ARCHITECTURE.md](ARCHITECTURE.md), [INSTALL.md](INSTALL.md), [TROUBLESHOOT.md](TROUBLESHOOT.md)

---

## Environnements

| Environnement | Usage | URL |
|---------------|-------|-----|
| **Development** | Local | `http://127.0.0.1:4500` |
| **Docker** | Local/Prod | `http://localhost:4500` |
| **Systemd** | Production | `http://0.0.0.0:4500` |

## Docker

### Démarrer

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
cp .env.example .env
nano .env  # Configurer les clés API
docker compose up -d
```

### Commandes

```bash
docker compose up -d          # Démarrer
docker compose down           # Arrêter
docker compose logs -f        # Voir les logs
docker compose ps             # Status
docker compose build --no-cache  # Reconstruire
```

### docker-compose.yml

```yaml
services:
  websearch-agent:
    build: .
    ports: ["127.0.0.1:4500:4500"]
    env_file: .env
    deploy:
      resources:
        limits: { cpus: '2.0', memory: 512M }

  searxng:
    image: searxng/searxng:latest
    ports: ["127.0.0.1:8086:8080"]
```

## Manuel

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
uvicorn server:app --host 127.0.0.1 --port 4500 --loop uvloop --http httptools
```

## Systemd

```ini
[Unit]
Description=WebSearch Agent
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/websearch-agent
ExecStart=/opt/websearch-agent/venv/bin/uvicorn server:app --host 0.0.0.0 --port 4500
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable websearch-agent
sudo systemctl start websearch-agent
sudo systemctl status websearch-agent
sudo systemctl restart websearch-agent
sudo systemctl stop websearch-agent
journalctl -u websearch-agent -f
```

## Variables d'environnement critiques

```bash
# .env
PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
PERPLEXITY_API_KEY=pplx-...
TAVILY_API_KEY=tvly-...
BRAVE_API_KEY=BSA...
JWT_SECRET=your-secret-here
ADMIN_USER=admin
ADMIN_PASSWORD=your-strong-password
ADMIN_TOTP_SECRET=your-totp-secret
```

---

## Maintenance

### Quotidien

| Tâche | Commande |
|-------|----------|
| Vérifier les logs | `tail -f data/websearch-agent.log` |
| Vérifier l'espace disque | `df -h` |
| Vérifier les tests | `pytest tests/ -v` |

### Hebdomadaire

| Tâche | Commande |
|-------|----------|
| Nettoyer les logs | Auto (rotating 5MB, 3 backups) |
| Vérifier les dépendances | `pip list --outdated` |
| Review des erreurs | Dashboard admin → Logs |

### Mensuel

| Tâche | Commande |
|-------|----------|
| Mettre à jour les dépendances | `pip install --upgrade -r requirements.txt` |
| Rotation des credentials | Admin → Clients → Regenerate |
| Backup de la DB | `cp data/threads.db data/threads.db.backup` |
| Review des métriques | Dashboard → Metrics |

### Sauvegarde

```bash
cp data/threads.db data/threads.db.$(date +%Y%m%d).backup
cp data/settings.json data/settings.json.$(date +%Y%m%d).backup
cp .env .env.$(date +%Y%m%d).backup
```

### Mise à jour

```bash
# 1. Sauvegarder
cp data/threads.db data/threads.db.backup
cp .env .env.backup

# 2. Pull
git pull origin main

# 3. Dépendances
source venv/bin/activate
pip install -r requirements.txt

# 4. Redémarrer
sudo systemctl restart websearch-agent
# ou
docker compose up -d --build
```

---

## Dépannage

### Le serveur ne démarre pas

```bash
lsof -i :4500
tail -20 data/websearch-agent.log
cat .env | grep -v "^#" | head -20
```

### Erreur 401 sur /admin

```bash
curl -v -c /tmp/cookies.txt http://127.0.0.1:4500/admin/api/auth/check
CODE=$(python3 -c "import pyotp; print(pyotp.TOTP('your-totp-secret').now())")
curl -c /tmp/cookies.txt -X POST http://127.0.0.1:4500/admin/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"your-password\",\"totp_code\":\"$CODE\"}"
```

### Erreur 429 Rate Limit

```bash
# Attendre 60 secondes
# Ou régénérer l'API key
curl -X POST http://127.0.0.1:4500/admin/clients/{id}/regenerate -H "Cookie: session=..."
```

### Erreur LLM

```bash
curl http://127.0.0.1:4500/admin/env | python3 -m json.tool
curl http://127.0.0.1:4500/admin/models | python3 -m json.tool
```

### DB corrompue

```bash
sqlite3 data/threads.db "PRAGMA integrity_check;"
cp data/threads.db.backup data/threads.db
```

### Memory leak

```bash
curl http://127.0.0.1:4500/metrics | python3 -c "import sys,json; print(json.load(sys.stdin)['cache'])"
curl -X POST http://127.0.0.1:4500/admin/cache/clear
```
