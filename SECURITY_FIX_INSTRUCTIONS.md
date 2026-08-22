# Instructions — Correction des failles de sécurité (websearch_agent)

Tu agis comme un senior full-stack developer top 1%. Rigueur absolue. Zéro régression. Zéro raccourci.

## Règles globales (non négociables)

1. **Branche dédiée** : `git checkout -b security/fix-audit-2026-08`. Un commit atomique par faille corrigée, message clair (`fix(auth): constant-time password comparison + hashing`).
2. **Baseline avant tout** : lance la suite de tests existante (`pytest`) et note le résultat AVANT toute modification. Si un test échoue déjà, documente-le, ne le corrige pas sauf si lié à ta tâche.
3. **Scope strict** : ne touche AUCUN fichier hors du périmètre des 6 failles listées. Pas de refactor "pendant qu'on y est". Pas de renommage, pas de reformatage de fichiers non concernés.
4. **Non-régression fonctionnelle** : après chaque fix, la suite de tests complète doit passer. Si un comportement existant change (contrat API, réponse JSON, variable d'env requise), tu dois : (a) le signaler explicitement dans le message de commit, (b) documenter dans `docs/` et `docs-users/` correspondants, (c) fournir un chemin de migration rétrocompatible — jamais casser un déploiement existant sans avertissement.
5. **Tests obligatoires pour CHAQUE fix** : un test qui prouve que la faille est corrigée (exploit ne fonctionne plus) + tests de non-régression sur le comportement légitime. Pas de fix sans test.
6. **Pas de secrets en dur, pas de nouvelles dépendances non justifiées.** Si tu ajoutes une lib (ex: `argon2-cffi`), ajoute-la à `requirements.txt` avec version pinnée et justifie-la dans le commit.
7. **Aucune fonctionnalité supprimée silencieusement.** Si un fix implique de retirer une capacité existante (ex: affichage d'une clé API en clair dans l'UI admin), tu dois d'abord vérifier tous les usages (`grep -rn` sur tout le repo), lister les impacts, et proposer l'alternative avant de coder.
8. **Livrable final** : une description de PR récapitulant, pour chaque faille — le risque initial, le fix appliqué, les tests ajoutés, et tout changement de contrat (env vars, schéma DB, réponses API).

---

## Priorité 1 — Authentification admin (timing attack + password en clair)

**Fichier** : `routes/auth.py`, `routes/admin.py`

**Exigences** :
- Remplacer `req.username != auth_mod.ADMIN_USER or req.password != auth_mod.ADMIN_PASSWORD` par une comparaison **constant-time** (`secrets.compare_digest`) sur les deux champs, séparément, sans court-circuit qui fuiterait un timing différentiel.
- Le mot de passe admin ne doit plus être stocké en clair dans `.env`. Utiliser `argon2-cffi` (Argon2id) pour hasher. Stocker dans `ADMIN_PASSWORD_HASH`.
- **Migration rétrocompatible obligatoire** : au démarrage, si `ADMIN_PASSWORD` (legacy, clair) est présent et `ADMIN_PASSWORD_HASH` absent :
  - hasher `ADMIN_PASSWORD` automatiquement, écrire `ADMIN_PASSWORD_HASH` dans `.env` via `_write_env`, supprimer `ADMIN_PASSWORD` du fichier, logger un warning explicite (`"ADMIN_PASSWORD legacy migré vers ADMIN_PASSWORD_HASH"`).
  - Ne jamais faire échouer le démarrage à cause de cette migration.
- Appliquer le même traitement au TOTP secret si stocké de façon non protégée (vérifier, documenter si acceptable tel quel — un secret TOTP n'est pas un hash de mot de passe, mais doit rester dans `.env` avec permissions fichier restreintes, 600).
- Mettre à jour `docs/INSTALL.md`, `docs-users/INSTALL.md`, `.env.example` (si absent, le créer) pour refléter `ADMIN_PASSWORD_HASH`.

**Tests requis** :
- Test unitaire : deux mots de passe de longueurs différentes ne doivent pas produire de différence de timing mesurable (test structurel : vérifier que `secrets.compare_digest` est bien utilisé, pas un test de timing réel qui serait flaky).
- Test : login avec `ADMIN_PASSWORD` legacy dans `.env` → migration auto → hash présent → login fonctionne toujours avec le mot de passe clair d'origine.
- Test : `.env` ne contient plus jamais `ADMIN_PASSWORD` en clair après migration.
- Test négatif : mauvais mot de passe → 401, aucune fuite d'info sur quel champ est faux.

**Critère d'acceptation** : aucun mot de passe en clair persisté nulle part après le premier démarrage post-fix. Comparaison constant-time vérifiable dans le code.

---

## Priorité 2 — CSRF (code mort)

**Fichiers** : `routes/auth.py`, `routes/admin.py`, `admin/js/*.js`

**Décision à prendre AVANT de coder** — pas de choix par défaut, documente ton raisonnement dans le commit :
- **Option A (recommandée)** : implémenter réellement le CSRF sur toutes les routes admin mutantes (POST/PUT/DELETE) via double-submit cookie ou header `X-CSRF-Token` vérifié côté serveur avec `validate_csrf_token`. Le frontend doit récupérer le token au login et l'envoyer sur chaque requête mutante.
- **Option B** : si tu juges `SameSite=Strict` + vérification d'origine suffisante pour ce périmètre (session cookie only, pas de cross-site form posting possible), alors **supprimer** le code mort trompeur (`generate_csrf_token`/`validate_csrf_token` non appelés) et documenter explicitement pourquoi dans `docs/ARCHITECTURE.md`.

Ne fais jamais un mix des deux (code présent mais partiellement appliqué).

**Exigences si Option A** :
- Middleware ou dépendance FastAPI qui vérifie le header CSRF sur toute route `/admin/*` en POST/PUT/DELETE, sauf login/logout.
- Le token est émis à la création de session, lié au `session_token` (déjà prévu dans `generate_csrf_token`), envoyé au client via une route dédiée ou dans la réponse de login.
- Frontend admin (`admin/js/`) mis à jour pour inclure `X-CSRF-Token` sur tous les `fetch` mutants existants — vérifier **chaque** appel réseau dans `admin/js/*.js`, pas seulement un exemple.

**Tests requis** :
- Requête mutante sans token CSRF → rejetée (403).
- Requête mutante avec token valide → acceptée.
- Token à usage unique déjà implémenté (`del _csrf_tokens[key]`) → vérifier qu'un replay du même token échoue.
- Tests d'intégration sur au moins 3 routes admin mutantes différentes (clients, settings, service control).

**Critère d'acceptation** : aucune route d'état mutable admin n'est atteignable sans token CSRF valide (si Option A), ou justification écrite formelle si Option B.

---

## Priorité 3 — Clés API stockées en clair en DB

**Fichier** : `clients.py`

**Exigences** :
- Avant toute modification : `grep -rn "\[.\]api_key\b" routes/ admin/` pour identifier CHAQUE endroit qui lit la colonne `api_key` (clair) — notamment dans l'UI admin (liste des clients, affichage de la clé après création).
- Le comportement attendu et standard de l'industrie : la clé en clair n'est **jamais** persistée, elle est retournée **une seule fois** à la création/régénération (déjà le cas dans le `return` de `create_client`/`regenerate_api_key` — vérifier que c'est bien la seule occurrence de transmission en clair).
- Migration DB SQLite :
  - Écrire un script de migration idempotent (`migrations/002_drop_api_key_plaintext.py` ou équivalent) qui :
    1. Vérifie que `api_key_hash` est renseigné pour toutes les lignes existantes (sinon, échec bloquant avec message clair — ne jamais migrer en silence si des données seraient perdues sans hash de repli).
    2. Recrée la table sans la colonne `api_key` (SQLite ne supporte pas `DROP COLUMN` nativement avant 3.35+ — vérifier la version SQLite cible ; si `ALTER TABLE DROP COLUMN` non supporté, faire un `CREATE TABLE new` + `INSERT INTO new SELECT ... FROM old` + `DROP TABLE old` + `RENAME`, dans une transaction).
    3. Est **réversible en théorie mais irréversible en pratique** (les clés en clair existantes seront perdues) — documenter ça noir sur blanc dans le message de migration et dans le commit. Si des admins ont besoin de retrouver une clé existante, prévenir qu'il faudra la régénérer après migration.
- Mettre à jour `_init_schema` pour que les nouvelles installations ne créent plus jamais la colonne `api_key`.
- Adapter toute UI admin qui affichait la clé en clair après coup pour n'afficher que le hash tronqué ou les 4 derniers caractères (pattern standard : `sk-...a1b2`), jamais la valeur complète après la création initiale.

**Tests requis** :
- Test : après `create_client`, la DB ne contient la clé en clair nulle part (`SELECT * FROM clients` ne doit plus avoir de colonne `api_key`).
- Test de migration : DB de test pré-migration avec données factices → migration → intégrité des `api_key_hash`, `client_secret_hash`, scopes, rate_limits préservée à l'identique.
- Test : authentification par clé API (`get_client_by_api_key`) fonctionne toujours après migration (déjà basée sur le hash — confirmer aucune régression).

**Critère d'acceptation** : `sqlite3 threads.db ".schema clients"` ne montre plus de colonne `api_key` en clair après migration. Aucune perte de fonctionnalité d'authentification.

---

## Priorité 4 — `sudo systemctl restart/stop` exposé

**Fichier** : `routes/admin.py`

**Exigences** :
- Ajouter une confirmation explicite côté serveur pour ces deux routes : re-vérification de la session (déjà couverte par le middleware) **+** exigence du token CSRF (cf Priorité 2) **+** log d'audit obligatoire (qui, quand, quelle action) dans un fichier de log séparé et append-only, distinct des logs applicatifs standards.
- Vérifier la configuration `sudoers` réelle du serveur (pas modifiable depuis le code, mais à documenter dans `docs/DEPLOYMENT.md`) : le compte de service ne doit avoir NOPASSWD que sur les commandes exactes `systemctl restart websearch-agent` et `systemctl stop websearch-agent`, rien de plus large (pas de wildcard, pas de `ALL`).
- Ajouter un rate limit dédié sur ces deux routes (distinct du rate limit login) — ex: max 3 appels / 5 min — pour limiter l'impact d'une session compromise utilisée en boucle (DoS auto-infligé).
- Ne PAS supprimer la fonctionnalité — elle est légitime pour un panneau d'admin — mais réduire strictement le rayon d'explosion en cas de session volée.

**Tests requis** :
- Requête sans CSRF token (si Option A retenue en Priorité 2) → rejetée.
- Log d'audit créé à chaque appel réussi, contenant timestamp + IP + identifiant de session (pas le token complet).
- Rate limit déclenché après le seuil défini.

**Critère d'acceptation** : chaque redémarrage/arrêt du service via l'admin est tracé, protégé par CSRF, et limité en fréquence.

---

## Priorité 5 — `/docs` et `/redoc` exposés publiquement

**Fichier** : `server.py`

**Exigences** :
- `docs_url` et `redoc_url` de l'instance `FastAPI(...)` doivent être `None` en production (`ENVIRONMENT == "production"`) sauf si `ADMIN_ALLOW_DOCS=true`, en cohérence avec la logique déjà existante pour `/admin/docs`.
- Si `ADMIN_ALLOW_DOCS=true` en prod, ces routes globales `/docs` et `/redoc` doivent être protégées par le même middleware d'authentification admin que `/admin/docs` — actuellement il ne s'applique qu'aux chemins commençant par `/admin`, donc il faut soit déplacer ces routes sous `/admin/`, soit étendre explicitement le check du middleware à ces deux chemins.
- Ne jamais dupliquer la logique d'auth — réutiliser `_validate_session` existant.

**Tests requis** :
- En environnement `production` sans `ADMIN_ALLOW_DOCS` : `GET /docs` et `GET /redoc` → 404.
- En environnement `production` avec `ADMIN_ALLOW_DOCS=true`, sans session valide → redirect ou 401 (cohérent avec le comportement de `/admin/docs`).
- En `development` : comportement actuel préservé (docs accessibles, pas de régression du confort dev).

**Critère d'acceptation** : aucune route de documentation OpenAPI accessible sans authentification en production.

---

## Priorité 6 — SSRF potentiel dans `content_extractor.py`

**Fichier** : `sources/content_extractor.py`

**Exigences** :
- Avant chaque fetch, résoudre le hostname de l'URL et vérifier que l'IP résolue n'appartient à aucune plage privée/réservée : loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`, incluant explicitement `169.254.169.254` — metadata cloud AWS/GCP/Azure), privées RFC1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), et `0.0.0.0/8`. Utiliser le module `ipaddress` de la stdlib pour la vérification, pas de regex sur des strings d'IP.
- **Se protéger du DNS rebinding** : ne pas se contenter de vérifier le hostname avant la requête puis laisser `aiohttp` re-résoudre au moment de la connexion. Résoudre explicitement l'IP, vérifier, puis connecter sur cette IP précise (via un resolver custom ou en épinglant la connexion), ou au minimum désactiver les redirections HTTP automatiques vers des cibles non re-vérifiées (`allow_redirects=False` puis re-valider chaque redirect manuellement).
- Bloquer aussi les schémas non-HTTP(S) explicitement (`file://`, `gopher://`, etc.) si jamais un schéma arbitraire pouvait être injecté.
- Cette validation doit s'appliquer uniquement au chemin d'extraction de contenu (URLs issues des résultats de recherche), sans casser le comportement pour les domaines publics légitimes — tester sur un panel d'URLs réelles (Wikipedia, sites d'actualité) pour confirmer zéro faux positif.

**Tests requis** :
- URL pointant vers `127.0.0.1`, `169.254.169.254`, `10.0.0.1`, `192.168.1.1` → fetch refusé, log d'avertissement, extraction "skip" gracieuse (comportement déjà existant pour les patterns dans `_SKIP_PATTERNS` — suivre le même pattern de dégradation gracieuse, pas de crash).
- URL légitime publique → comportement inchangé, contenu extrait normalement.
- Cas DNS rebinding simulé (mock resolver) → requête bloquée ou IP re-vérifiée avant connexion effective.

**Critère d'acceptation** : aucune requête sortante possible vers une IP privée/metadata, résolution vérifiée au plus près de la connexion réelle, zéro régression sur l'extraction de contenu public.

---

## Checklist finale avant de considérer la tâche terminée

- [ ] Les 6 failles ont chacune : fix + tests + doc mise à jour si contrat changé.
- [ ] `pytest` complet passe (comparer au baseline de l'étape 2 des règles globales).
- [ ] Aucun fichier hors scope modifié (`git diff --stat` revu ligne par ligne).
- [ ] Aucun secret en dur ajouté.
- [ ] `.env.example` reflète les nouvelles variables (`ADMIN_PASSWORD_HASH`, etc.) si applicable.
- [ ] Message de PR récapitulatif rédigé (risque → fix → tests → impact de compatibilité) pour chacune des 6 failles.
- [ ] Aucune fonctionnalité existante supprimée sans documentation explicite du remplacement.
