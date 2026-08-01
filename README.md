# WebSearch Agent

Agent IA avec function-calling (DeepSeek / OpenRouter) branché sur 4 sources de données maison :

- **Wikipedia** — recherche encyclopédique via l'API officielle
- **GitHub** — recherche de repos via l'API officielle
- **Actualités** — 112 flux RSS (médias, tech, IA, cybersécurité, programmation...)
- **Datasets** — ~1000 datasets publics (statiques + temps réel, indexés depuis awesome-public-datasets)

Le modèle choisit lui-même quelle source interroger selon la question.

## Architecture

```
websearch_agent/
├── sources/
│   ├── wikipedia.py    # Recherche Wikipedia (fr)
│   ├── github.py       # Recherche GitHub
│   ├── news_rss.py     # 112 flux RSS
│   └── datasets.py     # ~1000 datasets publics
├── scripts/
│   └── build_datasets_index.py  # Build de l'index datasets
├── agent.py            # Agent function-calling
├── server.py           # Serveur FastAPI
├── websearch-agent.service  # Service systemd
├── requirements.txt
└── .env.example
```

## Installation

```bash
cd websearch_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env avec tes clés API
```

## Utilisation

### Ligne de commande

```bash
python agent.py "qui a inventé Python ?"
python agent.py "dernières actualités sur l'IA"
python agent.py "trouve des frameworks d'agents IA open source"
python agent.py "trouve des datasets publics sur le changement climatique"
python agent.py "quels flux temps réel pour les cryptos ?"
```

### Serveur API

```bash
uvicorn server:app --reload
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"actualités cybersécurité"}'
```

### Service systemd

```bash
systemctl --user status websearch-agent
systemctl --user restart websearch-agent
journalctl --user -u websearch-agent -f
```

## Variables d'environnement

| Variable | Description |
|---|---|
| `PROVIDER` | `deepseek` ou `openrouter` |
| `DEEPSEEK_API_KEY` | Clé API DeepSeek |
| `OPENROUTER_API_KEY` | Clé API OpenRouter |
| `GITHUB_TOKEN` | Token GitHub (optionnel, 5000 req/h au lieu de 60) |

## Flux RSS

112 flux couvrant :

- 🇫🇷 **Francophone** (Le Monde, France24, Mediapart, France Info...)
- 🌍 **International** (BBC, CNN, Guardian, Al Jazeera...)
- 💻 **Tech** (TechCrunch, The Verge, Ars Technica, Slashdot...)
- 🤖 **IA** (OpenAI, DeepMind, Hugging Face, arXiv...)
- 🛡️ **Cybersécurité** (Krebs, Schneier, BleepingComputer, Dark Reading...)
- 📝 **Programmation** (Coding Horror, InfoQ, Stack Overflow, Martin Fowler...)
- 🔧 **Langages** (Python, Rust, Go, React, Vue, TypeScript...)
- 🏢 **Engineering blogs** (Netflix, Meta, Spotify, AWS, Cloudflare, GitHub...)
- 🔬 **Sciences/Espace** (Nature, NASA, Scientific American...)
