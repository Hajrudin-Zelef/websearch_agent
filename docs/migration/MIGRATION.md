# Guide de Migration — WebSearch Agent

> Procédure complète pour migrer WebSearch Agent d'un VPS à un autre, ou mettre en place un environnement de dev local.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Prérequis](#2-prerequis)
3. [Sauvegarde (ancien VPS)](#3-sauvegarde-ancien-vps)
4. [Transfert](#4-transfert)
5. [Restauration (nouveau VPS)](#5-restauration-nouveau-vps)
6. [Vérification](#6-verification)
7. [Migration partielle](#7-migration-partielle)
8. [Dépannage](#8-depannage)
9. [Checklist](#9-checklist)
10. [Setup VM dev (Hyper-V)](#10-setup-vm-dev-hyper-v)
11. [Workflow Cython (protection du code)](#11-workflow-cython-protection-du-code)
12. [CI/CD avec GitHub Actions](#12-cicd-avec-github-actions)

---

## 1. Vue d'ensemble

### Qu'est-ce qui est sauvegardé ?

| Composant | Fichiers | Taille typique |
|-----------|----------|----------------|
| **Configuration** | `.env`, `settings.json` | ~2 KB |
| **Bases de données** | `threads.db`, `metrics.db` | ~1-10 MB |
| **Logs** | `websearch-agent.log`, `audit.log` | ~1-50 MB |
| **Service** | `websearch-agent.service` | ~1 KB |
| **Docker** | `docker-compose.yml`, config SearXNG | ~5 KB |
| **Code** | Git clone depuis GitHub | ~1 MB |

### Flux de migration

```
Ancien VPS                    Nouveau VPS
┌─────────────┐              ┌─────────────┐
│  backup.sh  │  ──scp──►   │ restore.sh  │
│             │              │             │
│ .env        │              │ .env        │
│ threads.db  │              │ threads.db  │
│ metrics.db  │              │ metrics.db  │
│ settings    │              │ settings    │
│ logs        │              │ logs        │
│ service     │              │ service     │
└─────────────┘              └─────────────┘
```

---

## 2. Prérequis

### Ancien VPS (backup)

```bash
# Aucun prérequis — le script utilise les outils déjà installés
# Vérifier que sqlite3 est disponible (optionnel mais recommandé)
sqlite3 --version
```

### Nouveau VPS (restore)

```bash
# Installer les dépendances système
sudo apt update && sudo apt install -y \
    python3 \
    python3-venv \
    python3-pip \
    sqlite3 \
    curl \
    git

# Installer Docker (pour SearXNG)
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Se déconnecter et se reconnecter pour que le groupe prenne effet

# Vérifier
python3 --version    # 3.11+ requis
docker --version
sqlite3 --version
```

---

## 3. Sauvegarde (ancien VPS)

### Étape 1 : Lancer le backup

```bash
cd /home/sam/websearch_agent
./backup.sh /tmp/websearch-backup
```

Sortie attendue :
```
╔══════════════════════════════════════════╗
║   WebSearch Agent — Backup               ║
╚══════════════════════════════════════════╝

Source: /home/sam/websearch_agent
Destination: /tmp/websearch-backup

📁 Création de la structure...
📋 Sauvegarde des fichiers...
  ✅ .env
  ✅ service systemd
  ✅ docker-compose.yml
  ✅ Dockerfile
  ✅ requirements.txt

🗄️  Sauvegarde des bases de données...
  ✅ threads.db (200K)
  ✅ metrics.db (444K)
  ✅ settings.json
  ✅ logs websearch-agent
  ✅ logs audit

📦 Création de l'archive...
  ✅ /tmp/websearch-backup.tar.gz (176K)

╔══════════════════════════════════════════╗
║   ✅ Backup terminé                      ║
╚══════════════════════════════════════════╝
```

### Étape 2 : Vérifier le contenu

```bash
# Lister le contenu du backup
tar -tzf /tmp/websearch-backup.tar.gz

# Vérifier la taille
du -h /tmp/websearch-backup.tar.gz
```

### Étape 3 : Arrêter le service (optionnel, recommandé)

```bash
# Pour éviter une écriture pendant le backup
sudo systemctl stop websearch-agent
```

---

## 4. Transfert

### Méthode 1 : SCP (recommandé)

```bash
# Depuis l'ancien VPS
scp /tmp/websearch-backup.tar.gz user@NOUVEAU_VPS:/tmp/
```

### Méthode 2 : rsync (pour les gros volumes)

```bash
rsync -avz --progress /tmp/websearch-backup.tar.gz user@NOUVEAU_VPS:/tmp/
```

### Méthode 3 : Download sécurisé

```bash
# Sur l'ancien VPS, servir le fichier temporairement
python3 -m http.server 8888 -d /tmp

# Sur le nouveau VPS
wget http://ANCIEN_VPS_IP:8888/websearch-backup.tar.gz -P /tmp/
```

### Vérification du transfert

```bash
# Sur le nouveau VPS
md5sum /tmp/websearch-backup.tar.gz
# Comparer avec l'ancien VPS :
md5sum /tmp/websearch-backup.tar.gz
```

---

## 5. Restauration (nouveau VPS)

### Étape 1 : Cloner le repo

```bash
cd /home/sam
git clone https://github.com/Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
```

### Étape 2 : Lancer le restore

```bash
chmod +x restore.sh
./restore.sh /tmp/websearch-backup.tar.gz
```

Sortie attendue :
```
╔══════════════════════════════════════════╗
║   WebSearch Agent — Restore              ║
╚══════════════════════════════════════════╝

📦 Extraction de l'archive...
  ✅ Extrait dans /tmp/xxx

🛑 Arrêt du service...
  ℹ️  Service déjà arrêté

📋 Restauration des fichiers...
  ✅ .env
  ✅ docker-compose.yml
  ✅ Dockerfile
  ✅ requirements.txt
  ✅ websearch-agent.service

🗄️  Restauration des bases de données...
  ✅ threads.db (200K)
  ✅ metrics.db (444K)
  ✅ settings.json

🐍 Création du virtualenv Python...
  ✅ venv créé avec 85 packages

⚙️  Installation du service systemd...
  ✅ Service systemd installé

🐳 Démarrage de SearXNG...
  ✅ SearXNG démarré

🚀 Démarrage du service...
  ✅ Service démarré

🔍 Vérification...
  ✅ Serveur OK — http://127.0.0.1:4500

╔══════════════════════════════════════════╗
║   ✅ Restore terminé                     ║
╚══════════════════════════════════════════╝
```

### Étape 3 : Vérifier le .env

```bash
# Vérifier que les clés API sont bien restaurées
grep -E "^[A-Z_]+=" .env | sed 's/=.*/=***/'
```

### Étape 4 : Configurer le reverse proxy (production)

```bash
# Si vous utilisez Nginx, mettre à jour le fichier de config
# pour pointer vers le nouveau VPS

# Exemple Nginx :
sudo nano /etc/nginx/sites-available/websearch-agent
# Modifier : server_name nouveau-domaine.com;

sudo nginx -t && sudo systemctl reload nginx
```

---

## 6. Vérification

### Tests rapides

```bash
# Health check
curl -s http://127.0.0.1:4500/health
# → {"status":"ok","db":"ok"}

# Status du service
sudo systemctl status websearch-agent

# Logs (dernières lignes)
journalctl -u websearch-agent -n 20

# Test de recherche
curl -s "http://127.0.0.1:4500/search?q=test&max_results=2" | python3 -m json.tool | head -10

# Admin panel
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4500/admin
# → 200
```

### Vérification complète

```bash
# 1. Service actif
systemctl is-active websearch-agent

# 2. Base de données
sqlite3 data/threads.db "SELECT COUNT(*) FROM threads;"

# 3. Métriques
curl -s http://127.0.0.1:4500/metrics | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Sources: {len(d.get(\"sources\",{}))}')"

# 4. SearXNG
curl -s http://127.0.0.1:8086/search?q=test&format=json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Résultats: {len(d.get(\"results\",[]))}')"
```

---

## 7. Migration partielle

### Cas 1 : Migrer uniquement les conversations

```bash
# Backup
sqlite3 data/threads.db ".backup /tmp/threads-backup.db"

# Restore
scp /tmp/threads-backup.db user@nouveau-vps:/home/sam/websearch_agent/data/threads.db
```

### Cas 2 : Migrer uniquement la configuration

```bash
# Backup
tar -czf /tmp/config-backup.tar.gz data/settings.json .env

# Restore
tar -xzf /tmp/config-backup.tar.gz -C /home/sam/websearch_agent/
```

### Cas 3 : Migrer sans les logs

```bash
# Backup sans logs
./backup.sh /tmp/backup-no-logs
# Puis supprimer les logs de l'archive
tar -xf /tmp/backup-no-logs.tar.gz
rm -rf backup-no-logs/logs/
tar -czf /tmp/backup-no-logs.tar.gz backup-no-logs/
```

---

## 8. Dépannage

### Le service ne démarre pas

```bash
# Vérifier les logs
journalctl -u websearch-agent -n 50

# Causes courantes :
# 1. .env manquant ou incomplet
cat .env | grep -E "^[A-Z_]+=$" | head -5
# → Les variables vides sont un problème

# 2. Python venv cassé
source venv/bin/activate
python -c "import fastapi; print('OK')"

# 3. Port déjà utilisé
ss -tlnp | grep 4500

# 4. Permissions
ls -la data/
# → Le dossier data/ doit être accessible par l'utilisateur du service
```

### La base de données est corrompue

```bash
# Vérifier l'intégrité
sqlite3 data/threads.db "PRAGMA integrity_check;"

# Réparer si nécessaire
sqlite3 data/threads.db ".recover" | sqlite3 data/threads-repaired.db
mv data/threads-repaired.db data/threads.db
```

### SearXNG ne répond pas

```bash
# Vérifier Docker
docker ps | grep searxng

# Redémarrer
docker compose restart searxng

# Vérifier les logs
docker compose logs searxng --tail 20
```

### Erreur "Module not found" après migration

```bash
# Recréer le venv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 9. Checklist

### Avant le backup

- [ ] Service websearch-agent actif
- [ ] Dernier backup récent (data/)
- [ ] .env à jour avec toutes les clés API
- [ ] Espace disque suffisant sur le nouveau VPS (500 MB min)

### Après le restore

- [ ] `curl http://127.0.0.1:4500/health` → `{"status":"ok"}`
- [ ] `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4500/admin` → `200`
- [ ] Login admin fonctionne
- [ ] Recherche fonctionne (`/search?q=test`)
- [ ] SearXNG actif (`curl http://127.0.0.1:8086`)
- [ ] Reverse proxy configuré (Nginx/Caddy)
- [ ] SSL/TLS configuré (Let's Encrypt)
- [ ] DNS mis à jour (si changement de domaine)
- [ ] Ancien VPS arrêté (pour éviter les conflits)

---

## 10. Setup VM dev (Hyper-V)

### Pourquoi une VM dédiée ?

| Aspect | VPS (prod) | VM dev (Hyper-V) |
|--------|-----------|------------------|
| **Code** | .so uniquement (protégé) | .py sources (modifiables) |
| **Données** | Production réelle | Copie pour tests |
| **Accès** | Public (reverse proxy) | Local uniquement |
| **Risque** | Casser la prod | Aucun |

### Étape 1 : Créer la VM

| Paramètre | Valeur |
|-----------|--------|
| **Hyperviseur** | Hyper-V (Windows Pro/Enterprise) |
| **OS** | Debian 12 (Bookworm) — netinst |
| **RAM** | 4 Go (minimum 2 Go) |
| **Disk** | 40 Go (dynamic) |
| **Réseau** |桥接 (IP locale sur le même réseau) |
| **User** | `sam` (même nom que le VPS) |

```powershell
# Dans Hyper-V Manager
1. New → Virtual Machine
2. Name: dev-websearch
3. Generation: 2
4. Memory: 4096 MB (dynamic)
5. Network: Default Switch (ou Bridged)
6. Disk: 40 GB VHDX (dynamic)
7. Install Debian 12 from ISO
```

### Étape 2 : Installer les dev tools

```bash
# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Installer les outils de dev
sudo apt install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    build-essential \
    cython3 \
    git \
    sqlite3 \
    curl \
    wget \
    htop \
    docker.io \
    docker-compose-v2

# Activer Docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Se déconnecter et se reconnecter

# Vérifier
python3 --version    # 3.11+ ou 3.13
docker --version
cython3 --version
```

### Étape 3 : Cloner le repo

```bash
cd /home/sam
git clone git@github.com:Hajrudin-Zelef/websearch_agent.git
cd websearch_agent
```

### Étape 4 : Créer le venv

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Étape 5 : Récupérer les données depuis le VPS

```bash
# Depuis ta VM dev, récupérer le .env
scp sam@VPS_IP:/home/sam/websearch_agent/.env /home/sam/websearch_agent/.env

# Récupérer les bases de données
scp sam@VPS_IP:/home/sam/websearch_agent/data/threads.db /home/sam/websearch_agent/data/
scp sam@VPS_IP:/home/sam/websearch_agent/data/metrics.db /home/sam/websearch_agent/data/
scp sam@VPS_IP:/home/sam/websearch_agent/data/settings.json /home/sam/websearch_agent/data/

# Vérifier
ls -la .env data/
```

### Étape 6 : Tester

```bash
# Démarrer SearXNG
docker compose up -d searxng

# Démarrer le serveur
source venv/bin/activate
uvicorn server:app --host 127.0.0.1 --port 4500

# Vérifier
curl http://127.0.0.1:4500/health
# → {"status":"ok","db":"ok"}

# Lancer les tests
python -m pytest tests/ -v
```

### Étape 7 : Configurer Git

```bash
# Configurer l'utilisateur Git
git config user.name "Ton Nom"
git config user.email "ton@email.com"

# Vérifier que le push fonctionne
git remote -v
# → origin git@github.com:Hajrudin-Zelef/websearch_agent.git

# Tester un push (optionnel)
echo "# test" >> .gitignore.test
git add .gitignore.test
git commit -m "test: verify git push works"
git push origin main
rm .gitignore.test
git commit -m "chore: remove test file"
git push origin main
```

---

## 11. Workflow Cython (protection du code)

### Principe

```
VM dev (Hyper-V)                    VPS (production)
┌──────────────────┐               ┌──────────────────┐
│ sources/router.py │ ─compile──► │ router.cpython-*.so │
│ (modifiable)     │               │ (binaire)         │
└──────────────────┘               └──────────────────┘
```

### Modules à compiler

| Module | Raison |
|--------|--------|
| `sources/router.py` | Logique de routage intelligent — IP |
| `core/models.py` | Sélection de modèles LLM |
| `core/tools.py` | Exécution des outils |
| `core/circuit_breaker.py` | Protection circuit breaker |
| `sources/duckduckgo.py` | Extraction DuckDuckGo |
| `sources/perplexity.py` | Extraction Perplexity |
| `sources/tavily.py` | Extraction Tavily |

### Modules à NE PAS compiler

| Module | Raison |
|--------|--------|
| `sources/__init__.py` | Utilise `importlib` dynamique |
| `server.py` | FastAPI routes — API publique |
| `routes/api.py` | Endpoints HTTP |
| `admin/` | HTML/CSS/JS — pas de logique métier |

### Script de build

```python
# setup_cython.py — à exécuter depuis la racine du projet
from Cython.Build import cythonize
from setuptools import setup
import os

# Modules à compiler
MODULES = [
    "sources/router",
    "core/models",
    "core/tools",
    "core/circuit_breaker",
    "sources/duckduckgo",
    "sources/perplexity",
    "sources/tavily",
]

# Filtrer ceux qui existent
existing = [m for m in MODULES if os.path.exists(m.replace("/", "/") + ".py")]
print(f"Compilation de {len(existing)}/{len(MODULES)} modules...")

setup(
    ext_modules=cythonize(
        existing,
        compiler_directives={"language_level": "3"},
    ),
)
```

### Compiler

```bash
cd /home/sam/websearch_agent
source venv/bin/activate

# Compiler
python setup_cython.py build_ext --inplace

# Les .so sont générés dans chaque dossier
ls sources/router.cpython-*.so
ls core/models.cpython-*.so
```

### Tester

```bash
# Vérifier que le serveur démarre
python -c "from sources.router import route_query; print('OK')"

# Lancer les tests
python -m pytest tests/ -v

# Tester le search
curl -s "http://127.0.0.1:4500/search?q=test&max_results=2" | python -m json.tool | head -10
```

### Déployer sur le VPS

```bash
# Sur la VM dev
git add sources/*.so core/*.so setup_cython.py
git commit -m "build: compile modules Cython for production"
git push origin main

# Le VPS reçoit les .so via CI/CD (voir section 12)
# OU manuellement sur le VPS :
cd /home/sam/websearch_agent
git pull origin main
sudo systemctl restart websearch-agent
```

---

## 12. CI/CD avec GitHub Actions

### Principe

```
git push (VM dev) → GitHub Actions → Tests → Deploy VPS
```

### Workflow existant (tests)

```yaml
# .github/workflows/test.yml (déjà en place)
name: Tests
on:
  push:
    branches: [main, master]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v
```

### Nouveau workflow : deploy

```yaml
# .github/workflows/deploy.yml — à créer
name: Deploy to VPS

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: success()
    steps:
      - uses: actions/checkout@v4

      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /home/sam/websearch_agent
            git pull origin main
            source venv/bin/activate
            pip install -r requirements.txt
            sudo systemctl restart websearch-agent
            echo "Deploy OK: $(curl -s http://127.0.0.1:4500/health)"
```

### Secrets GitHub à configurer

Aller dans **GitHub → Settings → Secrets and variables → Actions** :

| Secret | Valeur | Comment l'obtenir |
|--------|--------|-------------------|
| `VPS_HOST` | IP du VPS | `curl ifconfig.me` sur le VPS |
| `VPS_USER` | User SSH | `whoami` sur le VPS (ex: `sam`) |
| `VPS_SSH_KEY` | Clé privée SSH | Voir ci-dessous |

### Générer la clé SSH

```bash
# Sur la VM dev
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_deploy
cat ~/.ssh/github_deploy.pub

# Sur le VPS
echo "clé_publique" >> ~/.ssh/authorized_keys

# Copier la clé privée pour GitHub
cat ~/.ssh/github_deploy
# → Copier tout le contenu dans le secret VPS_SSH_KEY
```

### Flow complet

```
1. Tu modifies router.py sur la VM dev
2. Tu compiles: python setup_cython.py build_ext --inplace
3. Tu testes: python -m pytest tests/ -v
4. Tu pushes: git push origin main
5. GitHub Actions lance les tests
6. Si OK → déploie sur le VPS via SSH
7. Le VPS: git pull + pip install + restart
8. ✅ En ligne
```

---

*Dernière mise à jour : 21 août 2026 — Ajout setup VM dev, Cython, CI/CD*
