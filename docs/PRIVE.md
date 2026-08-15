# PRIVE — Livre Blanc Technique

> Voir aussi : [[index]], [[AGENTS]], [[ARCHITECTURE]], [[OAUTH]], [[DEPLOYMENT]], [[API]]

> Document confidentiel — Maîtrise complète de l'application.
> Ce document couvre TOUS les aspects : architecture, code, données, déploiement, maintenance, évolution.

---

# Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture technique](#2-architecture-technique)
3. [Le moteur de recherche](#3-le-moteur-de-recherche)
4. [L'agent IA](#4-lagent-ia)
5. [Authentification et sécurité](#5-authentification-et-sécurité)
6. [Base de données](#6-base-de-données)
7. [Configuration](#7-configuration)
8. [Frontend admin](#8-frontend-admin)
9. [API publique](#9-api-publique)
10. [Tests](#10-tests)
11. [Déploiement](#11-déploiement)
12. [Maintenance](#12-maintenance)
13. [Optimisation des performances](#13-optimisation-des-performances)
14. [Sécurité en profondeur](#14-sécurité-en-profondeur)
15. [Dépannage](#15-dépannage)
16. [Évolution future](#16-évolution-future)
17. [Annexes](#17-annexes)

---

# 1. Vue d'ensemble

## Qu'est-ce que WebSearch Agent ?

Un agent de recherche web IA qui :
- Reçoit une question en naturel
- Détecte l'intention, le domaine, la complexité
- Sélectionne les bons outils de recherche (parmi 13 sources)
- Exécute la recherche en parallèle
- Synthétise les résultats via un LLM
- Retourne une réponse structurée avec citations

## Stack technique

| Couche | Technologie |
|--------|-------------|
| **Backend** | Python 3.13, FastAPI, uvicorn (uvloop + httptools) |
| **Frontend** | HTML/CSS/JS vanilla, Lucide icons, Marked.js |
| **LLM** | OpenRouter (10 modèles, 3 tiers) |
| **Bases de données** | SQLite (WAL mode) pour threads + clients |
| **Cache** | LRU OrderedDict en mémoire (TTL 5min, max 200) |
| **Conteneurs** | Docker multi-stage, docker-compose + SearXNG |
| **Auth** | API Key, OAuth2 JWT, 2FA TOTP |

## Métriques clés

| Métrique | Valeur |
|----------|--------|
| Tests | 126 (unittest + pytest) |
| Sources de recherche | 13 |
| Modèles LLM | 10 (3 tiers) |
| Endpoints API | 25+ |
| Endpoints admin | 25+ |
| Modules métier | 16 |
| Flux RSS | 112 |
| Datasets | ~1000 |

---

# 2. Architecture technique

## Structure des fichiers

```
websearch_agent/
├── server.py              # Point d'entrée FastAPI
├── agent.py               # Cerveau de l'application
├── clients.py             # Gestion des apps clientes
├── threads.py             # Persistance des conversations
│
├── routes/                # Couche API
│   ├── api.py             # Endpoints publics
│   ├── admin.py           # Endpoints admin (25+)
│   ├── auth.py            # Authentification
│   ├── oauth.py           # OAuth2 JWT
│   └── rate_limit.py      # Rate limiting
│
├── core/                  # Logique métier
│   ├── settings.py        # Configuration runtime
│   ├── prompts.py         # Prompts LLM
│   ├── monitoring.py      # Métriques
│   ├── cache.py           # Cache LRU
│   ├── circuit_breaker.py # Protection circuits
│   ├── events.py          # Webhooks
│   ├── models.py          # Pool de modèles
│   ├── parser.py          # Parsing tool calls
│   └── tools.py           # Registry des outils
│
├── sources/               # 13 sources de recherche
│   ├── __init__.py        # Lazy loading + registry
│   ├── router.py          # Routeur intelligent
│   ├── content_extractor.py # Extraction de contenu
│   └── [10 fichiers sources]
│
├── admin/                 # Frontend web
│   ├── index.html         # SPA principale (1840 lignes)
│   ├── js/                # 12 modules JS
│   └── vendor/            # Librairies tierces
│
├── tests/                 # 126 tests
├── data/                  # Données runtime
├── docs/                  # Documentation
└── docker-compose.yml     # Orchestration
```

## Flux de requête complet

```
Client HTTP
    │
    ▼
┌─────────────────────────────────────────┐
│  server.py — FastAPI                    │
│  ├── GZipMiddleware (compression)       │
│  ├── CORSMiddleware (whitelist)         │
│  ├── BodySizeLimitMiddleware (10KB)     │
│  ├── Security headers middleware        │
│  └── admin_auth middleware (session)    │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  Router (api.py / admin.py / oauth.py)  │
│  ├── Auth check (API key / JWT / IP)    │
│  ├── Scope check (read/write/admin)     │
│  ├── Rate limit (sliding window 60s)    │
│  └── Validation Pydantic                │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  agent.py — run_agent_async()           │
│  ├── route_query() → tools selection    │
│  ├── cache check (LRU TTL 5min)         │
│  ├── _pick_random_models(tier)          │
│  ├── _try_model_async()                 │
│  │   ├── LLM call (tool-calling)        │
│  │   ├── Execute tools (parallel 6)     │
│  │   └── Synthesize (2nd LLM call)      │
│  └── Fallback: next model               │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  Sources (13)                           │
│  ├── Perplexity, Tavily, Brave (API)    │
│  ├── DuckDuckGo, SearXNG (gratuit)      │
│  ├── Firecrawl, Just Scrape (extraction)│
│  ├── Wikipedia FR/EN, Research          │
│  ├── GitHub, News RSS (112 flux)        │
│  └── Datasets (~1000)                   │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  Retour au client                       │
│  ├── {response, refused, thread_id}     │
│  ├── Webhook dispatch (async)           │
│  └── Stats monitoring                   │
└─────────────────────────────────────────┘
```

## Middleware — ordre d'exécution

1. **GZipMiddleware** — Compression des réponses > 2KB
2. **CORSMiddleware** — Whitelist origines (localhost:3000,4500,3080)
3. **BodySizeLimitMiddleware** — Rejette les bodies > 10KB (413)
4. **Security headers** — X-Content-Type-Options, X-Frame-Options, Referrer-Policy
5. **admin_auth** — Vérifie session cookie pour /admin/*

---

# 3. Le moteur de recherche

## Les 13 sources

| Source | Type | API Key | Cache | Timeout | Usage |
|--------|------|---------|-------|---------|-------|
| **Perplexity** | Web | Requise | Non | 15s | Recherche intelligente avec citations |
| **Tavily** | Web | Requise | Non | 10s | Recherche optimisée agents IA |
| **Brave** | Web | Requise | Non | 10s | Moteur privé sans tracking |
| **DuckDuckGo** | Web | Non | Non | 10s | Moteur privé gratuit |
| **SearXNG** | Web | Non | Non | 10s | Meta-moteur open-source |
| **Firecrawl** | Web | Requise | Non | 15s | Extraction contenu complet |
| **Just Scrape** | Web | Requise | Non | 15s | Scraping intelligent IA |
| **Research** | Research | Non | Non | 10s | Recherche approfondie |
| **Wikipedia FR** | Encyclopédie | Non | Non | 5s | Questions factuelles FR |
| **Wikipedia EN** | Encyclopédie | Non | Non | 5s | Sujets techniques EN |
| **GitHub** | Code | Optionnel | Non | 10s | Repositories open-source |
| **News** | Actualités | Non | **10min** | 30s | 112 flux RSS |
| **Databases** | Données | Non | Non | 10s | ~1000 datasets publics |

## Lazy loading

Les sources ne sont chargées que lors du premier appel :

```python
# Ceci ne charge PAS les 13 modules :
from sources import SOURCES  # Juste un dict

# Ceci ne charge QUE wikipedia.py :
from sources import wikipedia_search
```

Le lazy loading est implémenté via `__getattr__` dans `sources/__init__.py`.

## Routeur intelligent (sources/router.py)

Le routeur analyse chaque requête et retourne :
- **complexity_score** : 0-100
- **level** : 1 (simple), 2 (moyen), 3 (complexe)
- **tools** : liste des outils à utiliser
- **intents** : intentions détectées
- **domains** : domaines détectés

### Niveaux de complexité

| Niveau | Score | Outils | Exemple |
|--------|-------|--------|---------|
| 1 - Simple | 0-39 | 3 max | "python", "bonjour" |
| 2 - Moyen | 40-64 | 7 | "comparaison React vs Vue.js" |
| 3 - Complexe | 65-100 | 13 | "quel est le meilleur framework AI en 2026" |

### Intentions détectées (12)

`search_general`, `explain`, `compare`, `news`, `code`, `data`, `recommend`, `howto`, `definition`, `history`, `technical`, `finance`, `science`

### Domaines détectés (6)

`tech`, `science`, `history`, `geography`, `philosophy`, `art`

### Signaux de complexité

| Catégorie | Signaux | Poids |
|-----------|---------|-------|
| Structure | "pourquoi", "quel", "?" | +2 à +15 |
| Longueur | < 15 chars | -15, > 60 chars | +15 |
| Connecteurs | "et", "mais", "donc" | +2 à +8 |
| Cognitif | "analyser", "comparer" | +15 à +20 |
| Temporel | "aujourd'hui", "en 2026" | +5 à +8 |
| Quantification | "combien", "statistiques" | +5 à +10 |

### Boosts par module métier (16)

Les modules métier (productivity, design, marketing, etc.) boostent certaines sources :

```python
MODULE_SOURCE_BOOSTS = {
    "productivity": ["perplexity_search", "searxng_search"],
    "engineering": ["github_search", "perplexity_search", "searxng_search"],
    "marketing": ["perplexity_search", "news_search", "searxng_search", "tavily_search"],
    # ... 16 modules au total
}
```

## Extraction de contenu (content_extractor.py)

Pipeline async pour extraire le texte lisible des URLs :

1. **Fetch HTML** — aiohttp, 6 pages en parallèle, timeout 8s
2. **Extraction texte** — trafilatura (CPU-bound, thread pool)
3. **Nettoyage** — Max 3000 chars, min 50 chars
4. **Filtrage** — Skip PDF, YouTube, Twitter, Facebook

Configuration :
```python
_FETCH_TIMEOUT = 8.0
_MAX_PAGES = 6
_MAX_CONTENT_BYTES = 1_000_000  # 1 MB
_MAX_TEXT_LENGTH = 3000
_MIN_TEXT_LENGTH = 50
```

## Circuit Breaker (circuit_breaker.py)

Protection contre les sources en échec :

```
3 échecs consécutifs → Circuit OPEN (skip pendant 60s)
                       → HALF-OPEN (teste à nouveau)
                       → CLOSED (rétabli)
```

---

# 4. L'agent IA

## Pool de modèles (core/models.py)

10 modèles répartis en 3 tiers :

### Tier 1 — Rapide (requêtes simples)

| Modèle | Timeout | Poids |
|--------|---------|-------|
| inclusionai/ling-2.6-flash | 8s | 4 |
| ibm-granite/granite-4.1-8b | 8s | 3 |
| poolside/laguna-xs-2.1 | 8s | 3 |

### Tier 2 — Standard (requêtes moyennes)

| Modèle | Timeout | Poids |
|--------|---------|-------|
| qwen/qwen3.7-flash | 10s | 4 |
| deepseek/deepseek-v4-flash-latest | 10s | 4 |
| mistralai/ministral-14b-2512 | 10s | 3 |
| nvidia/nemotron-3.5-lightning | 10s | 3 |

### Tier 3 — Elite (requêtes complexes)

| Modèle | Timeout | Poids |
|--------|---------|-------|
| meta-llama/llama-4-scout | 12s | 5 |
| xiaomi/mimo-v2-flash | 12s | 4 |
| stepfun/step-3.5-flash | 12s | 3 |

### Selection des modèles

```python
def _pick_random_models(count: int, tier: int) -> list[dict]:
    # Filtre par tier, pondère par weight, sélectionne count modèles
```

La selection est **aléatoire pondérée** — un modèle avec poids 4 a 2x plus de chances d'être choisi qu'un modèle avec poids 2.

### Speed config

| Mode | Modèles/requête | Timeout multiplier |
|------|-----------------|-------------------|
| fast | 1 | 0.7x |
| normal | 2 | 1.0x |
| deep | 3 | 1.5x |

## Fast path vs Fallback

### Fast path (1 appel LLM)

```
User message → LLM avec tools → Tool calls → Execute tools → Synthèse → Réponse
```

Le LLM reçoit les outils disponibles et décide lesquels appeler. Les outils sont exécutés en parallèle (ThreadPoolExecutor, 6 workers).

### Fallback (2 appels LLM)

Si le premier LLM ne fait pas de tool calls mais génère du DSML ou du JSON brut :
1. Parser les tool calls depuis le texte
2. Les exécuter
3. 2ème appel LLM pour synthétiser

### Format DSML

```xml
<DSML>invoke name="perplexity_search">
<DSML>parameter name="query">machine learning</DSML>
</DSML>invoke>
```

### Format JSON brut

```json
{"name": "perplexity_search", "arguments": {"query": "machine learning"}}
```

## Cache LRU (core/cache.py)

```python
_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
# Clé: "query|tool1|tool2"
# Valeur: (timestamp, response)
# TTL: 5 minutes (configurable)
# Max: 200 entrées (configurable)
```

## Détection de refus (core/prompts.py)

Le système détecte les réponses de refus via :
1. **Markers** — 36 phrases prédéfinies (FR + EN)
2. **Heuristiques** — Réponse trop courte (< 10 chars), pas de citation

---

# 5. Authentification et sécurité

## 3 modes d'authentification

### Mode 1 : API Key

```
X-API-Key: ws_4b6faafc3e620ab6492024c210588c29
# ou
Authorization: Bearer ws_4b6faafc3e620ab6492024c210588c29
```

- Token permanent
- Rate limit par client (configurable)
- Pas de scopes

### Mode 2 : OAuth2 JWT

```bash
# 1. Obtenir un token
POST /oauth/token
{"client_id": "...", "client_secret": "..."}

# Réponse :
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scopes": ["read", "write"]
}

# 2. Utiliser le token
Authorization: Bearer eyJ...
```

- Token temporaire (1h)
- Scopes (read, write, admin)
- Rate limit par client
- Refresh possible (15 min grace period)

### Mode 3 : Sans credentials

```
# Rate limit par IP (30 req/min)
```

## Scopes

| Scope | Description | Endpoints |
|-------|-------------|-----------|
| `read` | Lire et rechercher | `/search`, `/threads`, `/datasets` |
| `write` | Envoyer des messages | `/chat` |
| `admin` | Gérer l'administration | `/admin/*` |

Scopes par défaut : `["read", "write"]`

## JWT — Structure du token

```json
{
  "sub": "client_id",
  "name": "client_name",
  "scopes": ["read", "write"],
  "iat": 1786833233,
  "exp": 1786836833,
  "iss": "websearch-agent"
}
```

- Algorithme : HS256
- Expiration : 1 heure
- Grace period pour refresh : 15 minutes
- Secret : `JWT_SECRET` env var (défaut : généré aléatoirement)

## Refresh token

```bash
POST /oauth/token/refresh
{"refresh_token": "eyJ..."}

# Fonctionne avec :
# - Token valide → nouveau token
# - Token expiré < 15 min → nouveau token
# - Token expiré > 15 min → 401
```

## Rate limiting

```python
# Sliding window de 60 secondes
_check_rate(key, max_requests=30)

# Clés :
# - "client:{client_id}" pour les clients authentifiés
# - "ip:{client_ip}" pour les clients anonymes
```

| Type | Limite | Configurable |
|------|--------|--------------|
| Par client | 30 req/min (défaut) | Oui (1-10000) |
| Par IP | 30 req/min | Non |

## Sessions admin

```python
_sessions: dict[str, float] = {}  # token -> expiry
_SESSION_TTL = 86400  # 24 heures

# Cookie: admin_session=...
# httponly, samesite=strict
# secure en production
```

## Protection brute-force

```python
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW = 300  # 5 minutes
# 5 tentatives échouées en 5 min → bloqué
```

## 2FA TOTP

```python
import pyotp
totp = pyotp.TOTP(ADMIN_TOTP_SECRET)
valid = totp.verify(code, valid_window=1)  # ±30 secondes
```

## Headers de sécurité

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 0
Referrer-Policy: no-referrer
```

---

# 6. Base de données

## SQLite — Configuration

```python
DB_PATH = "data/threads.db"

# PRAGMA optimizations :
PRAGMA journal_mode=WAL        # Write-Ahead Logging
PRAGMA synchronous=NORMAL      # Balance performance/durabilité
PRAGMA foreign_keys=ON         # Intégrité référentielle
PRAGMA cache_size=-8000        # 8 MB cache
PRAGMA busy_timeout=5000       # 5s attente lock
PRAGMA temp_store=MEMORY       # Tables temporaires en RAM
PRAGMA mmap_size=268435456     # 256 MB memory-mapped
```

## Schéma — Tables

### Table `threads`

```sql
CREATE TABLE threads (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
```

### Table `messages`

```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT REFERENCES threads(id) ON DELETE CASCADE,
    role TEXT NOT NULL,           -- 'user' ou 'assistant'
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    metadata TEXT DEFAULT '{}'    -- JSON
);
```

### Table `clients`

```sql
CREATE TABLE clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    api_key_hash TEXT UNIQUE NOT NULL,
    client_secret TEXT UNIQUE NOT NULL DEFAULT '',
    client_secret_hash TEXT UNIQUE NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    scopes TEXT NOT NULL DEFAULT '[]',     -- JSON array
    rate_limit INTEGER NOT NULL DEFAULT 30,
    created_at REAL NOT NULL,
    last_used_at REAL,
    active INTEGER DEFAULT 1,
    request_count INTEGER DEFAULT 0
);
```

### Table `client_logs`

```sql
CREATE TABLE client_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT REFERENCES clients(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    timestamp REAL NOT NULL,
    query TEXT,
    tools_used TEXT,
    path TEXT,
    models_used TEXT,
    response_time_ms INTEGER,
    cached INTEGER DEFAULT 0
);
```

## Connexion DB

```python
# Singleton avec thread-safety
_db: Optional[sqlite3.Connection] = None
_db_lock = threading.Lock()
_write_lock = threading.Lock()  # Protège les écritures

def _get_db() -> sqlite3.Connection:
    # Double-checked locking pattern
    # Auto-reconnect si connexion cassée
```

## Migration automatique

Les migrations sont dans `_init_schema()` :

```python
# Vérifie les colonnes existantes
cursor = db.execute("PRAGMA table_info(clients)")
columns = [row[1] for row in cursor.fetchall()]

if "client_secret" not in columns:
    db.execute("ALTER TABLE clients ADD COLUMN client_secret ...")
if "scopes" not in columns:
    db.execute("ALTER TABLE clients ADD COLUMN scopes ...")
if "rate_limit" not in columns:
    db.execute("ALTER TABLE clients ADD COLUMN rate_limit ...")
```

---

# 7. Configuration

## Fichier settings.json

```json
{
  "general": {
    "fullname": "Admin",
    "displayname": "Admin",
    "language": "fr",
    "timezone": "Europe/Paris"
  },
  "appearance": {
    "theme": "dark",
    "font_size": "medium",
    "animations": true,
    "wide_messages": false
  },
  "ai": {
    "name": "WebSearch Agent",
    "response_style": "balanced",
    "search_speed": "normal"
  },
  "agent": {
    "system_prompt": "...",
    "refusal_markers": "...",
    "max_context_length": 6000
  },
  "plugins": {
    "disabled_sources": [],
    "enabled_modules": []
  },
  "developer": {
    "log_level": "INFO",
    "webhook_url": "",
    "webhooks_enabled": false,
    "streaming": false,
    "rag": false
  },
  "cache": {
    "ttl": 300,
    "max_size": 200
  },
  "models": {
    "tool_timeout": 5.0,
    "synthesis_timeout": 6.0,
    "max_tokens_tool_selection": 300,
    "max_tokens_synthesis": 500
  }
}
```

## Cache des settings

```python
_SETTINGS_CACHE_TTL = 30.0  # 30 secondes
# Relit le fichier toutes les 30s max
# Vérifie le mtime pour détecter les changements
```

## Variables d'environnement

### Obligatoires

| Variable | Description | Défaut |
|----------|-------------|--------|
| `PROVIDER` | Fournisseur LLM | `openrouter` |
| `OPENROUTER_API_KEY` | Clé API | — |

### Optionnelles

| Variable | Description | Défaut |
|----------|-------------|--------|
| `PERPLEXITY_API_KEY` | Clé Perplexity | — |
| `TAVILY_API_KEY` | Clé Tavily | — |
| `BRAVE_API_KEY` | Clé Brave | — |
| `SEARXNG_URL` | URL SearXNG | — |
| `GITHUB_TOKEN` | Token GitHub | — |
| `FIRECRAWL_API_KEY` | Clé Firecrawl | — |
| `SGAI_API_KEY` | Clé ScrapeGraph | — |
| `JWT_SECRET` | Secret JWT | généré |
| `ADMIN_USER` | Login admin | `admin` |
| `ADMIN_PASSWORD` | MDP admin | `admin123` |
| `ADMIN_TOTP_SECRET` | Secret 2FA | — |
| `THREADS_DB_PATH` | chemin DB | `data/threads.db` |
| `HOST` | Host listen | `127.0.0.1` |
| `PORT` | Port listen | `4500` |
| `ENVIRONMENT` | env | `development` |
| `DISABLED_SOURCES` | Sources désactivées | — |

---

# 8. Frontend admin

## Structure

| Fichier | Rôle | Taille |
|---------|------|--------|
| `index.html` | SPA principale | 1840 lignes |
| `login.html` | Page login + 2FA | — |
| `chat.html` | Chat dédié | — |
| `app.html` | PWA standalone | — |
| `styles.css` | CSS global | — |
| `utils.js` | Helpers globaux | 196 lignes |
| `js/init.js` | Navigation, auth | 78 lignes |
| `js/dashboard.js` | Dashboard | 185 lignes |
| `js/chat.js` | Chat | 227 lignes |
| `js/logs.js` | Logs live | 171 lignes |
| `js/threads.js` | Threads | 119 lignes |
| `js/metrics.js` | Métriques | 223 lignes |
| `js/settings.js` | Paramètres | 552 lignes |
| `js/clients.js` | Clients API | 416 lignes |
| `js/sources.js` | Sources | 56 lignes |
| `js/apikeys.js` | Clés API | 267 lignes |
| `js/service.js` | Service control | 34 lignes |

## Pages SPA

| Page | ID | Description |
|------|----|-------------|
| Dashboard | `#page-dashboard` | Status, health, threads récents |
| API Keys | `#page-apikeys` | 9 providers, toggle, reveal |
| Sources | `#page-sources` | Toggle 13 sources |
| Models | `#page-models` | Pool LLM, config |
| Clients | `#page-clients` | CRUD apps, credentials |
| Chat | `#page-chat` | Interface chat complète |
| Threads | `#page-threads` | Liste conversations |
| Logs | `#page-logs` | Logs temps réel |
| Metrics | `#page-metrics` | Métriques live |
| Service | `#page-service` | Restart, stop, cache |
| Settings | `#page-settings` | General, AI, plugins, dev |

## Navigation

```javascript
// SPA routing via data-page
$$('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        // Cache toutes les pages
        // Affiche la page sélectionnée
        // Charge les données si nécessaire
    });
});
```

## Auth check

```javascript
// Au boot, vérifie l'auth
(async () => {
    const res = await fetch('/admin/api/auth/check');
    const data = await res.json();
    if (!data.authenticated) {
        window.location.href = '/admin/login.html';
    }
})();
```

## API helper

```javascript
async function api(path, opts = {}) {
    const res = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',  // Cookie session
        ...opts,
    });
    if (res.status === 401) {
        window.location.href = '/admin/login.html';
        return;
    }
    return res.json();
}
```

## PWA

- `manifest.json` — Installable
- `service-worker.js` — Cache offline
- Pages accessibles hors-ligne après premier chargement

---

# 9. API publique

## Endpoints

| Méthode | Endpoint | Auth | Scope | Description |
|---------|----------|------|-------|-------------|
| `POST` | `/chat` | JWT/API key | write | Recherche conversationnelle |
| `GET` | `/search` | JWT/API key | read | Recherche structurée |
| `POST` | `/oauth/token` | client_id/secret | — | Obtenir un token |
| `POST` | `/oauth/token/refresh` | refresh_token | — | Rafraîchir un token |
| `GET` | `/threads` | — | — | Liste threads |
| `GET` | `/threads/{id}` | — | — | Détail thread |
| `DELETE` | `/threads/{id}` | — | — | Supprimer thread |
| `GET` | `/threads/{id}/context` | — | — | Contexte follow-up |
| `GET` | `/datasets` | — | — | Recherche datasets |
| `GET` | `/health` | — | — | Health check |
| `GET` | `/metrics` | — | — | Métriques agent |

## Réponse /chat

```json
{
  "response": "Le W3C est un organisme... [1] [2]",
  "refused": false,
  "thread_id": "5595c0fb-8ffe-41f7-a1d1-0eb4fc19f37a"
}
```

## Réponse /search

```json
{
  "sources": [
    {"url": "https://...", "title": "...", "snippet": "..."}
  ],
  "query": "coupe du monde 2026",
  "count": 8,
  "truncated": false
}
```

## Réponse /oauth/token

```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "client_id": "...",
  "scopes": ["read", "write"]
}
```

## Erreurs

| Code | Signification |
|------|---------------|
| 401 | Non authentifié / credentials invalides |
| 403 | Scope insuffisant |
| 413 | Body trop volumineux (> 10KB) |
| 429 | Rate limit atteint |
| 500 | Erreur serveur |

---

# 10. Tests

## Structure

```
tests/
├── test_auth.py           # Authentification, 2FA, sessions
├── test_cache.py          # Cache LRU
├── test_events.py         # Webhooks
├── test_integration.py    # Flows complets
├── test_models.py         # Pool modèles
├── test_oauth.py          # OAuth2, JWT, scopes, refresh (37 tests)
├── test_parser.py         # Parsing DSML/JSON
├── test_rate_limit.py     # Rate limiting
├── test_router.py         # Routeur intelligent
├── test_routes.py         # Endpoints API
└── test_settings.py       # Settings
```

## Commandes

```bash
# Un fichier
venv/bin/python -m pytest tests/test_auth.py -v --tb=short

# Une classe
venv/bin/python -m pytest tests/test_integration.py::TestAuthFlow -v --tb=short

# Un test
venv/bin/python -m pytest tests/test_oauth.py::TestTokenRefresh::test_refresh_valid_token -v

# Tout
venv/bin/python -m pytest tests/ -v --tb=short
```

## Authentification pour tests

```bash
CODE=$(python3 -c "import pyotp; print(pyotp.TOTP('VEUJD46PMPRPWXDLHILDF2GMI7BWAXV7').now())")
curl -c /tmp/cookies.txt -X POST http://127.0.0.1:4500/admin/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"admin123\",\"totp_code\":\"$CODE\"}"
```

## Conventions de test

- `setUp()` / `tearDown()` pour chaque test
- TestClient partagé (pas de re-création)
- Cleanup des sessions/rate limit entre tests
- Mocks pour les appels réseau

---

# 11. Déploiement

## Docker

### Dockerfile (multi-stage)

```dockerfile
# Stage 1: Build
FROM python:3.13-slim AS builder
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim
COPY --from=builder /install /usr/local
COPY . .
RUN useradd -m -u 1000 appuser
USER appuser
EXPOSE 4500
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "4500"]
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
    deploy:
      resources:
        limits: { cpus: '1.0', memory: 256M }
```

### Commandes

```bash
docker compose up -d
docker compose logs -f
docker compose down
docker compose build --no-cache
```

## Manuel

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env avec les clés API
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

# 12. Maintenance

## Quotidien

| Tâche | Commande | Fréquence |
|-------|----------|-----------|
| Vérifier les logs | `tail -f data/websearch-agent.log` | Quotidien |
| Vérifier l'espace disque | `df -h` | Quotidien |
| Vérifier les tests | `pytest tests/ -v` | Après chaque modification |

## Hebdomadaire

| Tâche | Commande | Fréquence |
|-------|----------|-----------|
| Nettoyer les logs | Log rotating automatique (5MB, 3 backups) | Auto |
| Vérifier les dépendances | `pip list --outdated` | Hebdo |
| Review des erreurs | Dashboard admin → Logs | Hebdo |

## Mensuel

| Tâche | Commande | Fréquence |
|-------|----------|-----------|
| Mettre à jour les dépendances | `pip install --upgrade -r requirements.txt` | Mensuel |
| Rotation des credentials | Admin → Clients → Regenerate | Mensuel |
| Backup de la DB | `cp data/threads.db data/threads.db.backup` | Mensuel |
| Review des métriques | Dashboard → Metrics | Mensuel |

## Sauvegarde

```bash
# DB
cp data/threads.db data/threads.db.$(date +%Y%m%d).backup

# Settings
cp data/settings.json data/settings.json.$(date +%Y%m%d).backup

# .env
cp .env .env.$(date +%Y%m%d).backup
```

## Mise à jour

```bash
# 1. Sauvegarder
cp data/threads.db data/threads.db.backup
cp .env .env.backup

# 2. Pull les changements
git pull origin main

# 3. Installer les nouvelles dépendances
source venv/bin/activate
pip install -r requirements.txt

# 4. Redémarrer
sudo systemctl restart websearch-agent
# ou
docker compose up -d --build
```

---

# 13. Optimisation des performances

## Points critiques

| Zone | Optimisation | Impact |
|------|-------------|--------|
| **Event loop** | uvloop + httptools | 2-4x plus rapide |
| **Compression** | GZip middleware | ~70% moins de poids |
| **Cache** | LRU TTL 5min | 0ms sur un hit |
| **Parallelisme** | ThreadPool(6) pour tools | 6 outils en parallèle |
| **Lazy loading** | Sources non chargées au boot | Démarrage rapide |
| **DB** | SQLite WAL + mmap | Écritures non bloquées |
| **Connection pooling** | aiohttp + requests.Session | Connections réutilisées |

## Configuration uvicorn

```bash
uvicorn server:app \
  --loop uvloop \
  --http httptools \
  --limit-concurrency 100 \
  --backlog 128 \
  --timeout-keep-alive 65 \
  --timeout-graceful-shutdown 10
```

## Limites

| Ressource | Limite | Configurable |
|-----------|--------|--------------|
| Body HTTP | 10 KB | Non |
| Conversions | 100 | Oui (uvicorn) |
| Cache LRU | 200 entrées | Oui (settings.json) |
| Cache TTL | 5 min | Oui (settings.json) |
| Rate limit | 30 req/min | Oui (par client) |
| Timeout LLM | 8-15s | Oui (par modèle) |
| Pages extraites | 6 en parallèle | Non |

## Monitoring

```python
# Métriques disponibles
GET /metrics → {
    "sources": { "perplexity": { "calls": 10, "success": 8, "errors": 2, "avg_time": 1.2 } },
    "cache": { "hits": 50, "misses": 30, "hit_rate": 0.625 },
    "agent": { "calls": 100, "success": 95, "errors": 5, "avg_time": 3.5 },
    "rate_limit": { "hits": 15, "top_clients": [...] }
}
```

---

# 14. Sécurité en profondeur

## Couches de sécurité

| Couche | Protection |
|--------|-----------|
| **Network** | localhost uniquement (127.0.0.1:4500) |
| **Transport** | HTTPS en production (reverse proxy) |
| **Auth** | 3 modes, 2FA TOTP, brute-force protection |
| **Authorization** | Scopes JWT (read/write/admin) |
| **Input** | Validation Pydantic, body size limit |
| **SQL** | Paramètres requêtes (pas de f-strings) |
| **XSS** | escapeHtml(), Content-Security-Policy |
| **Secrets** | Hash SHA-256 pour client_secret |
| **Rate limiting** | Sliding window par client/IP |
| **Logs** | Pas de secrets dans les logs |
| **Docker** | Non-root (appuser UID 1000) |

## Secrets

| Secret | Stockage | Visible |
|--------|----------|---------|
| `api_key` | En clair en DB | Oui (1 fois) |
| `client_secret` | Hash SHA-256 en DB | Oui (1 fois) |
| `JWT_SECRET` | Env var | Non |
| `ADMIN_PASSWORD` | Env var | Non |
| `ADMIN_TOTP_SECRET` | Env var | Non |

## OWASP Top 10

| Risque | Mitigation |
|--------|-----------|
| A01 Broken Access Control | Scopes JWT, auth middleware |
| A02 Cryptographic Failures | SHA-256, JWT HS256 |
| A03 Injection | Pydantic validation, parameterized queries |
| A04 Insecure Design | Rate limiting, circuit breaker |
| A05 Security Misconfiguration | Defaults sûrs, CORS whitelist |
| A06 Vulnerable Components | Dependencies review |
| A07 Auth Failures | 2FA, brute-force protection |
| A08 Data Integrity | SQLite WAL, foreign keys |
| A09 Logging Failures | RotatingFileHandler, structured logs |
| A10 SSRF | Pas de user-controlled URLs |

---

# 15. Dépannage

## Problèmes courants

### Le serveur ne démarre pas

```bash
# Vérifier les ports
lsof -i :4500

# Vérifier les logs
tail -20 data/websearch-agent.log

# Vérifier .env
cat .env | grep -v "^#" | head -20
```

### Erreur 401 sur /admin

```bash
# Vérifier la session
curl -v -c /tmp/cookies.txt http://127.0.0.1:4500/admin/api/auth/check

# Se reconnecter
CODE=$(python3 -c "import pyotp; print(pyotp.TOTP('VEUJD46PMPRPWXDLHILDF2GMI7BWAXV7').now())")
curl -c /tmp/cookies.txt -X POST http://127.0.0.1:4500/admin/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"admin123\",\"totp_code\":\"$CODE\"}"
```

### Erreur 429 Rate Limit

```bash
# Attendre 60 secondes
# Ou régénérer l'API key
curl -X POST http://127.0.0.1:4500/admin/clients/{id}/regenerate \
  -H "Cookie: session=..."
```

### Erreur LLM

```bash
# Vérifier la clé API
curl http://127.0.0.1:4500/admin/env | python3 -m json.tool

# Vérifier les modèles disponibles
curl http://127.0.0.1:4500/admin/models | python3 -m json.tool
```

### DB corrompue

```bash
# Vérifier l'intégrité
sqlite3 data/threads.db "PRAGMA integrity_check;"

# Restaurer le backup
cp data/threads.db.backup data/threads.db
```

### Memory leak

```bash
# Vérifier la taille du cache
curl http://127.0.0.1:4500/metrics | python3 -c "import sys,json; print(json.load(sys.stdin)['cache'])"

# Vider le cache
curl -X POST http://127.0.0.1:4500/admin/cache/clear
```

---

# 16. Évolution future

## Fonctionnalités envisageables

| Priorité | Fonctionnalité | Effort |
|----------|---------------|--------|
| Haute | Streaming SSE pour /chat | Moyen |
| Haute | Auth OAuth2 scopes par endpoint | Faible |
| Moyenne | Rate limiting Redis (multi-instance) | Élevé |
| Moyenne | Metrics persistantes (InfluxDB/Prometheus) | Élevé |
| Moyenne | Admin PWA push notifications | Moyen |
| Faible | WebSocket pour les logs live | Faible |
| Faible | Backup automatique S3 | Moyen |
| Faible | Rate limiting par endpoint | Faible |

## Améliorations du code

| Zone | Amélioration | Priorité |
|------|-------------|----------|
| `agent.py` | Extraire la logique de parsing | Haute |
| `routes/api.py` | Diviser en plus petits modules | Haute |
| `admin/index.html` | Séparer en fichiers HTML par page | Moyenne |
| `threads.py` | Async SQLite (aiosqlite) | Moyenne |
| `clients.py` | Migration formelle (Alembic-style) | Faible |

## Dettes techniques

| Dette | Impact | Effort pour corriger |
|-------|--------|---------------------|
| Pas de migration DB formelle | Risque de données | Faible |
| Sessions en mémoire (pas Redis) | Reset au restart | Élevé |
| Pas de tests d'intégration LLM | Couverture partielle | Moyen |
| `@app.on_event` deprecated | Warning FastAPI | Faible |
| Pas de health check DB | Détection retardée | Faible |

---

# 17. Annexes

## A. Modèles LLM — Détails

| Modèle | Provider | Tier | Poids | Timeout | Prix approx |
|--------|----------|------|-------|---------|-------------|
| inclusionai/ling-2.6-flash | OpenRouter | 1 | 4 | 8s | Gratuit |
| ibm-granite/granite-4.1-8b | OpenRouter | 1 | 3 | 8s | Gratuit |
| poolside/laguna-xs-2.1 | OpenRouter | 1 | 3 | 8s | Gratuit |
| qwen/qwen3.7-flash | OpenRouter | 2 | 4 | 10s | ~$0.10/M |
| deepseek/deepseek-v4-flash-latest | OpenRouter | 2 | 4 | 10s | ~$0.07/M |
| mistralai/ministral-14b-2512 | OpenRouter | 2 | 3 | 10s | ~$0.10/M |
| nvidia/nemotron-3.5-lightning | OpenRouter | 2 | 3 | 10s | ~$0.10/M |
| meta-llama/llama-4-scout | OpenRouter | 3 | 5 | 12s | ~$0.20/M |
| xiaomi/mimo-v2-flash | OpenRouter | 3 | 4 | 12s | ~$0.10/M |
| stepfun/step-3.5-flash | OpenRouter | 3 | 3 | 12s | ~$0.10/M |

## B. Flux RSS — Catégories

| Catégorie | Nombre | Exemples |
|-----------|--------|----------|
| Francophone | 15 | Le Monde, France24, Mediapart |
| International | 12 | BBC, CNN, Guardian |
| Tech | 15 | TechCrunch, The Verge, Wired |
| IA | 15 | OpenAI, DeepMind, arXiv |
| Cybersécurité | 10 | Krebs, BleepingComputer |
| Programmation | 12 | Coding Horror, InfoQ |
| Langages | 15 | Python Weekly, Rust Weekly |
| Frontend | 8 | Smashing, CSS-Tricks |
| Engineering | 10 | Netflix, Meta, AWS |
| Sciences | 10 | Nature, NASA |

## C. Modules métier (16)

| Module | Sources boostées |
|--------|-----------------|
| productivity | perplexity, searxng |
| design | perplexity, firecrawl, research |
| marketing | perplexity, news, searxng, tavily |
| engineering | github, perplexity, searxng |
| data | datasets, perplexity, github |
| finance | perplexity, news, tavily |
| product_management | perplexity, tavily, research |
| pdf_viewer | perplexity, searxng |
| sales | perplexity, tavily, news |
| operations | perplexity, searxng, research |
| legal | perplexity, research, wikipedia |
| enterprise_search | perplexity, searxng, tavily |
| small_business | perplexity, news, tavily |
| human_resources | perplexity, news, research |
| customer_support | perplexity, searxng, research |
| bio_research | perplexity, research, wikipedia, wikipedia_en |

## D. Endpoints admin complets

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/admin/api/login` | Connexion |
| POST | `/admin/api/logout` | Déconnexion |
| GET | `/admin/api/auth/check` | Vérifier auth |
| GET | `/admin/api/2fa/setup` | Setup 2FA |
| GET | `/admin/env` | Variables d'env |
| POST | `/admin/env` | Mettre à jour env |
| GET | `/admin/env/{key}/reveal` | Révéler clé |
| GET | `/admin/sources` | Lister sources |
| POST | `/admin/sources/{name}` | Toggle source |
| GET | `/admin/models` | Pool modèles |
| GET | `/admin/router` | Routeur info |
| GET | `/admin/logs` | Logs serveur |
| GET | `/admin/clients` | Lister clients |
| POST | `/admin/clients` | Créer client |
| GET | `/admin/clients/{id}` | Détail client |
| PUT | `/admin/clients/{id}/scopes` | Modifier scopes |
| PUT | `/admin/clients/{id}/rate-limit` | Modifier rate limit |
| POST | `/admin/clients/{id}/regenerate` | Régénérer credentials |
| POST | `/admin/clients/{id}/deactivate` | Désactiver |
| POST | `/admin/clients/{id}/activate` | Activer |
| DELETE | `/admin/clients/{id}` | Supprimer |
| GET | `/admin/clients/{id}/logs` | Logs client |
| GET | `/admin/clients/{id}/stats` | Stats client |
| GET | `/admin/scopes` | Scopes disponibles |
| GET | `/admin/service/status` | Status service |
| POST | `/admin/service/restart` | Restart |
| POST | `/admin/service/stop` | Stop |
| POST | `/admin/cache/clear` | Vider cache |
| GET | `/admin/settings` | Lire settings |
| POST | `/admin/settings` | Écrire settings |
| GET | `/admin/account` | Compte |
| POST | `/admin/account/email` | Email |
| POST | `/admin/account/password` | Mot de passe |
| GET | `/admin/account/sessions` | Sessions |
| DELETE | `/admin/account/sessions/{prefix}` | Déconnecter session |
| GET | `/admin/security` | Sécurité |
| POST | `/admin/security/2fa` | Toggle 2FA |
| GET | `/admin/plugins` | Plugins |
| POST | `/admin/plugins/{name}/toggle` | Toggle plugin |
| GET | `/admin/developer` | Settings dev |
| POST | `/admin/developer` | Update dev |
| POST | `/admin/api-keys` | API keys |
| GET | `/admin/data/export` | Export données |
| DELETE | `/admin/data/history` | Supprimer historique |
| POST | `/admin/danger/disconnect-all` | Déconnecter tous |
| POST | `/admin/danger/reset` | Reset settings |

---

> **Document généré le 2026-08-16**
> **Dernière mise à jour : commit a68fb7d**
> **126 tests passent.**
