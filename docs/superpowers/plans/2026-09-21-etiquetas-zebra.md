# Etiquetas Zebra desde Excel (`atlas_labels`): plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un paquete `atlas_labels/` que lee un catálogo `.xlsx`/`.csv`, genera ZPL de 51 x 25 mm y lo manda RAW a una Zebra GX420t, con CLI y app Tkinter sobre la misma lógica.

**Architecture:** Módulos pequeños con una responsabilidad cada uno: `model` (datos), `catalog` (lectura y mapeo de columnas), `barcode` (detección EAN-13/Code 128), `zpl` (layout), `batch` (plan de copias y omitidos), `printer` (envío RAW), `settings` (impresora recordada), `cli` y `gui` como interfaces. Ningún módulo de lógica importa Tkinter ni toca la impresora; todo se prueba con dobles.

**Tech Stack:** Python 3.10+, `openpyxl`, `pywin32` solo en Windows, `lp` de CUPS en Linux/macOS, Tkinter de la biblioteca estándar, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-21-etiquetas-zebra-design.md`

## Global Constraints

- Python 3.10 o superior. Sin pandas. Dependencias: `openpyxl`; `pywin32>=306` solo con `sys_platform == 'win32'`.
- Etiqueta 51 x 25 mm a 203 dpi: `^PW408`, `^LL200`, `^CI28`, texto enviado en UTF-8.
- Toda salida al usuario (CLI, mensajes de error, diálogos) en español.
- Nombre de cola validado con `[A-Za-z0-9_\-. ()]`, igual que el agente.
- Las celdas se leen siempre como texto; el código de barras nunca pierde ceros iniciales.
- Comando de tests: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q` desde la raíz del repo.
- Mensajes de commit en español, con la línea `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` al final.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `atlas_labels/__init__.py` | Versión del paquete. |
| `atlas_labels/model.py` | `Product`, `parse_price`, `parse_stock`. |
| `atlas_labels/barcode.py` | `BarcodeSpec`, `detect`, checksum EAN-13, ancho Code 128. |
| `atlas_labels/catalog.py` | `read_catalog`, `sheet_names`, `map_columns`, `select`, `CatalogError`. |
| `atlas_labels/zpl.py` | `build_label`, `build_batch`, `build_test_label`, `fit_text`. |
| `atlas_labels/batch.py` | `BatchPlan`, `plan`. |
| `atlas_labels/printer.py` | `PrinterError`, `safe_queue_name`, `list_printers`, `send_raw`. |
| `atlas_labels/settings.py` | `load_settings`, `save_settings`, `resolve_printer`. |
| `atlas_labels/cli.py`, `atlas_labels/__main__.py` | Subcomandos `imprimir`, `previsualizar`, `impresoras`, `prueba`. |
| `atlas_labels/gui.py` | App Tkinter. |
| `tests/labels/conftest.py` | Fixture que genera xlsx de prueba. |
| `tests/labels/test_*.py` | Un archivo por módulo de lógica. |
| `requirements-labels.txt` | Dependencias del paquete. |
| `docs/reference/eleven-label-printer-task-pack.md` | TASK_PACK del prototipo, conservado. |

---

### Task 1: Esqueleto del paquete y modelo `Product`

**Files:**
- Create: `atlas_labels/__init__.py`
- Create: `atlas_labels/model.py`
- Create: `requirements-labels.txt`
- Create: `tests/__init__.py` y `tests/labels/__init__.py` (vacíos, para que pytest importe `tests.labels.conftest`)
- Test: `tests/labels/test_model.py`

**Interfaces:**
- Produces: `Product(sku, name, brand="", barcode="", price=None, price_text="", stock=0, color="", size="")` dataclass congelada con propiedad `price_display -> str`; `parse_price(text: str) -> tuple[Decimal | None, str]`; `parse_stock(text: str) -> int`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/labels/test_model.py
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
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_model.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels'`

- [ ] **Step 3: Crear el paquete y el modelo**

```python
# atlas_labels/__init__.py
"""Impresión de etiquetas 51 x 25 mm en Zebra desde un catálogo .xlsx o .csv."""

__version__ = "0.1.0"
```

```python
# atlas_labels/model.py
"""Modelo de producto y conversión de precio y existencia."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    brand: str = ""
    barcode: str = ""
    price: Decimal | None = None
    price_text: str = ""  # texto original cuando el precio no es numérico
    stock: int = 0
    color: str = ""
    size: str = ""

    @property
    def price_display(self) -> str:
        if self.price is not None:
            return f"${self.price:,.2f}"
        return self.price_text


def parse_price(text: str) -> tuple[Decimal | None, str]:
    """Devuelve (Decimal, "") si el texto es un número, o (None, texto) si no."""
    raw = (text or "").strip()
    if not raw:
        return None, ""
    cleaned = raw.replace("$", "").replace(",", "").replace(" ", "")
    try:
        return Decimal(cleaned), ""
    except InvalidOperation:
        return None, raw


def parse_stock(text: str) -> int:
    try:
        return int(float((text or "").strip()))
    except ValueError:
        return 0
```

```
# requirements-labels.txt
openpyxl>=3.1
pywin32>=306; sys_platform == 'win32'
```

Crear `tests/__init__.py` y `tests/labels/__init__.py` vacíos.

