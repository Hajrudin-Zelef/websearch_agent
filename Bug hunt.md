# 🐛 Bug Hunt Report — WebSearch Agent

**Date:** 2026-08-02
**Méthodologie:** Revue de code exhaustive + systematic debugging

---

## 🔴 Sévère (4 bugs)

---

### BUG #1 — Race condition: cache partagé sans lock entre appels concurrents

- **Fichier:** `agent.py:353,363,374`
- **Impact:** Corruption de données ou crash si 2 requêtes simultanées
- **Preuve:**

```python
_cache: dict[str, tuple[float, str]] = {}  # module-level, partagé

def _get_cached(query, tools):  # lit _cache sans lock
def _set_cached(query, tools, result):  # écrit _cache sans lock
```

`run_agent_async` est appelé depuis FastAPI. Si 2 requêtes HTTP arrivent simultanément, 2 coroutines asyncio accèdent au même dict `_cache`. Les opérations dict Python ne sont pas thread-safe ni async-safe — une coroutine peut itérer pendant qu'une autre modifie → `RuntimeError: dictionary changed size during iteration` ou corruption silencieuse.

`_set_cached` itère avec `sorted(_cache.items(), ...)` pendant qu'un `del _cache[key]` concurrent peut s'exécuter.

**Fix suggéré:** Utiliser `asyncio.Lock` ou remplacer par `functools.lru_cache`.

---

### BUG #2 — Les singletons `_get_client` / `_get_async_client` ne sont jamais utilisés

- **Fichier:** `agent.py:468-495` (définis) vs `agent.py:622,709` (ignorés)
- **Impact:** Nouveau client + connection pool HTTP créé à chaque requête, pas de reuse des connexions
- **Preuve:**

```python
# Ligne 468 — défini mais jamais appelé:
def _get_client(model: str) -> OpenAI:
    if model not in _clients: ...
    return _clients[model]

# Ligne 622 — crée un NOUVEAU client à chaque appel:
client = OpenAI(
    base_url=PROVIDER_CONFIG[PROVIDER]["base_url"],
    api_key=os.getenv(...),
    timeout=timeout,
    max_retries=0,
)
```

`_try_model_sync` et `_try_model_async` bypassent le singleton et créent une nouvelle instance client + connection pool HTTP à **chaque requête**. Les fonctions `_get_client` et `_get_async_client` sont du **code mort**. Résultat: pas de reuse des connexions HTTP, overhead inutile.

**Fix suggéré:** Utiliser `_get_client(model)` / `_get_async_client(model)` dans `_try_model_sync` / `_try_model_async`.

---

### BUG #3 — La réponse textuelle légitime du LLM est jetée à la poubelle

- **Fichier:** `agent.py:640-642` et `agent.py:727-729`
- **Impact:** Si le LLM répond du texte sans tool call, l'utilisateur reçoit un fallback générique au lieu de la vraie réponse
- **Preuve:**

```python
if not message.tool_calls:
    if not _handle_dsml_recovery(message):
        return _FALLBACK_RESPONSE  # ← jette la réponse du LLM!
```

Si le LLM répond un texte comme *"Je ne trouve pas d'information sur ce sujet dans mes sources"*, le code jette ce message et retourne un fallback générique. L'utilisateur perd l'information contextuelle.

De plus, si `_handle_dsml_recovery` réussit, `message.content` contient encore le texte DSML brut, qui est inclus dans l'historique envoyé au LLM pour le 2e appel (`_build_tool_call_message` inclut `message.content`). Le LLM voit du markup DSML dans la conversation → confusion possible.

**Fix suggéré:** Si `message.content` est non vide et pas du DSML, retourner `message.content` directement.

---

### BUG #4 — `for` séquentiel, pas une "race condition" comme annoncé

- **Fichier:** `agent.py:783-789`
- **Impact:** L'utilisateur attend le timeout du modèle 1 avant que le modèle 2 ne démarre
- **Preuve:**

```python
# Race condition — le premier qui repond gagne  ← commentaire TROMPEUR
for model_info in models:                        ← boucle SÉQUENTIELLE
    try:
        result = await asyncio.wait_for(
            _try_model_async(model_info, ...),
            timeout=model_info["timeout"] + 2,
        )
```

Le commentaire dit "race condition" mais c'est un `for` séquentiel. Modèle 1 échoue → seulement APRÈS, modèle 2 est essayé. Si modèle 1 timeout après 12s, l'utilisateur attend 12s avant que modèle 2 ne commence. Une vraie race condition utiliserait `asyncio.gather` ou `asyncio.wait(FIRST_COMPLETED)`.

**Fix suggéré:** Remplacer par `asyncio.wait(..., return_when=FIRST_COMPLETED)`.

---

## 🟠 Medium (4 bugs)

---

### BUG #5 — Double fetch massif: fallback refetch TOUS les 112 flux RSS

- **Fichier:** `news_rss.py:301-308`
- **Impact:** 112 connexions HTTP simultanées pour un simple "aucun résultat"
- **Preuve:**

```python
# Si aucun article ne matche le filtre:
if query_lower and not all_articles:
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(_fetch_feed, source, url, "", ...)
                   for source, url in FEEDS.items()]  # 112 requêtes!
```

Si un utilisateur cherche "xyz123" (aucun match), le code refetch **tous les 112 flux RSS** depuis le réseau — même ceux déjà en cache. 112 connexions HTTP simultanées pour un résultat vide.

**Fix suggéré:** Ne pas refetch ce qui est déjà en cache, ou limiter le fallback à N flux prioritaires.

---

### BUG #6 — Race condition dans le cache RSS

