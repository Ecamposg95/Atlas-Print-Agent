"""Rutas de importación y aislamiento para los tests del agente empaquetado.

El agente vive en legacy/print_agent/core como módulos sueltos (main, agent_state,
generate_cert, lanzador), y las herramientas de empaquetado en installers/agent.
Ninguno es un paquete, así que se agregan al sys.path.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CORE = RAIZ / "legacy" / "print_agent" / "core"
INSTALADORES = RAIZ / "installers" / "agent"

for _ruta in (CORE, INSTALADORES):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))


@pytest.fixture(autouse=True)
def _estado_aislado(tmp_path, monkeypatch):
    """Ningún test lee ni escribe el directorio de estado real de esta máquina."""
    monkeypatch.setenv("ATLAS_AGENT_STATE_DIR", str(tmp_path / "estado"))
    for clave in ("ATLAS_AGENT_PORT", "ATLAS_AGENT_ORIGINS", "ATLAS_AGENT_HOST", "STATE_DIRECTORY"):
        monkeypatch.delenv(clave, raising=False)
