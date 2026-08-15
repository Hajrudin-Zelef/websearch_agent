# Installation Complète - WebSearch Agent

Guide d'installation ultra-complet pour toutes les plateformes.

---

## Table des matières

1. [Prérequis](#1-prérequis)
2. [Installation manuelle](#2-installation-manuelle)
3. [Installation avec Docker](#3-installation-avec-docker)
4. [Configuration](#4-configuration)
5. [Sources de données](#5-sources-de-données)
6. [Utilisation](#6-utilisation)
7. [Déploiement production](#7-déploiement-production)
8. [Dépannage](#8-dépannage)
9. [FAQ](#9-faq)

---

## 1. Prérequis

### Système requis

| Composant | Minimum | Recommandé |
|-----------|---------|------------|
| OS | Linux, macOS, Windows (WSL2) | Ubuntu 22.04+ |
| Python | 3.11+ | 3.13 |
| RAM | 512 Mo | 2 Go |
| Disque | 200 Mo | 1 Go |
| Réseau | Internet | Internet haut débit |

### Comptes requis

| Service | Usage | Lien inscription |
|---------|-------|------------------|
| OpenRouter | LLM (obligatoire) | https://openrouter.ai |
| Perplexity | Recherche web (optionnel) | https://perplexity.ai |
| Tavily | Recherche web (optionnel) | https://tavily.com |
| Brave Search | Recherche web (optionnel) | https://brave.com/search/api/ |
| Firecrawl | Recherche web (optionnel) | https://firecrawl.dev |
| ScrapeGraph AI (Just Scrape) | Recherche web (optionnel) | https://scrapegraphai.com |
| GitHub | Token optionnel | https://github.com/settings/tokens |

---

## 2. Installation manuelle

### 2.1 Cloner le dépôt

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
```

### 2.2 Créer l'environnement virtuel

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Windows (CMD)
python -m venv venv
venv\Scripts\activate.bat
```

### 2.3 Installer les dépendances

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.4 Configurer les variables d'environnement

```bash
cp .env.example .env
```

Éditer `.env` avec vos clés API :

```bash
# Linux / macOS
nano .env

# Windows
notepad .env
```

### 2.5 Vérifier l'installation

```bash
python -c "
from agent import TOOLS, TOOL_FUNCTIONS
print(f'{len(TOOLS)} outils chargés')
print('Installation OK')
"
```

### 2.6 Tester

```bash
python agent.py "qu'est-ce que le W3C ?"
```

### 2.7 Creer le repertoire data (pour les threads SQLite)

```bash
mkdir -p data
```

---

## 3. Installation avec Docker

### 3.1 Prérequis Docker

```bash
# Installer Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Vérifier
docker --version
docker compose version
```

### 3.2 Construire et démarrer

```bash
# Cloner le dépôt
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent

# Configurer
cp .env.example .env
nano .env  # Ajouter vos clés API

# Démarrer
docker compose up -d

# Vérifier
docker compose ps
docker compose logs websearch-agent
```

### 3.3 Services démarrés

| Service | Port | Description |
|---------|------|-------------|
| websearch-agent | 4500 | API principale |
| searxng | 8086 | Meta-moteur de recherche |

### 3.4 Commandes Docker utiles

```bash
# Voir les logs
docker compose logs -f websearch-agent

# Redémarrer
docker compose restart websearch-agent

# Arrêter
docker compose down

# Reconstruire après modification
docker compose up -d --build

# Nettoyer
docker compose down -v
```

---

## 4. Configuration

### 4.1 Variables d'environnement

#### Obligatoires

```bash
# Fournisseur LLM
PROVIDER=openrouter

# Clé API OpenRouter (https://openrouter.ai/keys)
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

#### Optionnelles - Recherche web

```bash
# Perplexity (https://perplexity.ai/settings/api)
PERPLEXITY_API_KEY=pplx-xxxxx

# Tavily (https://tavily.com)
TAVILY_API_KEY=tvly-xxxxx

# Brave Search (https://brave.com/search/api/)
BRAVE_API_KEY=BSAxxxxx

# Firecrawl (https://firecrawl.dev)
FIRECRAWL_API_KEY=fc-xxxxx

# ScrapeGraph AI / Just Scrape (https://scrapegraphai.com)
SGAI_API_KEY=sgai-xxxxx
```

#### Optionnelles - Autres

```bash
# GitHub (optionnel, 5000 req/h au lieu de 60)
GITHUB_TOKEN=ghp_xxxxx

# SearXNG (défaut: instance publique)
SEARXNG_URL=http://localhost:8086
```

### 4.2 Obtenir les clés API

#### OpenRouter (obligatoire)

1. Aller sur https://openrouter.ai
2. Créer un compte
3. Aller sur https://openrouter.ai/keys
4. Créer une clé
5. Copier dans `.env`

#### Perplexity (optionnel)

1. Aller sur https://perplexity.ai
2. Créer un compte
3. Aller sur Settings > API
4. Générer une clé
5. Copier dans `.env`

#### Tavily (optionnel)

1. Aller sur https://tavily.com
2. Créer un compte
3. Copier la clé API
4. Coller dans `.env`

#### Brave Search (optionnel)

1. Aller sur https://brave.com/search/api/
2. S'inscrire au plan gratuit (2000 req/mois)
3. Copier la clé
4. Coller dans `.env`

#### Firecrawl (optionnel)

1. Aller sur https://firecrawl.dev
2. Créer un compte
3. Copier la clé API
4. Coller dans `.env`

#### ScrapeGraph AI / Just Scrape (optionnel)

1. Aller sur https://scrapegraphai.com
2. Créer un compte
3. Copier la clé API
4. Coller dans `.env`

### 4.3 Configuration SearXNG

Par défaut, le système utilise l'instance publique `https://search.inetol.net`.

Pour utiliser une instance locale (recommandé) :

```bash
# Avec Docker (inclus dans docker-compose.yml)
# accessible sur http://localhost:8086

# Sans Docker, installer SearXNG manuellement
# https://docs.searxng.org/admin/installation.html
```

---

## 5. Sources de données

### 5.1 Détail des sources

13 sources au total, réparties sur les 3 niveaux du routeur intelligent (un outil peut apparaître à plusieurs niveaux) :

| Source | Niveaux | Outil | Cle requise | Description |
|--------|---------|-------|--------------|-------------|
| Perplexity | 1, 2, 3 | `perplexity_search` | Oui | Recherche web IA avec citations |
| Tavily | 2, 3 | `tavily_search` | Oui | Recherche web optimisée agents |
| Brave | 3 | `brave_search` | Oui | Moteur privé sans tracking |
| DuckDuckGo | 3 | `duckduckgo_search` | Non | Moteur privé gratuit |
| SearXNG | 1, 2, 3 | `searxng_search` | Non | Meta-moteur open-source |
| Firecrawl | 2, 3 | `firecrawl_search` | Oui | Recherche avec extraction de contenu complet |
| Just Scrape | 3 | `just_scrape_search` | Oui | ScrapeGraph AI intelligent |
| Research | 1, 2, 3 | `research_search` | Non | Recherche approfondie Wikipedia FR/EN |
| Wikipedia FR | 2, 3 | `wikipedia_search` | Non | Encyclopédie française |
| Wikipedia EN | 2, 3 | `wikipedia_en_search` | Non | Encyclopédie anglaise |
| GitHub | 3 | `github_search` | Optionnel | Repositories et code |
| News | 3 | `news_search` | Non | 112 flux RSS |
| Datasets | 3 | `datasets_search` | Non | ~1000 datasets publics |

### 5.2 Routeur intelligent

Le routeur sélectionne automatiquement les outils selon :

- **Intention** : search, explain, compare, news, code, data, recommend, howto, definition, history, technical, finance, science
- **Domaine** : tech, science, history, geography, philosophy, art
- **Complexité** : Score 0-100 déterminant le niveau (1, 2 ou 3)

Nombre d'outils par niveau : le niveau 1 démarre à 3 outils de base (plafonné à 4 avec les outils boostés par intention/domaine), le niveau 2 à 7 (sans plafond), le niveau 3 à 13 (tous les outils disponibles).

### 5.3 Pool de modèles

| Modèle | Poids | Timeout | Usage |
|--------|-------|---------|-------|
| llama-4-maverick | 3 | 8s | Principal |
| qwen-2.5-7b | 2 | 10s | Backup |
| qwen3-8b | 2 | 12s | Backup |
| deepseek-chat-v3 | 1 | 10s | Alternatif |
| mistral-small-3.1 | 1 | 10s | Alternatif |

---

## 6. Utilisation

### 6.1 Ligne de commande

```bash
# Recherche simple
python agent.py "qu'est-ce que le W3C ?"

# Actualités
python agent.py "dernières actualités IA"

# Code
python agent.py "github langchain"

# Comparaison
python agent.py "comparaison React vs Vue.js"

# Données
python agent.py "dataset climat"
```

### 6.2 API REST

#### Démarrer le serveur

```bash
# Développement
uvicorn server:app --reload

# Production (écoute en local uniquement — recommandé,
# voir la section 7 pour exposer via un reverse proxy)
uvicorn server:app --host 127.0.0.1 --port 4500 --loop uvloop --http httptools --workers 4
```

> ⚠️ N'utilisez `--host 0.0.0.0` que si vous savez exactement ce que vous faites : cela expose l'API sur toutes les interfaces réseau, potentiellement Internet, sans authentification (voir le finding C2 de l'audit de sécurité). La configuration recommandée est `127.0.0.1` derrière un reverse proxy (section 7.2).

#### Endpoints

```bash
# Health check
curl http://localhost:4500/health

# Recherche (chat, avec follow-up et citations)
curl -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "qu\'est-ce que le W3C ?"}'

# Recherche structurée (pour providers externes type DeepSeek Harness)
curl "http://localhost:4500/search?q=climat&max_results=10"

# Datasets
curl "http://localhost:4500/datasets?query=climat&max_results=5"
```

#### Réponse `/chat`

```json
{
  "response": "Le W3C (World Wide Web Consortium) est un organisme... [1] [2]",
  "refused": false,
  "thread_id": "5595c0fb-8ffe-41f7-a1d1-0eb4fc19f37a"
}
```

#### Réponse `/search`

```json
{
  "sources": [
    {"url": "https://...", "title": "...", "snippet": "..."}
  ],
  "query": "climat",
  "count": 8,
  "truncated": false
}
```

Guide d'integration API complet : [API.md](API.md)

### 6.3 Service systemd

Le service tourne en systemd **système** (pas `--user`), car il doit démarrer indépendamment d'une session utilisateur ouverte et survivre aux reconnexions SSH.

```bash
# Installer le service
sudo cp websearch-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable websearch-agent
sudo systemctl start websearch-agent

# Commandes
sudo systemctl status websearch-agent
sudo systemctl restart websearch-agent
sudo systemctl stop websearch-agent
sudo journalctl -u websearch-agent -f
```

### 6.4 Docker

```bash
# Démarrer
docker compose up -d

# Logs
docker compose logs -f

# Arrêter
docker compose down
```

---

## 7. Déploiement production

### 7.1 Recommandations

| Aspect | Recommandation |
|--------|----------------|
| Serveur | 2+ CPU, 2+ Go RAM |
| OS | Ubuntu 22.04 LTS |
| Reverse proxy | Nginx / Caddy |
| SSL | Let's Encrypt |
| Monitoring | Prometheus + Grafana |
| Logs | journald / syslog |

### 7.2 Nginx (reverse proxy)

```nginx
server {
    listen 80;
    server_name search.votredomaine.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name search.votredomaine.com;

    ssl_certificate /etc/letsencrypt/live/search.votredomaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/search.votredomaine.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:4500;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
}
```

### 7.3 Docker Compose production

```yaml
version: "3.8"

services:
  websearch-agent:
    build: .
    restart: always
    ports:
      - "127.0.0.1:4500:4500"
    env_file:
      - .env
    environment:
      - PROVIDER=openrouter
      - SEARXNG_URL=http://searxng:8080
    depends_on:
      searxng:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 1G
    networks:
      - websearch

  searxng:
    image: searxng/searxng:latest
    restart: always
    ports:
      - "127.0.0.1:8086:8080"
    volumes:
      - searxng-data:/etc/searxng
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080"]
      interval: 30s
      timeout: 5s
      retries: 3
    networks:
      - websearch

volumes:
  searxng-data:

networks:
  websearch:
    driver: bridge
```

### 7.4 Monitoring

```bash
# Vérifier les métriques
curl http://localhost:4500/health

# Logs en temps réel (service systemd)
sudo journalctl -u websearch-agent -f

# Docker
docker compose logs --tail=100 -f
```

---

## 8. Dépannage

### 8.1 Erreurs courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `PERPLEXITY_API_KEY non definie` | Clé API manquante | Ajouter dans `.env` |
| `Variable OPENROUTER_API_KEY non definie` | Clé API manquante | Ajouter dans `.env` |
| `Rate limit atteint` | Trop de requêtes | Attendre 1 minute |
| `429 Too Many Requests` | API tier limitée | Réduire la fréquence |
| `Timeout` | Modèle trop lent | Le fallback fonctionne automatiquement |
| `Connection refused` | Serveur non démarré | `sudo systemctl start websearch-agent` ou `docker compose up` |

### 8.2 Vérifications

```bash
# Vérifier Python
python --version

# Vérifier les dépendances
pip list | grep -E "openai|fastapi|requests"

# Vérifier le .env
cat .env | grep -v "KEY\|TOKEN"  # Sans les secrets

# Tester l'agent
python agent.py "test"

# Tester le serveur
curl http://localhost:4500/health
```

### 8.3 Logs

```bash
# Logs Python
python agent.py "test" 2>&1 | tee debug.log

# Logs serveur (service systemd)
sudo journalctl -u websearch-agent -f

# Logs Docker
docker compose logs websearch-agent
docker compose logs searxng
```

---

## 9. FAQ

### Q: Combien coûte l'utilisation ?

| Service | Gratuit | Payant |
|---------|---------|--------|
| OpenRouter | Crédits de bienvenue | ~$0.001/req |
| Perplexity | - | ~$0.002/req |
| Tavily | 1000 req/mois | ~$0.001/req |
| Brave | 2000 req/mois | $3/mois |
| Firecrawl | Crédits d'essai | Variable selon plan |
| ScrapeGraph AI | Crédits d'essai | Variable selon plan |
| DuckDuckGo | Illimité | - |
| SearXNG | Illimité | - |

### Q: Quel modèle LLM utiliser ?

Par défaut : `meta-llama/llama-4-maverick` (via OpenRouter)

Le système sélectionne automatiquement un modèle aléatoirement parmi :
- llama-4-maverick
- qwen-2.5-7b
- qwen3-8b
- deepseek-chat-v3
- mistral-small-3.1

### Q: Comment ajouter une source ?

1. Créer `sources/ma_source.py` avec une fonction `ma_source_search(query) -> list[dict]`
2. L'ajouter dans `sources/__init__.py` (dans `_LAZY_IMPORTS` et `SOURCES`)
3. L'ajouter dans `TOOLS_REGISTRY` dans `agent.py`
4. L'ajouter dans `sources/router.py` (dans `TOOL_LEVELS`, et éventuellement `TOOL_KEYWORD_INDEX`)

### Q: Le serveur est-il sécurisé ?

- Authentification admin avec 2FA (TOTP)
- Rate limiting (30 req/min par IP)
- Validation Pydantic des entrées
- Body size limit (10 KB max)
- Headers de sécurité (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- CORS whitelist explicite
- Pas d'exécution de code utilisateur
- Variables d'environnement pour les secrets
- `.env` dans `.gitignore`
- Clés API clients hashées (SHA-256) en base

### Q: Comment mettre à jour ?

```bash
git pull
pip install -r requirements.txt
# Redémarrer le serveur
sudo systemctl restart websearch-agent
```

---

## Support

- GitHub : https://github.com/Hajrudin-Zelef/websearch_agent
- Issues : https://github.com/Hajrudin-Zelef/websearch_agent/issues
