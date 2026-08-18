Mission: durcir et corriger le projet websearch_agent après audit sécurité/robustesse.

Contexte:
Le projet est une app FastAPI avec interface admin dans /admin, API publique (/chat, /search, /threads, /metrics, /datasets), gestion clients API, OAuth/JWT, rate limiting, settings JSON et variables .env. Les fichiers audités sont:
- server.py
- routes/admin.py
- routes/auth.py
- routes/api.py
- routes/oauth.py
- routes/rate_limit.py
- clients.py
- core/settings.py
- admin/js/apikeys.js
- admin/js/init.js
- admin/index.html
- admin/styles.css

Objectif global:
Corriger les failles critiques sans casser l’usage local existant. Priorité absolue: empêcher accès non authentifié aux routes admin sensibles, empêcher fuite/écrasement de secrets, protéger threads/metrics, corriger les bugs Python/JS réels, puis améliorer robustesse et auditabilité.

Règles de travail:
1. Commencer par inspecter l’état réel des fichiers avant modification avec grep/sed, car des correctifs partiels existent déjà.
2. Faire un backup horodaté de chaque fichier modifié.
3. Garder les changements minimalement invasifs, compatibles avec le code existant.
4. Ne pas supprimer de fonctionnalité sans fallback via variable d’environnement.
5. Ajouter logs utiles, mais ne jamais logger de secrets, tokens complets, clés API, mots de passe ou contenu sensible complet.
6. Après chaque lot, vérifier avec grep, python -m py_compile, node --check si applicable.
7. Fournir à la fin les commandes exactes de vérification et redémarrage.

