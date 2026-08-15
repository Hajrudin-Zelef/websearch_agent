# dsh-web-search-local

A local web search provider for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) that calls a local FastAPI search backend with 13+ aggregated search sources.

## What it does

When DeepSeek Harness needs to search the web (via the `web_search` tool), this plugin routes the query to your local `websearch_agent` server, which:

- Aggregates 13+ search sources (Perplexity, Tavily, Brave, DuckDuckGo, SearXNG, Wikipedia, GitHub, News RSS, Datasets, etc.)
- Uses an intelligent router to detect intent, domain, and complexity
- Runs sources in parallel and deduplicates results
- Returns structured results (URLs, titles, snippets) compatible with DSH

## Architecture

```
DSH agent → ctx.web.search() → LocalSearchProvider → GET http://127.0.0.1:4500/search?q=... → websearch_agent → 13 sources → WebSearchResult
```

## Installation

1. Install the plugin in your DSH project:

```bash
cd /path/to/your/dsh/project
npm install /home/sam/websearch_agent/dsh-web-search-local
```

2. Add the plugin to your DSH composition (see Configuration below).

3. Make sure your `websearch_agent` server is running on port 4500.

## Configuration

Add this to your DSH `agent.cordis.yml` (or a custom composition):

```yaml
# Host composition — replace or supplement the existing web-search-deepseek row
- id: web-search-local
  name: dsh-web-search-local
  config:
    baseURL: http://127.0.0.1:4500
    maxResults: 10
```

To **replace** the default DeepSeek search provider, also set:

```yaml
- id: web
  name: '@deepseek-ai/dsh-web'
  config:
    searchProvider: local-search
```

Or use the environment variable:

```bash
DSH_WEB_SEARCH_PROVIDER=local-search
```

## API Contract

The plugin calls `GET /search` on your FastAPI server:

**Request:**
```
GET /search?q=python+async&max_results=10
```

**Response:**
```json
{
  "sources": [
    {
      "url": "https://docs.python.org/3/library/asyncio.html",
      "title": "asyncio — I/O,.coroutines and concurrent execution",
      "snippet": "asyncio is a library to write concurrent code using the async/await syntax."
    }
  ],
  "query": "python async",
  "count": 1,
  "truncated": false
}
```

## Plugin Config

| Key | Default | Meaning |
|---|---|---|
| `baseURL` | `http://127.0.0.1:4500` | Base URL of the websearch_agent server |
| `maxResults` | `10` | Maximum results per search |

## How it differs from dsh-web-search-deepSeek

| | dsh-web-search-deepseek | dsh-web-search-local |
|---|---|---|
| Backend | DeepSeek API (Anthropic Messages) | Local FastAPI server |
| Cost | 1 model turn per search | Free (local) |
| Sources | DeepSeek's native web_search | 13+ aggregated sources |
| Latency | ~2-5s (API call) | ~1-3s (local) |
| Requires | DeepSeek API key | Just the server running |
