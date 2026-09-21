import pytest

from atlas_labels import cli
from atlas_labels.printer import PrinterError
from tests.labels.conftest import ATLAS_HEADERS


@pytest.fixture
def catalog(make_xlsx):
    return make_xlsx({"Plantilla": [
        ATLAS_HEADERS,
        ["A", "Playera", None, "Nike", "2017000000013", 1800, 3, None, "M"],
        ["B", "Tenis", None, "Nike", "", 4500, 9, None, None],
        ["C", "Gorra", None, "Puma", "*1A43KE*", 500, 0, None, None],
    ]})


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "send_raw", lambda name, data: calls.append((name, data)))
    return calls


def test_dry_run_muestra_resumen_y_no_imprime(catalog, sent, capsys):
    code = cli.main(["imprimir", str(catalog), "--dry-run", "--impresora", "Zebra"])
    out = capsys.readouterr().out
    assert code == 0
    assert "1 productos, 3 etiquetas" in out
    assert "B: sin código" in out
    assert "C: sin existencia" in out
    assert "dry-run" in out
    assert sent == []


def test_imprimir_envia_lote_a_la_impresora(catalog, sent, capsys):
    code = cli.main(["imprimir", str(catalog), "--impresora", "Zebra", "--copias", "2"])
    assert code == 0
    name, data = sent[0]
    assert name == "Zebra"
    assert data.count(b"^XA") == 2  # A y C (B sigue sin código)
    assert b"^PQ2" in data
    assert "Enviadas 4 etiquetas a Zebra" in capsys.readouterr().out


def test_imprimir_filtra_por_sku(catalog, sent):
    cli.main(["imprimir", str(catalog), "--impresora", "Zebra", "--sku", "a"])
    assert sent[0][1].count(b"^XA") == 1


def test_imprimir_sin_nada_que_imprimir_sale_1(catalog, sent):
    assert cli.main(["imprimir", str(catalog), "--impresora", "Zebra", "--sku", "B"]) == 1
    assert sent == []


def test_imprimir_sin_impresora_sale_2(catalog, sent, monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(cli.ENV_PRINTER, raising=False)
    monkeypatch.setattr(cli, "resolve_printer", lambda explicit=None: None)
    assert cli.main(["imprimir", str(catalog)]) == 2
    assert "impresora" in capsys.readouterr().err.lower()


def test_imprimir_copias_invalidas_sale_2(catalog, sent):
    assert cli.main(["imprimir", str(catalog), "--impresora", "Z", "--copias", "0"]) == 2


def test_error_de_catalogo_sale_2(tmp_path, capsys):
    assert cli.main(["imprimir", str(tmp_path / "no.xlsx"), "--impresora", "Z"]) == 2
    assert "No existe" in capsys.readouterr().err


def test_error_de_impresora_sale_2(catalog, monkeypatch, capsys):
    def boom(name, data):
        raise PrinterError("lp falló")
    monkeypatch.setattr(cli, "send_raw", boom)
    assert cli.main(["imprimir", str(catalog), "--impresora", "Z"]) == 2
    assert "lp falló" in capsys.readouterr().err


def test_previsualizar_imprime_zpl(catalog, capsys):
    assert cli.main(["previsualizar", str(catalog), "--sku", "A"]) == 0
    out = capsys.readouterr().out
    assert "^XA" in out and "^PQ3" in out


def test_previsualizar_sku_inexistente_sale_1(catalog):
    assert cli.main(["previsualizar", str(catalog), "--sku", "ZZZ"]) == 1


def test_impresoras_lista(monkeypatch, capsys):
    monkeypatch.setattr(cli, "list_printers", lambda: ["Zebra", "POS-80"])
    assert cli.main(["impresoras"]) == 0
    assert capsys.readouterr().out == "Zebra\nPOS-80\n"


def test_prueba_envia_etiqueta_fija(sent, capsys):
    assert cli.main(["prueba", "--impresora", "Zebra"]) == 0
    assert b"ATLAS TECH" in sent[0][1]
    assert "modo EPL" in capsys.readouterr().out
