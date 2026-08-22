#!/bin/bash
# Setup script for dsh-web-search-local plugin
# This installs the plugin and configures DSH to use it

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
DSH_PROFILE_DIR="$DSH_HOME/profiles/web"
PATCH_FILE="$DSH_PROFILE_DIR/cordis.patch.yml"

echo "=== dsh-web-search-local setup ==="
echo "Plugin dir: $PLUGIN_DIR"
echo "DSH home: $DSH_HOME"
echo "DSH profile: $DSH_PROFILE_DIR"
echo ""

# 1. Install plugin dependencies
echo "1. Installing plugin dependencies..."
cd "$PLUGIN_DIR"
if [ ! -d "node_modules" ]; then
    npm install --save @deepseek-ai/schemastery 2>/dev/null || true
fi

# 2. Check if websearch_agent is running
echo "2. Checking websearch_agent..."
if curl -s http://127.0.0.1:4500/health > /dev/null 2>&1; then
    echo "   ✓ websearch_agent is running on port 4500"
else
    echo "   ⚠ websearch_agent is NOT running on port 4500"
    echo "   Start it with: cd $HOME/websearch_agent && uvicorn server:app --host 127.0.0.1 --port 4500"
fi

# 3. Create/update DSH profile patch
echo "3. Configuring DSH profile..."
if [ ! -d "$DSH_PROFILE_DIR" ]; then
    echo "   Creating profile directory..."
    mkdir -p "$DSH_PROFILE_DIR"
fi

# Backup existing patch
if [ -f "$PATCH_FILE" ]; then
    cp "$PATCH_FILE" "$PATCH_FILE.bak.$(date +%s)"
    echo "   ✓ Backed up existing cordis.patch.yml"
fi

# Write the patch file
cat > "$PATCH_FILE" << 'PATCH_EOF'
# Local web search provider — overrides DeepSeek search with local websearch_agent
# See: dsh-web-search-local/README.md

- patch:
    id: web
    config:
      searchProvider: local-search

- insert:
    - id: web-search-local
      name: dsh-web-search-local
      config:
        baseURL: http://127.0.0.1:4500
        maxResults: 10
PATCH_EOF

echo "   ✓ Written $PATCH_FILE"

# 4. Test the endpoint
echo "4. Testing /search endpoint..."
if curl -s "http://127.0.0.1:4500/search?q=test&max_results=2" | grep -q "sources"; then
    echo "   ✓ /search endpoint is working"
else
    echo "   ⚠ /search endpoint not responding correctly"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Make sure websearch_agent is running:"
echo "     cd $HOME/websearch_agent && uvicorn server:app --host 127.0.0.1 --port 4500"
echo ""
echo "  2. Restart DSH to pick up the new plugin:"
echo "     (Kill the current DSH process and restart)"
echo ""
echo "  3. Test by asking the agent to search something:"
echo "     The agent will now use your 13+ search sources instead of DeepSeek API"
