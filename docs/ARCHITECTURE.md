# ARCHITECTURE.md — Architecture technique complète

---

## Arborescence

```
├── server.py              # FastAPI bootstrap + middleware (GZip, CORS, BodySize, Security, AdminAuth)
├── agent.py               # Agent principal (fast path 1 LLM call + fallback 2 calls, race models)
├── clients.py             # Gestion clients API (api_key, client_secret, scopes, rate_limit, logs)
├── threads.py             # Gestion threads (SQLite WAL, messages, context follow-up)
│
├── routes/
│   ├── api.py             # /chat (write), /search (read), /datasets, /health, /metrics, /threads
│   ├── admin.py           # /admin/* (25+ endpoints: settings, plugins, clients, logs, env, service)
│   ├── auth.py            # Login, logout, sessions (in-memory), 2FA TOTP, brute-force protection
│   ├── oauth.py           # OAuth2 JWT (token, refresh, scopes, helpers auth)
│   └── rate_limit.py      # Rate limiting (sliding window 60s, configurable par client)
│
├── core/
│   ├── settings.py        # Cache settings (TTL 30s, settings.json)
│   ├── prompts.py         # System prompts + refusal markers + modules métier
│   ├── monitoring.py      # Métriques (SourceStats, CacheStats, AgentStats, RateLimitStats)
│   ├── cache.py           # Cache LLM (LRU OrderedDict, TTL 5min, max 200)
│   ├── circuit_breaker.py # Circuit breaker (3 échecs → open 60s → half-open)
│   ├── events.py          # Webhook dispatch asynchrone (aiohttp, timeout 5s)
│   ├── models.py          # Pool de modèles LLM (10 modèles, 3 tiers, selection pondérée)
│   ├── parser.py          # Parsing tool calls (DSML + JSON brut)
│   └── tools.py           # Registry des outils (13 sources, dispatch, filtres)
│
├── sources/
│   ├── __init__.py        # Lazy loading, registry SOURCES, smart_search
│   ├── router.py          # Routeur intelligent (intent/domain/complexity scoring, 3 tool levels)
│   ├── content_extractor.py # Extraction async (aiohttp, trafilatura, 6 pages parallel)
│   ├── perplexity.py      # Perplexity sonar (API, citations)
│   ├── tavily.py          # Tavily (recherche IA)
│   ├── brave.py           # Brave Search (prive)
│   ├── duckduckgo.py      # DuckDuckGo (sans API)
│   ├── searxng.py         # SearXNG (meta-moteur)
│   ├── firecrawl_search.py # Firecrawl (extraction contenu)
│   ├── just_scrape.py     # ScrapeGraph AI (scraping intelligent)
│   ├── research.py        # Recherche approfondie (Wikipedia FR/EN)
│   ├── wikipedia.py       # Wikipedia français
│   ├── wikipedia_en.py    # Wikipedia anglais
│   ├── github.py          # GitHub API (repositories)
│   ├── news_rss.py        # 112 flux RSS (cache TTL 10min, ThreadPool 30)
│   └── datasets.py        # ~1000 datasets publics
│
├── data/
│   ├── settings.json      # Settings persistées (runtime)
│   ├── threads.db         # SQLite (threads + messages + clients + client_logs)
│   └── websearch-agent.log # Log rotating (5MB, 3 backups)
│
├── admin/
│   ├── index.html         # SPA complète (1840 lignes, 10 pages)
│   ├── login.html         # Page login + 2FA
│   ├── chat.html          # Interface chat dédiée
│   ├── app.html           # PWA standalone
│   ├── start.html         # Écran démarrage
│   ├── install.html       # Wizard installation
│   ├── styles.css         # CSS global
│   ├── utils.js           # api(), $(), toast(), renderMd(), escapeHtml(), timeAgo()
│   ├── js/
│   │   ├── init.js        # Navigation, auth check, keyboard shortcuts
│   │   ├── dashboard.js   # Status serveur, threads, SVG donuts
│   │   ├── chat.js        # Chat complet (thread, typing 3 steps, markdown)
│   │   ├── logs.js        # Logs live 3s, filtres level/catégorie, timeline
│   │   ├── threads.js     # Liste threads, stats today/week, recherche
│   │   ├── metrics.js     # Polling 5s, SVG charts, circuit breaker
│   │   ├── settings.js    # General, appearance, AI, plugins, developer
│   │   ├── clients.js     # CRUD clients, credentials card, logs panel
│   │   ├── sources.js     # Toggle 13 sources, display 10 LLMs
│   │   ├── apikeys.js     # 9 providers, reveal/copy/toggle, add custom
│   │   ├── service.js     # Status, restart, stop, clear cache
│   │   └── pwa.js         # Logic PWA
│   ├── vendor/            # lucide.js, marked.min.js
│   ├── img/               # Icons, logos
│   ├── manifest.json      # PWA manifest
│   ├── service-worker.js  # Cache offline
│   └── pwa.js             # Logic PWA
│
├── tests/                 # 126 tests (unittest + pytest)
│   ├── test_auth.py       # Tests authentification, 2FA, sessions
│   ├── test_cache.py      # Tests cache LRU
│   ├── test_events.py     # Tests webhooks
│   ├── test_integration.py # Tests intégration (flows complets)
│   ├── test_models.py     # Tests pool modèles
│   ├── test_oauth.py      # Tests OAuth2, JWT, scopes, refresh (37 tests)
│   ├── test_parser.py     # Tests parsing DSML/JSON
│   ├── test_rate_limit.py # Tests rate limiting
│   ├── test_router.py     # Tests routeur intelligent
│   ├── test_routes.py     # Tests endpoints API
│   └── test_settings.py   # Tests settings
│
├── docs/
│   ├── README.md          # Documentation générale
│   ├── API.md             # Guide intégration API (13 langages)
│   ├── OAUTH.md           # Guide complet OAuth2, scopes, rate limiting
│   ├── INSTALL.md         # Guide installation
│   ├── TROUBLESHOOT.md    # Guide dépannage
│   ├── ARCHITECTURE.md    # Ce fichier
│   ├── SECURITY.md        # Sécurité en profondeur
│   ├── DEPLOYMENT.md      # Déploiement et maintenance
│   └── PRIVÉ.md           # Livre blanc technique
│
├── Dockerfile             # Multi-stage build (Python 3.13-slim)
├── docker-compose.yml     # Docker + SearXNG
├── requirements.txt       # 16 dépendances Python
├── .env.example           # Template variables d'environnement
└── AGENTS.md              # Index et règles
```

