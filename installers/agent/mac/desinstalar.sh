#!/bin/bash
# Desinstala el agente de impresión Atlas de esta Mac.
#   sudo "/Library/Application Support/AtlasPrintAgent/desinstalar.sh"            conserva certificado y agent.conf
#   sudo "/Library/Application Support/AtlasPrintAgent/desinstalar.sh" --purgar   también los borra
set -u
[ "$(id -u)" -eq 0 ] || { echo "Corre con sudo." >&2; exit 1; }
LABEL=com.atlasone.print-agent
USUARIO="$(stat -f %Su /dev/console)"
UIDC="$(id -u "$USUARIO")"
HOGAR="$(dscl . -read "/Users/$USUARIO" NFSHomeDirectory | awk '{print $2}')"
launchctl bootout "gui/$UIDC/$LABEL" 2>/dev/null
rm -f "$HOGAR/Library/LaunchAgents/$LABEL.plist" "$HOGAR/Desktop/Atlas Print Agent"
rm -rf "/Applications/Atlas Print Agent.app"
if [ "${1:-}" = "--purgar" ]; then
    rm -rf "$HOGAR/Library/Application Support/AtlasPrintAgent" "$HOGAR/Library/Logs/AtlasPrintAgent"
fi
pkgutil --forget com.atlasone.print-agent >/dev/null 2>&1
rm -rf "/Library/Application Support/AtlasPrintAgent"
echo "✓ Agente desinstalado."
