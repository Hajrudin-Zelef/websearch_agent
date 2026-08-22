# TROUBLESHOOT — Guide de dépannage

> Voir aussi : [DEPLOYMENT.md](DEPLOYMENT.md), [INSTALL.md](INSTALL.md)

Guide complet pour diagnostiquer et resoudre tous les problemes.

---

## Table des matières

1. [Erreurs d'installation](#1-erreurs-dinstallation)
2. [Erreurs de configuration](#2-erreurs-de-configuration)
3. [Erreurs de demarrage](#3-erreurs-de-demarrage)
4. [Erreurs API](#4-erreurs-api)
5. [Erreurs de recherche](#5-erreurs-de-recherche)
6. [Erreurs Docker](#6-erreurs-docker)
7. [Erreurs reseau](#7-erreurs-reseau)
8. [Erreurs de performance](#8-erreurs-de-performance)
9. [Erreurs de securite](#9-erreurs-de-securite)
10. [Erreurs OAuth2](#10-erreurs-oauth2)
11. [Erreurs panneau admin](#11-erreurs-panneau-admin)
12. [Erreurs SQLite](#12-erreurs-sqlite)
13. [Erreurs webhooks](#13-erreurs-webhooks)
14. [Problemes de cache](#14-problemes-de-cache)
15. [Erreurs LLM](#15-erreurs-llm)
16. [Erreurs extraction de contenu](#16-erreurs-extraction-de-contenu)
17. [Problemes PWA](#17-problemes-pwa)
18. [Erreurs CORS](#18-erreurs-cors)
19. [Problemes de migration](#19-problemes-de-migration)
20. [Diagnostic automatique](#20-diagnostic-automatique)

---

## 1. Erreurs d'installation

### 1.1 Python

| Erreur | Cause | Solution |
|--------|-------|----------|
| `python: command not found` | Python non installe | `sudo apt install python3 python3-pip python3-venv` |
| `python3: command not found` | Alias manquant | `sudo ln -s /usr/bin/python3 /usr/bin/python` |
| `pip: command not found` | pip non installe | `sudo apt install python3-pip` |
| `ensurepip is not available` | venv incomplet | `sudo apt install python3-venv` |

**Verification :**
```bash
python3 --version
pip3 --version
```

### 1.2 Dependances Python

| Erreur | Cause | Solution |
|--------|-------|----------|
| `error: externally-managed-environment` | Python 3.11+ | `pip install --break-system-packages -r requirements.txt` |
| `Could not find a version that satisfies` | Package inexistant | `pip install --upgrade pip` |
| `Failed building wheel for` | Compilation manquante | `sudo apt install build-essential python3-dev` |
| `No module named '_ssl'` | SSL manquant | `sudo apt install python3-ssl` |

**Solution universelle :**
```bash
python3 -m venv --clear venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 1.3 Git

| Erreur | Cause | Solution |
|--------|-------|----------|
| `git: command not found` | Git non installe | `sudo apt install git` |
| `Permission denied (publickey)` | SSH non configure | Utiliser HTTPS : `git clone https://...` |
| `Repository not found` | Depot inexistant | Verifier l'URL du depot |

---

## 2. Erreurs de configuration

### 2.1 Variables d'environnement

| Erreur | Cause | Solution |
|--------|-------|----------|
| `OPENROUTER_API_KEY non definie` | Cle manquante | Ajouter dans `.env` |
| `PERPLEXITY_API_KEY non definie` | Cle manquante | Ajouter dans `.env` |
| `TAVILY_API_KEY non definie` | Cle manquante | Ajouter dans `.env` |
| `BRAVE_API_KEY non definie` | Cle manquante | Ajouter dans `.env` |
| `Variable X non definie` | Variable manquante | Verifier `.env` |

**Verification :**
```bash
# Verifier le fichier .env
cat .env

# Verifier une variable
grep "OPENROUTER_API_KEY" .env
```

### 2.2 Cles API invalides

| Erreur | Cause | Solution |
|--------|-------|----------|
| `401 Unauthorized` | Cle invalide | Regenerer la cle sur le site |
| `403 Forbidden` | Cle expiree | Verifier le statut de la cle |
| `Invalid API key` | Copie incorrecte | Recopier la cle sans espaces |

**Test de validite :**
```bash
# Tester OpenRouter
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models | head -50

# Tester Perplexity
curl -H "Authorization: Bearer $PERPLEXITY_API_KEY" \
  https://api.perplexity.ai/chat/completions \
  -d '{"model":"sonar","messages":[{"role":"user","content":"test"}]}'
```

### 2.3 Fichier .env

| Erreur | Cause | Solution |
|--------|-------|----------|
| `No such file or directory` | Fichier manquant | `cp .env.example .env` |
| `SyntaxError` | Mauvais format | Verifier les guillemets |
| `KeyError` | Variable vide | Ajouter une valeur |

**Format correct :**
```bash
# Bon
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# Mauvais
OPENROUTER_API_KEY = sk-or-v1-xxxxx  # Espaces
OPENROUTER_API_KEY: sk-or-v1-xxxxx   # Mauvais separateur
```

---

## 3. Erreurs de demarrage

### 3.1 Port deja utilise

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Address already in use` | Port 4500 occupe | Changer le port ou tuer le process |

**Solution :**
```bash
# Trouver le process sur le port 4500
sudo ss -tlnp | grep 4500
# ou (si lsof est installe)
sudo lsof -i :4500

# Si le service tourne deja en systemd, ne pas le relancer en manuel :
sudo systemctl status websearch-agent

# Sinon, tuer le process manuel
kill -9 <PID>

# Ou utiliser un autre port
uvicorn server:app --port 8001
```

### 3.2 Erreurs de syntaxe Python

| Erreur | Cause | Solution |
|--------|-------|----------|
| `SyntaxError: invalid syntax` | Code invalide | Verifier la syntaxe |
| `IndentationError` | Indentation incorrecte | Corriger les espaces |
| `NameError: name 'X' is not defined` | Variable non definie | Verifier les imports |

**Verification :**
```bash
python3 -m py_compile agent.py
python3 -m py_compile server.py
```

### 3.3 Erreurs d'import

| Erreur | Cause | Solution |
|--------|-------|----------|
| `ModuleNotFoundError` | Module manquant | `pip install <module>` |
| `ImportError` | Module corrompu | Reinstaller le venv |
| `cannot import name` | Nom incorrect | Verifier le nom de l'import |

**Solution :**
```bash
# Reinstaller toutes les dependances
pip install --force-reinstall -r requirements.txt
```

---

## 4. Erreurs API

### 4.1 OpenRouter

| Erreur | Code | Solution |
|--------|------|----------|
| `401 Unauthorized` | Auth echouee | Verifier la cle API |
| `429 Too Many Requests` | Rate limit | Attendre ou reduire la frequence |
| `500 Internal Server Error` | Cote serveur | Reessayer plus tard |
| `503 Service Unavailable` | Service indisponible | Reessayer plus tard |
| `Model not found` | Modele inexistant | Verifier le nom du modele |

**Rate limits :**
- Gratuit : 10 req/min, 200 req/jour
- Payant : 500 req/min, 10000 req/jour

### 4.2 Perplexity

| Erreur | Code | Solution |
|--------|------|----------|
| `401 Unauthorized` | Cle invalide | Regenerer la cle |
| `402 Payment Required` | Credit epuise | Ajouter des credits |
| `429 Too Many Requests` | Rate limit | Attendre 1 minute |
| `400 Bad Request` | Requete invalide | Verifier les parametres |

### 4.3 Tavily

| Erreur | Code | Solution |
|--------|------|----------|
| `401 Unauthorized` | Cle invalide | Verifier la cle |
| `429 Too Many Requests` | Limite atteinte | Attendre ou upgrader |
| `400 Bad Request` | Parametres incorrects | Verifier la requete |

### 4.4 Brave Search

| Erreur | Code | Solution |
|--------|------|----------|
| `401 Unauthorized` | Cle invalide | Verifier la cle |
| `403 Forbidden` | Acces refuse | Verifier le plan |
| `429 Too Many Requests` | Quota depasse | Attendre le mois suivant |

### 4.5 SearXNG

| Erreur | Code | Solution |
|--------|------|----------|
| `429 Too Many Requests` | Rate limit | Utiliser une autre instance |
| `Connection refused` | Instance down | Verifier l'URL |
| `403 Forbidden` | Acces bloque | Changer d'instance |

**Instances publiques :**
```
https://search.inetol.net
https://searx.be
https://search.bus-hit.me
https://searxng.ch
```

### 4.6 Firecrawl / ScrapeGraph AI (Just Scrape)

| Erreur | Code | Solution |
|--------|------|----------|
| `401 Unauthorized` | Cle invalide | Verifier `FIRECRAWL_API_KEY` / `SGAI_API_KEY` |
| `429 Too Many Requests` | Quota depasse | Attendre ou upgrader le plan |
| `Timeout` | Extraction lente | Normal sur des pages lourdes, le fallback s'applique |

---

## 5. Erreurs de recherche

### 5.1 Aucun resultat

| Symptome | Cause | Solution |
|----------|-------|----------|
| Resultats vides | Requete trop specifique | Elargir la recherche |
| Resultats vides | Source indisponible | Essayer une autre source |
| Resultats vides | Timeout | Augmenter le timeout |

### 5.2 Resultats incorrects

| Symptome | Cause | Solution |
|----------|-------|----------|
| Reponse fausse | Modele hallucine | Verifier avec une autre source |
| Reponse incomplete | Contexte insuffisant | Reformuler la question |
| Reponse en anglais | Mauvais detecteur | Ajouter "en francais" |

### 5.3 Erreurs de parsing

| Erreur | Cause | Solution |
|--------|-------|----------|
| `JSONDecodeError` | Reponse invalide | Reessayer |
| `KeyError` | Champ manquant | Signaler le bug |
| `UnicodeDecodeError` | Encodage | Normaliser l'encodage |

### 5.4 Cache et temporal detection

| Symptome | Cause | Solution |
|----------|-------|----------|
| Reponse lente (>8s) | Toutes les sources timeout | Verifier circuit breaker : `curl http://localhost:4500/metrics` |
| Resultats obsolètes | Cache TTL 60s | Attendre 60s ou changer la requete |
| X-Cache: HIT | Reponse du cache | Normal — la requete identique est cachée 60s |
| X-Cache: MISS | Nouvelle recherche | Normal — le cache a expire ou premiere requete |
| Reponses non pertinentes | Routing temporel mal detecte | Verifier les logs : `journalctl -u websearch-agent \| grep temporal` |
| Sources fresques manquantes | Circuit breaker ouvert | Redemarrer : `sudo systemctl restart websearch-agent` |

**Commandes utiles :**
```bash
# Voir les metriques des sources
curl -s http://localhost:4500/metrics | python3 -m json.tool

# Vider le cache
curl -X POST http://localhost:4500/admin/cache/clear

# Voir les logs de routage
journalctl -u websearch-agent | grep -i "temporal\|select\|route"
```

---

## 6. Erreurs Docker

### 6.1 Installation

| Erreur | Cause | Solution |
|--------|-------|----------|
| `docker: command not found` | Docker non installe | `curl -fsSL https://get.docker.com \| sh` |
| `Cannot connect to Docker daemon` | Service arrete | `sudo systemctl start docker` |
| `permission denied` | Permissions | `sudo usermod -aG docker $USER` |

### 6.2 Build

| Erreur | Cause | Solution |
|--------|-------|----------|
| `ERROR: failed to solve` | Erreur Dockerfile | Verifier le Dockerfile |
| `Could not pull image` | Image introuvable | Verifier le nom de l'image |
| `No space left on device` | Espace disque | `docker system prune -a` |

### 6.3 Demarrage

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Container failed to start` | Erreur au demarrage | `docker compose logs` |
| `Port already in use` | Port occupe | Changer le port |
| `Network already exists` | Reseau existant | `docker network rm` |

**Commandes de diagnostic :**
```bash
# Voir les logs
docker compose logs websearch-agent
docker compose logs searxng

# Voir les conteneurs
docker compose ps

# Redemarrer
docker compose restart

# Rebuild complet
docker compose down
docker compose up -d --build
```

### 6.4 SearXNG

| Erreur | Cause | Solution |
|--------|-------|----------|
| `502 Bad Gateway` | SearXNG pas pret | Attendre le healthcheck |
| `Connection refused` | SearXNG arrete | `docker compose restart searxng` |
| `Rate limited` | Trop de requetes | Utiliser une autre instance |

---

## 7. Erreurs reseau

### 7.1 Connexion

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Connection refused` | Serveur arrete | `sudo systemctl start websearch-agent` |
| `Connection timeout` | Reseau lent | Augmenter le timeout |
| `DNS resolution failed` | DNS KO | Verifier la connexion |
| `SSL certificate problem` | Certificat invalide | `pip install certifi` |

### 7.2 Proxy

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Proxy connection refused` | Proxy incorrect | Verifier les parametres |
| `407 Proxy Authentication Required` | Auth proxy | Configurer les identifiants |

**Configuration proxy :**
```bash
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
```

### 7.3 Firewall

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Connection timeout` | Port bloque | Ouvrir le port |
| `Permission denied` | SELinux | `setsebool -P httpd_can_network_connect 1` |

---

## 8. Erreurs de performance

### 8.1 Lenteur

| Symptome | Cause | Solution |
|----------|-------|----------|
| Reponse lente (>10s) | Modele lent | Utiliser un modele plus rapide |
| Reponse lente | Timeout eleve | Reduire les timeouts |
| Reponse lente | Trop d'outils | Limiter les outils |
| Reponse lente | Cache vide | Premier appel = lent |

**Optimisations :**
```bash
# Reduire les timeouts dans agent.py
MODEL_POOL = [
    {"model": "...", "timeout": 5.0},  # Plus agressif
]

# Limiter les outils dans router.py
TOOL_LEVELS[1] = ["perplexity_search"]  # Un seul outil
```

### 8.2 Memoire

| Symptome | Cause | Solution |
|----------|-------|----------|
| `MemoryError` | Fuite memoire | Redemarrer le serveur |
| `OOMKilled` (Docker) | Limite depassee | Augmenter la limite |
| Service tue par systemd | `MemoryMax` atteint (512M par defaut) | Augmenter `MemoryMax` dans `websearch-agent.service` |

**Limites Docker :**
```yaml
deploy:
  resources:
    limits:
      memory: 1G
```

**Limite systemd (service reel) :**
```ini
# Dans /etc/systemd/system/websearch-agent.service
MemoryMax=512M
```

### 8.3 CPU

| Symptome | Cause | Solution |
|----------|-------|----------|
| CPU 100% | Boucle infinie | Verifier le code |
| CPU eleve | Trop de workers | Reduire les workers |

**Workers uvicorn :**
```bash
# Limiter a 2 workers
uvicorn server:app --workers 2
```

---

## 9. Erreurs de securite

### 9.1 Cles exposees

| Symptome | Solution |
|----------|----------|
| Cle dans les logs | Nettoyer les logs |
| Cle dans Git | `git filter-branch` (voir note ci-dessous) |
| Cle dans .env | Verifier .gitignore |

> `.env` est dans `.gitignore` par defaut et ne devrait jamais etre commite. Si vous constatez qu'une cle a fuite (Git, logs, backup), la seule protection fiable est de **revoquer et regenerer la cle** aupres du fournisseur — nettoyer l'historique Git ne suffit pas si la cle a deja pu etre vue ou indexee.

**Nettoyer Git (si une cle a ete commitee par erreur) :**
```bash
# Verifier si une cle est dans l'historique
git log --all -p | grep "sk-or-v1"

# Si oui, revoquer la cle en premier, puis reecrire l'historique
# (attention, c'est dangereux et reecrit les hashs de commits)
```

### 9.2 Rate limiting

| Symptome | Cause | Solution |
|----------|-------|----------|
| `429 Too Many Requests` | Trop de requetes | Augmenter les delais |
| `429` sur OpenRouter | Quota depasse | Upgrader le plan |

### 9.3 Injection

| Symptome | Prevention |
|----------|------------|
| Requete malforme | Validation Pydantic |
| XSS | Sanitisation des entrees, headers de securite (X-Content-Type-Options, X-Frame-Options) |

---

## 10. Erreurs OAuth2

### 10.1 Token expire

| Erreur | Cause | Solution |
|--------|-------|----------|
| `401 — Non authentifie` | Token JWT expire (duree de vie: 1h) | Rafraichir le token via `/oauth/token/refresh` |
| `Token invalide ou trop ancien pour etre rafraichi` | Token expire depuis plus de 15 min | Obtenir un nouveau token via `/oauth/token` |

**Explication :** Les tokens JWT ont une duree de vie de 3600 secondes (1 heure). Un token expire peut etre rafraichi dans les 15 minutes suivant son expiration (grace period). Pass ce delai, un nouveau token complet est requis.

**Solution — Rafraichir avant expiration :**
```python
import requests

# 1. Obtenir un token initial
resp = requests.post("http://localhost:4500/oauth/token", json={
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET"
})
token_data = resp.json()
access_token = token_data["access_token"]

# 2. Utiliser le token
headers = {"Authorization": f"Bearer {access_token}"}
resp = requests.post("http://localhost:4500/chat",
    headers=headers,
    json={"message": "test"})

# 3. Rafraichir (dans les 15 min apres expiration)
resp = requests.post("http://localhost:4500/oauth/token/refresh", json={
    "refresh_token": access_token  # L'ancien token sert de refresh
})
new_token_data = resp.json()
new_access_token = new_token_data["access_token"]
```

### 10.2 Client ID invalide

| Erreur | Cause | Solution |
|--------|-------|----------|
| `401 — Identifiants invalides ou client desactive` | `client_id` inexistant ou `client_secret` incorrect | Verifier les credentials dans le panel admin |
| `401 — Client introuvable ou desactive` | Le client a ete desactive | Reactiver le client dans `/admin/clients` |

**Diagnostic :**
```bash
# Verifier que le client existe et est actif
curl http://localhost:4500/admin/clients \
  -b /tmp/cookies.txt | python3 -m json.tool

# Si le client est desactive, le reactiver via le panel admin
# ou supprimer et recreer
```

### 10.3 Erreurs de scope

| Erreur | Cause | Solution |
|--------|-------|----------|
| `403 — Scope 'write' requis. Scopes disponibles: read` | Le token n'a pas le scope requis | Utiliser un token avec les bons scopes ou modifier les scopes du client |
| `403 — Aucun scope` | Le client n'a pas de scopes definis | Assigner des scopes via le panel admin |

**Scopes disponibles :**

| Scope | Droits |
|-------|--------|
| `read` | Lire les conversations et rechercher |
| `write` | Envoyer des messages et creer des threads |
| `admin` | Gerer les settings, clients et administration |

**Modifier les scopes d'un client :**
```bash
# Via l'API admin
curl -X PUT http://localhost:4500/admin/clients/CLIENT_ID/scopes \
  -H "Content-Type: application/json" \
  -b /tmp/cookies.txt \
  -d '{"scopes": ["read", "write", "admin"]}'
```

### 10.4 Echec de refresh

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Token invalide ou trop ancien pour etre rafraichi` | Token expire depuis plus de 15 min (grace period depassee) | Obtenir un nouveau token complet via `/oauth/token` |
| `Client introuvable ou desactive` | Le client a ete supprime ou desactive entre-temps | Recreer le client |

**Grace period :** Le endpoint `/oauth/token/refresh` accepte un token expire a condition qu'il ait expire il y a moins de 900 secondes (15 min). Ce mecanisme evite les coups de ble pour les tokens en fin de vie.

**Strategie de rafraichissement recommandee :**
```python
import time

class TokenManager:
    def __init__(self, client_id, client_secret, base_url="http://localhost:4500"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.token = None
        self.expires_at = 0

    def get_token(self):
        # Rafraichir 5 min avant expiration
        if self.token and time.time() < self.expires_at - 300:
            return self.token
        self._refresh()
        return self.token

    def _refresh(self):
        if self.token:
            # Essayer le refresh d'abord
            try:
                resp = requests.post(f"{self.base_url}/oauth/token/refresh",
                    json={"refresh_token": self.token})
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data["access_token"]
                    self.expires_at = time.time() + data["expires_in"]
                    return
            except Exception:
                pass
        # Sinon, obtenir un token neuf
        resp = requests.post(f"{self.base_url}/oauth/token", json={
            "client_id": self.client_id,
            "client_secret": self.client_secret
        })
        data = resp.json()
        self.token = data["access_token"]
        self.expires_at = time.time() + data["expires_in"]
```

---

## 11. Erreurs panneau admin

### 11.1 502 Bad Gateway

| Erreur | Cause | Solution |
|--------|-------|----------|
| `502 Bad Gateway` | Le serveur FastAPI ne repond pas | Redemarrer le service |
| `502 Bad Gateway` | Le port 4500 est bloque par un firewall | Verifier les regles firewall |

**Diagnostic :**
```bash
# Verifier que le service tourne
sudo systemctl status websearch-agent

# Verifier que le port repond
curl -s http://127.0.0.1:4500/health

# Verifier les logs
sudo journalctl -u websearch-agent -n 50 --no-pager

# Verifier les regles firewall
sudo iptables -L -n | grep 4500
```

**Redemarrage :**
```bash
# Redemarrer le service
sudo systemctl restart websearch-agent

# Attendre 3 secondes puis verifier
sleep 3 && curl -s http://127.0.0.1:4500/health
```

### 11.2 Session expiree / redirection vers login

| Erreur | Cause | Solution |
|--------|-------|----------|
| Redirection vers `/admin/login.html` en boucle | Cookie `admin_session` invalide ou expire | Se reconnecter |
| `401 Non authentifie` sur les API admin | Session expiree (TTL: 24h) | Se reconnecter |
| `429 Trop de tentatives` | Rate limit login depasse (5 tentatives / 5 min) | Attendre 5 minutes |

**Explication :** Les sessions admin sont stockees en memoire avec un TTL de 24 heures. Elles sont perdues au redemarrage du serveur. Le cookie est `httponly` et `samesite=strict`.

**Verifier la session :**
```bash
# Tester si la session est valide
curl -b /tmp/cookies.txt http://localhost:4500/admin/api/auth/check
# {"authenticated": true} ou {"authenticated": false}

# Se reconnecter
CODE=$(python3 -c "import pyotp; print(pyotp.TOTP('YOUR_TOTP_SECRET').now())")
curl -c /tmp/cookies.txt -X POST http://localhost:4500/admin/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"your-password\",\"totp_code\":\"$CODE\"}"
```

### 11.3 Page blanche / white page

| Erreur | Cause | Solution |
|--------|-------|----------|
| Page blanche apres login | Le service worker cache une ancienne version | Vider le cache du navigateur |
| Page blanche sur `/admin` | Fichier `admin/index.html` manquant | Verifier l'installation |
| `404 Admin UI not found` | Dossier `admin/` absent | Recloner le depot |

**Solution — Vider le cache du service worker :**
```bash
# 1. Ouvrir Chrome DevTools (F12)
# 2. Aller dans l'onglet Application
# 3. Section Service Workers → unregister
# 4. Section Cache Storage → supprimer tous les caches "websearch-static-*"
# 5. Recharger la page (Ctrl+Shift+R)

# Ou via la console :
navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()));
caches.keys().then(names => names.forEach(name => caches.delete(name)));
location.reload();
```

### 11.4 Impossible de se connecter

| Erreur | Cause | Solution |
|--------|-------|----------|
| `401 Identifiants incorrects` | Mauvais login/mdp | Verifier `ADMIN_USER` et `ADMIN_PASSWORD` dans `.env` |
| `401 Code 2FA requis` | 2FA active mais code non fourni | Fournir le code TOTP |
| `401 Code 2FA invalide` | Mauvais code ou horloge decalage | Verifier l'heure du serveur |

**Verifier les identifiants :**
```bash
# Lire les identifiants depuis .env
grep -E "^ADMIN_USER|^ADMIN_PASSWORD|^ADMIN_TOTP_SECRET" .env

# Tester sans 2FA (si ADMIN_TOTP_SECRET est vide)
curl -c /tmp/cookies.txt -X POST http://localhost:4500/admin/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

---

## 12. Erreurs SQLite

### 12.1 Database locked

| Erreur | Cause | Solution |
|--------|-------|----------|
| `sqlite3.OperationalError: database is locked` | Ecriture concurrente ou transaction non terminee | Redemarrer le serveur |
| `database is locked` (apres crash) | WAL journal reste ouvert | Supprimer les fichiers WAL |

**Explication :** SQLite en mode WAL (Write-Ahead Logging) permet la lecture concurrente mais une seule ecriture a la fois. Le `busy_timeout` est regle a 5000ms. Si le delai est depasse, l'erreur se declenche.

**Solution :**
```bash
# 1. Arreter le serveur
sudo systemctl stop websearch-agent

# 2. Verrouiller et recuperer la base
sqlite3 data/threads.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 3. Supprimer les fichiers WAL/SHM si necessaire
rm -f data/threads.db-wal data/threads.db-shm

# 4. Redemarrer
sudo systemctl start websearch-agent
```

### 12.2 Base corrompue

| Erreur | Cause | Solution |
|--------|-------|----------|
| `sqlite3.DatabaseError: database disk image is malformed` | Corruption disque ou crash pendant ecriture | Restaurer depuis la sauvegarde |
| `unable to open database file` | Permissions ou espace disque | Verifier les permissions |

**Diagnostic :**
```bash
# Verifier l'integrite
sqlite3 data/threads.db "PRAGMA integrity_check;"

# Si le resultat n'est pas "ok", il faut restaurer
# Verifier l'espace disque
df -h data/

# Verifier les permissions
ls -la data/threads.db
```

**Restauration :**
```bash
# 1. Sauvegarder la base corrompue
cp data/threads.db data/threads.db.corrupted

# 2. Exporter ce qui est encore lisible
sqlite3 data/threads.db.corrupted ".dump" > data/backup.sql

# 3. Recreer la base
rm data/threads.db data/threads.db-wal data/threads.db-shm
sqlite3 data/threads.db < data/backup.sql

# 4. Redemarrer le serveur
sudo systemctl start websearch-agent
```

### 12.3 Problemes de migration

| Erreur | Cause | Solution |
|--------|-------|----------|
| `column X does not exist` | Schema de base obsolete | Laisser le serveur executer les migrations auto |
| `table X has no column named Y` | Migration non appliquee | Redemarrer le serveur |

**Explication :** Les migrations de schema sont automatiques. Au demarrage, `_init_schema()` dans `clients.py` et `threads.py` verifie les colonnes et les ajoute si necessaire via `ALTER TABLE ADD COLUMN`.

```bash
# Verifier le schema actuel
sqlite3 data/threads.db ".schema clients"
sqlite3 data/threads.db ".schema messages"
sqlite3 data/threads.db ".schema threads"
```

### 12.4 Corruption du WAL journal

| Erreur | Cause | Solution |
|--------|-------|----------|
| `SQLITE_CORRUPT` | Crash pendant ecriture WAL | Truncate le WAL |
| `SQLITE_CANTOPEN` | Fichier WAL manquant ou inaccessible | Supprimer les fichiers WAL/SHM |

```bash
# Checkpoint et troncature du WAL
sqlite3 data/threads.db "PRAGMA wal_checkpoint(TRUNCATE);"

# Si echec, supprimer les fichiers WAL/SHM
rm -f data/threads.db-wal data/threads.db-shm
```

---

## 13. Erreurs webhooks

### 13.1 Webhook non envoye

| Erreur | Cause | Solution |
|--------|-------|----------|
| Aucune notification recue | Webhooks desactives | Activer dans le panel admin (Developer) |
| Aucune notification recue | URL de webhook vide | Configurer `webhook_url` dans settings |

**Verification :**
```bash
# Verifier la config webhook
curl -b /tmp/cookies.txt http://localhost:4500/admin/developer
# "webhooks_enabled": false, "webhook_url": "" → problema

# Activer via le panel admin ou l'API
curl -X POST http://localhost:4500/admin/developer \
  -H "Content-Type: application/json" \
  -b /tmp/cookies.txt \
  -d '{"webhooks_enabled": true, "webhook_url": "https://your-server.com/webhook"}'
```

### 13.2 Timeout webhook

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Webhook chat.completed -> https://... timed out` | Le serveur cible met plus de 5 secondes a repondre | Verifier la latence reseau |
| `Webhook ... failed: Connection refused` | Le serveur cible est arrete | Demarrer le serveur webhook |

**Logs d'echec (dans websearch-agent.log) :**
```
WARNING — Webhook chat.completed -> https://example.com/webhook timed out
WARNING — Webhook search.completed -> https://example.com/webhook failed: Connection refused
```

**Test manuel du webhook :**
```bash
# Tester que l'URL est accessible
curl -X POST https://your-server.com/webhook \
  -H "Content-Type: application/json" \
  -d '{"event":"test","timestamp":0,"data":{}}'

# Verifier la latence
curl -o /dev/null -s -w "Connect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  https://your-server.com/webhook
```

### 13.3 Echec de signature

| Erreur | Cause | Solution |
|--------|-------|----------|
| Aucune signature dans les webhooks | Les webhooks n'incluent pas de signature | Ajouter un secret webhook cote recepteur |

**Explication :** Les webhooks sont des POST JSON simples sans header de signature HMAC. Si vous avez besoin d'authentifier les webhooks, implementez un mecanisme cote recepteur (ex: header secret compare).

**Format des webhooks envoyes :**
```json
{
  "event": "chat.completed",
  "timestamp": 1700000000.0,
  "data": {
    "request_id": "a1b2c3d4",
    "thread_id": "...",
    "model": "openai/gpt-4",
    "duration": 3.2,
    "refused": false,
    "message_length": 42
  }
}
```

**Evenements disponibles :**

| Evenement | Declenche quand |
|-----------|-----------------|
| `chat.completed` | Reponse generee avec succes |
| `chat.error` | Erreur lors du traitement |
| `search.completed` | Recherche terminee |

---

## 14. Problemes de cache

### 14.1 Cache ne fonctionne pas

| Symptome | Cause | Solution |
|----------|-------|----------|
| Reponses toujours lentes | Cache vide ou TTL trop court | Verifier la config du cache |
| Reponses differentes a chaque fois | Cle de cache differente | Verifier que les outils sont identiques |

**Explication :** Le cache est une LRU en memoire (pas partage entre workers). La cle est composee de `query|tool1|tool2`. Si les outils changent d'une requete a l'autre, le cache est manque.

**Verifier les stats du cache :**
```bash
curl -b /tmp/cookies.txt http://localhost:4500/metrics
# "cache": {"size": 15, "max_size": 200, "hits": 42, "misses": 128}
```

### 14.2 Cache stale (resultats expires)

| Symptome | Cause | Solution |
|----------|-------|----------|
| Reponses anciennes served | TTL trop long (defaut: 300s) | Reduire le TTL dans settings.json |
| Besoin de fraicheur immediate | Pas de bypass du cache | Utiliser l'endpoint `/search` au lieu de `/chat` |

**Modifier le TTL :**
```json
// data/settings.json
{
  "cache": {
    "ttl": 60,
    "max_size": 100
  }
}
```

**Vider le cache manuellement :**
```bash
curl -X POST http://localhost:4500/admin/cache/clear \
  -b /tmp/cookies.txt
```

### 14.3 Problemes de memoire du cache

| Symptome | Cause | Solution |
|----------|-------|----------|
| Memoire qui croit indefiniment | Trop d'entrees en cache | Reduire `max_size` |
| `MemoryError` | Cache + autres composants depassent la RAM | Augmenter la RAM ou reduire le cache |

**Limiter la taille :**
```json
// data/settings.json
{
  "cache": {
    "ttl": 120,
    "max_size": 50
  }
}
```

### 14.4 Cache pas partage entre workers

| Symptome | Cause | Solution |
|----------|-------|----------|
| Cache fonctionne parfois | Plusieurs workers uvicorn | Limiter a 1 worker |

**Explication :** Le cache est en memoire Python. Chaque worker a son propre cache. Avec 2 workers, le cache est divise par 2.

```bash
# Limiter a 1 worker
uvicorn server:app --workers 1
```

---

## 15. Erreurs LLM

### 15.1 Tous les modeles ont echoue

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Tous les modeles ont echoue. Reessayez plus tard.` | Tous les modeles du pool ont echoue | Verifier la cle API et les quotas |

**Explication :** L'agent essaie aleatoirement plusieurs modeles (selon le tier de complexite). Si tous echouent, il retourne ce message d'erreur.

**Diagnostic :**
```bash
# Verifier la cle API OpenRouter
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])), 'modeles disponibles')"

# Tester un modele directement
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/chat/completions \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"test"}]}'
```

### 15.2 Timeout du modele

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Modele X echoue (8.0s): Timeout` | Le modele met trop de temps a repondre | Augmenter le timeout ou utiliser un modele plus rapide |
| Timeout sur le streaming | Modele lent ou surcharge | Changer de vitesse dans les settings |

**Configurer le timeout :**
```json
// data/settings.json
{
  "ai": {
    "search_speed": "fast"
  }
}
```

| Vitesse | Timeout multiplier | Modeles par requete |
|---------|-------------------|---------------------|
| `fast` | 0.5x | 2 |
| `normal` | 1.0x | 3 |
| `thorough` | 2.0x | 4 |

### 15.3 Rate limit OpenRouter

| Erreur | Cause | Solution |
|--------|-------|----------|
| `429 Too Many Requests` | Quota OpenRouter depasse | Attendre ou upgrader le plan |
| `402 Payment Required` | Credits epuises | Ajouter des credits |

**Rate limits OpenRouter :**
- Gratuit : 10 req/min, 200 req/jour
- Payant : 500 req/min, 10000 req/jour

**Solution — Circuit breaker :** Si une source echoue trop souvent, le circuit breaker la desactive automatiquement. Il se reinitialise apres un delai.

```bash
# Verifier l'etat du circuit breaker
curl -b /tmp/cookies.txt http://localhost:4500/metrics | python3 -m json.tool | grep circuit
```

### 15.4 Erreur de parsing de la reponse LLM

| Erreur | Cause | Solution |
|--------|-------|----------|
| `JSONDecodeError` | Le modele retourne du JSON invalide | Reessayer (le retry est automatique) |
| `DSML parse error` | Format DSML malforme | Normal — le fallback JSON s'applique |

**Explication :** Le parser essaie DSML d'abord, puis JSON brut. Si les deux echouent, la reponse est consideree comme un refus. C'est un comportement normal — pas un bug.

### 15.5 Modele non trouve

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Model not found` | Nom de modele incorrect dans le pool | Verifier `MODEL_POOL` dans `core/models.py` |
| `404 model not found` | Modele retire d'OpenRouter | Mettre a jour le pool de modeles |

```bash
# Lister les modeles disponibles sur OpenRouter
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('data', []):
    print(m['id'])
" | head -20
```

---

## 16. Erreurs extraction de contenu

### 16.1 Extraction echouee

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Timeout fetching: https://...` | La page met plus de 8 secondes | Normal — le fallback skip la page |
| `HTTP 403 for https://...` | La page bloque les bots | Accepter — la page n'est pas extraite |
| `Fetch error for https://...: ...` | Erreur reseau | Verifier la connectivite |

**Explication :** L'extraction de contenu est en graceful degradation. Si une page echoue, elle est simplement ignoree. L'agent continue avec les autres sources.

### 16.2 Encodage incorrect

| Erreur | Cause | Solution |
|--------|-------|----------|
| `UnicodeDecodeError` | Encodage non UTF-8 | Normal — `errors="replace"` gere les cas limites |
| Caracteres bizarres dans les resultats | Page en encodage ancien (ISO-8859-1) | Accepter — extraction partielle |

**Explication :** Le decodeur utilise `errors="replace"` pour gerer les pages en encodage non-UTF-8. Les caracteres non-decodables sont remplaces par `?`.

### 16.3 Trop de pages

| Erreur | Cause | Solution |
|--------|-------|----------|
| Extraction partielle | Limite de 6 pages atteinte | Normal — les 6 premieres pages sont extraites |
| Pages lourdesignorees | Limite de 1 MB par page | Normal — protection memoire |

**Configurer les limites (dans `content_extractor.py`) :**
```python
_MAX_PAGES = 6        # Nombre max de pages a extraire
_MAX_CONTENT_BYTES = 1_000_000  # 1 MB max par page
_FETCH_TIMEOUT = 8.0  # Timeout en secondes
_MAX_TEXT_LENGTH = 3000  # Texte tronque a 3000 chars
```

### 16.4 Site skippe automatiquement

| Pattern | Site concerne |
|---------|---------------|
| `\.(pdf\|zip\|tar\.gz\|exe\|dmg)$` | Fichiers binaires |
| `youtube\.com/watch` | YouTube |
| `vimeo\.com` | Vimeo |
| `twitter\.com` / `x\.com` | Twitter/X |
| `facebook\.com` | Facebook |
| `instagram\.com` | Instagram |

---

## 17. Problemes PWA

### 17.1 Service Worker ne se met pas a jour

| Symptome | Cause | Solution |
|----------|-------|----------|
| Anciennes pages served apres mise a jour | Cache du service worker | Forcer la mise a jour |
| `SW registration failed` | Chemin incorrect ou HTTPS requis | Verifier la config |

**Forcer la mise a jour du SW :**
```bash
# Le SW est versionne (SW_VERSION = 'v4'). Pour forcer :
# 1. Modifier SW_VERSION dans service-worker.js
# 2. Le nouveau SW activera skipWaiting()

# Ou via la console du navigateur :
navigator.serviceWorker.getRegistrations().then(regs => {
    regs.forEach(r => r.unregister());
    location.reload();
});
```

**Ou depuis l'admin :**
```bash
# Le bouton "Update" dans le panel admin envoie 'skipWaiting'
# au service worker pour activer immediatement la nouvelle version
```

### 17.2 Mode hors-ligne ne fonctionne pas

| Symptome | Cause | Solution |
|----------|-------|----------|
| Page blanche hors-ligne | Pas de page de fallback | Ajouter `/admin/app.html` dans le RUNTIME_CACHE |
| API erreurs hors-ligne | Les API `/api/` ne sont pas cachees | Normal — seules les pages HTML sont cachees |

**Explication :** Le service worker utilise :
- **Cache-first** pour les assets statiques (CSS, JS, images)
- **Network-first** pour les pages HTML
- **Pas de cache** pour les API (`/api/`)

La page de fallback hors-ligne est `/admin/app.html`. Si vous voyez "Offline" en blanc, c'est que la page n'a pas ete cachee.

### 17.3 PWA pas installable

| Symptome | Cause | Solution |
|----------|-------|----------|
| Pas de bouton "Installer" | `manifest.json` manquant ou invalide | Verifier `/admin/manifest.json` |
| `beforeinstallprompt` pas declenche | HTTPS requis | Utiliser HTTPS ou localhost |

**Verifier le manifest :**
```bash
curl -s http://localhost:4500/admin/manifest.json | python3 -m json.tool
```

**Exigences PWA :**
- Service worker enregistre
- `manifest.json` valide
- HTTPS (ou localhost)
- Icônes 192x192 et 512x512

---

## 18. Erreurs CORS

### 18.1 Bloque par CORS

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Access-Control-Allow-Origin` manquant | Origine non autorisee | Ajouter l'origine dans la config CORS |
| `blocked by CORS policy: No 'Access-Control-Allow-Origin' header` | Requete depuis un domaine non whitelist | Modifier `server.py` |

**Origines autorisees par defaut :**
```
http://localhost:3000
http://127.0.0.1:3000
http://localhost:4500
http://127.0.0.1:4500
http://localhost:3080
http://127.0.0.1:3080
```

**Ajouter une origine :**
```python
# Dans server.py, section CORS :
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:4500", "http://127.0.0.1:4500",
        "http://localhost:3080", "http://127.0.0.1:3080",
        "https://your-domain.com",  # Ajouter ici
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
```

### 18.2 Preflight echoue

| Erreur | Cause | Solution |
|--------|-------|----------|
| `405 Method Not Allowed` sur OPTIONS | Le middleware CORS ne gere pas les preflights | Verifier que CORSMiddleware est bien configure |
| `Request header 'content-type' not allowed` | Header non autorise | Ajouter le header dans `allow_headers` |

**Verifier les headers autorises :**
```
Content-Type, Authorization, X-API-Key
```

Si vous utilisez des headers custom, ajoutez-les.

### 18.3 Credentials non passes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `include credentials but 'Access-Control-Allow-Origin' is not '*'*` | `allow_credentials=True` avec origine specifique | Utiliser une origine precise (pas `*`) |

**Explication :** Quand `allow_credentials=True`, l'origine doit etre precise (pas `*`). Le serveur gere deja ce cas correctement.

---

## 19. Problemes de migration

### 19.1 Colonne manquante

| Erreur | Cause | Solution |
|--------|-------|----------|
| `column X does not exist` | Base de donnees ancienne sans la colonne | Redemarrer le serveur (migrations auto) |
| `table clients has no column named scopes` | Schema pre-refactoring | Les migrations auto ajoutent les colonnes |

**Explication :** Les migrations sont automatiques. Au demarrage, `_init_schema()` verifie le schema avec `PRAGMA table_info()` et ajoute les colonnes manquantes via `ALTER TABLE ADD COLUMN`.

**Colonnes migrables dans `clients` :**
| Colonne | Type | Defaut |
|---------|------|--------|
| `client_secret` | TEXT | `''` |
| `client_secret_hash` | TEXT | `''` |
| `scopes` | TEXT | `'[]'` |
| `rate_limit` | INTEGER | `30` |

**Verifier le schema :**
```bash
sqlite3 data/threads.db "PRAGMA table_info(clients);"
sqlite3 data/threads.db "PRAGMA table_info(messages);"
sqlite3 data/threads.db "PRAGMA table_info(threads);"
```

### 19.2 Erreur apres mise a jour du code

| Erreur | Cause | Solution |
|--------|-------|----------|
| `OperationalError: no such table` | Nouvelles tables pas encore creees | Redemarrer le serveur |
| `table X already exists` | Tentative de recreation | Normal — `IF NOT EXISTS` gere ca |

```bash
# Forcer la recreation du schema
sudo systemctl restart websearch-agent

# Verifier les logs de migration
sudo journalctl -u websearch-agent -n 20 | grep -i "schema\|migration\|init"
```

### 19.3 Base de donnees versionnee

| Erreur | Cause | Solution |
|--------|-------|----------|
| Schema incompatible | Base creee avec une ancienne version | Exporter, supprimer, recreer |

**Migration manuelle (dernier recours) :**
```bash
# 1. Arreter le serveur
sudo systemctl stop websearch-agent

# 2. Sauvegarder
cp data/threads.db data/threads.db.backup

# 3. Exporter les donnees
sqlite3 data/threads.db ".dump" > data/dump.sql

# 4. Supprimer l'ancienne base
rm -f data/threads.db data/threads.db-wal data/threads.db-shm

# 5. Redemarrer (le serveur recreera le schema)
sudo systemctl start websearch-agent

# 6. Si besoin, reinserer les donnees
sqlite3 data/threads.db < data/dump.sql
```

---

## 20. Diagnostic automatique

### 20.1 Script de diagnostic

```bash
#!/bin/bash
# Sauvegarder comme diagnostic.sh

echo "=== DIAGNOSTIC WEBSEARCH AGENT ==="
echo ""

echo "--- Python ---"
python3 --version
pip3 --version

echo ""
echo "--- Git ---"
git --version
git remote -v

echo ""
echo "--- Docker ---"
docker --version 2>/dev/null || echo "Docker non installe"
docker compose version 2>/dev/null || echo "Docker Compose non installe"

echo ""
echo "--- Dependances ---"
pip list 2>/dev/null | grep -E "openai|fastapi|requests|tavily|trafilatura" || echo "Dependances non installees"

echo ""
echo "--- Variables d'environnement ---"
[ -f .env ] && echo ".env existe" || echo ".env MANQUANT"
grep -q "OPENROUTER_API_KEY" .env 2>/dev/null && echo "OPENROUTER_API_KEY: OK" || echo "OPENROUTER_API_KEY: MANQUANTE"
grep -q "PERPLEXITY_API_KEY" .env 2>/dev/null && echo "PERPLEXITY_API_KEY: OK" || echo "PERPLEXITY_API_KEY: MANQUANTE"
grep -q "TAVILY_API_KEY" .env 2>/dev/null && echo "TAVILY_API_KEY: OK" || echo "TAVILY_API_KEY: MANQUANTE"

echo ""
echo "--- Service systemd ---"
systemctl is-active websearch-agent 2>/dev/null && echo "websearch-agent: actif" || echo "websearch-agent: inactif ou non installe"

echo ""
echo "--- Ports ---"
sudo ss -tlnp 2>/dev/null | grep -E "4500|8086" || echo "Aucun service detecte"

echo ""
echo "--- Sante ---"
curl -s http://localhost:4500/health 2>/dev/null && echo "Serveur: OK" || echo "Serveur: ARRETE"

echo ""
echo "=== FIN DU DIAGNOSTIC ==="
```

### 20.2 Commandes rapides

```bash
# Verifier l'installation
python3 -c "from agent import TOOLS; print(f'{len(TOOLS)} outils')"

# Tester l'agent
python3 agent.py "test"

# Tester le serveur
curl http://localhost:4500/health

# Voir les logs (service systemd)
sudo journalctl -u websearch-agent -f

# Docker
docker compose ps
docker compose logs --tail=50
```

### 20.3 Checklist pre-production

- [ ] Python 3.11+ installe
- [ ] Dependances installees (`pip install -r requirements.txt`)
- [ ] Fichier `.env` configure avec les cles API
- [ ] Repertoire `data/` cree (pour les threads SQLite)
- [ ] Test agent : `python3 agent.py "test"`
- [ ] Test serveur : `curl http://localhost:4500/health`
- [ ] Test threads : `curl -X POST http://localhost:4500/chat -H "Content-Type: application/json" -d '{"message":"test"}'`
- [ ] Service systemd installe et actif : `sudo systemctl status websearch-agent`
- [ ] Serveur ecoute bien sur `127.0.0.1` (pas `0.0.0.0`) sauf reverse proxy volontaire
- [ ] Docker fonctionnel (optionnel)
- [ ] SearXNG accessible (optionnel)
- [ ] Rate limiting configure
- [ ] Logs verifies
- [ ] Monitoring en place (optionnel)

---

## Support

Si le probleme persiste :

1. Executer le script de diagnostic
2. Collecter les logs (`sudo journalctl -u websearch-agent -n 100`)
3. Ouvrir une issue : https://github.com/Hajrudin-Zelef/websearch_agent/issues
4. Inclure :
   - Message d'erreur complet
   - Resultat du diagnostic
   - Version de Python
   - OS et version
