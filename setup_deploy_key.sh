#!/bin/bash
# Schritt 1: SSH Deploy Key erzeugen für GitHub (privates Repo)
# Direkt im HAOS Web Terminal ausführen — BEVOR das Repo geclont wird.

set -e

KEY_FILE="$HOME/.ssh/hassio_nodered_mcp"
GITHUB_REPO="micdede/hassioClaudeCodeMcp"

echo "=== Deploy Key Setup für $GITHUB_REPO ==="
echo ""

# SSH-Verzeichnis sicherstellen
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

# Key generieren (falls noch nicht vorhanden)
if [ -f "$KEY_FILE" ]; then
    echo "! Key existiert bereits: $KEY_FILE"
    echo "  Wird wiederverwendet."
else
    ssh-keygen -t ed25519 -C "hassio-nodered-mcp" -f "$KEY_FILE" -N ""
    echo "✓ SSH-Key erstellt: $KEY_FILE"
fi

# SSH-Config eintragen (damit der Key automatisch für GitHub genutzt wird)
SSH_CONFIG="$HOME/.ssh/config"
if grep -q "hassio_nodered_mcp" "$SSH_CONFIG" 2>/dev/null; then
    echo "✓ SSH-Config bereits vorhanden"
else
    cat >> "$SSH_CONFIG" <<EOF

Host github.com
  IdentityFile $KEY_FILE
  StrictHostKeyChecking no
EOF
    chmod 600 "$SSH_CONFIG"
    echo "✓ SSH-Config aktualisiert"
fi

echo ""
echo "============================================================"
echo "  JETZT AUF GITHUB DEN DEPLOY KEY EINTRAGEN:"
echo "============================================================"
echo ""
echo "1. Öffne im Browser:"
echo "   https://github.com/$GITHUB_REPO/settings/keys/new"
echo ""
echo "2. Füge diesen Public Key ein (alles in einer Zeile kopieren):"
echo ""
cat "$KEY_FILE.pub"
echo ""
echo "3. Titel: z.B. 'HA MiniPC Wohnzimmer' oder 'Papa MiniPC'"
echo "   Schreibzugriff: NICHT nötig (Read-only reicht)"
echo ""
echo "4. Auf 'Add key' klicken"
echo ""
echo "============================================================"
echo ""

# Warten bis der User bestätigt
read -r -p "Deploy Key auf GitHub eingetragen? Dann Enter drücken zum Testen... "

# Verbindung testen
echo ""
echo "Teste GitHub-Verbindung..."
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "✓ GitHub-Verbindung funktioniert!"
else
    echo "⚠ Verbindung noch nicht erfolgreich. Prüfe ob der Key auf GitHub eingetragen ist."
    echo "  Du kannst den Test wiederholen mit: ssh -T git@github.com"
    exit 1
fi

echo ""
echo "=== Jetzt das Repo clonen und installieren ==="
echo ""
echo "  git clone git@github.com:$GITHUB_REPO.git /root/nodered-mcp-setup"
echo "  bash /root/nodered-mcp-setup/install.sh"
