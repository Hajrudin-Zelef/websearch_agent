# TROUBLESHOOT — Guide de dépannage

> Voir aussi : [[AGENTS]], [[DEPLOYMENT]], [[INSTALL]]

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
10. [Diagnostic automatique](#10-diagnostic-automatique)

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

## 10. Diagnostic automatique

### 10.1 Script de diagnostic

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

### 10.2 Commandes rapides

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

### 10.3 Checklist pre-production

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
