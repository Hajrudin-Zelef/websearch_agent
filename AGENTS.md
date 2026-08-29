# WebSearch Agent — Règles du projet

## Aperçu

Agent IA de recherche web multi-sources avec interface admin. L'agent orchestre parallèlement 20+ sources de recherche (SearXNG, Tavily, DuckDuckGo, Exa, Firecrawl, Brave, etc.) et synthétise les résultats via des LLMs (OpenRouter/DeepSeek).

## Stack technique

- **Backend** : Python 3.13 / FastAPI / Uvicorn (uvloop + httptools)
- **Base de données** : SQLite (threads.db, metrics.db)
- **Conteneurs** : Docker multi-stage + Docker Compose
- **Reverse proxy** : SearXNG (meta search engine)
- **Auth** : JWT + Argon2id + TOTP 2FA
- **Sécurité** : SSRF protection, rate limiting, CORS, audit logging

## Architecture

```
server.py          → FastAPI bootstrap, middleware, montage des routes
agent.py           → Orchestrateur IA : function-calling, exécution parallèle des outils
threads.py         → Gestion des threads/conversations (SQLite)
clients.py         → Clients HTTP partagés
core/              → Modules métier extraits :
  ├── settings.py      → Lecture de settings.json
  ├── cache.py         → Cache LRU
  ├── models.py        → Pool de modèles LLM + clients OpenAI
  ├── prompts.py       → Prompts système et détection de refus
  ├── parser.py        → Parsing DSML et JSON
  ├── tools.py         → Registry des outils de recherche
  ├── circuit_breaker.py → Circuit breaker pour résilience
  ├── events.py        → Système d'événements
  ├── monitoring.py    → Métriques et monitoring
  ├── password.py      → Gestion des mots de passe (Argon2id)
  └── ssrf.py          → Protection SSRF
routes/            → Endpoints HTTP :
  ├── api.py           → /chat, /search, /datasets, /health, /threads
  ├── auth.py          → Authentification, sessions, 2FA
  ├── admin.py         → Endpoints /admin/*
  ├── oauth.py         → OAuth flows
  └── rate_limit.py    → Rate limiting
sources/           → 22 connecteurs de recherche (MoE routing) :
  ├── tavily.py, duckduckgo.py, searxng.py, brave.py, yacy.py
  ├── exa.py, firecrawl_search.py, perplexity.py
  ├── wikipedia.py, github.py, youtube.py, news_rss.py
  ├── brightdata.py, just_scrape.py, querit.py, langsearch.py
  ├── agent_reach.py, agent_reach_wrappers.py
  └── router.py        → Routage intelligent (MoE scoring, 26 domaines)
admin/             → Interface d'administration (frontend)
data/              → Données runtime (SQLite, logs, settings)
tests/             → Tests pytest (19 fichiers)
scripts/           → Scripts utilitaires
```

## Commandes

### Développement

```bash
# Installer les dépendances
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Lancer en dev (hot reload)
uvicorn server:app --host 127.0.0.1 --port 4500 --reload

# Ou via Docker Compose
docker compose up --build
```

### Tests

```bash
# Tous les tests
pytest tests/ -v

# Tests spécifiques
pytest tests/test_auth.py -v
pytest tests/test_cache.py -v
pytest tests/test_models.py -v
```

### Lint & Formatage

```bash
# Linting (ruff)
ruff check .

# Formatage
ruff format .

# Auto-fix lint
ruff check --fix .
```

### Déploiement

```bash
# Build image Docker
docker compose build

# Deploy (systemd)
sudo systemctl restart websearch-agent

# Backup/Restore
./backup.sh
./restore.sh
```

## Fichiers de configuration

- `.env` → Variables d'environnement (clés API, config admin)
- `.env.example` → Template des variables d'environnement
- `data/settings.json` → Settings de l'agent (modèles, outils, comportement)
- `docker-compose.yml` → Orchestration Docker

## Conventions de code

- **Langage** : Code comments et docstrings en français
- **Imports** : Toujours `from dotenv import load_dotenv` + `load_dotenv()` au début
- **Logging** : `logging.getLogger("websearch-agent")` pour le logger principal
- **Audit** : `logging.getLogger("websearch-agent.audit")` pour les actions sensibles
- **Fichiers .bak** : Backup automatique avant modifications critiques (format: `*.bak.YYYYMMDD_HHMM`)
- **Routes** : Extraire dans `routes/` quand un fichier dépasse ~300 lignes
- **Sources** : Chaque connecteur de recherche est un fichier autonome dans `sources/`

## Sécurité

- **Ne jamais** commit de clés API, tokens, ou mots de passe
- **Ne jamais** désactiver la protection SSRF sauf en dev local
- **Rate limiting** : implémenté sur les endpoints sensibles
- **Audit log** : toutes les actions admin sont loguées dans `data/audit.log`
- **Docker** : conteneurs en `read_only`, `no-new-privileges`, `cap_drop: ALL`
- **Admin** : 2FA obligatoire en production (TOTP)

## Obligation de skills

AVANT toute implémentation, modification de code, ou réponse technique :
1. Identifier le skill pertinent dans `.agents/skills/`
2. Le charger avec l'outil `skill`
3. Suivre ses instructions exactement

### Matrice de correspondance Tâche → Skill

| Tâche | Skills à charger |
|-------|-----------------|
| UI/Frontend/Responsive | `frontend-design` → `web-design-guidelines` → `ui-ux-pro-max` |
| Bug/Debug | `diagnosing-bugs` → `systematic-debugging` |
| Code Review | `code-review` → `webapp-testing` |
| Design/Polish | `impeccable` → `design-taste-frontend` |
| Planification | `brainstorming` → `writing-plans` |
| Refactor | `refactoring` → `simple-design` |
| API/Backend | `python-pro` |
| Sécurité | `security-review` → `secure-coding` |
| Testing | `test-driven-development` → `test-generator` |
| Déploiement | `containers` → `docker-expert` |

### Règle

Ne jamais implémenter sans avoir chargé au moins un skill pertinent.
Si aucun skill ne correspond, le signaler avant de continuer.
