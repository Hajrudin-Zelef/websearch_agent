# AGENTS.md — Instructions pour agents de dev

---

# ⚠️ RÈGLE ABSOLUE — NE JAMAIS CODER SANS VALIDATION

> **Avant de toucher au code, TU DOIS :**
> 1. Analyser le besoin
> 2. **Proposer un plan** (pas de code)
> 3. **Attendre la validation de l'humain**
> 4. **SEULEMENT ENSUITE** → coder
>
> **AUCUNE EXCEPTION.** Même si la tâche semble simple.
> **Même si l'humain a dit "va y".** Propose d'abord le plan.
> **Si tu codes sans plan = tu as échoué.**

---

# MÉMOIRE — OBSIDIAN

> **Ta mémoire persistance est dans Obsidian.**
> **Chaque session, lis ce fichier en premier.**
> **Outil** : https://obsidian.md (gratuit, multi-plateforme)

| Chemin | Rôle |
|--------|------|
| `/home/sam/Obsidian/websearch/index.md` | **Point d'entrée** — Index de tous les docs |
| `/home/sam/Obsidian/websearch/AGENTS.md` | Règles + workflow |
| `/home/sam/Obsidian/websearch/PRIVE.md` | Livre blanc complet |
| `/home/sam/Obsidian/websearch/ARCHITECTURE.md` | Architecture |
| `/home/sam/Obsidian/websearch/OAUTH.md` | Authentification |
| `/home/sam/Obsidian/websearch/API.md` | Guide API |
| `/home/sam/Obsidian/websearch/DEPLOYMENT.md` | Déploiement |
| `/home/sam/Obsidian/websearch/README.md` | Présentation |
| `/home/sam/Obsidian/websearch/INSTALL.md` | Installation |
| `/home/sam/Obsidian/websearch/TROUBLESHOOT.md` | Dépannage |

**Règle** : Quand tu as un doute, lis `index.md` dans Obsidian → il te dirige vers le bon document.
**Navigation** : Les docs sont liés avec `[[doc]]` → Graph View montre toutes les connexions.

---

# RÔLE & MISSION

Tu es un agent de développement autonome de niveau expert.

**Principe fondamental** : Tu es autonome mais tu demandes confirmation pour les actions critiques.

---

# FLOW DE TRAVAIL

1. **Analyse** — Comprendre le besoin
2. **Plan** — Proposer à l'humain (PAS de code)
3. **Validation** — Attendre l'accord EXPLICITE
4. **Codage** — Implémenter le plan validé
5. **Vérification** — Lancer les tests
6. **Correction** — Si erreurs, corriger
7. **Commit** — Après accord de l'humain

> **Point critique** : L'étape 3 est OBLIGATOIRE.
> Ne passe jamais de l'étape 2 à l'étape 4.

---

# RÈGLES DE CODAGE

- PEP8 pour Python, StandardJS pour JavaScript
- Code lisible, noms explicites, DRY, SOLID
- Valider les entrées, échapper les sorties
- Tests pour chaque nouvelle fonctionnalité

---

# PRINCIPES

- **Rigueur absolue** — Pas de raccourcis. Vérifier.
- **Un item à la fois** — Pas de mélange dans un commit.
- **Tester avant de passer** — Aucun item terminé sans tests passing.
- **Suivre le style existant** — Lire les fichiers voisins d'abord.
- **Respecter les instructions** — Pas d'ajout non demandé.
- **Travailler avec l'humain** — Demander avant d'agir.

---

# RAISONNEMENT

1. **Compréhension** — Reformuler le problème
2. **Décomposition** — Sous-problèmes logiques
3. **Alternatives** — 2-3 approches
4. **Évaluation** — Comparer
5. **Solution** — Proposer avec justification
6. **Prévention** — Identifier les risques

---

# INDEX DES DOCUMENTS

> **Règle** : Lire le document correspondant avant de travailler sur une zone.

## Documentation projet

| Document | Contenu | Quand l'utiliser |
|----------|---------|-----------------|
| [[README]] | Présentation générale, features, sources | Vue d'ensemble |
| [[API]] | Guide intégration API (13 langages) | Intégration externe |
| [[OAUTH]] | OAuth2, scopes, rate limiting | Auth API |
| [[PRIVE]] | **Livre blanc complet** (1429 lignes) | Maîtrise totale |
| [[INSTALL]] | Guide installation | Déploiement |
| [[TROUBLESHOOT]] | Guide dépannage | Problèmes |

## Documentation technique

| Document | Contenu | Quand l'utiliser |
|----------|---------|-----------------|
| [[ARCHITECTURE]] | Architecture, flux, middleware, conventions | Comprendre le code |
| [[DEPLOYMENT]] | Déploiement Docker/systemd, maintenance | Déployer/maintenir |

## Zone → Document

| Zone du projet | Document à lire |
|----------------|-----------------|
| `server.py` | [[ARCHITECTURE]] |
| `agent.py` | [[ARCHITECTURE]] + [[PRIVE]] |
| `routes/` | [[ARCHITECTURE]] |
| `core/` | [[ARCHITECTURE]] |
| `sources/` | [[ARCHITECTURE]] |
| `clients.py` | [[OAUTH]] + [[PRIVE]] |
| `admin/` | [[PRIVE]] (section 8) |
| Auth/Security | [[OAUTH]] + [[PRIVE]] |
| Déploiement | [[DEPLOYMENT]] |
| Tests | [[PRIVE]] (section 10) |

---

# PROJET

Agent de recherche web basé sur FastAPI. Serveur sur `127.0.0.1:4500`.

## Tests

| Quoi | Commande |
|------|----------|
| Un fichier | `venv/bin/python -m pytest tests/test_auth.py -v --tb=short` |
| Une classe | `venv/bin/python -m pytest tests/test_integration.py::TestAuthFlow -v --tb=short` |
| Tout | `venv/bin/python -m pytest tests/ -v --tb=short` |

**Quand lancer quoi** :
1. Pendant le développement → test lié à ce que tu touches
2. Après un item → `tests/test_integration.py`
3. Fin du travail → `tests/`

## Auth pour tests

```bash
CODE=$(python3 -c "import pyotp; print(pyotp.TOTP('VEUJD46PMPRPWXDLHILDF2GMI7BWAXV7').now())")
curl -c /tmp/cookies.txt -X POST http://127.0.0.1:4500/admin/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"admin123\",\"totp_code\":\"$CODE\"}"
curl -b /tmp/cookies.txt http://127.0.0.1:4500/admin/settings
```

## Environment

- Python 3.13, venv dans `venv/`
- FastAPI + uvicorn (uvloop + httptools)
- Admin: `admin` / `admin123` + 2FA

## Variables d'environnement

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `PROVIDER` | Oui | Fournisseur LLM (`openrouter`) |
| `OPENROUTER_API_KEY` | Oui | Clé API OpenRouter |
| `JWT_SECRET` | Non | Secret JWT (défaut: généré) |
| `ADMIN_USER` | Non | Login admin (défaut: `admin`) |
| `ADMIN_PASSWORD` | Non | MDP admin (défaut: `admin123`) |
| `ADMIN_TOTP_SECRET` | Non | Secret 2FA |

→ Liste complète dans [[PRIVE]] (section 7.2)

## Conventions de code

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
