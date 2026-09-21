import subprocess

import pytest

from atlas_labels import printer
from atlas_labels.printer import PrinterError, list_printers, safe_queue_name, send_raw


@pytest.fixture(autouse=True)
def unix(monkeypatch):
    monkeypatch.setattr(printer, "IS_WINDOWS", False)


def test_safe_queue_name_acepta_nombres_validos():
    assert safe_queue_name(" ZDesigner GX420t (EPL) ") == "ZDesigner GX420t (EPL)"


@pytest.mark.parametrize("bad", ["", "a;b", "cola|x", "../x", "x" * 129])
def test_safe_queue_name_rechaza(bad):
    with pytest.raises(PrinterError):
        safe_queue_name(bad)


def test_send_raw_unix_invoca_lp_raw(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(printer.shutil, "which", lambda c: "/usr/bin/lp")
    monkeypatch.setattr(printer.subprocess, "run", fake_run)
    send_raw("Zebra", b"^XA^XZ")
    cmd, kw = calls[0]
    assert cmd == ["/usr/bin/lp", "-d", "Zebra", "-o", "raw"]
    assert kw["input"] == b"^XA^XZ"


def test_send_raw_unix_sin_lp(monkeypatch):
    monkeypatch.setattr(printer.shutil, "which", lambda c: None)
    with pytest.raises(PrinterError) as exc:
        send_raw("Zebra", b"x")
    assert "lp" in str(exc.value)


def test_send_raw_unix_lp_falla(monkeypatch):
    monkeypatch.setattr(printer.shutil, "which", lambda c: "/usr/bin/lp")
    monkeypatch.setattr(
        printer.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, b"", b"lp: The printer or class does not exist."),
    )
    with pytest.raises(PrinterError) as exc:
        send_raw("Zebra", b"x")
    assert "does not exist" in str(exc.value)


def test_send_raw_valida_nombre_antes_de_imprimir(monkeypatch):
    monkeypatch.setattr(printer.subprocess, "run", lambda *a, **k: pytest.fail("no debe llamar a lp"))
    with pytest.raises(PrinterError):
        send_raw("mala;cola", b"x")


def test_list_printers_unix_parsea_lpstat(monkeypatch):
    monkeypatch.setattr(printer.shutil, "which", lambda c: "/usr/bin/lpstat")
    out = b"Zebra accepting requests since ...\nPOS-80 accepting requests since ...\n"
    monkeypatch.setattr(printer.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, out, b""))
    assert list_printers() == ["Zebra", "POS-80"]


def test_list_printers_unix_sin_lpstat(monkeypatch):
    monkeypatch.setattr(printer.shutil, "which", lambda c: None)
    assert list_printers() == []