- [ ] **Step 4: Correr los tests**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_model.py -q`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/__init__.py atlas_labels/model.py requirements-labels.txt tests/__init__.py tests/labels/__init__.py tests/labels/test_model.py
git commit -m "atlas_labels: esqueleto del paquete y modelo Product

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Detección de código de barras

**Files:**
- Create: `atlas_labels/barcode.py`
- Test: `tests/labels/test_barcode.py`

**Interfaces:**
- Produces: `BarcodeSpec(kind: str, data: str, module_width: int, warning: str = "")` con `kind` en `{"EAN13", "CODE128"}` y propiedad `width_dots -> int`; `detect(text: str) -> BarcodeSpec | None`; `ean13_checksum_ok(digits: str) -> bool`; `code128_modules(data: str) -> int`; constantes `MAX_CODE128_CHARS = 20`, `MAX_BARCODE_DOTS = 380`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/labels/test_barcode.py
from atlas_labels.barcode import (
    MAX_CODE128_CHARS,
    code128_modules,
    detect,
    ean13_checksum_ok,
)


def test_checksum_ean13_valido():
    assert ean13_checksum_ok("2017000000013")


def test_checksum_ean13_invalido():
    assert not ean13_checksum_ok("2017000000014")
    assert not ean13_checksum_ok("12345")
    assert not ean13_checksum_ok("20170000000A3")


def test_detect_ean13():
    spec = detect("2017000000013")
    assert spec.kind == "EAN13"
    assert spec.data == "2017000000013"
    assert spec.module_width == 2
    assert spec.width_dots == 190


def test_detect_ean13_con_checksum_malo_va_a_code128():
    assert detect("2017000000014").kind == "CODE128"


def test_detect_quita_asteriscos_y_espacios():
    spec = detect(" *1A43KE* ")
    assert spec.kind == "CODE128"
    assert spec.data == "1A43KE"
    assert spec.module_width == 2
    assert spec.warning == ""


def test_detect_descarta_caracteres_no_ascii_y_de_control_zpl():
    assert detect("AB^C~Dñ").data == "ABCD"


def test_detect_vacio_o_solo_basura_devuelve_none():
    assert detect("") is None
    assert detect("   ") is None
    assert detect("**") is None
    assert detect(None) is None


def test_detect_recorta_a_20_y_advierte():
    spec = detect("A" * 25)
    assert len(spec.data) == MAX_CODE128_CHARS
    assert "recortado" in spec.warning


def test_code128_modules_pares_de_digitos_cuentan_uno():
    # 13 dígitos: 6 pares + 1 suelto = 7 símbolos → 11*7 + 35 = 112
    assert code128_modules("2017000000014") == 112
    # "1A43KE" → símbolos 1, A, 43, K, E = 5 → 11*5 + 35 = 90
    assert code128_modules("1A43KE") == 90


def test_detect_codigo_largo_baja_a_modulo_1_y_advierte():
    spec = detect("ABCDEFGHIJKLMNOPQRST")  # 20 símbolos → 255 módulos → 510 dots
    assert spec.module_width == 1
    assert "angosto" in spec.warning
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_barcode.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels.barcode'`

- [ ] **Step 3: Implementar**

```python
# atlas_labels/barcode.py
"""Detección del tipo de código de barras: EAN-13 o Code 128."""

from __future__ import annotations

from dataclasses import dataclass

MAX_CODE128_CHARS = 20
MAX_BARCODE_DOTS = 380  # ancho útil de la etiqueta para el código
EAN13_MODULES = 95


@dataclass(frozen=True)
class BarcodeSpec:
    kind: str  # "EAN13" | "CODE128"
    data: str
    module_width: int  # 1 o 2 dots por módulo
    warning: str = ""

    @property
    def width_dots(self) -> int:
        modules = EAN13_MODULES if self.kind == "EAN13" else code128_modules(self.data)
        return modules * self.module_width


def ean13_checksum_ok(digits: str) -> bool:
    if len(digits) != 13 or not digits.isdigit():
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == int(digits[12])


def code128_modules(data: str) -> int:
    """Módulos estimados: pares de dígitos cuentan como un símbolo (subconjunto C)."""
    symbols = 0
    i = 0
    while i < len(data):
        if data[i].isdigit() and i + 1 < len(data) and data[i + 1].isdigit():
            i += 2
        else:
            i += 1
        symbols += 1
    return 11 * symbols + 35


def detect(text: str | None) -> BarcodeSpec | None:
    cleaned = (text or "").strip().strip("*").strip()
    if not cleaned:
        return None
    if ean13_checksum_ok(cleaned):
        return BarcodeSpec("EAN13", cleaned, 2)

    data = "".join(ch for ch in cleaned if 33 <= ord(ch) <= 126 and ch not in "^~")
    if not data:
        return None

    warnings: list[str] = []
    if len(data) > MAX_CODE128_CHARS:
        data = data[:MAX_CODE128_CHARS]
        warnings.append(f"código recortado a {MAX_CODE128_CHARS} caracteres")

    module_width = 2 if code128_modules(data) * 2 <= MAX_BARCODE_DOTS else 1
    if module_width == 1:
        warnings.append("código largo, impreso angosto; puede costar trabajo escanear")
    return BarcodeSpec("CODE128", data, module_width, "; ".join(warnings))
```

- [ ] **Step 4: Correr los tests**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_barcode.py -q`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/barcode.py tests/labels/test_barcode.py
git commit -m "atlas_labels: detección de código de barras EAN-13 y Code 128

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Lectura del catálogo y mapeo de columnas

**Files:**
- Create: `atlas_labels/catalog.py`
- Create: `tests/labels/conftest.py`
- Test: `tests/labels/test_catalog.py`

**Interfaces:**
- Consumes: `Product`, `parse_price`, `parse_stock` de `atlas_labels.model`.
- Produces: `CatalogError(Exception)`; `normalize_header(h) -> str`; `map_columns(headers: list) -> dict[str, int]`; `rows_to_products(headers, rows) -> list[Product]`; `sheet_names(path) -> list[str]`; `read_catalog(path, sheet: str | None = None) -> list[Product]`; `select(products, skus: list[str] | None = None, search: str | None = None) -> list[Product]`.

- [ ] **Step 1: Fixture para generar xlsx**

```python
# tests/labels/conftest.py
import openpyxl
import pytest


@pytest.fixture
def make_xlsx(tmp_path):
    """Crea un .xlsx con una o varias hojas: make_xlsx({"Hoja": [headers, row, ...]})."""

    def _make(sheets: dict, name: str = "catalogo.xlsx"):
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for title, rows in sheets.items():
            ws = wb.create_sheet(title)
            for row in rows:
                ws.append(row)
        path = tmp_path / name
        wb.save(path)
        return path

    return _make


ATLAS_HEADERS = ["SKU", "Nombre", "Descripcion", "Marca", "Codigo Barras", "Precio Base", "Stock", "Color", "Talla"]
```

- [ ] **Step 2: Escribir los tests que fallan**

```python
# tests/labels/test_catalog.py
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
```

- [ ] **Step 3: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_catalog.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels.catalog'`

- [ ] **Step 4: Implementar**

