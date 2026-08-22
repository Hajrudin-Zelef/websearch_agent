# Rapport dev – Refactor UI API Keys (accordéon)
sudo : Popo!26+
acces admin : admin admin123
pour le cest un authentification 2FA  - Clé : VEUJD46PMPRPWXDLHILDF2GMI7BWAXV7


**Plan – Refactor de l’interface API Keys en sections « accordéon »**

| Étape | Action | Détails |
|------|--------|----------|
| 1 | **Analyse** | Le formulaire des clés se trouve dans `admin/index.html` (section *API Keys*) et les champs sont générés dynamiquement à partir du tableau `API_KEY_FIELDS` défini dans `admin/js/apikeys.js`. |
| 2 | **Définir les catégories** | - **LLM Provider** (OpenRouter, Perplexity, Tavily, Brave) <br> - **Web Search** (Perplexity, Tavily, Brave, etc.) <br> - **Crawl** (Firecrawl, ScrapeGraph) <br> - **Code** (GitHub) <br> - **SearXNG** (URL & Key) <br> - **Agent‑Reach** (Jina, Exa, YouTube, Twitter/X, XiaoHongShu, LinkedIn, Bosszhipin) |
| 3 | **Modifier `API_KEY_FIELDS`** | Ajouter un champ `group` à chaque entrée, ex. `{ id: 'OPENROUTER_API_KEY', cat: 'llm', group: 'LLM Provider', label: 'OpenRouter' }`. Cela permet de regrouper les clés par catégorie sans toucher le reste du code. |
| 4 | **Créer un composant accordéon** | Dans `admin/js/apikeys.js` : <br>• Parcourir `API_KEY_FIELDS` et regrouper les items par `group`. <br>• Pour chaque groupe, injecter un bloc `<details>` / `<summary>` contenant les champs du groupe. <br>• Le premier groupe (`LLM Provider`) reste ouvert par défaut (`open` attribute). |
| 5 | **Gestion du switch « activer / désactiver »** <br>Chaque provider possède déjà un champ `*_ENABLED` qui est traité dans `loadAPIKeys()`. Le switch restera à l’intérieur du bloc du provider, donc visible uniquement quand le groupe est développé. |
| 6 | **Adapter le CSS** | Ajouter quelques règles simples pour les `<details>` : <br>```css
.apikeys-group { margin-bottom: var(--sp-4); border: 1px solid var(--border); border-radius: var(--radius-md); }
.apikeys-group summary { padding: var(--sp-3); cursor: pointer; font-weight: 600; }
``` |
| 7 | **Tests manuels** <br>• Recharger l’admin UI → les catégories s’affichent sous forme d’accordéon.<br>• Ouvrir/fermer chaque groupe, vérifier que les champs et les switches fonctionnent et que les valeurs sont bien enregistrées via la route `/admin/api-keys`. |
| 8 | **Rollback** | Le fichier original `admin/js/apikeys.js` sera conservé dans le dépôt (`git commit` précédent) ; en cas de problème, on pourra revenir rapidement. |
| 9 | **Commit** | `feat(admin): API keys displayed per category with collapsible sections` – inclure le fichier modifié `admin/js/apikeys.js` et les petites additions CSS dans `admin/styles.css` si besoin. |

---

*Ce plan est prêt à être implémenté.*

# Instruction for Claude Code – Refactor UI API Keys (accordéon) & Agent‑Reach Activation

## Objective
- Enable full activation of all *agent‑reach* channels in `websearch_agent` by simply adding credentials via the admin interface.

## Important Details
- Credentials must be stored in `data/settings.json` under `api_keys` and edited through the admin UI.
- All *agent‑reach* source functions should read credentials from settings via a helper.
- Provide wrappers for `yt‑dlp` and `xreach` that inject cookies/files when configured.
- Configure missing mcporter servers (exa, douyin, xiaohongshu, linkedin, bosszhipin) to read their credentials from settings.
- Update admin UI (`admin/js/apikeys.js`) to include new credential fields.
- Ensure no code is written to the workspace root; use `/tmp/` or `~/.agent‑reach/` only when needed.
- All unit tests must continue to pass.

