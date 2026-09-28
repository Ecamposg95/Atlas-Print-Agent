"""Desde 3.1.0 main.py guarda log, certificado y agent.conf en un directorio de estado.

Aquí apunta a un temporal para que importar el agente no escriba en el home de
quien corre los tests ni lea un agent.conf real, que podría cambiar el resultado
de los tests de CORS. No cambia qué tests pasan: siguen 27 y 3 fallan a propósito.
"""
import pytest


@pytest.fixture(autouse=True)
def _estado_aislado(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_AGENT_STATE_DIR", str(tmp_path / "estado"))