```python
# atlas_labels/catalog.py
"""Lectura de catálogos .xlsx y .csv con mapeo de columnas por alias."""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path
from typing import Iterable

from .model import Product, parse_price, parse_stock


class CatalogError(Exception):
    """Error legible al leer o interpretar el catálogo."""


# Primer alias presente gana. Encabezados normalizados con normalize_header.
ALIASES: dict[str, tuple[str, ...]] = {
    "sku": ("sku",),
    "name": ("nombreventa", "nombre", "producto"),
    "brand": ("marca",),
    "barcode": ("codigobarras", "barcode", "codigo"),
    "price": ("preciotexto", "preciobase", "precio"),
    "stock": ("stock", "cantidad", "existencia"),
    "color": ("color",),
    "size": ("talla",),
}
REQUIRED = ("sku", "name")


def normalize_header(header) -> str:
    text = unicodedata.normalize("NFKD", str(header or "")).encode("ascii", "ignore").decode()
    return "".join(ch for ch in text.lower() if ch.isalnum())


def map_columns(headers: list) -> dict[str, int]:
    positions: dict[str, int] = {}
    for idx, header in enumerate(headers):
        key = normalize_header(header)
        if key and key not in positions:
            positions[key] = idx
    mapping: dict[str, int] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            if alias in positions:
                mapping[field] = positions[alias]
                break
    missing = [f for f in REQUIRED if f not in mapping]
    if missing:
        found = ", ".join(str(h) for h in headers if h)
        raise CatalogError(
            f"Faltan columnas obligatorias: {', '.join(missing)}. Encabezados encontrados: {found}"
        )
    return mapping


def _cell(row, idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    value = row[idx]
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def rows_to_products(headers: list, rows: Iterable) -> list[Product]:
    mapping = map_columns(headers)
    products: list[Product] = []
    for row in rows:
        get = lambda field: _cell(row, mapping.get(field))  # noqa: E731
        sku, name = get("sku"), get("name")
        if not sku and not name:
            continue
        price, price_text = parse_price(get("price"))
        products.append(Product(
            sku=sku, name=name, brand=get("brand"), barcode=get("barcode"),
            price=price, price_text=price_text, stock=parse_stock(get("stock")),
            color=get("color"), size=get("size"),
        ))
    return products


def sheet_names(path) -> list[str]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def _read_xlsx(path: Path, sheet: str | None) -> list[Product]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet is not None:
            if sheet not in wb.sheetnames:
                raise CatalogError(f"La hoja {sheet!r} no existe. Hojas: {', '.join(wb.sheetnames)}")
            ws = wb[sheet]
        else:
            ws = wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        headers = next(rows, None)
        if headers is None:
            raise CatalogError(f"La hoja {ws.title!r} está vacía")
        return rows_to_products(list(headers), rows)
    finally:
        wb.close()


def _read_csv(path: Path) -> list[Product]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        headers = next(reader, None)
        if headers is None:
            raise CatalogError(f"El archivo {path.name} está vacío")
        return rows_to_products(headers, reader)


def read_catalog(path, sheet: str | None = None) -> list[Product]:
    p = Path(path)
    if not p.exists():
        raise CatalogError(f"No existe el archivo: {p}")
    suffix = p.suffix.lower()
    if suffix == ".csv":
        return _read_csv(p)
    if suffix in (".xlsx", ".xlsm"):
        return _read_xlsx(p, sheet)
    raise CatalogError(f"Formato no soportado: {p.suffix}. Usa .xlsx o .csv")


def select(products: list[Product], skus: list[str] | None = None, search: str | None = None) -> list[Product]:
    wanted = {s.strip().upper() for s in skus if s.strip()} if skus else None
    term = (search or "").strip().lower()
    out: list[Product] = []
    for p in products:
        if wanted is not None and p.sku.upper() not in wanted:
            continue
        if term and term not in " ".join((p.sku, p.barcode, p.brand, p.name)).lower():
            continue
        out.append(p)
    return out
```

- [ ] **Step 5: Correr los tests**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_catalog.py -q`
Expected: 14 passed

- [ ] **Step 6: Commit**

```bash
git add atlas_labels/catalog.py tests/labels/conftest.py tests/labels/test_catalog.py
git commit -m "atlas_labels: lectura de catálogo xlsx/csv con mapeo de columnas

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Generación de ZPL

**Files:**
- Create: `atlas_labels/zpl.py`
- Test: `tests/labels/test_zpl.py`

**Interfaces:**
- Consumes: `Product` de `model`; `detect`, `BarcodeSpec` de `barcode`.
- Produces: `zpl_safe(text) -> str`; `text_width(text: str, height: int) -> int`; `fit_text(text, height: int, max_width: int) -> str`; `build_label(product: Product, copies: int = 1, spec: BarcodeSpec | None = None) -> str` (lanza `ValueError` si no hay código); `build_batch(items: list[tuple[Product, int]]) -> str`; `build_test_label() -> str`; constantes `LABEL_WIDTH = 408`, `LABEL_HEIGHT = 200`, `CHAR_WIDTH_FACTOR = 0.55`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/labels/test_zpl.py
from decimal import Decimal

import pytest

from atlas_labels.model import Product
from atlas_labels.zpl import (
    LABEL_HEIGHT,
    LABEL_WIDTH,
    build_batch,
    build_label,
    build_test_label,
    fit_text,
    text_width,
    zpl_safe,
)


def _p(**kw):
    base = dict(sku="CH-PLAY-EP-CH", name="Playera estampada premium", brand="Chrome Hearts",
                barcode="2017000000013", price=Decimal("1800"), stock=3, color="Negro", size="M")
    base.update(kw)
    return Product(**base)


def test_zpl_safe_reemplaza_caracteres_de_control():
    assert zpl_safe("a^b~c") == "a b c"
    assert zpl_safe(None) == ""


def test_text_width_estima_por_altura():
    assert text_width("abcd", 20) == 44  # 4 * 20 * 0.55


def test_fit_text_recorta_por_ancho_sin_elipsis_unicode():
    out = fit_text("Nombre extremadamente largo para la etiqueta", 18, 200)
    assert "…" not in out
    assert out.endswith("..")
    assert text_width(out, 18) <= 200


def test_fit_text_deja_intacto_lo_que_cabe():
    assert fit_text("Corto", 18, 384) == "Corto"


