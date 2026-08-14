# WebSearch Agent

Agent IA de recherche web ultra-rapide avec function-calling. Selection aleatoire des modeles par requete, routage intelligent, 13 sources de donnees, et panneau d'administration complet.

## Installation rapide

### Option 1 : Installation automatique

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
./install.sh
```

### Option 2 : Docker

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
cp .env.example .env
nano .env
docker compose up -d
curl http://localhost:4500/health
```

### Option 3 : Manuel

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

Guide complet : [INSTALL.md](INSTALL.md)
Integration API : [API.md](API.md)
Depannage : [TROUBLESHOOT.md](TROUBLESHOOT.md)

## Performance

| Optimisation | Impact |
|---|---|
| uvloop + httptools | Event loop ~2-4x plus rapide |
| GZip middleware | Reponses HTTP compressees (~70% moins de poids) |
| Lazy loading sources | 0 modules charges au demarrage |
| Fast path (1 LLM call) | Outils en parallele + 1 synthese au lieu de 2 appels LLM |
| Content extractor async | aiohttp pour le fetch des pages |
| Cache LRU | 0ms sur un hit (TTL 5 min) |
| Race models | Premier modele qui repond gagne |
| Connection pooling | Clients HTTP reutilises |

Temps de reponse :
- Cache hit : **0ms**
- Requete simple : **3-4s**
- Requete complexe : **6-8s**

## Sources de donnees (13)

| Source | Type | Cle API |
|--------|------|---------|
| Perplexity | Web | Requise |
| Tavily | Web | Requise |
| Brave | Web | Requise |
| DuckDuckGo | Web | Non |
| SearXNG | Web | Non |
| Firecrawl | Web | Requise |
| Just Scrape | Web | Requise |
| Research | Research | Non |
| Wikipedia FR | Encyclopedie | Non |
| Wikipedia EN | Encyclopedie | Non |
| GitHub | Code | Optionnel |
| News | Actualites | Non |
| Datasets | Donnees | Non |

## Routeur intelligent

Detection automatique de l'intention, du domaine, et de la complexite. Outils minimum pour les requetes simples, maximum pour les complexes.

| Niveau | Score | Outils | Exemple |
|--------|-------|--------|---------|
| 1 | 0-39 | 3 | "python", "bonjour" |
| 2 | 40-64 | 7 | "comparaison React vs Vue.js" |
| 3 | 65-100 | 13 | "quel est le meilleur framework AI en 2026" |

## Pool de modeles

| Modele | Poids | Timeout |
|--------|-------|---------|
| llama-4-maverick | 4 | 6s |
| qwen-2.5-7b | 3 | 6s |
| qwen3-8b | 2 | 8s |
| deepseek-chat-v3 | 1 | 6s |
| mistral-small-3.1 | 1 | 6s |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Recherche (body: `{"message": "..."}`) |
| GET | `/threads` | Liste les threads |
| GET | `/threads/{id}` | Detail d'un thread |
| DELETE | `/threads/{id}` | Supprimer un thread |
| GET | `/threads/{id}/context` | Contexte pour follow-up |
| GET | `/datasets` | Datasets (params: `query`, `max_results`) |
| GET | `/health` | Health check |

### Reponse `/chat`

```json
{
  "response": "Le W3C est un organisme... [1] [2]",
  "refused": false,
  "thread_id": "5595c0fb-8ffe-41f7-a1d1-0eb4fc19f37a"
}
```

## Panneau d'administration

Acces : `https://votre-domaine/admin`

- Authentification avec 2FA (TOTP)
- Gestion des cles API clients
- Gestion des sources (activer/desactiver)
- Configuration des modeles
- Logs en temps reel
- Settings (system prompt, timeouts, cache)
- Restart/stop du service

## Variables d'environnement

| Variable | Description | Requise |
|----------|-------------|---------|
| `PROVIDER` | `openrouter` | Oui |
| `OPENROUTER_API_KEY` | Cle API OpenRouter | Oui |
| `PERPLEXITY_API_KEY` | Cle API Perplexity | Non |
| `TAVILY_API_KEY` | Cle API Tavily | Non |
| `BRAVE_API_KEY` | Cle API Brave Search | Non |
| `SEARXNG_URL` | URL instance SearXNG | Non |
| `GITHUB_TOKEN` | Token GitHub | Non |
| `FIRECRAWL_API_KEY` | Cle API Firecrawl | Non |
| `SGAI_API_KEY` | Cle API ScrapeGraph AI | Non |
| `ADMIN_USER` | Identifiant admin (defaut: admin) | Non |
| `ADMIN_PASSWORD` | Mot de passe admin (defaut: admin123) | Non |
| `ADMIN_TOTP_SECRET` | Secret TOTP pour le 2FA | Non |

## Architecture

```
websearch_agent/
├── sources/
│   ├── __init__.py             # Lazy loading + registry
│   ├── router.py               # Routeur intelligent
│   ├── content_extractor.py    # Extraction async (aiohttp)
│   ├── perplexity.py           # API Perplexity
│   ├── tavily.py               # API Tavily
│   ├── brave.py                # API Brave Search
│   ├── duckduckgo.py           # DuckDuckGo
│   ├── searxng.py              # SearXNG
│   ├── firecrawl_search.py     # Firecrawl
│   ├── just_scrape.py          # ScrapeGraph AI
│   ├── research.py             # Recherche Wikipedia FR/EN
│   ├── wikipedia.py            # Wikipedia francais
│   ├── wikipedia_en.py         # Wikipedia anglais
│   ├── github.py               # GitHub API
│   ├── news_rss.py             # 112 flux RSS
│   └── datasets.py             # ~1000 datasets
├── agent.py                    # Agent function-calling
├── server.py                   # FastAPI + admin + auth
├── threads.py                  # SQLite (threads)
├── clients.py                  # Gestion clients API
├── admin/                      # Panneau d'administration
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # Docker + SearXNG
├── websearch-agent.service     # Service systemd
├── settings.json               # Settings runtime
├── requirements.txt
├── .env.example
└── docs/
```

## Commandes utiles

```bash
# Serveur
uvicorn server:app --host 127.0.0.1 --port 4500 --loop uvloop --http httptools

# Systemd
systemctl --user status websearch-agent
systemctl --user restart websearch-agent
journalctl --user -u websearch-agent -f

# Docker
docker compose up -d
docker compose logs -f
docker compose down

# Test
curl http://localhost:4500/health
curl -X POST http://localhost:4500/chat -H "Content-Type: application/json" -d '{"message":"bonjour"}'
```

## Flux RSS (112)

Francophone (Le Monde, France24, Mediapart...), International (BBC, CNN, Guardian...), Tech (TechCrunch, The Verge, Ars Technica...), IA (OpenAI, DeepMind, arXiv...), Cybersecurite (Krebs, Schneier, BleepingComputer...), Programmation (Coding Horror, InfoQ, Stack Overflow...), Langages (Python, Rust, Go, React...), Engineering blogs (Netflix, Meta, AWS, Cloudflare...), Sciences (Nature, NASA...).
