# Guide de Migration — WebSearch Agent

> Procédure complète pour migrer WebSearch Agent d'un VPS à un autre, sans perte de données.

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

*Dernière mise à jour : 21 août 2026*
