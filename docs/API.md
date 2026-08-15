# API — Guide d'intégration

> Voir aussi : [[AGENTS]], [[OAUTH]], [[ARCHITECTURE]], [[README]]

Comment connecter vos applications a l'API WebSearch Agent.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Authentification](#2-authentification)
3. [OAuth2 (recommande)](#3-oauth2-recommande)
4. [JavaScript / Node.js](#4-javascript--nodejs)
5. [Python](#5-python)
6. [PHP](#6-php)
7. [Go](#7-go)
8. [Rust](#8-rust)
9. [cURL / Bash](#9-curl--bash)
10. [Webhook / n8n / Make](#10-webhook---n8n--make)
11. [Flutter / Dart](#11-flutter--dart)
12. [Swift (iOS)](#12-swift-ios)
13. [Kotlin (Android)](#13-kotlin-android)
14. [C# (.NET)](#14-c-net)
15. [Exemples avances](#15-exemples-avances)

---

## 1. Vue d'ensemble

### URL de base

```
http://localhost:4500
```

### Endpoints

| Methode | Endpoint | Description | Auth | Body / Query |
|---------|----------|-------------|------|-------------|
| `POST` | `/chat` | Recherche conversationnelle avec synthese LLM | write | `{"message": "..."}` |
| `POST` | `/chat` | Follow-up | write | `{"message": "...", "thread_id": "..."}` |
| `GET` | `/search` | Recherche structuree (sources brutes) | read | `?q=...&max_results=10` |
| `POST` | `/oauth/token` | Obtenir un access token | client_id/secret | `{"client_id":"...","client_secret":"..."}` |
| `POST` | `/oauth/token/refresh` | Rafraichir un token | refresh_token | `{"refresh_token":"eyJ..."}` |
| `GET` | `/threads` | Liste threads | - | - |
| `GET` | `/threads/{id}` | Detail thread | - | - |
| `DELETE` | `/threads/{id}` | Supprimer thread | - | - |
| `GET` | `/threads/{id}/context` | Contexte follow-up | - | - |
| `GET` | `/datasets` | Datasets | - | `?query=...&max_results=5` |
| `GET` | `/health` | Health check | - | - |
| `GET` | `/metrics` | Metriques agent | - | - |

### Headers

```
Content-Type: application/json
```

### Reponse type (`/chat`)

```json
{
  "response": "Le W3C est un organisme... [1] [2]",
  "refused": false,
  "thread_id": "5595c0fb-8ffe-41f7-a1d1-0eb4fc19f37a"
}
```

---

## 2. Authentification

L'API supporte 3 modes d'authentification :

### Mode 1 : API Key (simple)

```bash
# Via header X-API-Key
curl -H "X-API-Key: ws_..." http://localhost:4500/chat -d '{"message":"test"}'

# Via Authorization Bearer
curl -H "Authorization: Bearer ws_..." http://localhost:4500/chat -d '{"message":"test"}'
```

### Mode 2 : OAuth2 JWT (recommande)

```bash
# 1. Obtenir un token
curl -X POST http://localhost:4500/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"...","client_secret":"..."}'

# Reponse :
# {"access_token":"eyJ...","token_type":"Bearer","expires_in":3600,"scopes":["read","write"]}

# 2. Utiliser le token
curl -H "Authorization: Bearer eyJ..." http://localhost:4500/chat -d '{"message":"test"}'

# 3. Rafraichir avant expiration
curl -X POST http://localhost:4500/oauth/token/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"eyJ..."}'
```

### Mode 3 : Sans credentials (backward compatible)

```bash
curl http://localhost:4500/chat -d '{"message":"test"}'
# Rate limit par IP (30 req/min)
```

### Scopes disponibles

| Scope | Description | Endpoints |
|-------|-------------|-----------|
| `read` | Lire et rechercher | `/search`, `/threads`, `/datasets` |
| `write` | Envoyer des messages | `/chat` |
| `admin` | Gerer l'administration | `/admin/*` |

Guide complet : [OAUTH.md](OAUTH.md)

---

## 3. OAuth2 (recommande)

### Flow complet

```
┌─────────────┐     POST /oauth/token      ┌─────────────┐
│   Client    │ ──────────────────────────▶ │   Server    │
│             │   {client_id, secret}       │             │
│             │ ◀────────────────────────── │             │
│             │   {access_token, scopes}    │             │
│             │                             │             │
│             │   GET /chat                 │             │
│             │   Authorization: Bearer eyJ │             │
│             │ ──────────────────────────▶ │             │
│             │ ◀────────────────────────── │             │
│             │   {response, thread_id}     │             │
└─────────────┘                             └─────────────┘
```

### Scopes par client

| Client | Scopes | Limite |
|--------|--------|--------|
| App principale | `["read", "write"]` | 30 req/min |
| App admin | `["read", "write", "admin"]` | 100 req/min |
| App read-only | `["read"]` | 50 req/min |

### Gestion via admin

```bash
# Modifier les scopes d'un client
curl -X PUT http://localhost:4500/admin/clients/{id}/scopes \
  -H "Content-Type: application/json" \
  -d '{"scopes": ["read", "write", "admin"]}'

# Modifier le rate limit
curl -X PUT http://localhost:4500/admin/clients/{id}/rate-limit \
  -H "Content-Type: application/json" \
  -d '{"rate_limit": 100}'

# Lister les scopes disponibles
curl http://localhost:4500/admin/scopes
```

---

## 4. JavaScript / Node.js

### Fetch (natif)

```javascript
const response = await fetch('http://localhost:4500/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer eyJ...'  // ou 'X-API-Key: ws_...'
  },
  body: JSON.stringify({
    message: "qu'est-ce que le W3C ?"
  })
});

const data = await response.json();
console.log(data.response);
```

### Axios

```javascript
const axios = require('axios');

const response = await axios.post('http://localhost:4500/chat', {
  message: "dernières actualités IA"
}, {
  headers: { 'Authorization': 'Bearer eyJ...' }
});

console.log(response.data.response);
```

### Express.js (middleware)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/search', async (req, res) => {
  const response = await fetch('http://localhost:4500/chat', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${req.body.token}`
    },
    body: JSON.stringify({ message: req.body.query })
  });

  const data = await response.json();
  res.json(data);
});

app.listen(3000);
```

### React

```jsx
import { useState } from 'react';

function SearchComponent() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState('');
  const [threadId, setThreadId] = useState(null);

  const handleSearch = async () => {
    const body = { message: query };
    if (threadId) body.thread_id = threadId;

    const response = await fetch('http://localhost:4500/chat', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify(body)
    });

    const data = await response.json();
    setResult(data.response);
    setThreadId(data.thread_id);
  };

  return (
    <div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Votre question..."
      />
      <button onClick={handleSearch}>Rechercher</button>
      <p>{result}</p>
      {threadId && <small>Thread: {threadId.slice(0, 8)}</small>}
    </div>
  );
}
```

### OAuth2 en JavaScript

```javascript
// 1. Obtenir un token
async function login(clientId, clientSecret) {
  const response = await fetch('http://localhost:4500/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret })
  });
  const data = await response.json();
  localStorage.setItem('token', data.access_token);
  return data;
}

// 2. Utiliser le token
async function search(query) {
  const token = localStorage.getItem('token');
  const response = await fetch('http://localhost:4500/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ message: query })
  });
  return response.json();
}

// 3. Rafraichir le token
async function refreshToken(refreshToken) {
  const response = await fetch('http://localhost:4500/oauth/token/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  const data = await response.json();
  localStorage.setItem('token', data.access_token);
  return data;
}
```

---

## 5. Python

### Requests

```python
import requests

response = requests.post(
    'http://localhost:4500/chat',
    json={'message': 'github langchain'},
    headers={'Authorization': 'Bearer eyJ...'}  # ou 'X-API-Key': 'ws_...'
)

data = response.json()
print(data['response'])
```

### httpx (async)

```python
import httpx
import asyncio

async def search(query: str, token: str = None):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'http://localhost:4500/chat',
            json={'message': query},
            headers=headers
        )
        return response.json()

result = asyncio.run(search('comparaison React vs Vue.js', token='eyJ...'))
print(result['response'])
```

### FastAPI (client)

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

@app.post("/proxy-search")
async def proxy_search(query: str, token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'http://localhost:4500/chat',
            json={'message': query},
            headers={'Authorization': f'Bearer {token}'}
        )
        return response.json()
```

### Flask

```python
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    response = requests.post(
        'http://localhost:4500/chat',
        json={'message': data['query']},
        headers={'Authorization': f'Bearer {data.get("token")}'}
    )
    return jsonify(response.json())
```

### OAuth2 en Python

```python
import requests

# 1. Obtenir un token
def get_token(client_id: str, client_secret: str) -> dict:
    response = requests.post(
        'http://localhost:4500/oauth/token',
        json={'client_id': client_id, 'client_secret': client_secret}
    )
    return response.json()

# 2. Utiliser le token
def search(query: str, token: str) -> dict:
    response = requests.post(
        'http://localhost:4500/chat',
        json={'message': query},
        headers={'Authorization': f'Bearer {token}'}
    )
    return response.json()

# 3. Rafraichir le token
def refresh_token(refresh_token: str) -> dict:
    response = requests.post(
        'http://localhost:4500/oauth/token/refresh',
        json={'refresh_token': refresh_token}
    )
    return response.json()

# Utilisation
token_data = get_token('your-client-id', 'your-client-secret')
result = search('github langchain', token_data['access_token'])
```

---

## 6. PHP

### cURL

```php
<?php
$ch = curl_init('http://localhost:4500/chat');

curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    'message' => "qu'est-ce que le W3C ?"
]));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'Authorization: Bearer eyJ...'  // ou 'X-API-Key: ws_...'
]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

$response = curl_exec($ch);
curl_close($ch);

$data = json_decode($response, true);
echo $data['response'];
?>
```

### Guzzle

```php
<?php
require 'vendor/autoload.php';

use GuzzleHttp\Client;

$client = new Client();

$response = $client->post('http://localhost:4500/chat', [
    'json' => ['message' => 'actualités IA'],
    'headers' => ['Authorization' => 'Bearer eyJ...']
]);

$data = json_decode($response->getBody(), true);
echo $data['response'];
?>
```

### OAuth2 en PHP

```php
<?php
// 1. Obtenir un token
$ch = curl_init('http://localhost:4500/oauth/token');
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    'client_id' => 'your-client-id',
    'client_secret' => 'your-client-secret'
]));
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$tokenData = json_decode(curl_exec($ch), true);
$token = $tokenData['access_token'];

// 2. Utiliser le token
$ch = curl_init('http://localhost:4500/chat');
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(['message' => 'test']));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    "Authorization: Bearer $token"
]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = json_decode(curl_exec($ch), true);
echo $response['response'];
?>
```

---

## 7. Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type Request struct {
    Message  string `json:"message"`
    ThreadID string `json:"thread_id,omitempty"`
}

type Response struct {
    Response string `json:"response"`
    Refused  bool   `json:"refused"`
    ThreadID string `json:"thread_id"`
}

func main() {
    reqBody, _ := json.Marshal(Request{
        Message: "github langchain",
    })

    req, _ := http.NewRequest("POST", "http://localhost:4500/chat", bytes.NewBuffer(reqBody))
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Authorization", "Bearer eyJ...")  // ou "X-API-Key: ws_..."

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        panic(err)
    }
    defer resp.Body.Close()

    var result Response
    json.NewDecoder(resp.Body).Decode(&result)

    fmt.Println(result.Response)
    fmt.Println("Thread:", result.ThreadID)
}
```

### OAuth2 en Go

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

func main() {
    token, _ := getToken("your-client-id", "your-client-secret")
    fmt.Println("Token:", token)
}
```

---

## 8. Rust

```rust
use reqwest::Client;
use serde::{Deserialize, Serialize};

#[derive(Serialize)]
struct SearchRequest {
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    thread_id: Option<String>,
}

#[derive(Deserialize)]
struct SearchResponse {
    response: String,
    refused: bool,
    thread_id: String,
}

#[tokio::main]
async fn main() -> Result<(), reqwest::Error> {
    let client = Client::new();

    let response = client
        .post("http://localhost:4500/chat")
        .header("Authorization", "Bearer eyJ...")  // ou .header("X-API-Key", "ws_...")
        .json(&SearchRequest {
            message: "qu'est-ce que le W3C ?".to_string(),
            thread_id: None,
        })
        .send()
        .await?
        .json::<SearchResponse>()
        .await?;

    println!("{}", response.response);
    println!("Thread: {}", response.thread_id);

    Ok(())
}
```

---

## 9. cURL / Bash

### Requete simple

```bash
curl -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "qu'\''est-ce que le W3C ?"}'
```

### Avec API key

```bash
curl -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ws_..." \
  -d '{"message": "qu'\''est-ce que le W3C ?"}'
```

### Avec OAuth2

```bash
# 1. Obtenir un token
TOKEN=$(curl -s -X POST http://localhost:4500/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"...","client_secret":"..."}' | jq -r '.access_token')

# 2. Utiliser le token
curl -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "qu'\''est-ce que le W3C ?"}'

# 3. Rafraichir le token
REFRESH_TOKEN=$(curl -s -X POST http://localhost:4500/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"...","client_secret":"..."}' | jq -r '.access_token')

curl -X POST http://localhost:4500/oauth/token/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}"
```

### Avec jq

```bash
curl -s -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJ..." \
  -d '{"message": "actualités IA"}' | jq -r '.response'
```

### Script Bash

```bash
#!/bin/bash

# Configuration
CLIENT_ID="your-client-id"
CLIENT_SECRET="your-client-secret"

# Fonction pour obtenir un token
get_token() {
    curl -s -X POST http://localhost:4500/oauth/token \
        -H "Content-Type: application/json" \
        -d "{\"client_id\":\"$CLIENT_ID\",\"client_secret\":\"$CLIENT_SECRET\"}" | jq -r '.access_token'
}

# Fonction de recherche
search() {
    local TOKEN=$(get_token)
    curl -s -X POST http://localhost:4500/chat \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"message\": \"$1\"}" | jq -r '.response'
}

# Utilisation
search "github langchain"
search "comparaison React vs Vue.js"
```

### Health check

```bash
curl http://localhost:4500/health
```

### Recherche structuree (sources brutes)

```bash
curl "http://localhost:4500/search?q=climat&max_results=10"
```

### Datasets

```bash
curl "http://localhost:4500/datasets?query=climat&max_results=5"
```

### Threads

```bash
# Lister les threads
curl http://localhost:4500/threads

# Detail d'un thread
curl http://localhost:4500/threads/{thread_id}

# Contexte pour follow-up
curl http://localhost:4500/threads/{thread_id}/context

# Supprimer un thread
curl -X DELETE http://localhost:4500/threads/{thread_id}
```

### Follow-up dans un thread

```bash
# Premiere question (cree un thread)
curl -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJ..." \
  -d '{"message": "Qu'\''est-ce que le W3C ?"}'

# Follow-up (reutilise le thread)
curl -X POST http://localhost:4500/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJ..." \
  -d '{"message": "Et ses standards principaux ?", "thread_id": "5595c0fb-..."}'
```

---

## 10. Webhook / n8n / Make

### Webhook simple

```javascript
// Express.js
app.post('/webhook', async (req, res) => {
  const { message } = req.body;

  const response = await fetch('http://localhost:4500/chat', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.API_TOKEN}`
    },
    body: JSON.stringify({ message })
  });

  const data = await response.json();
  res.json(data);
});
```

### n8n

1. Creer un workflow avec un trigger **Webhook**
2. Ajouter un node **HTTP Request** :
   - Method: POST
   - URL: `http://localhost:4500/chat`
   - Headers: `Authorization: Bearer {{$env.API_TOKEN}}`
   - Body: `{"message": "{{$json.body.message}}"}`
3. Connecter a un node **Response** ou **Slack** / **Email**

### Make (Integromat)

1. Creer un scenario avec un trigger **Webhook**
2. Ajouter un module **HTTP** :
   - Method: POST
   - URL: `http://localhost:4500/chat`
   - Headers: `Content-Type: application/json`, `Authorization: Bearer {{token}}`
   - Body: `{"message": "{{message}}"}`

### Zapier

1. Creer un zap avec un trigger **Webhooks by Zapier**
2. Ajouter une action **Code by Zapier** (Python) :

```python
import requests

response = requests.post(
    'http://localhost:4500/chat',
    json={'message': input_data['message']},
    headers={'Authorization': f'Bearer {input_data["token"]}'}
)

return {'response': response.json()['response']}
```

---

## 11. Flutter / Dart

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

Future<String> search(String query, {String? token}) async {
  final headers = {'Content-Type': 'application/json'};
  if (token != null) headers['Authorization'] = 'Bearer $token';

  final response = await http.post(
    Uri.parse('http://localhost:4500/chat'),
    headers: headers,
    body: jsonEncode({'message': query}),
  );

  final data = jsonDecode(response.body);
  return data['response'];
}

// Utilisation
String result = await search('qu'est-ce que le W3C ?', token: 'eyJ...');
```

### OAuth2 en Flutter

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class WebSearchClient {
  final String clientId;
  final String clientSecret;
  String? _token;

  WebSearchClient({required this.clientId, required this.clientSecret});

  Future<void> login() async {
    final response = await http.post(
      Uri.parse('http://localhost:4500/oauth/token'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'client_id': clientId, 'client_secret': clientSecret}),
    );
    final data = jsonDecode(response.body);
    _token = data['access_token'];
  }

  Future<String> search(String query) async {
    final response = await http.post(
      Uri.parse('http://localhost:4500/chat'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $_token',
      },
      body: jsonEncode({'message': query}),
    );
    final data = jsonDecode(response.body);
    return data['response'];
  }
}
```

---

## 12. Swift (iOS)

```swift
import Foundation

func search(query: String, token: String? = nil) async throws -> String {
    let url = URL(string: "http://localhost:4500/chat")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.addValue("application/json", forHTTPHeaderField: "Content-Type")
    if let token = token {
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    }

    let body = ["message": query]
    request.httpBody = try JSONSerialization.data(withJSONObject: body)

    let (data, _) = try await URLSession.shared.data(for: request)
    let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

    return json?["response"] as? String ?? ""
}

// Utilisation
let result = try await search(query: "github langchain", token: "eyJ...")
```

### OAuth2 en Swift

```swift
import Foundation

struct TokenResponse: Codable {
    let accessToken: String
    let tokenType: String
    let expiresIn: Int
    let scopes: [String]
}

func getToken(clientId: String, clientSecret: String) async throws -> String {
    let url = URL(string: "http://localhost:4500/oauth/token")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.addValue("application/json", forHTTPHeaderField: "Content-Type")
    
    let body = ["client_id": clientId, "client_secret": clientSecret]
    request.httpBody = try JSONSerialization.data(withJSONObject: body)
    
    let (data, _) = try await URLSession.shared.data(for: request)
    let token = try JSONDecoder().decode(TokenResponse.self, from: data)
    return token.accessToken
}
```

---

## 13. Kotlin (Android)

```kotlin
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

fun search(query: String, token: String? = null): String {
    val client = OkHttpClient()

    val json = JSONObject().put("message", query)
    val body = json.toString().toRequestBody("application/json".toMediaType())

    val requestBuilder = Request.Builder()
        .url("http://localhost:4500/chat")
        .post(body)
    
    token?.let {
        requestBuilder.addHeader("Authorization", "Bearer $it")
    }

    val response = client.newCall(requestBuilder.build()).execute()
    val responseBody = response.body?.string() ?: ""

    return JSONObject(responseBody).getString("response")
}

// Utilisation
val result = search("qu'est-ce que le W3C ?", token = "eyJ...")
```

### OAuth2 en Kotlin

```kotlin
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

fun getToken(clientId: String, clientSecret: String): String {
    val client = OkHttpClient()

    val json = JSONObject()
        .put("client_id", clientId)
        .put("client_secret", clientSecret)
    val body = json.toString().toRequestBody("application/json".toMediaType())

    val request = Request.Builder()
        .url("http://localhost:4500/oauth/token")
        .post(body)
        .build()

    val response = client.newCall(request).execute()
    val responseBody = response.body?.string() ?: ""
    return JSONObject(responseBody).getString("access_token")
}
```

---

## 14. C# (.NET)

```csharp
using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

class Program
{
    static async Task Main()
    {
        using var client = new HttpClient();
        client.DefaultRequestHeaders.Add("Authorization", "Bearer eyJ...");

        var body = new { message = "github langchain" };
        var json = JsonSerializer.Serialize(body);
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        var response = await client.PostAsync("http://localhost:4500/chat", content);
        var responseString = await response.Content.ReadAsStringAsync();

        var result = JsonSerializer.Deserialize<JsonElement>(responseString);
        Console.WriteLine(result.GetProperty("response").GetString());
    }
}
```

### OAuth2 en C#

```csharp
using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

class Program
{
    static async Task<string> GetToken(string clientId, string clientSecret)
    {
        using var client = new HttpClient();
        
        var body = new { client_id = clientId, client_secret = clientSecret };
        var json = JsonSerializer.Serialize(body);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        var response = await client.PostAsync("http://localhost:4500/oauth/token", content);
        var responseString = await response.Content.ReadAsStringAsync();
        
        var result = JsonSerializer.Deserialize<JsonElement>(responseString);
        return result.GetProperty("access_token").GetString();
    }

    static async Task Main()
    {
        var token = await GetToken("your-client-id", "your-client-secret");
        Console.WriteLine("Token: " + token);
    }
}
```

---

## 15. Exemples avances

### Recherche structuree pour providers externes (`/search`)

Cet endpoint retourne des sources brutes (url/titre/extrait) sans passer par la synthese LLM — pensé pour des integrations comme DeepSeek Harness ou tout autre systeme qui a son propre modele et veut juste des resultats de recherche bruts, dedupliques par URL.

```python
import httpx

response = httpx.get(
    'http://localhost:4500/search',
    params={'q': 'coupe du monde 2026', 'max_results': 10}
)
data = response.json()

for source in data['sources']:
    print(f"{source['title']} — {source['url']}")
    print(f"  {source['snippet']}")

print(f"\n{data['count']} resultats (tronque: {data['truncated']})")
```

```bash
curl "http://localhost:4500/search?q=coupe%20du%20monde%202026&max_results=10"
```

Reponse :

```json
{
  "sources": [
    {"url": "https://...", "title": "...", "snippet": "..."}
  ],
  "query": "coupe du monde 2026",
  "count": 8,
  "truncated": false
}
```

`max_results` accepte une valeur entre 1 et 30 (defaut : 10).

### Retry automatique

```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search(query: str):
    response = requests.post(
        'http://localhost:4500/chat',
        json={'message': query},
        timeout=30
    )
    response.raise_for_status()
    return response.json()
```

### Cache cote client

```python
from functools import lru_cache
import requests

@lru_cache(maxsize=128)
def search_cached(query: str):
    response = requests.post(
        'http://localhost:4500/chat',
        json={'message': query}
    )
    return response.json()['response']

# Meme requete = cache
result = search_cached("qu'est-ce que le W3C ?")
```

### Batch de requetes

```python
import asyncio
import httpx

async def search_batch(queries: list[str]):
    async with httpx.AsyncClient() as client:
        tasks = [
            client.post('http://localhost:4500/chat', json={'message': q})
            for q in queries
        ]
        responses = await asyncio.gather(*tasks)
        return [r.json()['response'] for r in responses]

# Utilisation
queries = ["python", "javascript", "rust"]
results = asyncio.run(search_batch(queries))
```

### Follow-up avec threads

```python
import httpx

# Premiere question
response = httpx.post(
    'http://localhost:4500/chat',
    json={'message': "Qu'est-ce que le machine learning ?"}
)
data = response.json()
thread_id = data['thread_id']

# Follow-up dans le meme thread
followup = httpx.post(
    'http://localhost:4500/chat',
    json={
        'message': "Et le deep learning ?",
        'thread_id': thread_id
    }
)
print(followup.json()['response'])
```

### Lister les threads

```python
import httpx

threads = httpx.get('http://localhost:4500/threads').json()
for t in threads:
    print(f"{t['id'][:8]} — {t['title']}")
```

### Timeout personnalise

```javascript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 10000); // 10s

try {
  const response = await fetch('http://localhost:4500/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: 'test' }),
    signal: controller.signal
  });

  const data = await response.json();
  console.log(data.response);
} catch (error) {
  if (error.name === 'AbortError') {
    console.log('Timeout');
  }
} finally {
  clearTimeout(timeout);
}
```

---

## Limites et bonnes pratiques

| Aspect | Recommandation |
|--------|----------------|
| Rate limiting | 30 req/min par client (defaut), configurable via admin |
| Rate limiting IP | 30 req/min par IP (sans credentials) |
| Authentification | OAuth2 recommande (scopes + rate limit par client) |
| Timeout client | 30 secondes maximum |
| Taille message | 500 caracteres max |
| Taille body HTTP | 10 KB max |
| `/search` max_results | 1 a 30 (defaut 10) |
| Retry | Maximum 3 tentatives |
| Cache | 5 minutes de TTL |
| Token expiration | 1 heure (refresh possible 15 min apres expiration) |

---

## Support

- GitHub : https://github.com/Hajrudin-Zelef/websearch_agent
- Issues : https://github.com/Hajrudin-Zelef/websearch_agent/issues
