# WebSearch Agent

Agent IA de recherche web ultra-rapide avec function-calling. Routage intelligent MoE (Mixture of Experts), 22 sources de données, authentification OAuth2/JWT avec scopes, rate limiting par client, et panneau d'administration complet avec 2FA.

## Démarrage rapide

### Docker (recommandé)

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
cp .env.example .env
nano .env  # Configurer les clés API
docker compose up -d
```

### Manuel

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
uvicorn server:app --host 127.0.0.1 --port 4500 --loop uvloop --http httptools
```

### Installation automatique

```bash
chmod +x install.sh && ./install.sh
```

## Documentation

| Document | Contenu |
|----------|---------|
| [docs-users/README.md](docs-users/README.md) | Présentation complète |
| [docs-users/ARCHITECTURE.md](docs-users/ARCHITECTURE.md) | Architecture technique |
| [docs-users/INSTALL.md](docs-users/INSTALL.md) | Guide d'installation |
| [docs-users/DEPLOYMENT.md](docs-users/DEPLOYMENT.md) | Déploiement et maintenance |
| [docs-users/API.md](docs-users/API.md) | Guide d'intégration API |
| [docs-users/OAUTH.md](docs-users/OAUTH.md) | Authentification OAuth2 |
| [docs-users/TROUBLESHOOT.md](docs-users/TROUBLESHOOT.md) | Guide de dépannage |

## Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/chat` | Recherche conversationnelle |
| GET | `/search` | Recherche structurée |
| GET | `/health` | Health check |
| GET | `/admin` | Panneau d'administration |

## Commandes utiles

```bash
# Health check
curl http://localhost:4500/health

# Recherche
curl -X POST http://localhost:4500/chat -H "Content-Type: application/json" -d '{"message":"test"}'

# Docker
docker compose up -d
docker compose logs -f
docker compose down

# Backup/Restore
./backup.sh /tmp/backup
./restore.sh /tmp/backup.tar.gz
```

## License

Privé — Usage interne uniquement.
