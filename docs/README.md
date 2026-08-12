# WebSearch Agent

Agent IA de recherche web ultra-rapide avec function-calling. Selection aleatoire des modeles par requete, routage intelligent, et 13 sources de donnees.

## Installation rapide

### Option 1 : Installation automatique (recommande)

```bash
curl -fsSL https://raw.githubusercontent.com/Hajrudin-Zelef/websearch_agent/main/install.sh | bash
```

Ou cloner et lancer le script :

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
./install.sh
```

Le script vous guidera pour :
1. Installer Docker automatiquement
2. Configurer vos cles API
3. Demarrer tous les services

### Option 2 : Docker manuel

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent

# Configurer les cles API
cp .env.example .env
nano .env

# Demarrer
docker compose up -d

# Verifier
curl http://localhost:8000/health
```

### Option 3 : Installation manuelle

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env

uvicorn server:app --host 127.0.0.1 --port 8000
```

### Guide complet

Voir [INSTALL.md](INSTALL.md) pour le guide d'installation complet.

Voir [API.md](API.md) pour le guide d'integration API (JavaScript, Python, PHP, Go, Rust, etc.).

Voir [TROUBLESHOOT.md](TROUBLESHOOT.md) pour le guide de depannage.

## Sources de donnees

| Source | Type | Cle API | Description |
|--------|------|---------|-------------|
| Perplexity | Web | Requise | Recherche web intelligente avec citations |
| Tavily | Web | Requise | Recherche web optimisee pour les agents IA |
| Brave | Web | Requise | Moteur prive sans tracking |
| DuckDuckGo | Web | Non | Moteur prive sans tracking |
| SearXNG | Web | Non | Meta-moteur open-source decentralise |
| Firecrawl | Web | Requise | Recherche avec extraction de contenu complet |
| Just Scrape | Web | Requise | ScrapeGraph AI intelligent |
| Research | Research | Non | Recherche approfondie Wikipedia FR/EN |
| Wikipedia FR | Encyclopedie | Non | Wikipedia francais |
| Wikipedia EN | Encyclopedie | Non | Wikipedia anglais |
| GitHub | Code | Optionnel | Repositories et code open-source |
| News | Actualites | Non | 112 flux RSS |
| Datasets | Donnees | Non | ~1000 datasets publics |

## Architecture

```
websearch_agent/
├── sources/
│   ├── perplexity.py           # API Perplexity (sonar)
│   ├── tavily.py               # API Tavily
│   ├── brave.py                # API Brave Search
│   ├── duckduckgo.py           # DuckDuckGo (sans API)
│   ├── searxng.py              # SearXNG (local ou public)
│   ├── firecrawl_search.py     # Firecrawl (contenu complet)
│   ├── just_scrape.py          # ScrapeGraph AI
│   ├── research.py             # Recherche approfondie Wikipedia
│   ├── wikipedia.py            # Wikipedia francais
│   ├── wikipedia_en.py         # Wikipedia anglais
│   ├── github.py               # GitHub API
│   ├── news_rss.py             # 112 flux RSS
│   ├── datasets.py             # ~1000 datasets
│   ├── content_extractor.py    # Extraction contenu pages (trafilatura)
│   ├── router.py               # Routeur intelligent
│   └── __init__.py             # Registry unifie
├── agent.py                    # Agent function-calling
├── server.py                   # Serveur FastAPI + threads
├── threads.py                  # Persistance SQLite (threads)
├── install.sh                  # Script installation auto
├── Dockerfile                  # Image Docker
├── docker-compose.yml          # Orchestration Docker
├── websearch-agent.service     # Service systemd
├── data/                       # Donnees SQLite (threads.db)
├── requirements.txt
├── .env.example
├── docs/
│   ├── README.md               # Documentation principale
│   ├── INSTALL.md              # Guide d'installation
│   ├── API.md                  # Guide d'integration API
│   └── TROUBLESHOOT.md         # Guide de depannage
└── .gitignore
```

## Installation

```bash
cd websearch_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editer .env avec les cles API
```

## Variables d'environnement

| Variable | Description | Requise |
|----------|-------------|---------|
| `PROVIDER` | `openrouter` | Oui |
| `OPENROUTER_API_KEY` | Cle API OpenRouter | Oui |
| `PERPLEXITY_API_KEY` | Cle API Perplexity | Non |
| `TAVILY_API_KEY` | Cle API Tavily | Non |
| `BRAVE_API_KEY` | Cle API Brave Search | Non |
| `SEARXNG_URL` | URL instance SearXNG | Non |
| `GITHUB_TOKEN` | Token GitHub (optionnel) | Non |
| `FIRECRAWL_API_KEY` | Cle API Firecrawl | Non |
| `SGAI_API_KEY` | Cle API ScrapeGraph AI | Non |
| `THREADS_DB_PATH` | Chemin BDD SQLite threads (defaut: `./data/threads.db`) | Non |

## Utilisation

### Ligne de commande

```bash
python agent.py "qu'est-ce que le W3C ?"
python agent.py "dernières actualités sur l'IA"
python agent.py "github langchain"
python agent.py "comparaison React vs Vue.js"
```

### Serveur API

```bash
# Demarrer le serveur
uvicorn server:app --host 127.0.0.1 --port 8000