## Middleware — ordre d'exécution

1. **GZipMiddleware** — Compression des réponses > 2KB
2. **CORSMiddleware** — Whitelist origines (localhost:3000,4500,3080)
3. **BodySizeLimitMiddleware** — Rejette les bodies > 10KB (413)
4. **Security headers** — X-Content-Type-Options, X-Frame-Options, Referrer-Policy
5. **admin_auth** — Vérifie session cookie pour /admin/*

## Flux de requête

```
Client → server.py (middleware) → routes/api.py (auth + scope + rate limit)
  → agent.py (run_agent_async)
    → router.py (intent + complexity → tools)
    → cache.py (LRU check)
    → models.py (_pick_random_models → tier 1-3)
    → _try_model_async() (LLM call + tool execution)
    → sources/* (parallel search)
    → _synthesize_async() (2nd LLM call)
  → threads.py (add_message)
  → Retour {response, refused, thread_id}
```

## Conventions

| Aspect | Convention |
|--------|------------|
| **Erreurs** | HTTPException(4xx/5xx) + logging.warning, pas de crash |
| **Config** | settings.json avec cache TTL 30s, fallback defaults |
| **Tests** | unittest + pytest, TestClient partagé, 126 tests |
| **Logging** | `logging.getLogger("websearch-agent")`, RotatingFileHandler |
| **DB** | SQLite WAL mode, thread-safe, _write_lock pour les writes |
| **Auth** | 3 modes: API key / OAuth2 JWT / backward compatible (IP) |
| **Rate limit** | Sliding window 60s, configurable par client |
| **Imports** | Lazy loading pour les sources (pas de charge au boot) |
| **Async** | FastAPI async, aiohttp pour les webhooks, ThreadPool pour tools |
