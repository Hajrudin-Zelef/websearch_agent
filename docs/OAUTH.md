# Guide OAuth2 - WebSearch Agent

Guide complet pour l'authentification OAuth2, les scopes, et le rate limiting par client.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Authentification](#2-authentification)
3. [OAuth2 Flow](#3-oauth2-flow)
4. [Scopes et permissions](#4-scopes-et-permissions)
5. [Rate limiting par client](#5-rate-limiting-par-client)
6. [Gestion via Admin](#6-gestion-via-admin)
7. [Exemples par langage](#7-exemples-par-langage)
8. [Securite](#8-securite)
9. [FAQ](#9-faq)

---

## 1. Vue d'ensemble

WebSearch Agent supporte 3 modes d'authentification :

| Mode | Usage | Avantages |
|------|-------|-----------|
| **API Key** | Integration simple | Pas de token a gerer |
| **OAuth2 JWT** | Production | Scopes, rate limit, expiration |
| **Sans credentials** | Development | Aucune configuration |

### Recommandation

Pour la production, utilisez **OAuth2 JWT** car il offre :
- **Scopes** : controler l'acces par endpoint (read, write, admin)
- **Rate limit** : quota configurable par client
- **Expiration** : tokens temporaires (1h) avec refresh
- **Securite** : secrets hashés en base de données

---

## 2. Authentification

### Mode 1 : API Key (simple)

```bash
# Via header X-API-Key
curl -H "X-API-Key: ws_..." http://localhost:4500/chat -d '{"message":"test"}'

# Via Authorization Bearer
curl -H "Authorization: Bearer ws_..." http://localhost:4500/chat -d '{"message":"test"}'
```

**Avantages** : Simple, pas de token a gerer
**Inconvenients** : Pas de scopes, rate limit fixe (30/min)

### Mode 2 : OAuth2 JWT (recommande)

```bash
# 1. Obtenir un token
curl -X POST http://localhost:4500/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"...","client_secret":"..."}'

# Reponse :
# {
#   "access_token": "eyJ...",
#   "token_type": "Bearer",
#   "expires_in": 3600,
#   "client_id": "...",
#   "scopes": ["read", "write"]
# }

# 2. Utiliser le token
curl -H "Authorization: Bearer eyJ..." http://localhost:4500/chat -d '{"message":"test"}'
```

**Avantages** : Scopes, rate limit configurable, expiration
**Inconvenients** : Nécessite un token

### Mode 3 : Sans credentials (backward compatible)

```bash
curl http://localhost:4500/chat -d '{"message":"test"}'
# Rate limit par IP (30 req/min)
```

**Avantages** : Aucune configuration
**Inconvenients** : Rate limit strict par IP

---

## 3. OAuth2 Flow

### Flow complet

```
┌─────────────┐                             ┌─────────────┐
│             │                             │             │
│   Client    │                             │   Server    │
│             │                             │             │
└──────┬──────┘                             └──────┬──────┘
       │                                          │
       │  1. POST /oauth/token                    │
       │  {client_id, client_secret}              │
       │ ────────────────────────────────────────▶ │
       │                                          │
       │  2. Reponse avec access_token            │
       │  {access_token, scopes, expires_in}      │
       │ ◀──────────────────────────────────────── │
       │                                          │
       │  3. Utiliser le token                    │
       │  Authorization: Bearer eyJ...            │
       │ ────────────────────────────────────────▶ │
       │                                          │
       │  4. Reponse avec les donnees             │
       │ ◀──────────────────────────────────────── │
       │                                          │
       │  5. Rafraichir avant expiration          │
       │  POST /oauth/token/refresh               │
       │  {refresh_token: eyJ...}                 │
       │ ────────────────────────────────────────▶ │
       │                                          │
       │  6. Nouveau token                        │
       │ ◀──────────────────────────────────────── │
       │                                          │
```

### Creation d'un client

1. **Via l'admin UI** : `/admin` → Clients → Creer une app
2. **Via l'API** :

```bash
curl -X POST http://localhost:4500/admin/clients \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"name": "mon-app", "description": "Application mobile"}'
```

### Reponse

```json
{
  "id": "2da1db9a-5604-4000-8560-2b973b8b2f9d",
  "name": "mon-app",
  "api_key": "ws_4b6faafc3e620ab6492024c210588c29",
  "client_secret": "cs_4883fbaf0bbe5872463614d49460f305deef271c",
  "scopes": ["read", "write"],
  "rate_limit": 30
}
```

**IMPORTANT** : Le `client_secret` n'est affiche qu'une seule fois. Copiez-le !

---

## 4. Scopes et permissions

### Scopes disponibles

| Scope | Description | Endpoints |
|-------|-------------|-----------|
| `read` | Lire les conversations et rechercher | `/search`, `/threads`, `/datasets` |
| `write` | Envoyer des messages et creer des threads | `/chat` |
| `admin` | Gerer les settings, clients et administration | `/admin/*` |

### Scopes par defaut

Nouveau client → `["read", "write"]`

### Exemples de configuration

| Usage | Scopes | Rate Limit |
|-------|--------|------------|
| App mobile (lecture seule) | `["read"]` | 50/min |
| App mobile (complet) | `["read", "write"]` | 30/min |
| Dashboard admin | `["read", "write", "admin"]` | 100/min |
| Integration externe | `["read"]` | 1000/min |

### Verification des scopes

Les scopes sont verifies automatiquement sur chaque endpoint :

- `/chat` → scope `write` requis (sinon 403)
- `/search` → scope `read` requis (sinon 403)
- `/admin/*` → scope `admin` requis (sinon 403)

### Erreur 403

```json
{
  "detail": "Scope 'write' requis. Scopes disponibles: read"
}
```

---

## 5. Rate limiting par client

### Configuration

| Champ | Description | Defaut | Min | Max |
|-------|-------------|--------|-----|-----|
| `rate_limit` | Requetes par minute | 30 | 1 | 10000 |

### Fonctionnement

```
Fenetre glissante de 60 secondes
├── Client A (rate_limit: 30) → 30 req/min
├── Client B (rate_limit: 100) → 100 req/min
└── Sans credentials (par IP) → 30 req/min
```

### Erreur 429

```json
{
  "detail": "Trop de requetes. Limite: 30/min."
}
```

### Avantages par rapport au rate limiting par IP

| Aspect | Par IP | Par Client |
|--------|--------|------------|
| Limite | Fixe (30/min) | Configurable (1-10000/min) |
| Cle | IP source | client_id |
| Persistance | Non | Oui (meme apres regeneration de cle) |
| Multi-apps | Non | Oui (chaque app a sa propre limite) |

---

## 6. Gestion via Admin

### Endpoints admin

| Methode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/admin/clients` | Lister tous les clients |
| `POST` | `/admin/clients` | Creer un client |
| `GET` | `/admin/clients/{id}` | Detail d'un client |
| `PUT` | `/admin/clients/{id}/scopes` | Modifier les scopes |
| `PUT` | `/admin/clients/{id}/rate-limit` | Modifier le rate limit |
| `POST` | `/admin/clients/{id}/regenerate` | Regenerer les credentials |
| `POST` | `/admin/clients/{id}/deactivate` | Desactiver un client |
| `POST` | `/admin/clients/{id}/activate` | Activer un client |
| `DELETE` | `/admin/clients/{id}` | Supprimer un client |
| `GET` | `/admin/scopes` | Lister les scopes disponibles |

### Modifier les scopes

```bash
curl -X PUT http://localhost:4500/admin/clients/{id}/scopes \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"scopes": ["read", "write", "admin"]}'
```

### Modifier le rate limit

```bash
curl -X PUT http://localhost:4500/admin/clients/{id}/rate-limit \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"rate_limit": 100}'
```

### Regenerer les credentials

```bash
curl -X POST http://localhost:4500/admin/clients/{id}/regenerate \
  -H "Cookie: session=..."
```

**Attention** : L'ancien api_key et client_secret sont immediatement desactives.

---

## 7. Exemples par langage

### JavaScript / Node.js

```javascript
// 1. Obtenir un token
async function login(clientId, clientSecret) {
  const response = await fetch('http://localhost:4500/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret })
  });
  return await response.json();
}

// 2. Utiliser le token
async function search(query, token) {
  const response = await fetch('http://localhost:4500/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ message: query })
  });
  return await response.json();
}

// 3. Rafraichir le token
async function refreshToken(refreshToken) {
  const response = await fetch('http://localhost:4500/oauth/token/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  return await response.json();
}

// Utilisation
const tokenData = await login('your-client-id', 'your-client-secret');
const result = await search('github langchain', tokenData.access_token);
```

### Python

```python
import requests

class WebSearchClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
    
    def login(self):
        response = requests.post(
            'http://localhost:4500/oauth/token',
            json={
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
        )
        data = response.json()
        self.token = data['access_token']
        return data
    
    def search(self, query: str) -> dict:
        response = requests.post(
            'http://localhost:4500/chat',
            json={'message': query},
            headers={'Authorization': f'Bearer {self.token}'}
        )
        return response.json()
    
    def refresh(self, refresh_token: str) -> dict:
        response = requests.post(
            'http://localhost:4500/oauth/token/refresh',
            json={'refresh_token': refresh_token}
        )
        data = response.json()
        self.token = data['access_token']
        return data

# Utilisation
client = WebSearchClient('your-client-id', 'your-client-secret')
client.login()
result = client.search('github langchain')
print(result['response'])
```

### Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type TokenRequest struct {
    ClientID     string `json:"client_id"`
    ClientSecret string `json:"client_secret"`
}

type TokenResponse struct {
    AccessToken string   `json:"access_token"`
    TokenType   string   `json:"token_type"`
    ExpiresIn   int      `json:"expires_in"`
    Scopes      []string `json:"scopes"`
}

func getToken(clientID, clientSecret string) (string, error) {
    body, _ := json.Marshal(TokenRequest{
        ClientID:     clientID,
        ClientSecret: clientSecret,
    })

    resp, err := http.Post(
        "http://localhost:4500/oauth/token",
        "application/json",
        bytes.NewBuffer(body),
    )
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()

    var token TokenResponse
    json.NewDecoder(resp.Body).Decode(&token)
    return token.AccessToken, nil
}

func search(query, token string) (string, error) {
    body, _ := json.Marshal(map[string]string{"message": query})
    
    req, _ := http.NewRequest("POST", "http://localhost:4500/chat", bytes.NewBuffer(body))
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Authorization", "Bearer "+token)
    
    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()
    
    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    return result["response"].(string), nil
}

func main() {
    token, _ := getToken("your-client-id", "your-client-secret")
    result, _ := search("github langchain", token)
    fmt.Println(result)
}
```

### cURL

```bash
# 1. Obtenir un token
TOKEN=$(curl -s -X POST http://localhost:4500/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"...","client_secret":"..."}' | jq -r '.access_token')

# 2. Utiliser le token
curl -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "test"}'

# 3. Rafraichir le token
NEW_TOKEN=$(curl -s -X POST http://localhost:4500/oauth/token/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$TOKEN\"}" | jq -r '.access_token')
```

---

## 8. Securite

### Bonnes pratiques

1. **Stockage des credentials** :
   - Ne jamais stocker le `client_secret` dans le code source
   - Utiliser des variables d'environnement ou un gestionnaire de secrets
   - Le serveur stocke uniquement le hash SHA-256 du secret

2. **Tokens JWT** :
   - Expiration : 1 heure par defaut
   - Refresh possible pendant 15 min apres expiration
   - Les scopes sont mis a jour au refresh (pas de cache stale)

3. **Rate limiting** :
   - Configurer des limites adaptées a chaque usage
   - Surveiller les erreurs 429 dans les logs
   - Augmenter les limites pour les clients leggitimes

4. **Rotation des credentials** :
   - Regenerer les credentials periodiquement
   - Le refresh token reste valide pendant la grace period (15 min)
   - Notification a l'equipe avant la rotation

### Secrets

| Secret | Description | Stockage |
|--------|-------------|----------|
| `api_key` | Clé d'API (format `ws_...`) | En clair (affiché 1 fois) |
| `client_secret` | Secret OAuth2 (format `cs_...`) | Hash SHA-256 en DB |
| `JWT_SECRET` | Secret pour signer les JWT | Variable d'environnement |

### Variables d'environnement

```bash
# Secret pour les tokens JWT (defaut: genere aleatoirement)
JWT_SECRET=your-secret-here

# Ou laisser le systeme en generer un aleatoirement
# JWT_SECRET non defini → secrets.token_hex(32)
```

---

## 9. FAQ

### Q : Quelle est la difference entre API Key et OAuth2 ?

**A** : L'API Key est un token permanent qui donne acces complet. OAuth2 cree des tokens temporaires (1h) avec des permissions specifiques (scopes) et un rate limit configurable.

### Q : Comment changer les scopes d'un client ?

**A** : Via l'admin UI (`/admin` → Clients → Editer) ou l'API :
```bash
curl -X PUT http://localhost:4500/admin/clients/{id}/scopes \
  -d '{"scopes": ["read", "write"]}'
```

### Q : Que faire si le client_secret est perdu ?

**A** : Regenerer les credentials via l'admin. L'ancien secret est immediatement desactive.

### Q : Le token expiré est-il toujours valide ?

**A** : Non, mais il reste utilisable pendant 15 minutes pour le refresh. Apres, il faut se re-authentifier.

### Q : Comment savoir quel scope est requis ?

**A** : L'erreur 403 indique le scope requis :
```json
{
  "detail": "Scope 'write' requis. Scopes disponibles: read"
}
```

### Q : Le rate limit est-il par endpoint ?

**A** : Non, il est par client. Tous les endpoints partagent la meme limite pour un client donne.

### Q : Comment tester l'authentification ?

**A** :
```bash
# Test sans credentials
curl http://localhost:4500/health

# Test avec API key
curl -H "X-API-Key: ws_..." http://localhost:4500/health

# Test avec OAuth2
curl -X POST http://localhost:4500/oauth/token \
  -d '{"client_id":"...","client_secret":"..."}'
# Puis utiliser le token retourne
```

---

## Support

- GitHub : https://github.com/Hajrudin-Zelef/websearch_agent
- Issues : https://github.com/Hajrudin-Zelef/websearch_agent/issues