def test_build_label_estructura_basica():
    zpl = build_label(_p(), copies=5)
    assert zpl.startswith("^XA")
    assert zpl.rstrip().endswith("^XZ")
    for cmd in (f"^PW{LABEL_WIDTH}", f"^LL{LABEL_HEIGHT}", "^CI28", "^PQ5"):
        assert cmd in zpl


def test_build_label_ean13_usa_be_y_centra():
    zpl = build_label(_p())
    assert "^BEN,48,Y,N^FD2017000000013^FS" in zpl
    assert "^FO109,76^BY2,2,48" in zpl  # (408 - 190) // 2 = 109


def test_build_label_code128_usa_bc_con_texto_limpio():
    zpl = build_label(_p(barcode="*1A43KE*"))
    assert "^BCN,48,Y,N,N^FD1A43KE^FS" in zpl


def test_build_label_precio_alineado_a_la_derecha_con_fb():
    zpl = build_label(_p())
    assert "^FO246,162^A0N,22,22^FB150,1,0,R^FD$1,800.00^FS" in zpl


def test_build_label_sin_precio_omite_campo():
    zpl = build_label(_p(price=None, price_text=""))
    assert "^FB150" not in zpl


def test_build_label_variante_talla_color():
    assert "^FDM / Negro^FS" in build_label(_p())
    assert "^FDNegro^FS" in build_label(_p(size=""))
    assert ",56^" not in build_label(_p(size="", color=""))


def test_build_label_escapa_y_recorta_textos():
    zpl = build_label(_p(name="X" * 80, brand="Ma^rca"))
    assert "Ma rca" in zpl
    assert "X" * 80 not in zpl
    assert "…" not in zpl


def test_build_label_copias_minimo_uno():
    assert "^PQ1" in build_label(_p(), copies=0)


def test_build_label_sin_codigo_lanza_valueerror():
    with pytest.raises(ValueError):
        build_label(_p(barcode=""))


def test_build_batch_concatena_bloques():
    out = build_batch([(_p(), 2), (_p(sku="OTRO"), 1)])
    assert out.count("^XA") == 2
    assert out.count("^XZ") == 2
    assert "^PQ2" in out and "^PQ1" in out
    assert out.endswith("\n")


def test_build_test_label_es_valido():
    zpl = build_test_label()
    assert "^XA" in zpl and "^BEN" in zpl and "ATLAS TECH" in zpl
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_zpl.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels.zpl'`

- [ ] **Step 3: Implementar**

```python
# atlas_labels/zpl.py
"""Layout ZPL de la etiqueta 51 x 25 mm a 203 dpi."""

from __future__ import annotations

from decimal import Decimal

from .barcode import BarcodeSpec, detect
from .model import Product

DPI = 203
LABEL_WIDTH = 408
LABEL_HEIGHT = 200
MARGIN = 12
TEXT_WIDTH = LABEL_WIDTH - 2 * MARGIN  # 384
SKU_WIDTH = 240
PRICE_WIDTH = 150
BARCODE_HEIGHT = 48
# Ancho promedio de un carácter en fuente escalable A0, como fracción de su altura.
CHAR_WIDTH_FACTOR = 0.55


def zpl_safe(value) -> str:
    return str(value or "").replace("^", " ").replace("~", " ").strip()


def text_width(text: str, height: int) -> int:
    return int(len(text) * height * CHAR_WIDTH_FACTOR)


def fit_text(value, height: int, max_width: int) -> str:
    text = zpl_safe(value)
    if text_width(text, height) <= max_width:
        return text
    while text and text_width(text + "..", height) > max_width:
        text = text[:-1]
    return text.rstrip() + ".."


def _barcode_lines(spec: BarcodeSpec) -> list[str]:
    x = max(MARGIN, (LABEL_WIDTH - spec.width_dots) // 2)
    lines = [f"^FO{x},76^BY{spec.module_width},2,{BARCODE_HEIGHT}"]
    if spec.kind == "EAN13":
        lines.append(f"^BEN,{BARCODE_HEIGHT},Y,N^FD{spec.data}^FS")
    else:
        lines.append(f"^BCN,{BARCODE_HEIGHT},Y,N,N^FD{spec.data}^FS")
    return lines


def build_label(product: Product, copies: int = 1, spec: BarcodeSpec | None = None) -> str:
    spec = spec if spec is not None else detect(product.barcode)
    if spec is None:
        raise ValueError(f"{product.sku or product.name}: sin código de barras")

    size = fit_text(product.size, 15, 120)
    color = fit_text(product.color, 15, 200)
    variant = " / ".join(x for x in (size, color) if x)

    lines = [
        "^XA",
        f"^PW{LABEL_WIDTH}",
        f"^LL{LABEL_HEIGHT}",
        "^LH0,0",
        "^CI28",
        f"^PQ{max(1, int(copies))}",
        f"^FO{MARGIN},8^A0N,22,22^FD{fit_text(product.brand, 22, TEXT_WIDTH)}^FS",
        f"^FO{MARGIN},34^A0N,18,18^FD{fit_text(product.name, 18, TEXT_WIDTH)}^FS",
    ]
    if variant:
        lines.append(f"^FO{MARGIN},56^A0N,15,15^FD{variant}^FS")
    lines.extend(_barcode_lines(spec))
    lines.append(f"^FO{MARGIN},168^A0N,14,14^FD{fit_text(product.sku, 14, SKU_WIDTH)}^FS")
    price = zpl_safe(product.price_display)
    if price:
        x = LABEL_WIDTH - MARGIN - PRICE_WIDTH
        lines.append(f"^FO{x},162^A0N,22,22^FB{PRICE_WIDTH},1,0,R^FD{price}^FS")
    lines.append("^XZ")
    return "\n".join(lines)


def build_batch(items: list[tuple[Product, int]]) -> str:
    return "".join(build_label(product, copies) + "\n" for product, copies in items)


def build_test_label() -> str:
    product = Product(
        sku="PRUEBA-51X25", name="Etiqueta de prueba 51 x 25 mm", brand="ATLAS TECH",
        barcode="2017000000013", price=Decimal("1800"), size="M", color="Negro",
    )
    return build_label(product, 1)
```

