#!/bin/bash
# Envuelve dist/agent/atlas-print-agent/ en dist/atlas-print-agent_<versión>_amd64.deb.
# Uso, desde la raíz y después de installers/agent/construir.py:
#   bash installers/agent/linux/build_deb.sh
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
AQUI="$RAIZ/installers/agent/linux"
VERSION="$(python3 "$RAIZ/installers/agent/version_agente.py")"
ORIGEN="$RAIZ/dist/agent/atlas-print-agent"
[ -f "$ORIGEN/atlas-print-agent" ] || { echo "Falta $ORIGEN: corre antes installers/agent/construir.py" >&2; exit 1; }

# El árbol se arma en un disco de Linux: en /mnt/c (NTFS) todo aparece con permisos
# 777 y dpkg-deb rechaza el directorio DEBIAN.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ARBOL="$TMP/atlas-print-agent"
mkdir -p "$ARBOL/DEBIAN" "$ARBOL/usr/lib" "$ARBOL/usr/bin" \
         "$ARBOL/usr/lib/systemd/system" "$ARBOL/usr/share/applications"
cp -r "$ORIGEN" "$ARBOL/usr/lib/atlas-print-agent"
chmod -R u=rwX,go=rX "$ARBOL/usr/lib/atlas-print-agent"
chmod 755 "$ARBOL/usr/lib/atlas-print-agent/atlas-print-agent"
ln -s /usr/lib/atlas-print-agent/atlas-print-agent "$ARBOL/usr/bin/atlas-print-agent"
install -m 644 "$AQUI/atlas-print-agent.service" "$ARBOL/usr/lib/systemd/system/"
install -m 644 "$AQUI/atlas-print-agent.desktop" "$ARBOL/usr/share/applications/"
sed "s/__VERSION__/$VERSION/" "$AQUI/control" > "$ARBOL/DEBIAN/control"
install -m 755 "$AQUI/prerm" "$AQUI/postrm" "$ARBOL/DEBIAN/"
sed "s/__VERSION__/$VERSION/" "$AQUI/postinst" > "$ARBOL/DEBIAN/postinst"
chmod 755 "$ARBOL/DEBIAN/postinst"
chmod 755 "$ARBOL/DEBIAN"

mkdir -p "$RAIZ/dist"
SALIDA="$RAIZ/dist/atlas-print-agent_${VERSION}_amd64.deb"
dpkg-deb --root-owner-group --build "$ARBOL" "$SALIDA"
echo "$SALIDA"
