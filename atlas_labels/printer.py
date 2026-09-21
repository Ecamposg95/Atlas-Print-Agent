"""Envío de bytes RAW a la impresora: win32print en Windows, lp -o raw en el resto."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"
_QUEUE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-. ()]{1,128}$")


class PrinterError(Exception):
    """Error legible al listar impresoras o imprimir."""


def safe_queue_name(name: str) -> str:
    name = (name or "").strip()
    if not _QUEUE_NAME_RE.match(name):
        raise PrinterError(f"Nombre de impresora inválido: {name!r}")
    return name


def list_printers() -> list[str]:
    return _list_windows() if IS_WINDOWS else _list_unix()


def send_raw(printer_name: str, data: bytes) -> None:
    name = safe_queue_name(printer_name)
    if IS_WINDOWS:
        _send_windows(name, data)
    else:
        _send_unix(name, data)


# --- Linux / macOS -----------------------------------------------------------

def _list_unix() -> list[str]:
    lpstat = shutil.which("lpstat")
    if not lpstat:
        return []
    result = subprocess.run([lpstat, "-a"], capture_output=True, timeout=5)
    names = []
    for line in result.stdout.decode(errors="replace").splitlines():
        parts = line.split()
        if parts:
            names.append(parts[0])
    return names


def _send_unix(name: str, data: bytes) -> None:
    lp = shutil.which("lp")
    if not lp:
        raise PrinterError("No se encontró el comando `lp`. Instala CUPS: sudo apt install cups-client")
    result = subprocess.run([lp, "-d", name, "-o", "raw"], input=data, capture_output=True, timeout=30)
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise PrinterError(f"lp falló para {name!r}: {detail}")


# --- Windows -----------------------------------------------------------------

def _win32print():
    try:
        import win32print
    except ImportError as exc:
        raise PrinterError("Falta pywin32. Ejecuta: pip install pywin32") from exc
    return win32print


def _list_windows() -> list[str]:
    w = _win32print()
    flags = w.PRINTER_ENUM_LOCAL | w.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in w.EnumPrinters(flags)]


def _send_windows(name: str, data: bytes) -> None:
    w = _win32print()
    try:
        handle = w.OpenPrinter(name)
    except Exception as exc:  # pywintypes.error
        raise PrinterError(f"No se pudo abrir la impresora {name!r}: {exc}") from exc
    try:
        w.StartDocPrinter(handle, 1, ("Atlas Labels", None, "RAW"))
        try:
            w.StartPagePrinter(handle)
            w.WritePrinter(handle, data)
            w.EndPagePrinter(handle)
        finally:
            w.EndDocPrinter(handle)
    except Exception as exc:
        raise PrinterError(f"Error al imprimir en {name!r}: {exc}") from exc
    finally:
        w.ClosePrinter(handle)
