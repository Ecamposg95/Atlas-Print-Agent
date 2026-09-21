"""F1a B-2/B-7/Important-2: valida el regex de nombres de cola del agente de
impresión (legacy/print_agent/core/main.py:_QUEUE_NAME_RE / _safe_queue_name).

Carga el módulo real por ruta de archivo (no es un paquete instalable) para
probar la función tal cual la usan los endpoints — no una reimplementación
que pueda desincronizarse del regex de producción.

Casos legítimos (deben aceptarse):
  - Nombre local CUPS/Windows: "POS-80", "Epson TM-T20 (copia)"
  - Bluetooth (PrinterSettings guarda "BT:<nombre>"): "BT:Impresora 58"
  - UNC de red de un solo segmento: "\\\\PC-CAJA\\POS-80"

Casos peligrosos (deben rechazarse) — cerrados tras la revisión de
seguridad que encontró que el regex ampliado en B-2/B-7 era demasiado
permisivo:
  - Letra de unidad local: "C:\\Windows\\x"
  - Traversal: "..\\..\\etc"
  - UNC multi-segmento a host arbitrario (SSRF/fuga NetNTLMv2 vía
    win32print.OpenPrinter conectándose por SMB): "\\\\evil.example.com\\share\\extra\\segmentos"
  - Colon suelto fuera del prefijo BT:: "a:b:c"
  - Metacaracteres de shell: ; | & $ ` comillas salto de línea < > /
  - Salto de línea FINAL (residual encontrado en la 2a review): en Python
    `$` matchea antes de un '\n' de cierre sin consumirlo, así que
    "POS-80\n" pasaba `_QUEUE_NAME_RE.match(...)` pese a que el docstring
    afirma rechazar saltos de línea. Fix: `_safe_queue_name` usa
    `fullmatch` (exige consumir la cadena completa) en vez de `match`.
"""
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException

_MAIN_PATH = (
    Path(__file__).resolve().parent.parent
    / "print_agent" / "core" / "main.py"
)
_spec = importlib.util.spec_from_file_location("print_agent_main", _MAIN_PATH)
print_agent_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(print_agent_main)

_QUEUE_NAME_RE = print_agent_main._QUEUE_NAME_RE
_safe_queue_name = print_agent_main._safe_queue_name


ACCEPTED = [
    "POS-80",
    "Epson TM-T20 (copia)",
    "BT:Impresora 58",
    "\\\\PC-CAJA\\POS-80",
]

REJECTED = [
    "C:\\Windows\\x",
    "..\\..\\etc",
    "\\\\evil.example.com\\share\\extra\\segmentos",
    "a:b:c",
    "foo;rm -rf /",
    "foo|bar",
    "foo&bar",
    "foo$(bar)",
    "foo`bar`",
    'foo"bar',
    "foo'bar",
    "foo\nbar",
    "foo>bar",
    "foo<bar",
    "foo/bar",
    # Salto de línea final — ver docstring del módulo arriba.
    "POS-80\n",
    "BT:x\n",
    "\\\\host\\POS-80\n",
]


@pytest.mark.parametrize("name", ACCEPTED)
def test_queue_name_accepts_legit_names(name):
    # fullmatch (no match): coincide exactamente con lo que usa
    # _safe_queue_name en producción — ver Important-2/residual-1.
    assert _QUEUE_NAME_RE.fullmatch(name), f"debería aceptar {name!r}"
    # No debe lanzar
    assert _safe_queue_name(name) == name


@pytest.mark.parametrize("name", REJECTED)
def test_queue_name_rejects_dangerous_names(name):
    assert not _QUEUE_NAME_RE.fullmatch(name), f"debería rechazar {name!r}"
    with pytest.raises(HTTPException) as exc_info:
        _safe_queue_name(name)
    assert exc_info.value.status_code == 400
