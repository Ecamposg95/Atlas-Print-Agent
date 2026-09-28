"""Prueba de humo del binario recién construido: arranca, responde /health, muere.

Corre con un directorio de estado temporal y en el puerto 9199, para no chocar con
un agente real de la máquina. Un binario que no pasa esto no llega a la release.
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import construir
import version_agente

PUERTO = 9199
ESPERA = 60.0


def _health() -> dict | None:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))
    try:
        with abridor.open(f"https://127.0.0.1:{PUERTO}/health", timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return None


def main() -> int:
    # La consola de Windows en CI es cp1252: sin esto, imprimir "✓" tumba la prueba.
    for flujo in (sys.stdout, sys.stderr):
        flujo.reconfigure(encoding="utf-8", errors="replace")
    binario = construir.binario()
    esperada = version_agente.leer_version()
    estado = Path(tempfile.mkdtemp(prefix="atlas-humo-"))
    env = {**os.environ, "ATLAS_AGENT_STATE_DIR": str(estado), "ATLAS_AGENT_PORT": str(PUERTO)}
    print(f"Arrancando {binario} (estado en {estado})")
    proc = subprocess.Popen([str(binario), "--servicio"], env=env)
    try:
        limite = time.monotonic() + ESPERA
        datos = None
        while time.monotonic() < limite and proc.poll() is None:
            datos = _health()
            if datos:
                break
            time.sleep(1)
        fallas = []
        if not datos:
            fallas.append(f"/health no respondió en {ESPERA:.0f} s (código de salida: {proc.poll()})")
        elif datos.get("version") != esperada:
            fallas.append(f"/health reporta versión {datos.get('version')!r}, se esperaba {esperada!r}")
        if not (estado / "certs" / "cert.pem").is_file():
            fallas.append("no se generó certs/cert.pem en el directorio de estado")
        if not (estado / "agent.log").is_file():
            fallas.append("no se escribió agent.log en el directorio de estado")
        if fallas:
            for f in fallas:
                print(f"✗ {f}", file=sys.stderr)
            log = estado / "agent.log"
            if log.is_file():
                print(log.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            return 1
        print(f"✓ {binario.name} responde: {datos}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
