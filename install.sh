#!/bin/bash
# Node-RED MCP Server — Installation für Home Assistant OS (Web Terminal Add-on)
# Ausführen als root im HAOS Web Terminal — v4

set -e

INSTALL_DIR="/root/nodered-mcp"
CLAUDE_SETTINGS="/root/.claude/settings.json"
REPO_RAW="https://raw.githubusercontent.com/micdede/hassioClaudeCodeMcp/main"

echo "=== Node-RED MCP Server Installation ==="
echo ""

# 1. Server-Script von GitHub laden
mkdir -p "$INSTALL_DIR"
echo "Lade nodered_mcp_server.py von GitHub..."
if command -v wget &>/dev/null; then
    wget -qO "$INSTALL_DIR/nodered_mcp_server.py" "$REPO_RAW/nodered_mcp_server.py"
elif command -v curl &>/dev/null; then
    curl -fsSL "$REPO_RAW/nodered_mcp_server.py" -o "$INSTALL_DIR/nodered_mcp_server.py"
else
    echo "✗ Weder wget noch curl gefunden."
    exit 1
fi
chmod +x "$INSTALL_DIR/nodered_mcp_server.py"
echo "✓ Server-Script nach $INSTALL_DIR geladen"

# 2. Python3 prüfen — auf HAOS (Alpine) bei Bedarf installieren
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  Python nicht gefunden, installiere via apk..."
    apk add --quiet python3 py3-pip || {
        echo "✗ Python konnte nicht installiert werden."
        exit 1
    }
    PYTHON="python3"
fi
PYTHON_VERSION=$($PYTHON --version 2>&1)
echo "✓ Python: $PYTHON_VERSION"

# 3. pip sicherstellen
if ! $PYTHON -m pip --version &>/dev/null 2>&1; then
    echo "  pip nicht vorhanden, installiere..."
    apk add --quiet py3-pip 2>/dev/null || $PYTHON -m ensurepip --upgrade 2>/dev/null || {
        echo "✗ pip konnte nicht installiert werden."
        exit 1
    }
fi
echo "✓ pip verfügbar"

# 4. mcp-Paket installieren
echo "Installiere mcp-Paket (Anthropic MCP SDK)..."
$PYTHON -m pip install --quiet --upgrade "mcp>=1.0.0"
echo "✓ mcp-Paket installiert"

# 5. Node-RED Verbindung testen
NR_URL="${NODE_RED_URL:-http://localhost:1880}"
echo "Teste Verbindung zu Node-RED ($NR_URL)..."
if $PYTHON -c "
import urllib.request, sys
try:
    urllib.request.urlopen('$NR_URL/flows', timeout=5)
    print('ok')
except Exception as e:
    print(f'fehler: {e}')
    sys.exit(1)
" 2>/dev/null | grep -q ok; then
    echo "✓ Node-RED erreichbar"
else
    echo "⚠ Node-RED nicht erreichbar unter $NR_URL"
    echo "  Stelle sicher dass das Node-RED Add-on läuft."
    echo "  Falls ein anderer Port genutzt wird, setze die Umgebungsvariable:"
    echo "    NODE_RED_URL=http://localhost:DEIN_PORT bash install.sh"
fi

# 6. Claude Code Konfiguration
mkdir -p "$(dirname "$CLAUDE_SETTINGS")"

MCP_ENTRY=$(cat <<JSONEOF
{
  "command": "$PYTHON",
  "args": ["$INSTALL_DIR/nodered_mcp_server.py"],
  "env": {
    "NODE_RED_URL": "${NODE_RED_URL:-http://localhost:1880}"
  }
}
JSONEOF
)

if [ -f "$CLAUDE_SETTINGS" ]; then
    # settings.json existiert — nodered-Eintrag einfügen oder aktualisieren
    $PYTHON - <<PYEOF
import json, sys

path = "$CLAUDE_SETTINGS"
with open(path) as f:
    cfg = json.load(f)

cfg.setdefault("mcpServers", {})["nodered"] = {
    "command": "$PYTHON",
    "args": ["$INSTALL_DIR/nodered_mcp_server.py"],
    "env": {"NODE_RED_URL": "${NODE_RED_URL:-http://localhost:1880}"}
}

with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
print("ok")
PYEOF
    echo "✓ MCP-Eintrag in bestehende $CLAUDE_SETTINGS eingetragen"
else
    # Neue settings.json anlegen
    cat > "$CLAUDE_SETTINGS" <<JSONEOF
{
  "mcpServers": {
    "nodered": {
      "command": "$PYTHON",
      "args": ["$INSTALL_DIR/nodered_mcp_server.py"],
      "env": {
        "NODE_RED_URL": "${NODE_RED_URL:-http://localhost:1880}"
      }
    }
  }
}
JSONEOF
    echo "✓ Claude Code Konfiguration erstellt: $CLAUDE_SETTINGS"
fi

echo ""
echo "=== Installation abgeschlossen ==="
echo ""
echo "Starte Claude Code (Web Terminal) neu, damit der MCP-Server geladen wird."
echo ""
echo "Claude Code hat danach Zugriff auf diese Tools:"
echo "  list_flows       — Alle Node-RED Flows auflisten"
echo "  get_flow         — Einzelnen Flow anzeigen"
echo "  get_all_flows    — Gesamte Konfiguration abrufen"
echo "  search_flows     — In Flows suchen (Name, Code, Topic ...)"
echo "  update_flow      — Einen Flow ändern und deployen"
echo "  deploy_all_flows — Alle Flows deployen"
echo "  export_flows     — Flows als JSON exportieren"
echo "  import_flows     — Neue Flows importieren"
echo "  get_node         — Einzelnen Node per ID abrufen"
