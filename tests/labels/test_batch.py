from atlas_labels.batch import plan
from atlas_labels.model import Product


def _p(sku, barcode="2017000000013", stock=2):
    return Product(sku=sku, name=f"Producto {sku}", barcode=barcode, stock=stock)


def test_plan_usa_stock_por_defecto():
    b = plan([_p("A", stock=3), _p("B", stock=1)])
    assert b.items == [(_p("A", stock=3), 3), (_p("B", stock=1), 1)]
    assert b.total_labels == 4
    assert b.skipped == []


def test_plan_override_de_copias():
    b = plan([_p("A", stock=3), _p("B", stock=0)], copies=2)
    assert [c for _, c in b.items] == [2, 2]


def test_plan_omite_sin_existencia_y_sin_codigo():
    b = plan([_p("A", stock=0), _p("B", barcode=""), _p("C")])
    assert [p.sku for p, _ in b.items] == ["C"]
    assert b.skipped == [(_p("A", stock=0), "sin existencia"), (_p("B", barcode=""), "sin código")]


def test_plan_recoge_advertencias_de_barcode():
    b = plan([_p("A", barcode="A" * 25)])
    assert len(b.items) == 1
    assert b.warnings and b.warnings[0].startswith("A:")


def test_summary_en_espanol():
    text = plan([_p("A", stock=3), _p("B", stock=0)]).summary()
    assert "1 productos" in text
    assert "3 etiquetas" in text
    assert "B: sin existencia" in text