- [ ] **Step 4: Correr los tests**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_zpl.py -q`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/zpl.py tests/labels/test_zpl.py
git commit -m "atlas_labels: generación de ZPL 51x25 mm con recorte por ancho y precio alineado

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Plan de lote (copias y omitidos)

**Files:**
- Create: `atlas_labels/batch.py`
- Test: `tests/labels/test_batch.py`

**Interfaces:**
- Consumes: `Product`; `detect` de `barcode`.
- Produces: `BatchPlan(items: list[tuple[Product, int]], skipped: list[tuple[Product, str]], warnings: list[str])` con `total_labels -> int` y `summary() -> str`; `plan(products: list[Product], copies: int | None = None) -> BatchPlan`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/labels/test_batch.py
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
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_batch.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels.batch'`

- [ ] **Step 3: Implementar**

```python
# atlas_labels/batch.py
"""Decide cuántas copias imprimir de cada producto y cuáles se omiten."""

from __future__ import annotations

from dataclasses import dataclass, field

from .barcode import detect
from .model import Product


@dataclass
class BatchPlan:
    items: list[tuple[Product, int]] = field(default_factory=list)
    skipped: list[tuple[Product, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_labels(self) -> int:
        return sum(copies for _, copies in self.items)

    def summary(self) -> str:
        lines = [f"{len(self.items)} productos, {self.total_labels} etiquetas"]
        if self.skipped:
            lines.append(f"Omitidos ({len(self.skipped)}):")
            lines.extend(f"  {p.sku or p.name}: {reason}" for p, reason in self.skipped)
        if self.warnings:
            lines.append("Advertencias:")
            lines.extend(f"  {w}" for w in self.warnings)
        return "\n".join(lines)


def plan(products: list[Product], copies: int | None = None) -> BatchPlan:
    result = BatchPlan()
    for product in products:
        n = copies if copies is not None else product.stock
        if n <= 0:
            result.skipped.append((product, "sin existencia"))
            continue
        spec = detect(product.barcode)
        if spec is None:
            result.skipped.append((product, "sin código"))
            continue
        if spec.warning:
            result.warnings.append(f"{product.sku or product.name}: {spec.warning}")
        result.items.append((product, n))
    return result
```

- [ ] **Step 4: Correr los tests**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_batch.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/batch.py tests/labels/test_batch.py
git commit -m "atlas_labels: plan de lote con copias por existencia y omitidos

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Envío RAW a la impresora

**Files:**
- Create: `atlas_labels/printer.py`
- Test: `tests/labels/test_printer.py`

**Interfaces:**
- Produces: `PrinterError(Exception)`; `safe_queue_name(name: str) -> str`; `list_printers() -> list[str]`; `send_raw(printer_name: str, data: bytes) -> None`; bandera de módulo `IS_WINDOWS: bool`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/labels/test_printer.py
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
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_printer.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels.printer'`

- [ ] **Step 3: Implementar**

```python
# atlas_labels/printer.py
"""Envío de bytes RAW a la impresora: win32print en Windows, lp -o raw en el resto."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"
_QUEUE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-. ()]{1,128}$")


class PrinterError(Exception):
    """Error legible al listar impresoras o imprimir."""


def safe_queue_name(name: str) -> str:
    name = (name or "").strip()
    if not _QUEUE_NAME_RE.match(name):
        raise PrinterError(f"Nombre de impresora inválido: {name!r}")
    return name


def list_printers() -> list[str]:
    return _list_windows() if IS_WINDOWS else _list_unix()


def send_raw(printer_name: str, data: bytes) -> None:
    name = safe_queue_name(printer_name)
    if IS_WINDOWS:
        _send_windows(name, data)
    else:
        _send_unix(name, data)


# --- Linux / macOS -----------------------------------------------------------

def _list_unix() -> list[str]:
    lpstat = shutil.which("lpstat")
    if not lpstat:
        return []
    result = subprocess.run([lpstat, "-a"], capture_output=True, timeout=5)
    names = []
    for line in result.stdout.decode(errors="replace").splitlines():
        parts = line.split()
        if parts:
            names.append(parts[0])
    return names


def _send_unix(name: str, data: bytes) -> None:
    lp = shutil.which("lp")
    if not lp:
        raise PrinterError("No se encontró el comando `lp`. Instala CUPS: sudo apt install cups-client")
    result = subprocess.run([lp, "-d", name, "-o", "raw"], input=data, capture_output=True, timeout=30)
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise PrinterError(f"lp falló para {name!r}: {detail}")


# --- Windows -----------------------------------------------------------------

def _win32print():
    try:
        import win32print
    except ImportError as exc:
        raise PrinterError("Falta pywin32. Ejecuta: pip install pywin32") from exc
    return win32print


def _list_windows() -> list[str]:
    w = _win32print()
    flags = w.PRINTER_ENUM_LOCAL | w.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in w.EnumPrinters(flags)]


def _send_windows(name: str, data: bytes) -> None:
    w = _win32print()
    try:
        handle = w.OpenPrinter(name)
    except Exception as exc:  # pywintypes.error
        raise PrinterError(f"No se pudo abrir la impresora {name!r}: {exc}") from exc
    try:
        w.StartDocPrinter(handle, 1, ("Atlas Labels", None, "RAW"))
        try:
            w.StartPagePrinter(handle)
            w.WritePrinter(handle, data)
            w.EndPagePrinter(handle)
        finally:
            w.EndDocPrinter(handle)
    except Exception as exc:
        raise PrinterError(f"Error al imprimir en {name!r}: {exc}") from exc
    finally:
        w.ClosePrinter(handle)
```

- [ ] **Step 4: Correr los tests**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_printer.py -q`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/printer.py tests/labels/test_printer.py
git commit -m "atlas_labels: envío RAW por win32print y lp -o raw

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Impresora recordada (`settings.py`)

**Files:**
- Create: `atlas_labels/settings.py`
- Test: `tests/labels/test_settings.py`

**Interfaces:**
- Produces: `ENV_PRINTER = "ATLAS_LABELS_PRINTER"`; `SETTINGS_PATH: Path` (`~/.atlas_labels.json`); `load_settings(path=None) -> dict`; `save_settings(data: dict, path=None) -> None`; `resolve_printer(explicit: str | None = None, path=None) -> str | None`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/labels/test_settings.py
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
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_settings.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels.settings'`

