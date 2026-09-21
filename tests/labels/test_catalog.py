from decimal import Decimal

import pytest

from atlas_labels.catalog import (
    CatalogError,
    map_columns,
    normalize_header,
    read_catalog,
    select,
    sheet_names,
)
from atlas_labels.model import Product
from tests.labels.conftest import ATLAS_HEADERS


def test_normalize_header_quita_acentos_espacios_y_guiones():
    assert normalize_header("Código Barras") == "codigobarras"
    assert normalize_header("CODIGO_BARRAS") == "codigobarras"
    assert normalize_header(" Precio Base ") == "preciobase"
    assert normalize_header(None) == ""


def test_map_columns_export_atlas_one():
    m = map_columns(ATLAS_HEADERS)
    assert m == {"sku": 0, "name": 1, "brand": 3, "barcode": 4, "price": 5, "stock": 6, "color": 7, "size": 8}


def test_map_columns_csv_prototipo_prefiere_nombre_venta_y_precio_texto():
    headers = ["SKU", "CODIGO_BARRAS", "MARCA", "PRODUCTO", "NOMBRE_VENTA", "TALLA", "COLOR", "PRECIO", "PRECIO_TEXTO", "CANTIDAD"]
    m = map_columns(headers)
    assert m["name"] == 4
    assert m["price"] == 8
    assert m["stock"] == 9
    assert m["barcode"] == 1


def test_map_columns_faltan_obligatorias_lista_encabezados():
    with pytest.raises(CatalogError) as exc:
        map_columns(["Marca", "Precio"])
    assert "sku" in str(exc.value)
    assert "Marca" in str(exc.value)


def test_read_xlsx_atlas_one(make_xlsx):
    path = make_xlsx({"Plantilla": [
        ATLAS_HEADERS,
        ["CH-PLAY-EP-CH", "Playera estampada", None, "Chrome Hearts", "2017000000013", 1800, 100, None, "Ch"],
        ["AE5U3BMI61N430", "Tenis", None, "Louis Vuitton", "*1A43KE*", 4500.5, 9, "Negro", None],
    ]})
    products = read_catalog(path)
    assert len(products) == 2
    p = products[0]
    assert p == Product(sku="CH-PLAY-EP-CH", name="Playera estampada", brand="Chrome Hearts",
                        barcode="2017000000013", price=Decimal("1800"), stock=100, color="", size="Ch")
    assert products[1].price == Decimal("4500.5")
    assert products[1].barcode == "*1A43KE*"
    assert products[1].color == "Negro"


def test_read_xlsx_codigo_numerico_no_pierde_digitos(make_xlsx):
    path = make_xlsx({"Plantilla": [ATLAS_HEADERS, ["A", "B", None, None, 2017000000013, None, None, None, None]]})
    assert read_catalog(path)[0].barcode == "2017000000013"


def test_read_xlsx_codigo_flotante_entero_se_lee_sin_decimal(make_xlsx):
    path = make_xlsx({"Plantilla": [ATLAS_HEADERS, ["A", "B", None, None, 2017000000013.0, None, None, None, None]]})
    assert read_catalog(path)[0].barcode == "2017000000013"


def test_read_xlsx_salta_filas_vacias_y_conserva_precio_texto(make_xlsx):
    path = make_xlsx({"Plantilla": [
        ATLAS_HEADERS,
        [None, None, None, None, None, None, None, None, None],
        ["A", "B", None, None, None, "Consultar", None, None, None],
    ]})
    products = read_catalog(path)
    assert len(products) == 1
    assert products[0].price is None
    assert products[0].price_text == "Consultar"


def test_read_xlsx_hoja_por_nombre_y_sheet_names(make_xlsx):
    path = make_xlsx({
        "Listas": [["x"], [1]],
        "Plantilla": [ATLAS_HEADERS, ["A", "B", None, None, None, None, None, None, None]],
    })
    assert sheet_names(path) == ["Listas", "Plantilla"]
    assert read_catalog(path, "Plantilla")[0].sku == "A"
    with pytest.raises(CatalogError):
        read_catalog(path, "NoExiste")


def test_read_csv_prototipo(tmp_path):
    path = tmp_path / "eleven.csv"
    path.write_text(
        "﻿SKU,CODIGO_BARRAS,MARCA,PRODUCTO,NOMBRE_VENTA,TALLA,COLOR,PRECIO,PRECIO_TEXTO,CANTIDAD\n"
        "MM-BLUS,0012345,Miu Miu,Blusa,Blusa manga corta,M,Rojo,1500,\"$1,500.00\",3\n",
        encoding="utf-8",
    )
    p = read_catalog(path)[0]
    assert p.barcode == "0012345"
    assert p.name == "Blusa manga corta"
    assert p.price == Decimal("1500.00")
    assert p.stock == 3


def test_read_catalog_errores_de_archivo(tmp_path):
    with pytest.raises(CatalogError):
        read_catalog(tmp_path / "no_existe.xlsx")
    bad = tmp_path / "x.txt"
    bad.write_text("hola")
    with pytest.raises(CatalogError):
        read_catalog(bad)


def _products():
    return [
        Product(sku="A1", name="Blusa", brand="Miu Miu", barcode="111"),
        Product(sku="B2", name="Tenis", brand="Nike", barcode="222"),
        Product(sku="C3", name="Gorra", brand="Nike", barcode="333"),
    ]


def test_select_por_sku_ignora_mayusculas_y_espacios():
    assert [p.sku for p in select(_products(), skus=[" a1", "C3 "])] == ["A1", "C3"]


def test_select_por_texto_en_sku_codigo_marca_o_nombre():
    assert [p.sku for p in select(_products(), search="nike")] == ["B2", "C3"]
    assert [p.sku for p in select(_products(), search="222")] == ["B2"]
    assert [p.sku for p in select(_products(), search="blu")] == ["A1"]


def test_select_sin_filtros_devuelve_todo():
    assert len(select(_products())) == 3