## Work State
### Completed
- Created `sources/agent_reach.py` with `agent_reach_web_search`, `agent_reach_github_search`, `agent_reach_rss_search`.
- Added credential helper `_get_credential` and switched `agent_reach_web_search` to read `JINA_API_KEY` from settings.
- Updated `core/tools.py` (imports, registry, reliability scores).
- Modified `sources/__init__.py` (lazy imports, registry, `__all__`).
- Updated `sources/router.py` (tool levels, intent boosts, keyword index).
- Updated admin UI (`admin/js/apikeys.js`) with new `API_KEY_FIELDS` for all agent‑reach credentials.
- Created `sources/agent_reach_wrappers.py` (helpers, command wrappers).
- Added `scripts/configure_mcporter.py` to configure missing mcporter servers.
- Verified all changes via interactive testing and full test suite (126 passed).
- Confirmed credential‑less behavior of `agent_reach_web_search` and successful GitHub/RSS searches.

### Active
- None

## Plan – Refactor UI API Keys (accordéon)

| Étape | Action | Détails |
|------|--------|----------|
| 1 | **Analyse** | Le formulaire des clés se trouve dans `admin/index.html` (section *API Keys*) et les champs sont générés dynamiquement à partir du tableau `API_KEY_FIELDS` défini dans `admin/js/apikeys.js`. |
| 2 | **Définir les catégories** | - **LLM Provider** (OpenRouter, Perplexity, Tavily, Brave) <br> - **Web Search** (Perplexity, Tavily, Brave, etc.) <br> - **Crawl** (Firecrawl, ScrapeGraph) <br> - **Code** (GitHub) <br> - **SearXNG** (URL & Key) <br> - **Agent‑Reach** (Jina, Exa, YouTube, Twitter/X, XiaoHongShu, LinkedIn, Bosszhipin) |
| 3 | **Modifier `API_KEY_FIELDS`** | Ajouter un champ `group` à chaque entrée, ex. `{ id: 'OPENROUTER_API_KEY', cat: 'llm', group: 'LLM Provider', label: 'OpenRouter' }`. Cela permet de regrouper les clés par catégorie sans toucher le reste du code. |
| 4 | **Créer un composant accordéon** | Dans `admin/js/apikeys.js` : <br>• Parcourir `API_KEY_FIELDS` et regrouper les items par `group`. <br>• Pour chaque groupe, injecter un bloc `<details>` / `<summary>` contenant les champs du groupe. <br>• Le premier groupe (`LLM Provider`) reste ouvert par défaut (`open` attribute). |
| 5 | **Gestion du switch « activer / désactiver »** <br>Chaque provider possède déjà un champ `*_ENABLED` qui est traité dans `loadAPIKeys()`. Le switch restera à l’intérieur du bloc du provider, donc visible uniquement quand le groupe est développé. |
| 6 | **Adapter le CSS** | Ajouter quelques règles simples pour les `<details>` : <br>```css
.apikeys-group { margin-bottom: var(--sp-4); border: 1px solid var(--border); border-radius: var(--radius-md); }
.apikeys-group summary { padding: var(--sp-3); cursor: pointer; font-weight: 600; }
``` |
| 7 | **Tests manuels** <br>• Recharger l’admin UI → les catégories s’affichent sous forme d’accordéon.<br>• Ouvrir/fermer chaque groupe, vérifier que les champs et les switches fonctionnent et que les valeurs sont bien enregistrées via la route `/admin/api-keys`. |
| 8 | **Rollback** | Le fichier original `admin/js/apikeys.js` sera conservé dans le dépôt (`git commit` précédent) ; en cas de problème, on pourra revenir rapidement. |
| 9 | **Commit** | `feat(admin): API keys displayed per category with collapsible sections` – inclure le fichier modifié `admin/js/apikeys.js` et les petites additions CSS dans `admin/styles.css` si besoin. |

---
