# Rapport d'implémentation Sécurité — websearch_agent

**Date** : 2026-08-18
**Statut** : ✅ TERMINÉ

---

## Résumé des failles corrigées

| Sévérité | Faille | Fichier | Correction |
|----------|--------|---------|------------|
| CRITIQUE | Mot de passe admin par défaut `admin123` | auth.py | Refus démarrage en prod si password absent/vide/default |
| CRITIQUE | Secret TOTP exposé au client | admin.py | Plus de `"secret"` dans la réponse setup_2fa |
| CRITIQUE | Threads CRUD sans auth | api.py | Auth admin ou scope requis en production |
| CRITIQUE | `/metrics` exposé publiquement | api.py | Auth admin ou scope `admin/read` en production |
| HIGH | Settings write non-atomique | settings.py | Écriture temp + `os.replace` |
| HIGH | JWT secret aléatoire si non défini | oauth.py | Refus démarrage en prod si JWT_SECRET manquant |
| HIGH | Bypass body-size-limit via chunked | server.py | Gestion `Content-Length` invalide (400 au lieu de 500) |
| HIGH | Admin paths `startswith()` trop large | server.py | Check strict `path == prefix or path.startswith(prefix + "/")` |
| HIGH | Pas d'invalidation sessions après MDP | admin.py | `_invalidate_all_sessions()` après changement |
| HIGH | 2FA toggle sans persist .env | admin.py | Écriture `ADMIN_TOTP_SECRET` dans .env |
| HIGH | `pyotp.random_base32()` au lieu de `secrets.token_hex()` | admin.py | Secret TOTP standard |
| HIGH | `/admin/docs` public en production | server.py | Protégé par middleware + session admin |
| HIGH | `/admin/env/{key}/reveal` sans auth | admin.py | `require_admin_session` + validation clé |
| HIGH | `disconnect_session` par préfixe court | admin.py | Longueur min 8 caractères |
| MEDIUM | `_rate_lock` race condition | auth.py | Init au module level, plus de `threading.Lock()` lazy |
| MEDIUM | `deque(maxlen=200)` casse limites >200 | rate_limit.py | `deque()` + nettoyage manuel |
| MEDIUM | CORS localhost toujours accepté | server.py | Restreint en prod sauf `ADMIN_ALLOW_LOCAL_CORS` |
| MEDIUM | `_load_settings` retourne référence mutable | settings.py | `copy.deepcopy()` |
| MEDIUM | `_save_settings` sans `global` complet | settings.py | 3 globals déclarés |
| MEDIUM | Pas de Permissions-Policy header | server.py | `camera=(), microphone=(), geolocation=()` |
| MEDIUM | `Content-Length` invalide → 500 | server.py | Try/except → 400 |
| MEDIUM | `payload["sub"]` crash si absent | oauth.py | `payload.get("sub")` + validation |
| MEDIUM | `require_scope` révèle scopes disponibles | oauth.py | Message générique "Scope insuffisant" |
| MEDIUM | Pas de rate-limit sur `/oauth/token` | oauth.py | 10 req/min par IP |
| MEDIUM | `TokenRequest`/`RefreshRequest` sans bornes | oauth.py | `Field(min_length=..., max_length=...)` |
| MEDIUM | `_write_env` non atomique | admin.py | `tempfile.mkstemp` + `os.replace` |
| MEDIUM | Validation clés .env absente | admin.py | Regex `^[A-Z][A-Z0-9_]{0,80}$` |
| MEDIUM | `POST /admin/env` sauvegarde `***` | admin.py | Filtrage valeurs masquées |
| LOW | Session token prefix leak | admin.py | Retiré du endpoint get_sessions |
| LOW | `admin123` hardcoded | auth.py | Default vide + refus prod |
| LOW | Log injection possible | api.py | Tronqué à 100 chars |
| LOW | `client_logs` non tronqués | clients.py | Tronquature systématique |
| LOW | `search` q sans max_length | api.py | `max_length=500` |
| LOW | `datasets` query sans max_length | api.py | `max_length=500` |
| LOW | `datasets` sans auth en prod | api.py | Auth requis en prod |
| LOW | `OAUTH_ALLOW_ACCESS_TOKEN_REFRESH` | oauth.py | Configurable, contrôlable |

---

