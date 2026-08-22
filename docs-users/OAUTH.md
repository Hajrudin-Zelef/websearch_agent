# OAUTH — Authentication and Security

> See also: [API.md](API.md), [ARCHITECTURE.md](ARCHITECTURE.md)

Complete guide to OAuth2 authentication, scopes, and per-client rate limiting.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Authentication](#2-authentication)
3. [OAuth2 Flow](#3-oauth2-flow)
4. [Scopes and Permissions](#4-scopes-and-permissions)
5. [Per-Client Rate Limiting](#5-per-client-rate-limiting)
6. [Admin Management](#6-admin-management)
7. [Language Examples](#7-language-examples)
8. [Security](#8-security)
9. [FAQ](#9-faq)

---

## 1. Overview

WebSearch Agent supports 3 authentication modes:

| Mode | Usage | Advantages |
|------|-------|-----------|
| **API Key** | Simple integration | No token management |
| **OAuth2 JWT** | Production | Scopes, rate limiting, expiration |
| **No credentials** | Development | Zero configuration |

### Recommendation

For production, use **OAuth2 JWT** because it provides:
- **Scopes**: control access per endpoint (read, write, admin)
- **Rate limiting**: configurable quota per client
- **Expiration**: temporary tokens (1h) with refresh
- **Security**: secrets hashed in the database

---

## 2. Authentication

### Mode 1: API Key (Simple)

```bash
# Via X-API-Key header
curl -H "X-API-Key: ws_..." http://localhost:4500/chat -d '{"message":"test"}'

# Via Authorization Bearer
curl -H "Authorization: Bearer ws_..." http://localhost:4500/chat -d '{"message":"test"}'
```

**Pros**: Simple, no token to manage
**Cons**: No scopes, fixed rate limit (30/min)

### Mode 2: OAuth2 JWT (Recommended)

```bash
# 1. Get a token
curl -X POST http://localhost:4500/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"...","client_secret":"..."}'

# Response:
# {
#   "access_token": "eyJ...",
#   "token_type": "Bearer",
#   "expires_in": 3600,
#   "client_id": "...",
#   "scopes": ["read", "write"]
# }

# 2. Use the token
curl -H "Authorization: Bearer eyJ..." http://localhost:4500/chat -d '{"message":"test"}'
```

**Pros**: Scopes, configurable rate limiting, expiration
**Cons**: Requires a token

### Mode 3: No Credentials (Backward Compatible)

```bash
curl http://localhost:4500/chat -d '{"message":"test"}'
# Rate limited by IP (30 req/min)
```

**Pros**: Zero configuration
**Cons**: Strict rate limiting by IP

---

## 3. OAuth2 Flow

### Complete Flow

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
       │  2. Response with access_token           │
       │  {access_token, scopes, expires_in}      │
       │ ◀──────────────────────────────────────── │
       │                                          │
       │  3. Use the token                        │
       │  Authorization: Bearer eyJ...            │
       │ ────────────────────────────────────────▶ │
       │                                          │
       │  4. Response with data                   │
       │ ◀──────────────────────────────────────── │
       │                                          │
       │  5. Refresh before expiration            │
       │  POST /oauth/token/refresh               │
       │  {refresh_token: eyJ...}                 │
       │ ────────────────────────────────────────▶ │
       │                                          │
       │  6. New token                            │
       │ ◀──────────────────────────────────────── │
       │                                          │
```

### Creating a Client

1. **Via the admin UI**: `/admin` → Clients → Create App
2. **Via the API**:

```bash
curl -X POST http://localhost:4500/admin/clients \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"name": "mon-app", "description": "Mobile application"}'
```

### Response

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

**IMPORTANT**: The `client_secret` is only displayed once. Copy it!

---

## 4. Scopes and Permissions

### Available Scopes

| Scope | Description | Endpoints |
|-------|-------------|-----------|
| `read` | Read conversations and search | `/search`, `/threads`, `/datasets` |
| `write` | Send messages and create threads | `/chat` |
| `admin` | Manage settings, clients, and administration | `/admin/*` |

### Default Scopes

New client → `["read", "write"]`

### Configuration Examples

| Use Case | Scopes | Rate Limit |
|----------|--------|------------|
| Mobile app (read-only) | `["read"]` | 50/min |
| Mobile app (full) | `["read", "write"]` | 30/min |
| Admin dashboard | `["read", "write", "admin"]` | 100/min |
| External integration | `["read"]` | 1000/min |

### Scope Verification

Scopes are automatically verified on each endpoint:

- `/chat` → scope `write` required (otherwise 403)
- `/search` → scope `read` required (otherwise 403)
- `/admin/*` → scope `admin` required (otherwise 403)

### 403 Error

```json
{
  "detail": "Scope 'write' required. Available scopes: read"
}
```

---

## 5. Per-Client Rate Limiting

### Configuration

| Field | Description | Default | Min | Max |
|-------|-------------|---------|-----|-----|
| `rate_limit` | Requests per minute | 30 | 1 | 10000 |

### How It Works

```
Sliding window of 60 seconds
├── Client A (rate_limit: 30) → 30 req/min
├── Client B (rate_limit: 100) → 100 req/min
└── No credentials (by IP) → 30 req/min
```

### 429 Error

```json
{
  "detail": "Too many requests. Limit: 30/min."
}
```

### Comparison with IP-Based Rate Limiting

| Aspect | By IP | By Client |
|--------|-------|-----------|
| Limit | Fixed (30/min) | Configurable (1-10000/min) |
| Key | Source IP | client_id |
| Persistence | No | Yes (survives key regeneration) |
| Multi-app | No | Yes (each app has its own limit) |

---

## 6. Admin Management

### Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/clients` | List all clients |
| `POST` | `/admin/clients` | Create a client |
| `GET` | `/admin/clients/{id}` | Client details |
| `PUT` | `/admin/clients/{id}/scopes` | Update scopes |
| `PUT` | `/admin/clients/{id}/rate-limit` | Update rate limit |
| `POST` | `/admin/clients/{id}/regenerate` | Regenerate credentials |
| `POST` | `/admin/clients/{id}/deactivate` | Deactivate a client |
| `POST` | `/admin/clients/{id}/activate` | Activate a client |
| `DELETE` | `/admin/clients/{id}` | Delete a client |
| `GET` | `/admin/scopes` | List available scopes |

### Update Scopes

```bash
curl -X PUT http://localhost:4500/admin/clients/{id}/scopes \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"scopes": ["read", "write", "admin"]}'
```

### Update Rate Limit

```bash
curl -X PUT http://localhost:4500/admin/clients/{id}/rate-limit \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"rate_limit": 100}'
```

### Regenerate Credentials

```bash
curl -X POST http://localhost:4500/admin/clients/{id}/regenerate \
  -H "Cookie: session=..."
```

**Warning**: The old api_key and client_secret are immediately deactivated.

---

## 7. Language Examples

### JavaScript / Node.js

```javascript
// 1. Get a token
async function login(clientId, clientSecret) {
  const response = await fetch('http://localhost:4500/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret })
  });
  return await response.json();
}

// 2. Use the token
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

// 3. Refresh the token
async function refreshToken(refreshToken) {
  const response = await fetch('http://localhost:4500/oauth/token/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  return await response.json();
}

// Usage
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

# Usage
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
# 1. Get a token
TOKEN=$(curl -s -X POST http://localhost:4500/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"...","client_secret":"..."}' | jq -r '.access_token')

# 2. Use the token
curl -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "test"}'

# 3. Refresh the token
NEW_TOKEN=$(curl -s -X POST http://localhost:4500/oauth/token/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$TOKEN\"}" | jq -r '.access_token')
```

---

## 8. Security

### Best Practices

1. **Credentials Storage**:
   - Never store `client_secret` in source code
   - Use environment variables or a secrets manager
   - The server stores only the SHA-256 hash of the secret

2. **JWT Tokens**:
   - Expiration: 1 hour by default
   - Refresh possible for 15 minutes after expiration
   - Scopes are updated on refresh (no stale cache)

3. **Rate Limiting**:
   - Configure appropriate limits for each use case
   - Monitor 429 errors in logs
   - Increase limits for legitimate clients

4. **Credential Rotation**:
   - Regenerate credentials periodically
   - Refresh token remains valid during the grace period (15 min)
   - Notify the team before rotation

### Secrets

| Secret | Description | Storage |
|--------|-------------|---------|
| `api_key` | API key (format `ws_...`) | Stored in plaintext (displayed once) |
| `client_secret` | OAuth2 secret (format `cs_...`) | SHA-256 hash in DB |
| `JWT_SECRET` | Secret for signing JWTs | Environment variable |

### Environment Variables

```bash
# Secret for JWT tokens (default: randomly generated)
JWT_SECRET=your-secret-here

# Or let the system generate one randomly
# JWT_SECRET not defined → secrets.token_hex(32)
```

---

## 9. FAQ

### Q: What is the difference between API Key and OAuth2?

**A**: API Key is a permanent token that grants full access. OAuth2 creates temporary tokens (1h) with specific permissions (scopes) and configurable rate limiting.

### Q: How do I change a client's scopes?

**A**: Via the admin UI (`/admin` → Clients → Edit) or the API:
```bash
curl -X PUT http://localhost:4500/admin/clients/{id}/scopes \
  -d '{"scopes": ["read", "write"]}'
```

### Q: What if I lose the client_secret?

**A**: Regenerate the credentials via the admin. The old secret is immediately deactivated.

### Q: Is an expired token still valid?

**A**: No, but it can still be used for refresh for 15 minutes. After that, you must re-authenticate.

### Q: How do I know which scope is required?

**A**: The 403 error indicates the required scope:
```json
{
  "detail": "Scope 'write' required. Available scopes: read"
}
```

### Q: Is the rate limit per endpoint?

**A**: No, it is per client. All endpoints share the same limit for a given client.

### Q: How do I test authentication?

**A**:
```bash
# Test without credentials
curl http://localhost:4500/health

# Test with API key
curl -H "X-API-Key: ws_..." http://localhost:4500/health

# Test with OAuth2
curl -X POST http://localhost:4500/oauth/token \
  -d '{"client_id":"...","client_secret":"..."}'
# Then use the returned token
```

---

## Support

- GitHub: https://github.com/Hajrudin-Zelef/websearch_agent
- Issues: https://github.com/Hajrudin-Zelef/websearch_agent/issues
