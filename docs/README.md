# WebSearch Agent

Agent IA de recherche web avec function-calling. Routage intelligent, 13 sources de donnees, panneau d'administration.

## Demo

```
https://nweb.neva-ci.pro
```

## Installation

```bash
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
./install.sh
```

Ou manuellement :

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn server:app --host 127.0.0.1 --port 4500 --loop uvloop --http httptools
```

## Sources

Perplexity, Tavily, Brave, DuckDuckGo, SearXNG, Firecrawl, ScrapeGraph AI, Wikipedia FR/EN, GitHub, 112 flux RSS, ~1000 datasets.

## API

| Endpoint | Description |
|----------|-------------|
| `POST /chat` | Recherche (`{"message": "..."}`) |
| `GET /threads` | Threads de conversation |
| `GET /health` | Health check |

## Admin

`/admin` — Auth 2FA, gestion des cles API, sources, modeles, logs, settings.

## License

MIT
