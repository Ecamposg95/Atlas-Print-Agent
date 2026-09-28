"""Herramientas de empaquetado: versión y rutas del binario."""
from pathlib import Path

import construir
import version_agente


def test_lee_la_version_de_main():
    assert version_agente.leer_version() == "3.1.0"


def test_lee_la_version_de_cualquier_archivo(tmp_path):
    f = tmp_path / "main.py"
    f.write_text('x = 1\nVERSION = "9.8.7"\n', encoding="utf-8")
    assert version_agente.leer_version(f) == "9.8.7"


def test_tag_coincide():
    assert version_agente.tag_coincide("v3.1.0", "3.1.0")
    assert not version_agente.tag_coincide("v3.1.1", "3.1.0")
    assert not version_agente.tag_coincide("3.1.0", "3.1.0")


def test_cli_verificar_tag(capsys):
    assert version_agente.main(["--verificar-tag", "v3.1.0"]) == 0
    assert version_agente.main(["--verificar-tag", "v9.9.9"]) == 1
    assert "no coincide" in capsys.readouterr().err


def test_rutas_del_binario_por_sistema():
    d = construir.DIST
    assert construir.binario("Linux") == d / "atlas-print-agent" / "atlas-print-agent"
    assert construir.binario("Windows") == d / "atlas-print-agent" / "atlas-print-agent.exe"
    assert construir.binario("Darwin") == (
        d / "Atlas Print Agent.app" / "Contents" / "MacOS" / "Atlas Print Agent"
    )


def test_argumentos_de_pyinstaller():
    args = construir.argumentos("Windows")
    assert "--onedir" in args and "--onefile" not in args
    assert "--windowed" in args
    assert args[-1].endswith("lanzador.py")
    for modulo in ("main", "agent_state", "generate_cert"):
        assert modulo in args
    assert "--windowed" not in construir.argumentos("Linux")
    assert "--osx-bundle-identifier" in construir.argumentos("Darwin")