- [ ] **Step 3: Implementar**

```python
# atlas_labels/settings.py
"""Preferencias del usuario: impresora recordada."""

from __future__ import annotations

import json
import os
from pathlib import Path

ENV_PRINTER = "ATLAS_LABELS_PRINTER"
SETTINGS_PATH = Path.home() / ".atlas_labels.json"


def load_settings(path=None) -> dict:
    p = Path(path) if path else SETTINGS_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict, path=None) -> None:
    p = Path(path) if path else SETTINGS_PATH
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_printer(explicit: str | None = None, path=None) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.environ.get(ENV_PRINTER, "").strip()
    if env:
        return env
    saved = str(load_settings(path).get("printer_name", "")).strip()
    return saved or None
```

- [ ] **Step 4: Correr los tests**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_settings.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/settings.py tests/labels/test_settings.py
git commit -m "atlas_labels: impresora recordada en ~/.atlas_labels.json

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: CLI

**Files:**
- Create: `atlas_labels/cli.py`
- Create: `atlas_labels/__main__.py`
- Test: `tests/labels/test_cli.py`

**Interfaces:**
- Consumes: `read_catalog`, `select`, `CatalogError` (catalog); `plan` (batch); `build_label`, `build_batch`, `build_test_label` (zpl); `send_raw`, `list_printers`, `PrinterError` (printer); `resolve_printer`, `ENV_PRINTER` (settings).
- Produces: `main(argv: list[str] | None = None) -> int`. Códigos de salida: 0 ok, 1 nada que imprimir o sin resultados, 2 error de uso, catálogo o impresora.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/labels/test_cli.py
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
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_cli.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels.cli'`

- [ ] **Step 3: Implementar**

```python
# atlas_labels/cli.py
"""Línea de comandos: python -m atlas_labels <subcomando>."""

from __future__ import annotations

import argparse
import sys

from .batch import plan
from .catalog import CatalogError, read_catalog, select
from .printer import PrinterError, list_printers, send_raw
from .settings import ENV_PRINTER, resolve_printer
from .zpl import build_batch, build_label, build_test_label


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="atlas_labels",
        description="Imprime etiquetas de 51 x 25 mm en una Zebra desde un catálogo .xlsx o .csv.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    imp = sub.add_parser("imprimir", help="Imprime las etiquetas de un catálogo")
    imp.add_argument("archivo", help="Catálogo .xlsx o .csv")
    imp.add_argument("--impresora", help=f"Nombre de la cola (o variable {ENV_PRINTER})")
    imp.add_argument("--copias", type=int, help="Copias fijas por producto (por defecto, la existencia)")
    imp.add_argument("--sku", help="Solo estos SKU, separados por coma")
    imp.add_argument("--buscar", help="Solo productos cuyo SKU, código, marca o nombre contenga este texto")
    imp.add_argument("--hoja", help="Hoja del libro (por defecto, la primera)")
    imp.add_argument("--dry-run", action="store_true", help="Muestra el resumen sin imprimir")

    pre = sub.add_parser("previsualizar", help="Muestra el ZPL de uno o más SKU")
    pre.add_argument("archivo")
    pre.add_argument("--sku", required=True, help="SKU separados por coma")
    pre.add_argument("--copias", type=int)
    pre.add_argument("--hoja")

    sub.add_parser("impresoras", help="Lista las impresoras del sistema")

    pr = sub.add_parser("prueba", help="Imprime una etiqueta fija para verificar la impresora")
    pr.add_argument("--impresora")
    return p


def _load(args) -> list:
    products = read_catalog(args.archivo, args.hoja)
    skus = [s for s in args.sku.split(",") if s.strip()] if getattr(args, "sku", None) else None
    return select(products, skus=skus, search=getattr(args, "buscar", None))


def _printer_or_fail(explicit: str | None) -> str:
    name = resolve_printer(explicit)
    if not name:
        raise PrinterError(
            f"No hay impresora configurada. Usa --impresora, la variable {ENV_PRINTER} "
            "o elige una en la app para recordarla."
        )
    return name


def cmd_imprimir(args) -> int:
    if args.copias is not None and args.copias < 1:
        print("--copias debe ser 1 o más", file=sys.stderr)
        return 2
    batch = plan(_load(args), args.copias)
    print(batch.summary())
    if not batch.items:
        print("Nada que imprimir.")
        return 1
    if args.dry_run:
        print("(dry-run: no se envió nada a la impresora)")
        return 0
    printer = _printer_or_fail(args.impresora)
    send_raw(printer, build_batch(batch.items).encode("utf-8"))
    print(f"Enviadas {batch.total_labels} etiquetas a {printer}.")
    return 0


def cmd_previsualizar(args) -> int:
    products = _load(args)
    if not products:
        print(f"No se encontró ningún producto con SKU {args.sku}", file=sys.stderr)
        return 1
    for product in products:
        copies = args.copias if args.copias else max(1, product.stock)
        try:
            print(build_label(product, copies))
        except ValueError as exc:
            print(f"No imprimible: {exc}", file=sys.stderr)
    return 0


def cmd_impresoras(args) -> int:
    names = list_printers()
    if not names:
        print("No se encontraron impresoras.")
        return 1
    print("\n".join(names))
    return 0


def cmd_prueba(args) -> int:
    printer = _printer_or_fail(args.impresora)
    send_raw(printer, build_test_label().encode("utf-8"))
    print(
        f"Etiqueta de prueba enviada a {printer}. "
        "Si no sale nada, la impresora está en modo EPL: cámbiala a ZPL desde Zebra Setup Utilities."
    )
    return 0


_HANDLERS = {
    "imprimir": cmd_imprimir,
    "previsualizar": cmd_previsualizar,
    "impresoras": cmd_impresoras,
    "prueba": cmd_prueba,
}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _HANDLERS[args.cmd](args)
    except (CatalogError, PrinterError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
```

```python
# atlas_labels/__main__.py
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Correr los tests**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_cli.py -q`
Expected: 12 passed

- [ ] **Step 5: Prueba manual de humo con el Excel real**