- **Fichier:** `news_rss.py:24-25, 246, 273-287`
- **Impact:** `RuntimeError` possible sous charge concurrente
- **Preuve:**

```python
_feed_cache: dict[str, tuple[float, list[dict]]] = {}  # module-level

def news_search(...):
    # Itère sur _feed_cache
    for source, url in FEEDS.items():
        if source in _feed_cache: ...

    # Lance des threads qui modifient _feed_cache
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(_fetch_feed, ...)]  # _fetch_feed écrit dans _feed_cache
```

`news_search` itère sur `_feed_cache` pendant que `_fetch_feed` (dans un thread concurrent) écrit dedans (ligne 246: `_feed_cache[source] = (now, all_articles)`). → `RuntimeError` possible.

**Fix suggéré:** Utiliser `threading.Lock` autour des accès à `_feed_cache`.

---

### BUG #7 — `_cleanup_rate_history` modifie le dict pendant qu'une autre requête le lit

- **Fichier:** `server.py:77-86`
- **Impact:** Crash possible si 2 requêtes arrivent simultanément
- **Preuve:**

```python
def _cleanup_rate_history():
    empty_ips = [
        ip for ip, hits in _rate_history.items()  # itération sur la vue
        ...
    ]
    for ip in empty_ips:
        del _rate_history[ip]  # modification concurrente possible
```

Si 2 requêtes arrivent en même temps, l'une peut appeler `_cleanup_rate_history` pendant que l'autre exécute `_check_rate` qui fait `hits.append(now)`. Le `deque` est thread-safe mais la suppression d'IP du dict ne l'est pas.

**Fix suggéré:** Protéger `_rate_history` avec `asyncio.Lock`.

---

### BUG #8 — `quote(title.replace(' ', '_'), safe='')` casse les URLs Wikipedia

- **Fichier:** `wikipedia.py:58` et `wikipedia_en.py:58`
- **Impact:** URLs invalides pour les titres avec accents ou apostrophes
- **Preuve:**

```python
url = f"https://fr.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}"
```

`quote` avec `safe=''` encode TOUT, y compris les caractères valides dans les URLs. Exemple: le titre `L'Île-de-France` devient une URL avec `%27` pour l'apostrophe. L'URL correcte serait `L'%C3%8Ele-de-France`. L'URL générée est invalide — Wikipedia retournera 404.

**Fix suggéré:** Utiliser `safe='/_'` ou `safe='/'` puisque les `_` sont déjà insérés.

---

## 🟡 Low (3 bugs)

---

### BUG #9 — `_FALLBACK_RESPONSE` ambiguë: erreur technique ou refus légitime?

- **Fichier:** `agent.py:450-454`
- **Impact:** L'appelant ne peut pas distinguer erreur technique vs refus légitime
- **Preuve:**

3 cas distincts retournent le même message:
1. LLM refuse (pas de tool_calls)
2. Tous les modèles échouent (timeout/réseau)
3. Synthèse vide après outils

L'appelant (`server.py`) ne peut pas distinguer, donc le champ `refused` dans la réponse API est peu fiable.

**Fix suggéré:** Retourner des messages d'erreur distincts ou utiliser un mécanisme de status code interne.

---

### BUG #10 — Pattern `nouvelle` matche des faux positifs dans le routeur

- **Fichier:** `router.py:89`
- **Impact:** Requêtes mal routées vers `news_search` au lieu de `perplexity_search`
- **Preuve:**

```python
r"\b(breaking|nouvelle|sujet du jour)\b",
```

`nouvelle` matche aussi *"nouvelle technologie"*, *"nouvelle version"*, routant à tort vers `news_search` au lieu de `perplexity_search`.

**Fix suggéré:** Remplacer par `r"\b(nouvelles?|actualit[ée]s?)\b"` ou utiliser un pattern plus spécifique comme `r"\b(dernière nouvelle|nouvelle actu)\b"`.

---

### BUG #11 — `safe=''` trop agressif dans `quote()` pour les URLs Wikipedia

- **Fichier:** `wikipedia.py:58` et `wikipedia_en.py:58`
- **Impact:** Même bug que #8, mais spécifique au paramètre `safe=''`
- **Preuve:**

```python
url = f"https://fr.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}"
```

`title.replace(' ', '_')` remplace les espaces par `_`, puis `quote` encode tout. Mais `_` n'a pas besoin d'être encodé dans une URL. Résultat: les titres avec accents ou apostrophes génèrent des URLs incorrectes.

**Fix suggéré:** `quote(title.replace(' ', '_'), safe='/_')`.

---

## 📊 Résumé

| # | Sévérité | Fichier | Description |
|---|----------|---------|-------------|
| 1 | 🔴 | `agent.py:353` | Race condition cache partagé sync/async |
| 2 | 🔴 | `agent.py:622,709` | Singletons client jamais utilisés (code mort) |
| 3 | 🔴 | `agent.py:640,727` | Réponse LLM jetée si pas de tool_calls |
| 4 | 🔴 | `agent.py:784` | Commentaire "race" mais boucle séquentielle |
| 5 | 🟠 | `news_rss.py:301` | Double fetch 112 flux en fallback |
| 6 | 🟠 | `news_rss.py:246` | Race condition cache RSS |
| 7 | 🟠 | `server.py:77` | Race condition cleanup rate history |
| 8 | 🟠 | `wikipedia.py:58` | `quote()` casse les URLs avec accents |
| 9 | 🟡 | `agent.py:450` | `_FALLBACK_RESPONSE` ambiguë |
| 10 | 🟡 | `router.py:89` | Pattern `nouvelle` → faux positifs |
| 11 | 🟡 | `wikipedia.py:58` | `safe=''` trop agressif dans `quote()` |