Phase 1: server.py, protection admin et surface publique.
- Corriger le bypass actuel où /admin est autorisé par le middleware et peut servir index.html sans session.
- /admin et /admin/ doivent rediriger vers /admin/login.html si aucune session valide, sinon servir l’admin.
- /admin/docs doit être protégé par session admin, pas public.
- Les assets publics admin doivent être strictement limités: /admin/login.html, /admin/styles.css, /admin/utils.js, /admin/vendor/*, /admin/img/*, /admin/js/*, /admin/service-worker.js, /admin/manifest.json, /admin/pwa.css, /admin/pwa.js, /admin/app.html seulement si réellement nécessaire.
- Remplacer les checks startswith trop larges par: path == prefix or path.startswith(prefix + "/").
- En production, désactiver ou protéger /docs et /redoc. Si FastAPI docs ne peuvent pas être dynamiquement retirées facilement, ajouter middleware qui bloque /docs, /redoc, /openapi.json sauf ENVIRONMENT != production ou ADMIN_ALLOW_DOCS=true.
- BodySizeLimitMiddleware: gérer content-length invalide sans 500.
- CORS: en production, ne pas accepter localhost par défaut sauf ADMIN_ALLOW_LOCAL_CORS=true ou CORS_ORIGINS explicite.

Phase 2: routes/auth.py et routes/admin.py, session/admin/2FA.
- Refuser le démarrage en production si ADMIN_PASSWORD est absent, vide ou vaut admin123.
- Ajouter helper require_admin_request(request) ou équivalent réutilisable, basé sur cookie admin_session + _validate_session.
- Si le middleware protège déjà, garder helper pour routes ultra sensibles comme défense en profondeur.
- Dans admin.py, éviter les imports stale de ADMIN_TOTP_SECRET / ADMIN_PASSWORD pour les valeurs qui peuvent changer à chaud. Utiliser import routes.auth as auth_mod puis auth_mod.ADMIN_TOTP_SECRET / auth_mod.ADMIN_PASSWORD.
- setup_2fa ne doit pas exposer le secret TOTP librement. Il doit être accessible seulement admin authentifié et idéalement seulement pendant enrôlement.
- toggle_2fa doit générer un secret avec pyotp.random_base32(), pas secrets.token_hex().
- Quand le mot de passe admin change, invalider toutes les sessions sauf éventuellement la session courante, ou toutes si plus simple.
- disconnect_session ne doit pas supprimer par préfixe court. Imposer longueur minimale stricte ou token exact côté serveur.
- Ajouter protection CSRF simple pour routes admin mutantes si possible sans gros refactor: token stocké session/cookie non-HttpOnly + header X-CSRF-Token, ou à défaut préparer TODO explicite et renforcer SameSite/Origin check.
- Pour les routes service restart/stop, env reveal, env write, history delete, danger reset: exiger admin authentifié explicitement.

Phase 3: secrets .env dans routes/admin.py.
- _read_env/_write_env doivent être robustes.
- _write_env doit écrire atomiquement: fichier temporaire dans même dossier, flush/fsync si raisonnable, os.replace.
- Refuser clés invalides: autoriser seulement ^[A-Z][A-Z0-9_]{1,80}$.
- Refuser valeurs contenant \n, \r, null byte.
- Ajouter allowlist pour clés sensibles connues: OPENROUTER_API_KEY, PERPLEXITY_API_KEY, TAVILY_API_KEY, BRAVE_API_KEY, FIRECRAWL_API_KEY, SGAI_API_KEY, GITHUB_TOKEN, SEARXNG_URL, SEARXNG_API_KEY, JINA_API_KEY, EXA_API_KEY, cookies paths, LinkedIn credentials, *_ENABLED. Pour clés custom, accepter seulement si ADMIN_ALLOW_CUSTOM_ENV=true.
- /admin/env doit masquer toutes les valeurs sensibles.
- /admin/env/{key}/reveal doit refuser noms invalides et clés non autorisées; retourner vraie valeur seulement admin authentifié.
- POST /admin/env ne doit jamais sauvegarder "***" ni valeurs contenant "...", pour ne pas écraser un secret masqué.
- Corriger toute erreur silencieuse en log warning/error sans secret.

Phase 4: routes/api.py, API publique.
- Protéger /threads, /threads/{id}, /threads/{id}/context et DELETE /threads/{id}. Exiger client API/JWT avec scope adapté ou session admin.
- Protéger /metrics: en production exiger admin ou scope admin/read selon choix minimal. Ne pas exposer métriques internes publiquement.
- /chat et /search peuvent rester anonymes en local, mais en production exiger API key/JWT sauf PUBLIC_API_ANONYMOUS=true.
- Ajouter limites Pydantic/Query:
  - q: min_length=1, max_length=500
  - thread_id: max_length raisonnable, format UUID si possible
  - include_domains/exclude_domains: longueur totale max, nombre max 20, domaine regex strict.
- Vérifier que require_scope("read") pour search/datasets/threads read, require_scope("write") pour chat/delete selon modèle choisi.
- Empêcher un client de lire/continuer/supprimer les threads d’un autre client si le schéma supporte owner/client_id. Si non supporté, au minimum documenter le risque et protéger threads derrière admin seulement.
- Limiter queries envoyées aux webhooks/logs: tronquer à 100 caractères ou rendre configurable.

Phase 5: clients.py, stockage credentials.
- Ne plus stocker les nouvelles api_key/client_secret en clair. Stocker seulement api_key_hash et client_secret_hash.
- Conserver compatibilité migration: anciennes colonnes peuvent rester, mais ne plus les remplir pour nouveaux clients si possible, ou les remplir avec ""/NULL selon schéma.
- Retourner api_key/client_secret seulement lors de create_client/regenerate_api_key.
- Utiliser hmac.compare_digest pour comparer les hash dans authenticate_client et API key verification.
- regenerate_api_key doit utiliser _write_lock.
- Valider name: 1-80 chars, description: <=500 chars, scopes subset AVAILABLE_SCOPES, rate_limit entre 1 et borne raisonnable.
- Assainir client_logs: tronquer query/user_agent/path/models/tools à longueurs bornées; ne jamais stocker headers Authorization/X-API-Key.
- Ajouter cleanup simple des logs clients ou fonction de rétention si facile.

Phase 6: routes/oauth.py.
- En production, JWT_SECRET doit être obligatoire et stable; ne pas générer secret aléatoire silencieux en prod.
- Ajouter Field min/max_length sur TokenRequest et RefreshRequest.
- Ajouter rate-limit sur /oauth/token et /oauth/token/refresh, par IP et idéalement par client_id.
- payload["sub"] doit devenir payload.get("sub") avec validation.
- require_scope ne doit pas révéler les scopes disponibles dans le message d’erreur.
- Pour révocation plus rapide, require_scope doit vérifier les scopes DB actuels plutôt que faire confiance uniquement aux scopes JWT, ou croiser intersection JWT/DB.
- Revoir /oauth/token/refresh: soit supprimer/désactiver par défaut, soit renommer clairement car il refresh un access token récent, pas un vrai refresh token. Préférer OAUTH_ALLOW_ACCESS_TOKEN_REFRESH=false par défaut en production.

Phase 7: routes/rate_limit.py.
- Corriger deque(maxlen=200), car ça casse les limites client >200/min. Utiliser deque() et nettoyage manuel, ou maxlen dynamique >= max_requests.
- Borner max_requests entre 1 et RATE_MAX_ABSOLUTE configurable.
- Ajouter helper optionnel retournant retry_after, ou au minimum calcul interne propre.
- Documenter que le rate-limit est in-memory et non fiable multi-worker. Ne pas implémenter Redis sauf si déjà dépendance présente.

Phase 8: core/settings.py.
- Corriger bug global: _save_settings doit déclarer global _settings_cache, _settings_mtime, _settings_last_check.
- Créer le dossier data avant écriture.
- Écrire settings.json atomiquement via fichier temporaire + os.replace.
- _load_settings doit retourner deepcopy(_settings_cache) pour éviter mutation non sauvegardée.
- Logger JSONDecodeError au lieu de remplacer silencieusement par {}.
- Optionnel: validation minimale des sections dans routes/admin.py avant existing.update(data).

Phase 9: frontend API keys.
- Vérifier que renderAPIKeysForm est appelé avant loadAPIKeys.
- Vérifier que le submit handler est protégé si #apikeys-form absent.
- Vérifier que la sauvegarde ignore les valeurs masquées "***" et "...".
- Garder cache bust sur styles.css, apikeys.js, init.js.
- Vérifier node --check admin/js/apikeys.js admin/js/init.js.

Critères d’acceptation:
- Un utilisateur non authentifié ne peut pas accéder à /admin, /admin/docs, /admin/env, /admin/env/*/reveal, /admin/service/*, /admin/data/history, /admin/danger/reset.
- En production, /threads et /metrics ne sont pas publics.
- Aucune vraie clé API n’est exposée par /admin/env.
- Une valeur masquée ne peut pas écraser un secret existant.
- Les nouveaux clients API ne stockent pas leurs secrets en clair.
- OAuth/JWT ne dépend pas d’un secret aléatoire instable en production.
- python -m py_compile passe sur les fichiers Python modifiés.
- node --check passe sur les fichiers JS modifiés.
- grep confirme les protections clés.
- Le serveur redémarre et l’admin API keys s’affiche encore.

Commandes de vérification attendues:
- python3 -m py_compile server.py routes/admin.py routes/auth.py routes/api.py routes/oauth.py routes/rate_limit.py clients.py core/settings.py
- node --check admin/js/apikeys.js
- node --check admin/js/init.js
- grep ciblés sur: require_admin, ADMIN_ALLOW, JWT_SECRET, compare_digest, os.replace, renderAPIKeysForm, isMaskedApiValue
- curl -i /admin sans cookie doit rediriger login
- curl -i /admin/env sans cookie doit retourner 401/redirect
- curl -i /threads en production sans credentials doit retourner 401
- curl -i /metrics en production sans credentials doit retourner 401

Livrable final:
- Résumé court par fichier.
- Liste des comportements changés.
- Commandes exécutées et résultat.
- Points volontairement laissés en option/configuration.
- Instructions de redémarrage: sudo systemctl restart websearch-agent, puis Ctrl+F5 ou clear PWA cache.