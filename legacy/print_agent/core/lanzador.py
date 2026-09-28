"""Punto de entrada del agente empaquetado.

Dos modos, según quién lo abre:

- Sin argumentos — el ícono del Escritorio, del menú o el .app. Si el agente ya
  responde, lo dice en un diálogo y sale: la cajera que le da doble clic por
  costumbre no debe ver un error de puerto ocupado. Si no responde, lo arranca
  aquí mismo y avisa cuando ya se puede imprimir.
- `--servicio` — lo que corren systemd, launchd y el Programador de tareas.
  Arranca sin mirar nada y sin diálogos; si falla, sale con error para que el
  supervisor lo reintente.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional, Sequence

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import agent_state  # noqa: E402

TITULO = "Agente de Impresión Atlas"
SERVICIO_AGENTE = "Atlas POS Print Agent"
MSG_YA_ACTIVO = (
    "El agente de impresión ya está activo.\n\n"
    "No necesitas abrir nada más: abre el navegador y vende normal."
)
MSG_INICIADO = (
    "El agente de impresión está activo.\n\n"
    "Ya puedes imprimir desde el punto de venta. Puedes cerrar este aviso."
)
MSG_NO_ARRANCO = (
    "El agente de impresión no pudo arrancar.\n\n"
    "Puede que otro programa esté usando el puerto de impresión.\n"
    "Reinicia la computadora; si sigue igual, llama a soporte y menciona este archivo:\n\n{log}"
)


def respuesta_es_agente(cuerpo: bytes) -> bool:
    """True si el cuerpo es el /health de este agente y no de otro programa."""
    try:
        datos = json.loads(cuerpo.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False
    return isinstance(datos, dict) and datos.get("service") == SERVICIO_AGENTE


def agente_activo(puerto: int, timeout: float = 2.0) -> bool:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # ProxyHandler({}): un proxy corporativo en el entorno no debe interceptar 127.0.0.1.
    abridor = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx)
    )
    for esquema in ("https", "http"):
        try:
            with abridor.open(f"{esquema}://127.0.0.1:{puerto}/health", timeout=timeout) as r:
                if respuesta_es_agente(r.read(4096)):
                    return True
        except Exception:
            continue
    return False


def _applescript(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"')


def comando_dialogo(
    sistema: str,
    titulo: str,
    mensaje: str,
    error: bool = False,
    hay: Callable[[str], Optional[str]] = shutil.which,
) -> Optional[list[str]]:
    """Comando externo que muestra el diálogo, o None si no hay con qué (Windows usa ctypes)."""
    if sistema == "Darwin":
        icono = "stop" if error else "note"
        guion = (
            f'display dialog "{_applescript(mensaje)}" with title "{_applescript(titulo)}" '
            f'buttons {{"Aceptar"}} default button 1 with icon {icono}'
        )
        return ["osascript", "-e", guion]
    if sistema == "Linux":
        if hay("zenity"):
            return ["zenity", "--error" if error else "--info", f"--title={titulo}", f"--text={mensaje}", "--no-wrap"]
        if hay("notify-send"):
            return ["notify-send", titulo, mensaje]
    return None


def mostrar_dialogo(titulo: str, mensaje: str, error: bool = False) -> None:
    sistema = platform.system()
    if sistema == "Windows":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, mensaje, titulo, 0x10 if error else 0x40)
            return
        except Exception:
            pass
    cmd = comando_dialogo(sistema, titulo, mensaje, error)
    if cmd:
        try:
            subprocess.run(cmd, timeout=600, check=False)
            return
        except Exception:
            pass
    print(f"{titulo}: {mensaje}")


def _avisar_cuando_responda(puerto: int, espera: float = 60.0) -> None:
    limite = time.monotonic() + espera
    while time.monotonic() < limite:
        if agente_activo(puerto, timeout=1.0):
            mostrar_dialogo(TITULO, MSG_INICIADO)
            return
        time.sleep(0.5)


def _silenciar_salidas_nulas() -> None:
    # Con --windowed (Windows y el .app de macOS) sys.stdout y sys.stderr son None,
    # y uvicorn llama isatty() sobre ellos al configurar su log: sin esto el agente
    # muere al arrancar sin dejar rastro.
    for nombre in ("stdout", "stderr"):
        if getattr(sys, nombre) is None:
            setattr(sys, nombre, open(os.devnull, "w", encoding="utf-8"))


def main(argv: Sequence[str]) -> int:
    _silenciar_salidas_nulas()
    servicio = "--servicio" in argv
    puerto = agent_state.port(agent_state.load_config(agent_state.state_dir()))

    if not servicio:
        if agente_activo(puerto):
            mostrar_dialogo(TITULO, MSG_YA_ACTIVO)
            return 0
        threading.Thread(target=_avisar_cuando_responda, args=(puerto,), daemon=True).start()

    import main as agente

    if servicio:
        agente.run()
        return 0
    try:
        agente.run()
    except (Exception, SystemExit) as e:
        if isinstance(e, SystemExit) and e.code in (0, None):
            return 0
        mostrar_dialogo(TITULO, MSG_NO_ARRANCO.format(log=agente._log_file), error=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
