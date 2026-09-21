from decimal import Decimal

from atlas_labels.model import Product, parse_price, parse_stock


def test_parse_price_entero():
    assert parse_price("1800") == (Decimal("1800"), "")


def test_parse_price_con_formato_moneda():
    assert parse_price("$1,800.50") == (Decimal("1800.50"), "")


def test_parse_price_texto_no_numerico_se_conserva():
    assert parse_price("Consultar") == (None, "Consultar")


def test_parse_price_vacio():
    assert parse_price("") == (None, "")


def test_parse_stock_acepta_flotante_y_vacio():
    assert parse_stock("9") == 9
    assert parse_stock("9.0") == 9
    assert parse_stock("") == 0
    assert parse_stock("abc") == 0


def test_price_display_formatea_moneda():
    p = Product(sku="A", name="B", price=Decimal("1800"))
    assert p.price_display == "$1,800.00"


def test_price_display_usa_texto_si_no_hay_numero():
    p = Product(sku="A", name="B", price_text="Consultar")
    assert p.price_display == "Consultar"


def test_price_display_vacio():
    assert Product(sku="A", name="B").price_display == ""