Run: `uv run --no-project --with openpyxl python -m atlas_labels imprimir "/mnt/c/Users/ecamp/Downloads/catalogo_2026-09-21.xlsx" --dry-run --impresora Zebra`
Expected: resumen con productos, etiquetas totales, y omitidos por "sin existencia" o "sin código"; sale con 0.

Run: `uv run --no-project --with openpyxl python -m atlas_labels previsualizar "/mnt/c/Users/ecamp/Downloads/catalogo_2026-09-21.xlsx" --sku CH-PLAY-EP-CH`
Expected: bloque `^XA…^XZ` con `^BEN` y `^PQ100`.

- [ ] **Step 6: Commit**

```bash
git add atlas_labels/cli.py atlas_labels/__main__.py tests/labels/test_cli.py
git commit -m "atlas_labels: CLI imprimir, previsualizar, impresoras y prueba

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: App Tkinter

**Files:**
- Create: `atlas_labels/gui.py`

**Interfaces:**
- Consumes: `read_catalog`, `select`, `sheet_names`, `CatalogError`; `plan`; `build_label`, `build_batch`; `list_printers`, `send_raw`, `PrinterError`; `load_settings`, `save_settings`, `resolve_printer`.
- Produces: `main()` que abre la ventana. Se lanza con `python -m atlas_labels.gui`.

Sin tests automáticos (ver spec §10); la verificación es manual en el Step 2.

- [ ] **Step 1: Implementar**

```python
# atlas_labels/gui.py
"""Interfaz de escritorio: abre un catálogo, elige productos e imprime en lote."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .batch import plan
from .catalog import CatalogError, read_catalog, select, sheet_names
from .printer import PrinterError, list_printers, send_raw
from .settings import load_settings, resolve_printer, save_settings
from .zpl import build_batch, build_label

COLUMNS = ("SKU", "Código", "Marca", "Nombre", "Talla", "Color", "Precio", "Stock")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Atlas Labels")
        self.geometry("1200x700")
        self.products = []
        self.visible = []
        self._build_ui()

    # --- construcción -------------------------------------------------------

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Button(top, text="Abrir catálogo", command=self.open_catalog).pack(side="left")

        ttk.Label(top, text=" Impresora:").pack(side="left")
        self.printer_var = tk.StringVar(value=resolve_printer() or "")
        try:
            printers = list_printers()
        except PrinterError:
            printers = []
        ttk.Combobox(top, width=34, textvariable=self.printer_var, values=printers).pack(side="left", padx=4)

        ttk.Label(top, text=" Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        ttk.Entry(top, width=28, textvariable=self.search_var).pack(side="left", padx=4)
        ttk.Button(top, text="Imprimir seleccionados", command=self.print_selected).pack(side="right")

        self.tree = ttk.Treeview(self, columns=COLUMNS, show="headings", selectmode="extended")
        for col in COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110, anchor="w")
        self.tree.column("Nombre", width=260)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.update_preview())

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        self.copies_mode = tk.StringVar(value="stock")
        ttk.Radiobutton(bottom, text="Copias = existencia", variable=self.copies_mode, value="stock").pack(side="left")
        ttk.Radiobutton(bottom, text="Copias fijas:", variable=self.copies_mode, value="fixed").pack(side="left", padx=(10, 2))
        self.copies_var = tk.StringVar(value="1")
        ttk.Spinbox(bottom, from_=1, to=999, width=6, textvariable=self.copies_var).pack(side="left")
        ttk.Label(bottom, text="  Vista previa ZPL:").pack(side="left", padx=(20, 4))
        self.preview = tk.Text(bottom, height=8, width=70)
        self.preview.pack(side="left", fill="x", expand=True)

        self.status = tk.StringVar(value="Abre un catálogo .xlsx o .csv para empezar.")
        ttk.Label(self, textvariable=self.status, padding=(10, 0, 10, 6)).pack(fill="x")

    # --- acciones -----------------------------------------------------------

    def open_catalog(self):
        path = filedialog.askopenfilename(
            filetypes=[("Catálogo", "*.xlsx *.csv"), ("Excel", "*.xlsx"), ("CSV", "*.csv")]
        )
        if not path:
            return
        try:
            sheet = None
            if path.lower().endswith(".xlsx"):
                names = sheet_names(path)
                if len(names) > 1:
                    sheet = simpledialog.askstring(
                        "Hoja", f"Hojas disponibles: {', '.join(names)}\nEscribe el nombre de la hoja:",
                        initialvalue=names[0], parent=self,
                    )
                    if sheet is None:
                        return
            self.products = read_catalog(path, sheet)
        except CatalogError as exc:
            messagebox.showerror("No se pudo leer el catálogo", str(exc))
            return
        self.search_var.set("")
        self.apply_filter()
        self.status.set(f"{len(self.products)} productos cargados de {path}")

    def apply_filter(self):
        self.visible = select(self.products, search=self.search_var.get())
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, p in enumerate(self.visible):
            self.tree.insert("", "end", iid=str(idx), values=(
                p.sku, p.barcode, p.brand, p.name, p.size, p.color, p.price_display, p.stock,
            ))

    def selected_products(self):
        return [self.visible[int(i)] for i in self.tree.selection()]

    def copies_override(self) -> int | None:
        if self.copies_mode.get() == "stock":
            return None
        try:
            return max(1, int(self.copies_var.get()))
        except ValueError:
            return 1

    def update_preview(self):
        self.preview.delete("1.0", "end")
        sel = self.selected_products()
        if not sel:
            return
        product = sel[0]
        copies = self.copies_override() or max(1, product.stock)
        try:
            self.preview.insert("1.0", build_label(product, copies))
        except ValueError as exc:
            self.preview.insert("1.0", f"No imprimible: {exc}")

    def print_selected(self):
        sel = self.selected_products()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona una o más filas de la tabla.")
            return
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Sin impresora", "Elige o escribe el nombre de la impresora.")
            return
        batch = plan(sel, self.copies_override())
        if not batch.items:
            messagebox.showwarning("Nada que imprimir", batch.summary())
            return
        if not messagebox.askokcancel("Confirmar impresión", f"{batch.summary()}\n\nImpresora: {printer}"):
            return
        try:
            send_raw(printer, build_batch(batch.items).encode("utf-8"))
        except PrinterError as exc:
            messagebox.showerror("Error de impresión", str(exc))
            return
        save_settings({**load_settings(), "printer_name": printer})
        msg = f"Enviadas {batch.total_labels} etiquetas de {len(batch.items)} productos a {printer}."
        self.status.set(msg)
        messagebox.showinfo("Enviado", msg)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificación manual**

En Windows, en la carpeta del repo:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-labels.txt
python -m atlas_labels.gui
```

Comprobar: abre `catalogo_2026-09-21.xlsx` y pregunta la hoja (hay dos); la tabla muestra 100 productos; buscar "chrome" filtra; seleccionar varias filas con Ctrl; la vista previa muestra el ZPL del primero; "Imprimir seleccionados" muestra el resumen con omitidos, y con la Zebra apagada el error sale en diálogo sin cerrar la app.

En Linux sin Tkinter instalado: `sudo apt install python3-tk` y `uv run --no-project --with openpyxl python -m atlas_labels.gui` para al menos verificar que la ventana abre y carga el catálogo.

- [ ] **Step 3: Commit**

```bash
git add atlas_labels/gui.py
git commit -m "atlas_labels: app Tkinter con Excel, selección múltiple y lote

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Documentación y retiro del prototipo

**Files:**
- Create: `docs/reference/eleven-label-printer-task-pack.md` (movido desde `Eleven_Label_Printer_Starter/TASK_PACK.md`)
- Create: `atlas_labels/README.md`
- Modify: `README.md` (raíz): tabla de estado y sección nueva
- Delete: `Eleven_Label_Printer_Starter/` completo

- [ ] **Step 1: Mover el TASK_PACK y borrar el prototipo**

```bash
git mv -k Eleven_Label_Printer_Starter/TASK_PACK.md docs/reference/eleven-label-printer-task-pack.md 2>/dev/null \
  || mv Eleven_Label_Printer_Starter/TASK_PACK.md docs/reference/eleven-label-printer-task-pack.md
rm -rf Eleven_Label_Printer_Starter
```

(`git mv` falla porque la carpeta nunca se versionó; el `mv` normal es el camino esperado.)

- [ ] **Step 2: README del paquete**

```markdown
# atlas_labels

Imprime etiquetas de producto de 51 x 25 mm en una Zebra GX420t (203 dpi) a partir del catálogo que exporta Atlas One (`catalogo_YYYY-MM-DD.xlsx`) o de un CSV.

## Requisitos

- Python 3.10 o superior.
- `pip install -r requirements-labels.txt` (openpyxl; pywin32 solo en Windows).
- La impresora debe estar en **modo ZPL**. El nombre de la cola de Windows puede ser `ZDesigner GX420t (EPL)`, eso no importa: se imprime en RAW. Si la etiqueta de prueba no sale, la impresora está en EPL; cámbiala a ZPL con Zebra Setup Utilities.
- En Linux/macOS la cola debe existir en CUPS; se imprime con `lp -o raw`.

## Línea de comandos

```bash
python -m atlas_labels impresoras
python -m atlas_labels prueba --impresora "ZDesigner GX420t (EPL)"
python -m atlas_labels imprimir catalogo.xlsx --impresora "ZDesigner GX420t (EPL)" --dry-run
python -m atlas_labels imprimir catalogo.xlsx --sku CH-PLAY-EP-CH,CH-PLAY-EP-M --copias 2
python -m atlas_labels imprimir catalogo.xlsx --buscar "chrome" --hoja Plantilla
python -m atlas_labels previsualizar catalogo.xlsx --sku CH-PLAY-EP-CH
```

- Copias por defecto = columna `Stock`; las filas con 0 se omiten. `--copias N` fija N para todas.
- Filas sin código de barras se omiten y se listan en el resumen.
- Impresora: `--impresora`, luego la variable `ATLAS_LABELS_PRINTER`, luego la guardada por la app en `~/.atlas_labels.json`.

## App de escritorio

```bash
python -m atlas_labels.gui
```

Abre el catálogo, busca, selecciona varias filas (Ctrl o Shift), elige copias por existencia o fijas y pulsa "Imprimir seleccionados". La impresora elegida se recuerda.

## Columnas que se reconocen

| Campo | Encabezados aceptados (sin importar acentos, mayúsculas ni espacios) |
|---|---|
| SKU (obligatorio) | `SKU` |
| Nombre (obligatorio) | `NOMBRE_VENTA`, `Nombre`, `PRODUCTO` |
| Marca | `Marca` |
| Código de barras | `Codigo Barras`, `CODIGO_BARRAS`, `Barcode`, `Codigo` |
| Precio | `PRECIO_TEXTO`, `Precio Base`, `PRECIO` |
| Existencia | `Stock`, `CANTIDAD`, `Existencia` |
| Color | `Color` |
| Talla | `Talla` |

Trece dígitos con checksum válido se imprimen como EAN-13; cualquier otro texto como Code 128 (se quitan asteriscos y espacios).

## Tests

```bash
uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q
```
```

- [ ] **Step 3: Actualizar el README de la raíz**

En la tabla de la sección "Estado", agregar una fila después de `docs/reference/`:

```markdown
| `atlas_labels/` | Módulo de etiquetas ZPL para Zebra GX420t desde el catálogo Excel de Atlas One. CLI y app de escritorio. Independiente del agente; ver [`atlas_labels/README.md`](atlas_labels/README.md) y su [diseño](docs/superpowers/specs/2026-09-21-etiquetas-zebra-design.md). |
```

Y antes de "## Siguientes pasos" agregar:

```markdown
## Etiquetas Zebra desde Excel

```bash
pip install -r requirements-labels.txt
python -m atlas_labels imprimir catalogo.xlsx --impresora "ZDesigner GX420t (EPL)" --dry-run
python -m atlas_labels.gui
```

Detalles en [`atlas_labels/README.md`](atlas_labels/README.md).
```

- [ ] **Step 4: Correr toda la suite**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q`
Expected: 81 passed (8 + 10 + 14 + 15 + 5 + 12 + 5 + 12)

- [ ] **Step 5: Commit**

```bash
git add README.md atlas_labels/README.md docs/reference/eleven-label-printer-task-pack.md
git status --short   # confirmar que Eleven_Label_Printer_Starter/ ya no aparece
git commit -m "atlas_labels: documentación y retiro del prototipo Eleven Label Printer

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
