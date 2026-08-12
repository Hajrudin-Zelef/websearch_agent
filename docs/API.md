# Guide d'Integration API - WebSearch Agent

Comment connecter vos applications a l'API WebSearch Agent.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [JavaScript / Node.js](#2-javascript--nodejs)
3. [Python](#3-python)
4. [PHP](#4-php)
5. [Go](#5-go)
6. [Rust](#6-rust)
7. [cURL / Bash](#7-curl--bash)
8. [Webhook / n8n / Make](#8-webhook--n8n--make)
9. [Flutter / Dart](#9-flutter--dart)
10. [Swift (iOS)](#10-swift-ios)
11. [Kotlin (Android)](#11-kotlin-android)
12. [C# (.NET)](#12-c-net)
13. [Exemples avances](#13-exemples-avances)

---

## 1. Vue d'ensemble

### URL de base

```
http://localhost:8000
```

### Endpoints

| Methode | Endpoint | Description | Body |
|---------|----------|-------------|------|
| `POST` | `/chat` | Recherche | `{"message": "..."}` |
| `POST` | `/chat` | Follow-up | `{"message": "...", "thread_id": "..."}` |
| `GET` | `/threads` | Liste threads | - |
| `GET` | `/threads/{id}` | Detail thread | - |
| `DELETE` | `/threads/{id}` | Supprimer thread | - |
| `GET` | `/threads/{id}/context` | Contexte follow-up | - |
| `GET` | `/datasets` | Datasets | `?query=...&max_results=5` |
| `GET` | `/health` | Health check | - |

### Headers

```
Content-Type: application/json
```

### Reponse type

```json
{
  "response": "Le W3C est un organisme... [1] [2]",
  "refused": false,
  "thread_id": "5595c0fb-8ffe-41f7-a1d1-0eb4fc19f37a"
}
```

---

## 2. JavaScript / Node.js

### Fetch (natif)

```javascript
const response = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
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

const response = await axios.post('http://localhost:8000/chat', {
  message: "dernières actualités IA"
});

console.log(response.data.response);
```

### Express.js (middleware)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/search', async (req, res) => {
  const response = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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

    const response = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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

---

## 3. Python

### Requests

```python
import requests

response = requests.post(
    'http://localhost:8000/chat',
    json={'message': 'github langchain'}
)

data = response.json()
print(data['response'])
```

### httpx (async)

```python
import httpx
import asyncio

async def search(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'http://localhost:8000/chat',
            json={'message': query}
        )
        return response.json()

result = asyncio.run(search('comparaison React vs Vue.js'))
print(result['response'])
```

### FastAPI (client)

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

@app.post("/proxy-search")
async def proxy_search(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'http://localhost:8000/chat',
            json={'message': query}
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
        'http://localhost:8000/chat',
        json={'message': data['query']}
    )
    return jsonify(response.json())
```

---

## 4. PHP

### cURL

```php
<?php
$ch = curl_init('http://localhost:8000/chat');

curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    'message' => "qu'est-ce que le W3C ?"
]));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json'
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

$response = $client->post('http://localhost:8000/chat', [
    'json' => ['message' => 'actualités IA']
]);

$data = json_decode($response->getBody(), true);
echo $data['response'];
?>
```

---

## 5. Go

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

    resp, err := http.Post(
        "http://localhost:8000/chat",
        "application/json",
        bytes.NewBuffer(reqBody),
    )
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

---

## 6. Rust

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
        .post("http://localhost:8000/chat")
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

## 7. cURL / Bash

### Requete simple

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "qu'\''est-ce que le W3C ?"}'
```

### Avec jq

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "actualités IA"}' | jq -r '.response'
```

### Script Bash

```bash
#!/bin/bash

search() {
    curl -s -X POST http://localhost:8000/chat \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"$1\"}" | jq -r '.response'
}

# Utilisation
search "github langchain"
search "comparaison React vs Vue.js"
```

### Health check

```bash
curl http://localhost:8000/health
```

### Datasets

```bash
curl "http://localhost:8000/datasets?query=climat&max_results=5"
```

### Threads

```bash
# Lister les threads
curl http://localhost:8000/threads

# Detail d'un thread
curl http://localhost:8000/threads/{thread_id}

# Contexte pour follow-up
curl http://localhost:8000/threads/{thread_id}/context

# Supprimer un thread
curl -X DELETE http://localhost:8000/threads/{thread_id}
```

### Follow-up dans un thread

```bash
# Premiere question (cree un thread)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Qu'\''est-ce que le W3C ?"}'

# Follow-up (reutilise le thread)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Et ses standards principaux ?", "thread_id": "5595c0fb-..."}'
```

---

## 8. Webhook / n8n / Make

### Webhook simple

```javascript
// Express.js
app.post('/webhook', async (req, res) => {
  const { message } = req.body;

  const response = await fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
   - URL: `http://localhost:8000/chat`
   - Body: `{"message": "{{$json.body.message}}"}`
3. Connecter a un node **Response** ou **Slack** / **Email**

### Make (Integromat)

1. Creer un scenario avec un trigger **Webhook**
2. Ajouter un module **HTTP** :
   - Method: POST
   - URL: `http://localhost:8000/chat`
   - Headers: `Content-Type: application/json`
   - Body: `{"message": "{{message}}"}`

### Zapier

1. Creer un zap avec un trigger **Webhooks by Zapier**
2. Ajouter une action **Code by Zapier** (Python) :

```python
import requests

response = requests.post(
    'http://localhost:8000/chat',
    json={'message': input_data['message']}
)

return {'response': response.json()['response']}
```

---

## 9. Flutter / Dart

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

Future<String> search(String query) async {
  final response = await http.post(
    Uri.parse('http://localhost:8000/chat'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'message': query}),
  );

  final data = jsonDecode(response.body);
  return data['response'];
}

// Utilisation
String result = await search('qu'est-ce que le W3C ?');
```

---

## 10. Swift (iOS)

```swift
import Foundation

func search(query: String) async throws -> String {
    let url = URL(string: "http://localhost:8000/chat")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.addValue("application/json", forHTTPHeaderField: "Content-Type")

    let body = ["message": query]
    request.httpBody = try JSONSerialization.data(withJSONObject: body)

    let (data, _) = try await URLSession.shared.data(for: request)
    let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

    return json?["response"] as? String ?? ""
}

// Utilisation
let result = try await search(query: "github langchain")
```

---

## 11. Kotlin (Android)

```kotlin
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

fun search(query: String): String {
    val client = OkHttpClient()

    val json = JSONObject().put("message", query)
    val body = json.toString().toRequestBody("application/json".toMediaType())

    val request = Request.Builder()
        .url("http://localhost:8000/chat")
        .post(body)
        .build()

    val response = client.newCall(request).execute()
    val responseBody = response.body?.string() ?: ""

    return JSONObject(responseBody).getString("response")
}

// Utilisation
val result = search("qu'est-ce que le W3C ?")
```

---

## 12. C# (.NET)

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

        var body = new { message = "github langchain" };
        var json = JsonSerializer.Serialize(body);
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        var response = await client.PostAsync("http://localhost:8000/chat", content);
        var responseString = await response.Content.ReadAsStringAsync();

        var result = JsonSerializer.Deserialize<JsonElement>(responseString);
        Console.WriteLine(result.GetProperty("response").GetString());
    }
}
```

---

## 13. Exemples avances

### Streaming (SSE)

```javascript
// Cote client
const eventSource = new EventSource('http://localhost:8000/stream?message=test');

eventSource.onmessage = (event) => {
  console.log(event.data);
};
```

### Retry automatique

```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search(query: str):
    response = requests.post(
        'http://localhost:8000/chat',
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
        'http://localhost:8000/chat',
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
            client.post('http://localhost:8000/chat', json={'message': q})
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
    'http://localhost:8000/chat',
    json={'message': "Qu'est-ce que le machine learning ?"}
)
data = response.json()
thread_id = data['thread_id']

# Follow-up dans le meme thread
followup = httpx.post(
    'http://localhost:8000/chat',
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

threads = httpx.get('http://localhost:8000/threads').json()
for t in threads:
    print(f"{t['id'][:8]} — {t['title']}")
```

### Timeout personnalise

```javascript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 10000); // 10s

try {
  const response = await fetch('http://localhost:8000/chat', {
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
| Rate limiting | 30 requetes/minute par IP |
| Timeout client | 30 secondes maximum |
| Taille message | 500 caracteres max |
| Retry | Maximum 3 tentatives |
| Cache | 5 minutes de TTL |

---

## Support

- GitHub : https://github.com/Hajrudin-Zelef/websearch_agent
- Issues : https://github.com/Hajrudin-Zelef/websearch_agent/issues
