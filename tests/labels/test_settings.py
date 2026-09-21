import json

from atlas_labels.settings import ENV_PRINTER, load_settings, resolve_printer, save_settings


def test_load_settings_sin_archivo_devuelve_vacio(tmp_path):
    assert load_settings(tmp_path / "no.json") == {}


def test_load_settings_archivo_corrupto_devuelve_vacio(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{no es json")
    assert load_settings(p) == {}


def test_save_y_load(tmp_path):
    p = tmp_path / "s.json"
    save_settings({"printer_name": "Zebra"}, p)
    assert json.loads(p.read_text(encoding="utf-8")) == {"printer_name": "Zebra"}
    assert load_settings(p) == {"printer_name": "Zebra"}


def test_resolve_printer_prioridad(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    save_settings({"printer_name": "Guardada"}, p)
    monkeypatch.delenv(ENV_PRINTER, raising=False)
    assert resolve_printer(None, p) == "Guardada"
    monkeypatch.setenv(ENV_PRINTER, "DeEntorno")
    assert resolve_printer(None, p) == "DeEntorno"
    assert resolve_printer("Explicita", p) == "Explicita"
    assert resolve_printer("  ", p) == "DeEntorno"


def test_resolve_printer_sin_nada(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_PRINTER, raising=False)
    assert resolve_printer(None, tmp_path / "no.json") is None
