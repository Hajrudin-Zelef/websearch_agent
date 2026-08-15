# WebSearch Agent — Index

> **Règle n°1** : Lire [[AGENTS]] en premier.
> **Mémoire** : Ce dossier = ta mémoire persistance. Lis `index.md` au démarrage de chaque session.

---

## Documents

### Règles & Workflow

| Document | Contenu | Quand l'utiliser |
|----------|---------|-----------------|
| [[AGENTS]] | Règles absolues, flow de travail, conventions, index | **TOUJOURS en premier** |

### Architecture & Code

| Document | Contenu | Quand l'utiliser |
|----------|---------|-----------------|
| [[ARCHITECTURE]] | Arborescence complète, middleware, flux de requête, conventions de code | Quand tu touches au code ([[server]], [[agent]], [[routes/]], [[core/]], [[sources/]]) |
| [[PRIVE]] | **Livre blanc complet** — 17 sections, 1429 lignes — tout sur l'app | Quand tu dois maîtriser un aspect en profondeur |

### Authentification & API

| Document | Contenu | Quand l'utiliser |
|----------|---------|-----------------|
| [[OAUTH]] | OAuth2, JWT, scopes, rate limiting, refresh token | Quand tu touches à l'auth, [[clients]], [[routes/oauth]] |
| [[API]] | Guide intégration API — 13 langages (JS, Python, Go, Rust, PHP, cURL...) | Quand tu dois documenter ou modifier les endpoints publics |

### Déploiement & Maintenance

| Document | Contenu | Quand l'utiliser |
|----------|---------|-----------------|
| [[DEPLOYMENT]] | Docker, systemd, maintenance quotidienne/hebdo/mensuel, dépannage | Quand tu déploies, maintiens, ou résous des problèmes |
| [[INSTALL]] | Guide d'installation complet | Première mise en route |
| [[TROUBLESHOOT]] | Guide de dépannage — problèmes courants + solutions | Quand quelque chose ne marche pas |

### Présentation

| Document | Contenu | Quand l'utiliser |
|----------|---------|-----------------|
| [[README]] | Présentation générale, features, 13 sources, pool LLM, architecture | Vue d'ensemble, onboarding |

---

## Zone du projet → Document

| Zone | Document(s) à lire |
|------|-------------------|
| [[server]] | [[ARCHITECTURE]] |
| [[agent]] | [[ARCHITECTURE]] + [[PRIVE]] (sections 3-4) |
| [[routes/api]] | [[ARCHITECTURE]] + [[OAUTH]] |
| [[routes/admin]] | [[PRIVE]] (section 8) |
| [[routes/auth]] | [[OAUTH]] |
| [[routes/oauth]] | [[OAUTH]] |
| [[routes/rate_limit]] | [[OAUTH]] |
| [[core/*]] | [[ARCHITECTURE]] + [[PRIVE]] (section 4) |
| [[sources/*]] | [[ARCHITECTURE]] + [[PRIVE]] (section 3) |
| [[clients]] | [[OAUTH]] + [[PRIVE]] (section 6) |
| [[threads]] | [[PRIVE]] (section 6) |
| [[admin/]] (frontend) | [[PRIVE]] (section 8) |
| [[tests/]] | [[PRIVE]] (section 10) |
| Docker/Deploy | [[DEPLOYMENT]] |
| Sécurité | [[OAUTH]] + [[PRIVE]] (section 14) |

---

## Workflow

```
1. Analyse → 2. Plan → 3. Validation humaine → 4. Codage → 5. Tests → 6. Commit
```

**Ne jamais coder sans plan + validation.**