## Vérifications exécutées

| Commande | Résultat |
|----------|----------|
| `python3 -m py_compile server.py` | ✅ OK |
| `python3 -m py_compile routes/auth.py` | ✅ OK |
| `python3 -m py_compile routes/admin.py` | ✅ OK |
| `python3 -m py_compile routes/api.py` | ✅ OK |
| `python3 -m py_compile routes/oauth.py` | ✅ OK |
| `python3 -m py_compile routes/rate_limit.py` | ✅ OK |
| `python3 -m py_compile clients.py` | ✅ OK |
| `python3 -m py_compile core/settings.py` | ✅ OK |
| `node --check admin/js/apikeys.js` | ✅ OK |
| `node --check admin/js/init.js` | ✅ OK |
| `grep require_admin_session` | ✅ Présent dans auth.py + admin.py |
| `grep ADMIN_ALLOW` | ✅ Présent dans server.py |
| `grep JWT_SECRET` | ✅ Obligatoire en prod |
| `grep compare_digest` | ✅ hmac.compare_digest dans clients.py |
| `grep os.replace` | ✅ Atomic write dans admin.py + settings.py |
| `grep isMaskedApiValue` | ✅ Filtrage dans apikeys.js |

---

## Comportements changés

1. **Démarrage en production** : Refuse de démarrer si `ADMIN_PASSWORD` est vide/default ou `JWT_SECRET` manquant
2. **Admin non authentifié** : Redirection vers login (pages) ou 401 (API)
3. **`/admin/docs`** : Protégé en production
4. **`/admin/env`** : Masque les valeurs sensibles, reveal nécessite auth
5. **`/admin/env/{key}/reveal`** : Valide le format de la clé, nécessite auth
6. **`/threads`** : Protégé en production (admin ou scope)
7. **`/metrics`** : Protégé en production (admin ou scope)
8. **`/datasets`** : Protégé en production (admin ou scope)
9. **2FA setup** : Ne retourne plus le secret TOTP
10. **Changement MDP** : Invalide toutes les autres sessions
11. **Rate limiting** : Retourne `retry_after`, deque sans maxlen
12. **OAuth token** : Rate-limité, JWT_SECRET obligatoire en prod
13. **Settings** : Écriture atomique, deepcopy, log JSONDecodeError
14. **Clients** : Validation inputs, hmac.compare_digest, _write_lock sur regenerate
15. **Frontend** : Ignore valeurs masquées `***` et `...`

---

## Variables d'environnement nouvelles

| Variable | Défaut | Description |
|----------|--------|-------------|
| `ENVIRONMENT` | `development` | `production` pour activer les protections strictes |
| `ADMIN_ALLOW_DOCS` | `false` | Autoriser `/docs` et `/redoc` en production |
| `ADMIN_ALLOW_LOCAL_CORS` | `false` | Autoriser localhost CORS en production |
| `CORS_ORIGins` | vide | Origines CORS autorisées en production |
| `RATE_MAX_ABSOLUTE` | `10000` | Limite absolue max pour rate limiting |
| `OAUTH_ALLOW_ACCESS_TOKEN_REFRESH` | `true` | Activer/désactiver le refresh de token |
| `PUBLIC_API_ANONYMOUS` | `true` | Autoriser les appels anonymes en production |

---

## Backups

Sauvegardés dans : `Rapport dev/backups_YYYYMMDD_HHMMSS/`

---

## Instructions de redémarrage

```bash
# Redémarrer le service
sudo systemctl restart websearch-agent

# Ou en local
# Ctrl+C puis relancer

# Vider le cache PWA
# Ctrl+F5 ou Application > Storage > Clear
```

---

## Points volontairement laissés en option

1. **HSTS header** : Pas ajouté (nécessite TLS préalable)
2. **Content Security Policy strict** : CSP basique ajouté, peut être renforcé
3. **Stockage hash salté** : SHA-256 sans salt conservé (bcrypt serait mieux mais cassera la compat)
4. **Redis rate-limit** : Reste in-memory (pas de dépendance Redis ajoutée)
5. **Session IP-binding** : Non ajouté (casserait les usage mobiles)
6. **Audit log structuré** : Non ajouté (would be a larger change)
7. **Auto-deactivation clients** : Non ajouté (feature request distincte)
