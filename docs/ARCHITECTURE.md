# ARCHITECTURE — Architecture technique complète

> Voir aussi : [[index]], [[AGENTS]], [[PRIVE]], [[OAUTH]], [[DEPLOYMENT]]

---

## Arborescence

```
├── server.py              # FastAPI bootstrap + middleware
├── agent.py               # Agent principal (fast path + fallback)
├── clients.py             # Gestion clients API
├── threads.py             # Gestion threads (SQLite)
│
├── routes/
│   ├── api.py             # /chat, /search, /datasets, /health, /metrics, /threads
│   ├── admin.py           # /admin/* (25+ endpoints)
│   ├── auth.py            # Login, logout, sessions, 2FA
│   ├── oauth.py           # OAuth2 JWT
│   └── rate_limit.py      # Rate limiting
│
├── core/
│   ├── settings.py        # Cache settings
│   ├── prompts.py         # System prompts
│   ├── monitoring.py      # Métriques
│   ├── cache.py           # Cache LRU
│   ├── circuit_breaker.py # Circuit breaker
│   ├── events.py          # Webhooks
│   ├── models.py          # Pool LLM
│   ├── parser.py          # Parsing tool calls
│   └── tools.py           # Registry outils
│
├── sources/               # 13 sources de recherche
├── admin/                 # Frontend HTML/JS
├── tests/                 # 126 tests
├── data/                  # Données runtime
└── docs/                  # Documentation
```

## Middleware — ordre d'exécution

1. **GZipMiddleware** — Compression > 2KB
2. **CORSMiddleware** — Whitelist origines
3. **BodySizeLimitMiddleware** — Bodies > 10KB → 413
4. **Security headers** — X-Content-Type-Options, X-Frame-Options
5. **admin_auth** — Session cookie pour /admin/*

## Flux de requête

```
Client → [[server]] (middleware) → [[routes/api]] (auth + scope + rate limit)
  → [[agent]] (run_agent_async)
    → [[sources/router]] (intent + complexity → tools)
    → [[core/cache]] (LRU check)
    → [[core/models]] (_pick_random_models → tier 1-3)
    → _try_model_async() (LLM call + tool execution)
    → [[sources/*]] (parallel search)
    → _synthesize_async() (2nd LLM call)
  → [[threads]] (add_message)
  → Retour {response, refused, thread_id}
```

## Conventions

| Aspect | Convention |
|--------|------------|
| **Erreurs** | HTTPException(4xx/5xx) + logging.warning |
| **Config** | settings.json cache TTL 30s |
| **Tests** | unittest + pytest, 126 tests |
| **Logging** | `logging.getLogger("websearch-agent")` |
| **DB** | SQLite WAL, _write_lock |
| **Auth** | 3 modes: API key / OAuth2 JWT / IP |
| **Rate limit** | Sliding window 60s, par client |
| **Imports** | Lazy loading pour les sources |
| **Async** | FastAPI async, ThreadPool pour tools |

## Documents liés

- [[OAUTH]] — Authentification détaillée
- [[PRIVE]] — Livre blanc complet
- [[DEPLOYMENT]] — Déploiement et maintenance
- [[AGENTS]] — Règles et workflow
