"""main.py guarda log y certificado en el directorio de estado y lee agent.conf.

Se importa por ruta con nombre único, igual que legacy/tests: el módulo lee su
configuración al importarse.
"""
import hashlib
import importlib.util
import itertools
import os
import sys
from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parents[2] / "legacy" / "print_agent" / "core" / "main.py"
_contador = itertools.count()


def _cargar():
    nombre = f"_main_estado_{next(_contador)}"
    spec = importlib.util.spec_from_file_location(nombre, MAIN)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def estado(tmp_path):
    return Path(os.environ["ATLAS_AGENT_STATE_DIR"])


def test_version(estado):
    assert _cargar().VERSION == "3.1.0"


def test_log_y_certificado_viven_en_el_estado(estado):
    mod = _cargar()
    assert mod.STATE_DIR == estado
    assert mod.CERT_DIR == estado / "certs"
    assert mod._log_file == estado / "agent.log"
    assert mod._log_file.exists()


def test_origenes_desde_agent_conf(estado):
    estado.mkdir(parents=True)
    (estado / "agent.conf").write_text("ATLAS_AGENT_ORIGINS=https://pos.micliente.com\n", encoding="utf-8")
    assert "https://pos.micliente.com" in _cargar()._CORS_ORIGINS


def test_el_entorno_gana_a_agent_conf(estado, monkeypatch):
    estado.mkdir(parents=True)
    (estado / "agent.conf").write_text("ATLAS_AGENT_ORIGINS=https://archivo.mx\n", encoding="utf-8")
    monkeypatch.setenv("ATLAS_AGENT_ORIGINS", "https://entorno.mx")
    origenes = _cargar()._CORS_ORIGINS
    assert "https://entorno.mx" in origenes
    assert "https://archivo.mx" not in origenes


def test_ensure_certs_genera_en_el_estado_y_no_lo_cambia_despues(estado):
    mod = _cargar()
    key, cert = mod._ensure_certs()
    assert cert == estado / "certs" / "cert.pem"
    assert key == estado / "certs" / "key.pem"
    huella = hashlib.sha256(cert.read_bytes()).hexdigest()
    # Otro arranque (un reinicio de la PC, una reinstalación) con el mismo estado.
    key2, cert2 = _cargar()._ensure_certs()
    assert hashlib.sha256(cert2.read_bytes()).hexdigest() == huella


def test_diagnostics_reporta_el_certificado_del_estado(estado):
    mod = _cargar()
    mod._ensure_certs()
    assert mod._cert_info()["exists"] is True


def test_estado_no_escribible_no_impide_importar(tmp_path, monkeypatch):
    # Un archivo donde debería haber un directorio: mkdir falla con OSError.
    tapon = tmp_path / "tapon"
    tapon.write_text("x")
    monkeypatch.setenv("ATLAS_AGENT_STATE_DIR", str(tapon / "estado"))
    mod = _cargar()
    assert mod._ensure_certs() == (None, None)


def test_run_existe():
    assert callable(_cargar().run)