# health check
curl http://localhost:8000/health

# recherche
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "qu\'est-ce que le W3C"}'

# datasets
curl "http://localhost:8000/datasets?query=climat&max_results=5"
```

### Service systemd

```bash
systemctl --user status websearch-agent
systemctl --user restart websearch-agent
journalctl --user -u websearch-agent -f
```

## Routeur intelligent

Le systeme detecte automatiquement :

### Intentions (14)

| Intent | Exemple |
|--------|---------|
| `search` | "cherche information sur..." |
| `explain` | "explique comment..." |
| `compare` | "comparaison entre X et Y" |
| `news` | "actualités IA" |
| `code` | "github langchain" |
| `data` | "dataset climat" |
| `recommend` | "meilleur framework" |
| `howto` | "comment installer Docker" |
| `definition` | "qu'est-ce que le W3C" |
| `history` | "histoire de la philosophie" |
| `technical` | "architecture microservices" |
| `finance` | "cours bitcoin" |
| `science` | "théorie quantique" |

### Domaines (8)

`tech`, `science`, `history`, `geography`, `philosophy`, `art`, `law`, `education`

### Niveaux de complexite

| Niveau | Score | Outils | Exemple |
|--------|-------|--------|---------|
| 1 | 0-39 | 3 | "python", "bonjour" |
| 2 | 40-64 | 7 | "comparaison React vs Vue.js" |
| 3 | 65-100 | 13 | "quel est le meilleur framework AI en 2026 et pourquoi" |

## Optimisations

### Rapidite

- **Selection aleatoire** — Chaque requete utilise un modele different du pool
- **Timeouts agressifs** — 8-12s au lieu de 15-30s
- **Cache LRU** — 5 minutes de TTL pour les requetes identiques
- **Execution parallele** — Outils executes en parallel (asyncio)
- **Connection pooling** — Clients HTTP reutilises

### Performance

| Requete | Temps |
|---------|-------|
| `github langchain` | ~3.6s |
| `comparaison React vs Vue.js` | ~3.2s |
| `qu'est-ce que le W3C` | ~6.4s |
| `actualités IA` | ~23s |

### Pool de modeles

| Modele | Poids | Timeout |
|--------|-------|---------|
| llama-4-maverick | 3 | 8s |
| qwen-2.5-7b | 2 | 10s |
| qwen3-8b | 2 | 12s |
| deepseek-chat-v3 | 1 | 10s |
| mistral-small-3.1 | 1 | 10s |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Recherche (body: `{"message": "..."}`) |
| GET | `/threads` | Liste les threads de conversation |
| GET | `/threads/{id}` | Detail d'un thread avec messages |
| DELETE | `/threads/{id}` | Supprimer un thread |
| GET | `/threads/{id}/context` | Contexte pour follow-up |
| GET | `/datasets` | Liste datasets (params: `query`, `max_results`) |
| GET | `/health` | Health check |

### Reponse `/chat`

```json
{
  "response": "Le W3C est un organisme... [1] [2]",
  "refused": false,
  "thread_id": "5595c0fb-8ffe-41f7-a1d1-0eb4fc19f37a"
}
```

### Follow-up dans un thread

```json
POST /chat
{
  "message": "Et les differences avec HTML5 ?",
  "thread_id": "5595c0fb-8ffe-41f7-a1d1-0eb4fc19f37a"
}
```

### Citations

Les reponses incluent des citations numerotees `[1]`, `[2]` correspondant aux sources extraites des pages web. Le systeme :
1. Execute les outils de recherche en parallele
2. Fetch les URLs trouvees et extrait le contenu lisible (trafilatura)
3. Passe les extraits numerotes au LLM pour synthese avec citations
4. Ne cite jamais une page qui n'a pas ete fetchee

### Threads

```bash
# Lister les threads
curl http://localhost:8000/threads

# Detail d'un thread
curl http://localhost:8000/threads/{thread_id}

# Contexte pour follow-up
curl http://localhost:8000/threads/{thread_id}/context

# Supprimer un thread
curl -X DELETE http://localhost:8000/threads/{thread_id}
```

## Flux RSS (112)

- **Francophone** — Le Monde, France24, Mediapart, France Info...
- **International** — BBC, CNN, Guardian, Al Jazeera...
- **Tech** — TechCrunch, The Verge, Ars Technica, Slashdot...
- **IA** — OpenAI, DeepMind, Hugging Face, arXiv...
- **Cybersecurite** — Krebs, Schneier, BleepingComputer, Dark Reading...
- **Programmation** — Coding Horror, InfoQ, Stack Overflow, Martin Fowler...
- **Langages** — Python, Rust, Go, React, Vue, TypeScript...
- **Engineering blogs** — Netflix, Meta, Spotify, AWS, Cloudflare, GitHub...
- **Sciences** — Nature, NASA, Scientific American...
