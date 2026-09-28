#!/bin/bash
# Envuelve dist/agent/Atlas Print Agent.app en dist/atlas-print-agent-<versión>-<arq>.pkg.
# Corre en macOS (runner de CI o la Mac del dueño), después de construir.py.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
AQUI="$RAIZ/installers/agent/mac"
VERSION="$(python3 "$RAIZ/installers/agent/version_agente.py")"
ARQ="$(uname -m)"   # arm64 o x86_64
APP="$RAIZ/dist/agent/Atlas Print Agent.app"
[ -d "$APP" ] || { echo "Falta $APP: corre antes installers/agent/construir.py" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
RAIZ_PKG="$TMP/raiz"
SOPORTE="$RAIZ_PKG/Library/Application Support/AtlasPrintAgent"
mkdir -p "$RAIZ_PKG/Applications" "$SOPORTE" "$TMP/scripts"
cp -R "$APP" "$RAIZ_PKG/Applications/"
install -m 755 "$AQUI/desinstalar.sh" "$SOPORTE/"
install -m 644 "$AQUI/com.atlasone.print-agent.plist" "$SOPORTE/"
install -m 755 "$AQUI/scripts/preinstall" "$AQUI/scripts/postinstall" "$TMP/scripts/"

# pkgbuild marca los .app como reubicables por omisión: si alguien movió el .app,
# el instalador actualizaría esa copia y el LaunchAgent apuntaría a la vieja.
pkgbuild --analyze --root "$RAIZ_PKG" "$TMP/componentes.plist"
plutil -replace 0.BundleIsRelocatable -bool NO "$TMP/componentes.plist"

pkgbuild --root "$RAIZ_PKG" --component-plist "$TMP/componentes.plist" \
         --scripts "$TMP/scripts" --identifier com.atlasone.print-agent \
         --version "$VERSION" --install-location / "$TMP/componente.pkg"
mkdir -p "$RAIZ/dist"
SALIDA="$RAIZ/dist/atlas-print-agent-$VERSION-$ARQ.pkg"
productbuild --package "$TMP/componente.pkg" "$SALIDA"
echo "$SALIDA"
