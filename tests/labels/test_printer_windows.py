"""Camino de impresión en Windows, con un win32print falso inyectado en sys.modules."""

from __future__ import annotations

import sys

import pytest

from atlas_labels import printer as printer_mod
from atlas_labels.printer import PrinterError, list_printers, send_raw


class FakeWin32Print:
    PRINTER_ENUM_LOCAL = 2
    PRINTER_ENUM_CONNECTIONS = 4

    def __init__(self):
        self.calls: list[tuple] = []
        self.printers = [(0, "", "Zebra", ""), (0, "", "POS-80", "")]
        self.fail_at: str | None = None
        self.error: Exception | None = None

    def _record(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_at == name:
            raise self.error

    def EnumPrinters(self, flags):
        self._record("EnumPrinters", flags)
        return self.printers

    def OpenPrinter(self, name):
        self._record("OpenPrinter", name)
        return "handle"

    def StartDocPrinter(self, handle, level, doc_info):
        self._record("StartDocPrinter", handle, level, doc_info)

    def StartPagePrinter(self, handle):
        self._record("StartPagePrinter", handle)

    def WritePrinter(self, handle, data):
        self._record("WritePrinter", handle, data)

    def EndPagePrinter(self, handle):
        self._record("EndPagePrinter", handle)

    def EndDocPrinter(self, handle):
        self._record("EndDocPrinter", handle)

    def ClosePrinter(self, handle):
        self._record("ClosePrinter", handle)


@pytest.fixture
def fake_win32print(monkeypatch):
    fake = FakeWin32Print()
    monkeypatch.setitem(sys.modules, "win32print", fake)
    monkeypatch.setattr(printer_mod, "IS_WINDOWS", True)
    return fake


def test_list_printers_windows(fake_win32print):
    assert list_printers() == ["Zebra", "POS-80"]


def test_send_raw_windows_orden_de_llamadas(fake_win32print):
    send_raw("Zebra", b"^XA^XZ")
    names = [c[0] for c in fake_win32print.calls]
    assert names == [
        "OpenPrinter",
        "StartDocPrinter",
        "StartPagePrinter",
        "WritePrinter",
        "EndPagePrinter",
        "EndDocPrinter",
        "ClosePrinter",
    ]
    start_doc = next(c for c in fake_win32print.calls if c[0] == "StartDocPrinter")
    assert start_doc[1:] == ("handle", 1, ("Atlas Labels", None, "RAW"))
    write = next(c for c in fake_win32print.calls if c[0] == "WritePrinter")
    assert write[2] == b"^XA^XZ"


def test_send_raw_windows_error_al_escribir_cierra_la_impresora(fake_win32print):
    fake_win32print.fail_at = "WritePrinter"
    fake_win32print.error = RuntimeError("spooler")
    with pytest.raises(PrinterError, match="spooler"):
        send_raw("Zebra", b"^XA^XZ")
    names = [c[0] for c in fake_win32print.calls]
    assert "ClosePrinter" in names
    assert names[-1] == "ClosePrinter"


def test_send_raw_windows_error_al_abrir_no_llama_a_nada_mas(fake_win32print):
    fake_win32print.fail_at = "OpenPrinter"
    fake_win32print.error = RuntimeError("no existe")
    with pytest.raises(PrinterError):
        send_raw("Zebra", b"^XA^XZ")
    names = [c[0] for c in fake_win32print.calls]
    assert names == ["OpenPrinter"]


def test_list_printers_sin_pywin32_da_printer_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "win32print", None)
    monkeypatch.setattr(printer_mod, "IS_WINDOWS", True)
    with pytest.raises(PrinterError, match="pywin32"):
        list_printers()
