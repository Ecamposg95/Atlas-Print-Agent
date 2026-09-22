# Atlas Labels app v2: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar la app Tkinter de `atlas_labels` con filtros por departamento y género, copias editables por fila, vista previa gráfica dibujada localmente y un `.exe` de doble clic.

**Architecture:** El layout de la etiqueta pasa a ser una lista de elementos (`Text`/`Bars`) que `zpl.build_label` traduce a ZPL y `render.draw` dibuja en un canvas, así impresión y preview no divergen. Los codificadores EAN-13 y Code 128 se implementan en `barcode.py` y dan el ancho exacto. `batch.plan_items` acepta copias por producto. La GUI consume todo eso; PyInstaller empaqueta `launch_gui.py`.

**Tech Stack:** Python 3.10+, Tkinter (biblioteca estándar), openpyxl, pywin32 solo en Windows, pytest, PyInstaller (solo para el `.exe`).

**Spec:** `docs/superpowers/specs/2026-09-21-atlas-labels-gui-v2-design.md`

## Global Constraints

- Python 3.10 o superior. Sin dependencias nuevas en runtime; PyInstaller solo en `installers/labels/build_exe.ps1`.
- Toda cadena visible para el usuario y todo mensaje de commit en español. Cada commit termina con la línea `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Los tests existentes (94) no se rompen; solo se modifica el test de `code128_modules` para 13 dígitos como indica la Task 2.
- Comando de tests: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q` desde la raíz del repo. Se agrega `--with pyinstaller` solo si se quiere probar la Task 7 en Linux (no es necesario).
- El ZPL emitido por `build_label` no cambia de forma respecto a hoy (`^PW408`, `^LL200`, `^CI28`, mismas coordenadas, `^BEN,48,Y,N`, `^BCN,48,Y,N,N,A`, `^FB150,1,0,R`).
- La GUI nunca se cierra por un error de lectura o impresión: todo error va a `messagebox`.
- Commit solo los archivos listados en cada tarea, con `git add <archivos>`, nunca `git add -A`.

---

## Estructura de archivos

| Archivo | Cambio | Responsabilidad |
|---|---|---|
| `atlas_labels/model.py` | modificar | `Product.department`, propiedad `gender`. |
| `atlas_labels/catalog.py` | modificar | alias `departamento`; `select(..., department=, gender=)`. |
| `atlas_labels/barcode.py` | modificar | `encode_ean13`, `encode_code128`, `BarcodeSpec.bits`, ancho exacto. |
| `atlas_labels/zpl.py` | modificar | `Text`, `Bars`, `layout()`; `build_label` traduce elementos. |
| `atlas_labels/batch.py` | modificar | `plan_items()`; `plan()` lo reutiliza. |
| `atlas_labels/render.py` | crear | `draw(canvas, elements, scale, offset)`. |
| `atlas_labels/gui.py` | reescribir | filtros, copias por fila, preview gráfica, pestaña ZPL. |
| `launch_gui.py` | crear | punto de entrada para PyInstaller y `python launch_gui.py`. |
| `installers/labels/build_exe.ps1`, `installers/labels/README.md` | crear | genera el `.exe` y el acceso directo. |
| `.gitignore` | modificar | `*.spec`. |
| `tests/labels/test_model.py`, `test_catalog.py`, `test_barcode.py`, `test_zpl.py`, `test_batch.py`, `test_render.py` | modificar/crear | pruebas. |

Dependencias entre tareas: T3 depende de T2; T5 depende de T3; T6 depende de T1, T3, T4 y T5; T7 es independiente (se verifica a mano al final). T1, T2 y T4 pueden ir en paralelo.

---

### Task 1: Departamento y género en el modelo y el catálogo

**Files:**
- Modify: `atlas_labels/model.py`
- Modify: `atlas_labels/catalog.py`
- Test: `tests/labels/test_model.py`, `tests/labels/test_catalog.py`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `Product.department: str = ""` (campo nuevo, va después de `size`); `Product.gender -> str` (`"Mujer"` | `"Hombre"`); `select(products, skus=None, search=None, department: str | None = None, gender: str | None = None)`.

- [ ] **Step 1: Tests que fallan**

Agregar al final de `tests/labels/test_model.py`:

```python
def test_gender_mujer_por_sufijo_del_sku():
    assert Product(sku="LP-PANT-MUJ", name="x").gender == "Mujer"
    assert Product(sku="BAL-PANT-MUJ-2", name="x").gender == "Mujer"
    assert Product(sku="lp-pant-muj", name="x").gender == "Mujer"


def test_gender_hombre_en_cualquier_otro_caso():
    assert Product(sku="LP-PANT", name="x").gender == "Hombre"
    assert Product(sku="AMI-PANT-MEZ", name="x").gender == "Hombre"
    assert Product(sku="", name="x").gender == "Hombre"


def test_department_por_defecto_vacio():
    assert Product(sku="A", name="B").department == ""
```

Agregar al final de `tests/labels/test_catalog.py`:

```python
def test_read_xlsx_mapea_departamento(make_xlsx):
    headers = ATLAS_HEADERS[:4] + ["Departamento"] + ATLAS_HEADERS[4:]
    path = make_xlsx({"Plantilla": [
        headers,
        ["A", "Pantalón", None, "Amiri", " Pantalones ", "2017000000013", 1800, 3, None, None],
    ]})
    assert read_catalog(path)[0].department == "Pantalones"


def _catalog():
    return [
        Product(sku="AMI-PANT-MEZ", name="Pantalón", department="Pantalones"),
        Product(sku="LP-PANT-MUJ", name="Pantalón", department="Pantalones"),
        Product(sku="CH-PLAY-EP-CH", name="Playera", department="Playeras"),
    ]


def test_select_por_departamento_sin_distinguir_mayusculas():
    assert [p.sku for p in select(_catalog(), department="pantalones ")] == ["AMI-PANT-MEZ", "LP-PANT-MUJ"]


def test_select_por_genero():
    assert [p.sku for p in select(_catalog(), gender="Mujer")] == ["LP-PANT-MUJ"]
    assert [p.sku for p in select(_catalog(), gender="hombre")] == ["AMI-PANT-MEZ", "CH-PLAY-EP-CH"]


def test_select_departamento_y_genero_vacios_no_filtran():
    assert len(select(_catalog(), department="", gender="")) == 3
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_model.py tests/labels/test_catalog.py -q`
Expected: FAIL (`AttributeError: 'Product' object has no attribute 'gender'`, `TypeError: unexpected keyword argument 'department'`).

- [ ] **Step 3: Implementar**

En `atlas_labels/model.py`, dentro de `Product`, agregar el campo `department: str = ""` justo después de `size: str = ""`, y la propiedad después de `price_display`:

```python
    @property
    def gender(self) -> str:
        """Derivado del SKU: el export de Atlas One marca las prendas de mujer con -MUJ."""
        sku = self.sku.upper()
        return "Mujer" if sku.endswith("-MUJ") or "-MUJ-" in sku else "Hombre"
```

En `atlas_labels/catalog.py`, agregar a `ALIASES` después de `"size"`:

```python
    "department": ("departamento", "depto", "categoria"),
```

En `rows_to_products`, agregar `department=get("department"),` al constructor `Product(...)` (después de `size=get("size")`).

Reemplazar `select` completo por:

```python
def select(
    products: list[Product],
    skus: list[str] | None = None,
    search: str | None = None,
    department: str | None = None,
    gender: str | None = None,
) -> list[Product]:
    wanted = {s.strip().upper() for s in skus if s.strip()} if skus else None
    term = (search or "").strip().lower()
    dept = (department or "").strip().lower()
    gen = (gender or "").strip().lower()
    out: list[Product] = []
    for p in products:
        if wanted is not None and p.sku.upper() not in wanted:
            continue
        if term and term not in " ".join((p.sku, p.barcode, p.brand, p.name)).lower():
            continue
        if dept and p.department.strip().lower() != dept:
            continue
        if gen and p.gender.lower() != gen:
            continue
        out.append(p)
    return out
```

- [ ] **Step 4: Correr toda la suite**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q`
Expected: 7 tests nuevos verdes; 101 passed si se corre sola sobre `main` (94 + 7).

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/model.py atlas_labels/catalog.py tests/labels/test_model.py tests/labels/test_catalog.py
git commit -m "atlas_labels: departamento y género en el catálogo y en select

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Codificadores EAN-13 y Code 128 con ancho exacto

**Files:**
- Modify: `atlas_labels/barcode.py`
- Test: `tests/labels/test_barcode.py`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `encode_ean13(digits: str) -> str` (95 caracteres `0`/`1`); `encode_code128(data: str) -> str`; `code128_modules(data) -> int` ahora exacto (`len(encode_code128(data))`); `BarcodeSpec.bits -> str` (propiedad); `BarcodeSpec.width_dots` sigue siendo `len(bits) * module_width`; constantes `CODE128_PATTERNS`, `CODE128_STOP`, `START_B = 104`, `START_C = 105`, `CODE_B = 100`, `CODE_C = 99`.

- [ ] **Step 1: Tests que fallan**

En `tests/labels/test_barcode.py` reemplazar la función `test_code128_modules_cota_superior_subconjunto_b` completa por:

```python
def test_code128_modules_es_exacto_segun_subconjuntos():
    # 13 dígitos: START B + '2' + CODE C + 6 pares + check = 10 símbolos de 11 + STOP de 13
    assert code128_modules("2017000000014") == 10 * 11 + 13
    # 6 alfanuméricos en B: START B + 6 + check = 8 símbolos + STOP
    assert code128_modules("1A43KE") == 8 * 11 + 13
    # 12 dígitos: START C + 6 pares + check = 8 símbolos + STOP
    assert code128_modules("201700000001") == 8 * 11 + 13
```

Agregar al final del archivo:

```python
from atlas_labels.barcode import (  # noqa: E402
    CODE128_PATTERNS,
    CODE128_STOP,
    CODE_C,
    START_B,
    START_C,
    encode_code128,
    encode_ean13,
)


def _bits(value: int) -> str:
    out, bar = "", True
    for w in CODE128_PATTERNS[value]:
        out += ("1" if bar else "0") * int(w)
        bar = not bar
    return out


def test_tabla_code128_es_consistente():
    assert len(CODE128_PATTERNS) == 106
    assert all(sum(int(w) for w in p) == 11 for p in CODE128_PATTERNS)
    assert sum(int(w) for w in CODE128_STOP) == 13
    assert _bits(0) == "11011001100"


def test_encode_code128_ab_en_subconjunto_b_con_checksum():
    # START B=104, 'A'=33, 'B'=34 → 104 + 33*1 + 34*2 = 205 → 205 % 103 = 102
    stop = "".join(("1" if i % 2 == 0 else "0") * int(w) for i, w in enumerate(CODE128_STOP))
    assert encode_code128("AB") == _bits(START_B) + _bits(33) + _bits(34) + _bits(102) + stop


def test_encode_code128_solo_digitos_pares_empieza_en_c():
    bits = encode_code128("1234")
    assert bits.startswith(_bits(START_C) + _bits(12) + _bits(34))
    assert len(bits) == 5 * 11 + 13


def test_encode_code128_corrida_impar_pone_primer_digito_en_b():
    bits = encode_code128("12345")
    assert bits.startswith(_bits(START_B) + _bits(ord("1") - 32) + _bits(CODE_C) + _bits(23) + _bits(45))


def test_encode_code128_corrida_corta_se_queda_en_b():
    bits = encode_code128("AB12CD")
    assert len(bits) == 8 * 11 + 13
    assert _bits(CODE_C) not in bits[: 3 * 11]


def test_encode_code128_rechaza_fuera_de_ascii():
    with pytest.raises(ValueError):
        encode_code128("ñ")


def test_encode_ean13_patron_conocido():
    bits = encode_ean13("2017000000013")
    assert len(bits) == 95
    assert bits == (
        "101"
        "0001101" "0011001" "0010001" "0100111" "0001101" "0100111"  # 0 1 7 0 0 0 con paridad LLGGLG
        "01010"
        "1110010" "1110010" "1110010" "1110010" "1100110" "1000010"  # 0 0 0 0 1 3 en R
        "101"
    )


def test_encode_ean13_rechaza_checksum_invalido():
    with pytest.raises(ValueError):
        encode_ean13("2017000000014")


def test_barcodespec_bits_y_width_dots_coinciden():
    spec = detect("2017000000013")
    assert spec.bits == encode_ean13("2017000000013")
    assert spec.width_dots == 190
    spec = detect("1A43KE")
    assert spec.bits == encode_code128("1A43KE")
    assert spec.width_dots == len(spec.bits) * 2
```

Agregar `import pytest` al inicio del archivo si no está.

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_barcode.py -q`
Expected: FAIL con `ImportError: cannot import name 'CODE128_PATTERNS'`.

- [ ] **Step 3: Implementar**

En `atlas_labels/barcode.py`, reemplazar el bloque desde `EAN13_MODULES = 95` hasta el final de `code128_modules` por:

```python
EAN13_MODULES = 95

# Code 128: anchos de barras y espacios (alternados, empezando en barra) de cada valor 0..105.
CODE128_PATTERNS = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232",
)
CODE128_STOP = "2331112"
CODE_C = 99
CODE_B = 100
START_B = 104
START_C = 105

# EAN-13: patrones L, G y R por dígito, y paridad de los seis dígitos izquierdos según el primero.
_EAN_L = ("0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011")
_EAN_G = ("0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111")
_EAN_R = ("1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100")
_EAN_PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")


@dataclass(frozen=True)
class BarcodeSpec:
    kind: str  # "EAN13" | "CODE128"
    data: str
    module_width: int  # 1 o 2 dots por módulo
    warning: str = ""

    @property
    def bits(self) -> str:
        return encode_ean13(self.data) if self.kind == "EAN13" else encode_code128(self.data)

    @property
    def width_dots(self) -> int:
        return len(self.bits) * self.module_width


def ean13_checksum_ok(digits: str) -> bool:
    if len(digits) != 13 or not digits.isdigit():
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == int(digits[12])


def encode_ean13(digits: str) -> str:
    """Módulos de un EAN-13 válido: 95 caracteres '1' (barra) o '0' (espacio)."""
    if not ean13_checksum_ok(digits):
        raise ValueError(f"EAN-13 inválido: {digits!r}")
    parity = _EAN_PARITY[int(digits[0])]
    left = "".join(
        (_EAN_L if parity[i] == "L" else _EAN_G)[int(d)] for i, d in enumerate(digits[1:7])
    )
    right = "".join(_EAN_R[int(d)] for d in digits[7:13])
    return "101" + left + "01010" + right + "101"


def _widths_to_bits(widths: str) -> str:
    out, bar = [], True
    for w in widths:
        out.append(("1" if bar else "0") * int(w))
        bar = not bar
    return "".join(out)


def _code128_values(data: str) -> list[int]:
    """Valores de símbolo con la regla del modo automático de Zebra: B por defecto,
    C para corridas de 4 o más dígitos (o toda la cadena si son solo dígitos y pares)."""
    values: list[int] = []
    current: str | None = None

    def switch(target: str) -> None:
        nonlocal current
        if current == target:
            return
        if not values:
            values.append(START_C if target == "C" else START_B)
        else:
            values.append(CODE_C if target == "C" else CODE_B)
        current = target

    i, n = 0, len(data)
    while i < n:
        run = 0
        while i + run < n and data[i + run].isdigit():
            run += 1
        use_c = run >= 4 or (i == 0 and run == n and n >= 2 and n % 2 == 0)
        if use_c:
            if run % 2 == 1:
                switch("B")
                values.append(ord(data[i]) - 32)
                i += 1
                run -= 1
            switch("C")
            for _ in range(run // 2):
                values.append(int(data[i : i + 2]))
                i += 2
        else:
            switch("B")
            values.append(ord(data[i]) - 32)
            i += 1
    return values


def encode_code128(data: str) -> str:
    """Módulos de un Code 128: START, datos, verificación y STOP, como '1'/'0'."""
    if not data or any(not 32 <= ord(ch) <= 126 for ch in data):
        raise ValueError(f"Code 128 solo admite ASCII imprimible: {data!r}")
    values = _code128_values(data)
    check = (values[0] + sum(i * v for i, v in enumerate(values[1:], 1))) % 103
    values.append(check)
    return "".join(_widths_to_bits(CODE128_PATTERNS[v]) for v in values) + _widths_to_bits(CODE128_STOP)


def code128_modules(data: str) -> int:
    """Ancho exacto en módulos del Code 128 que imprimirá la Zebra en modo automático."""
    return len(encode_code128(data))
```

`detect` no cambia. Verificar que `from dataclasses import dataclass` sigue al inicio.

- [ ] **Step 4: Correr toda la suite**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q`
Expected: 9 tests nuevos verdes más el de 13 dígitos reescrito; 103 passed si se corre sola sobre `main` (94 + 9). Los tests de `test_zpl.py` deben seguir verdes: EAN-13 sigue en 190 dots y `1A43KE` en 202.

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/barcode.py tests/labels/test_barcode.py
git commit -m "atlas_labels: codificadores EAN-13 y Code 128 con ancho exacto

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `layout()` como única fuente del diseño de la etiqueta

**Files:**
- Modify: `atlas_labels/zpl.py`
- Test: `tests/labels/test_zpl.py`

**Interfaces:**
- Consumes: `BarcodeSpec.bits`, `BarcodeSpec.width_dots`, `detect` (Task 2).
- Produces: dataclasses `Text(x, y, height, text, width=None, align="L")` y `Bars(x, y, height, bits, module_width, interpretation, kind, data)`; `layout(product, spec=None) -> list[Text | Bars]` (lanza `ValueError` sin código); `build_label` sin cambio de firma ni de salida.

- [ ] **Step 1: Tests que fallan**

Agregar al final de `tests/labels/test_zpl.py`:

```python
from atlas_labels.zpl import Bars, Text, layout  # noqa: E402


def test_layout_elementos_en_orden():
    els = layout(_p())
    kinds = [type(e).__name__ for e in els]
    assert kinds == ["Text", "Text", "Text", "Bars", "Text", "Text"]
    brand, name, variant, bars, sku, price = els
    assert (brand.x, brand.y, brand.height, brand.text) == (12, 8, 22, "Chrome Hearts")
    assert (name.y, name.height) == (34, 18)
    assert (variant.y, variant.text) == (56, "M / Negro")
    assert (bars.x, bars.y, bars.height, bars.module_width, bars.kind) == (109, 76, 48, 2, "EAN13")
    assert len(bars.bits) == 95 and bars.interpretation == "2017000000013"
    assert (sku.y, sku.text) == (168, "CH-PLAY-EP-CH")
    assert (price.x, price.y, price.width, price.align, price.text) == (246, 162, 150, "R", "$1,800.00")


def test_layout_omite_variante_y_precio_vacios():
    els = layout(_p(size="", color="", price=None, price_text=""))
    assert [type(e).__name__ for e in els] == ["Text", "Text", "Bars", "Text"]


def test_layout_sin_codigo_lanza_valueerror():
    with pytest.raises(ValueError):
        layout(_p(barcode=""))


def test_build_label_es_la_traduccion_de_layout():
    zpl = build_label(_p(), copies=2)
    for el in layout(_p()):
        if isinstance(el, Text):
            assert f"^FD{el.text}^FS" in zpl
        else:
            assert f"^FO{el.x},{el.y}^BY{el.module_width},2,{el.height}" in zpl
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_zpl.py -q`
Expected: FAIL con `ImportError: cannot import name 'Bars'`.

- [ ] **Step 3: Implementar**

En `atlas_labels/zpl.py`, reemplazar desde `def _barcode_lines` hasta el final de `build_label` por:

```python
@dataclass(frozen=True)
class Text:
    x: int
    y: int
    height: int
    text: str
    width: int | None = None  # caja ^FB; solo se usa con align="R"
    align: str = "L"  # "L" | "R"


@dataclass(frozen=True)
class Bars:
    x: int
    y: int
    height: int
    bits: str  # módulos '1'/'0'
    module_width: int
    interpretation: str  # línea legible bajo las barras
    kind: str  # "EAN13" | "CODE128"
    data: str


def layout(product: Product, spec: BarcodeSpec | None = None) -> list[Text | Bars]:
    """Elementos de la etiqueta con sus coordenadas en dots. Única fuente para ZPL y preview."""
    spec = spec if spec is not None else detect(product.barcode)
    if spec is None:
        raise ValueError(f"{product.sku or product.name}: sin código de barras")

    elements: list[Text | Bars] = [
        Text(MARGIN, 8, 22, fit_text(product.brand, 22, TEXT_WIDTH)),
        Text(MARGIN, 34, 18, fit_text(product.name, 18, TEXT_WIDTH)),
    ]
    variant = fit_text(
        " / ".join(x for x in (zpl_safe(product.size), zpl_safe(product.color)) if x),
        15,
        TEXT_WIDTH,
    )
    if variant:
        elements.append(Text(MARGIN, 56, 15, variant))
    x = max(MARGIN, (LABEL_WIDTH - spec.width_dots) // 2)
    elements.append(Bars(x, 76, BARCODE_HEIGHT, spec.bits, spec.module_width, spec.data, spec.kind, spec.data))
    elements.append(Text(MARGIN, 168, 14, fit_text(product.sku, 14, SKU_WIDTH)))
    price = fit_text(product.price_display, 22, PRICE_WIDTH)
    if price:
        elements.append(Text(LABEL_WIDTH - MARGIN - PRICE_WIDTH, 162, 22, price, PRICE_WIDTH, "R"))
    return elements


def _element_lines(el: Text | Bars) -> list[str]:
    if isinstance(el, Bars):
        lines = [f"^FO{el.x},{el.y}^BY{el.module_width},2,{el.height}"]
        if el.kind == "EAN13":
            lines.append(f"^BEN,{el.height},Y,N^FD{el.data}^FS")
        else:
            lines.append(f"^BCN,{el.height},Y,N,N,A^FD{el.data}^FS")
        return lines
    if el.width is not None and el.align == "R":
        return [f"^FO{el.x},{el.y}^A0N,{el.height},{el.height}^FB{el.width},1,0,R^FD{el.text}^FS"]
    return [f"^FO{el.x},{el.y}^A0N,{el.height},{el.height}^FD{el.text}^FS"]


def build_label(product: Product, copies: int = 1, spec: BarcodeSpec | None = None) -> str:
    lines = [
        "^XA",
        f"^PW{LABEL_WIDTH}",
        f"^LL{LABEL_HEIGHT}",
        "^LH0,0",
        "^CI28",
        f"^PQ{max(1, int(copies))}",
    ]
    for el in layout(product, spec):
        lines.extend(_element_lines(el))
    lines.append("^XZ")
    return "\n".join(lines)
```

Agregar `from dataclasses import dataclass` a los imports del módulo. `build_batch` y `build_test_label` quedan igual.

- [ ] **Step 4: Correr toda la suite**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q`
Expected: 4 tests nuevos verdes y los 17 previos de `test_zpl.py` intactos (total = base integrada + 4).

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/zpl.py tests/labels/test_zpl.py
git commit -m "atlas_labels: layout() como única fuente de la etiqueta; build_label lo traduce

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `plan_items` con copias por producto

**Files:**
- Modify: `atlas_labels/batch.py`
- Test: `tests/labels/test_batch.py`

**Interfaces:**
- Consumes: `detect`.
- Produces: `plan_items(items: list[tuple[Product, int]]) -> BatchPlan`; `plan(products, copies=None)` sin cambios de firma ni comportamiento.

- [ ] **Step 1: Tests que fallan**

Agregar al final de `tests/labels/test_batch.py`:

```python
from atlas_labels.batch import plan_items  # noqa: E402


def test_plan_items_respeta_copias_por_producto():
    b = plan_items([(_p("A", stock=9), 2), (_p("B", stock=0), 5)])
    assert b.items == [(_p("A", stock=9), 2), (_p("B", stock=0), 5)]
    assert b.total_labels == 7


def test_plan_items_omite_cero_y_sin_codigo():
    b = plan_items([(_p("A"), 0), (_p("B", barcode=""), 3), (_p("C"), 1)])
    assert [p.sku for p, _ in b.items] == ["C"]
    assert b.skipped == [(_p("A"), "sin existencia"), (_p("B", barcode=""), "sin código")]


def test_plan_equivale_a_plan_items_con_stock():
    products = [_p("A", stock=3), _p("B", stock=0)]
    assert plan(products) == plan_items([(p, p.stock) for p in products])
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_batch.py -q`
Expected: FAIL con `ImportError: cannot import name 'plan_items'`.

- [ ] **Step 3: Implementar**

En `atlas_labels/batch.py`, reemplazar la función `plan` por:

```python
def plan_items(items: list[tuple[Product, int]]) -> BatchPlan:
    """Valida copias ya decididas por producto: omite copias ≤ 0 y productos sin código."""
    result = BatchPlan()
    for product, n in items:
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


def plan(products: list[Product], copies: int | None = None) -> BatchPlan:
    return plan_items([(p, copies if copies is not None else p.stock) for p in products])
```

- [ ] **Step 4: Correr toda la suite**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q`
Expected: 3 tests nuevos verdes; 97 passed si se corre sola sobre `main` (94 + 3).

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/batch.py tests/labels/test_batch.py
git commit -m "atlas_labels: plan_items con copias por producto

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Dibujo de la etiqueta (`render.py`)

**Files:**
- Create: `atlas_labels/render.py`
- Test: `tests/labels/test_render.py`

**Interfaces:**
- Consumes: `Text`, `Bars`, `LABEL_WIDTH`, `LABEL_HEIGHT` de `zpl` (Task 3).
- Produces: `draw(canvas, elements, scale: float = 2.0, offset: tuple[int, int] = (0, 0)) -> None`. `canvas` es cualquier objeto con `create_rectangle(x1, y1, x2, y2, **kw)` y `create_text(x, y, **kw)` (un `tkinter.Canvas` o un doble en tests).

- [ ] **Step 1: Tests que fallan**

```python
# tests/labels/test_render.py
from atlas_labels.render import draw
from atlas_labels.zpl import LABEL_HEIGHT, LABEL_WIDTH, Bars, Text


class FakeCanvas:
    def __init__(self):
        self.rects = []
        self.texts = []

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        self.rects.append((x1, y1, x2, y2, kw))

    def create_text(self, x, y, **kw):
        self.texts.append((x, y, kw))


def test_draw_fondo_a_escala_con_offset():
    c = FakeCanvas()
    draw(c, [], scale=2, offset=(10, 10))
    assert c.rects[0][:4] == (10, 10, 10 + LABEL_WIDTH * 2, 10 + LABEL_HEIGHT * 2)
    assert c.rects[0][4]["fill"] == "white"


def test_draw_texto_izquierda_y_derecha():
    c = FakeCanvas()
    draw(c, [Text(12, 8, 22, "Marca"), Text(246, 162, 22, "$1,800.00", 150, "R")], scale=2)
    left, right = c.texts
    assert (left[0], left[1], left[2]["anchor"], left[2]["text"]) == (24, 16, "nw", "Marca")
    assert (right[0], right[1], right[2]["anchor"]) == ((246 + 150) * 2, 324, "ne")
    assert left[2]["font"] == ("Helvetica", -35)  # int(22 * 2 * 0.8)


def test_draw_barras_por_corridas_y_linea_legible():
    c = FakeCanvas()
    bars = Bars(100, 76, 48, "1101", 2, "1234", "CODE128", "1234")
    draw(c, [bars], scale=2)
    black = [r for r in c.rects if r[4].get("fill") == "black"]
    # corridas "11" (módulos 0-1) y "1" (módulo 3); unit = 2*2 = 4 px
    assert [(r[0], r[2]) for r in black] == [(200, 208), (212, 216)]
    assert all((r[1], r[3]) == (152, 152 + 96) for r in black)
    label = c.texts[-1]
    assert label[2]["text"] == "1234" and label[2]["anchor"] == "n"
    assert label[0] == 200 + 4 * 4 / 2 and label[1] == 152 + 96 + 4
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels/test_render.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'atlas_labels.render'`.

- [ ] **Step 3: Implementar**

```python
# atlas_labels/render.py
"""Dibuja los elementos de layout() en un canvas de Tk (o cualquier objeto compatible)."""

from __future__ import annotations

from .zpl import LABEL_HEIGHT, LABEL_WIDTH, Bars, Text

TEXT_FONT_FACTOR = 0.8  # altura ZPL → píxeles de fuente Tk, aproximado
INTERPRETATION_HEIGHT = 11


def draw(canvas, elements: list[Text | Bars], scale: float = 2.0, offset: tuple[int, int] = (0, 0)) -> None:
    ox, oy = offset
    canvas.create_rectangle(
        ox, oy, ox + LABEL_WIDTH * scale, oy + LABEL_HEIGHT * scale, fill="white", outline="#999999"
    )
    for el in elements:
        if isinstance(el, Bars):
            _draw_bars(canvas, el, scale, ox, oy)
        else:
            _draw_text(canvas, el, scale, ox, oy)


def _font(height: float, scale: float) -> tuple[str, int]:
    return ("Helvetica", -max(6, int(height * scale * TEXT_FONT_FACTOR)))


def _draw_text(canvas, el: Text, scale: float, ox: float, oy: float) -> None:
    font = _font(el.height, scale)
    if el.width is not None and el.align == "R":
        canvas.create_text((ox + (el.x + el.width) * scale), oy + el.y * scale, text=el.text, anchor="ne", font=font)
    else:
        canvas.create_text(ox + el.x * scale, oy + el.y * scale, text=el.text, anchor="nw", font=font)


def _draw_bars(canvas, el: Bars, scale: float, ox: float, oy: float) -> None:
    x0 = ox + el.x * scale
    top = oy + el.y * scale
    bottom = top + el.height * scale
    unit = el.module_width * scale
    i = 0
    while i < len(el.bits):
        if el.bits[i] != "1":
            i += 1
            continue
        j = i
        while j < len(el.bits) and el.bits[j] == "1":
            j += 1
        canvas.create_rectangle(x0 + i * unit, top, x0 + j * unit, bottom, fill="black", outline="")
        i = j
    center = x0 + len(el.bits) * unit / 2
    canvas.create_text(center, bottom + 2 * scale, text=el.interpretation, anchor="n", font=_font(INTERPRETATION_HEIGHT, scale))
```

- [ ] **Step 4: Correr toda la suite**

Run: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q`
Expected: 3 tests nuevos verdes (total = base integrada + 3).

- [ ] **Step 5: Commit**

```bash
git add atlas_labels/render.py tests/labels/test_render.py
git commit -m "atlas_labels: dibujo de la etiqueta a partir de layout()

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: App v2 (`gui.py`)

**Files:**
- Rewrite: `atlas_labels/gui.py`

**Interfaces:**
- Consumes: `select(products, search=, department=, gender=)`, `Product.department`, `Product.gender` (T1); `layout`, `build_label`, `build_batch`, `LABEL_WIDTH`, `LABEL_HEIGHT` (T3); `plan_items` (T4); `draw` (T5); `read_catalog`, `sheet_names`, `CatalogError`; `send_raw`, `list_printers`, `PrinterError`; `load_settings`, `save_settings`, `resolve_printer`.
- Produces: `main()`; se lanza con `python -m atlas_labels.gui`.

Sin tests automáticos (spec §7 y §9). Verificación: sintaxis, import con Tk disponible, y la prueba manual del Step 2 en Windows.

- [ ] **Step 1: Reescribir `atlas_labels/gui.py` completo**

```python
"""Interfaz de escritorio: abre un catálogo, filtra, ajusta copias por fila e imprime en lote."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .batch import plan_items
from .catalog import CatalogError, read_catalog, select, sheet_names
from .printer import PrinterError, list_printers, send_raw
from .render import draw
from .settings import load_settings, resolve_printer, save_settings
from .zpl import LABEL_HEIGHT, LABEL_WIDTH, build_batch, build_label, layout

COLUMNS = ("SKU", "Código", "Marca", "Nombre", "Departamento", "Talla", "Color", "Precio", "Stock", "Etiquetas")
COLUMN_WIDTHS = {
    "SKU": 130, "Código": 120, "Marca": 120, "Nombre": 220, "Departamento": 100,
    "Talla": 50, "Color": 80, "Precio": 90, "Stock": 50, "Etiquetas": 70,
}
ALL = "Todos"
GENDER_LABELS = {"Hombre / sin especificar": "Hombre", "Mujer": "Mujer"}
PREVIEW_SCALE = 2
PREVIEW_PAD = 10


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Atlas Labels")
        self.geometry("1320x780")
        self.products = []
        self.visible = []
        self.copies: dict[str, int] = {}  # SKU → etiquetas a imprimir; sobrevive a los filtros
        self._editor: ttk.Entry | None = None
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
        ttk.Combobox(top, width=30, textvariable=self.printer_var, values=printers).pack(side="left", padx=4)
        ttk.Button(top, text="Imprimir seleccionados", command=self.print_selected).pack(side="right")

        filters = ttk.Frame(self, padding=(10, 0, 10, 6))
        filters.pack(fill="x")
        ttk.Label(filters, text="Departamento:").pack(side="left")
        self.department_var = tk.StringVar(value=ALL)
        self.department_box = ttk.Combobox(
            filters, width=22, textvariable=self.department_var, values=(ALL,), state="readonly"
        )
        self.department_box.pack(side="left", padx=4)
        ttk.Label(filters, text=" Género:").pack(side="left")
        self.gender_var = tk.StringVar(value=ALL)
        ttk.Combobox(
            filters, width=24, textvariable=self.gender_var, values=(ALL, *GENDER_LABELS), state="readonly"
        ).pack(side="left", padx=4)
        ttk.Label(filters, text=" Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(filters, width=28, textvariable=self.search_var).pack(side="left", padx=4)
        for var in (self.department_var, self.gender_var, self.search_var):
            var.trace_add("write", lambda *_: self.apply_filter())

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10)

        left = ttk.Frame(body)
        body.add(left, weight=3)
        self.tree = ttk.Treeview(left, columns=COLUMNS, show="headings", selectmode="extended")
        for col in COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=COLUMN_WIDTHS[col], anchor="w")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.update_preview())
        self.tree.bind("<Double-1>", self.edit_copies)

        right = ttk.Frame(body)
        body.add(right, weight=2)
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            self.tabs,
            width=LABEL_WIDTH * PREVIEW_SCALE + 2 * PREVIEW_PAD,
            height=LABEL_HEIGHT * PREVIEW_SCALE + 2 * PREVIEW_PAD,
            background="#e6e6e6",
            highlightthickness=0,
        )
        self.tabs.add(self.canvas, text="Etiqueta")
        self.zpl_text = tk.Text(self.tabs, width=60, height=20)
        self.tabs.add(self.zpl_text, text="ZPL")

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Usar existencia", command=self.use_stock).pack(side="left")
        ttk.Label(bottom, text="   Poner").pack(side="left")
        self.copies_var = tk.StringVar(value="1")
        ttk.Spinbox(bottom, from_=0, to=999, width=6, textvariable=self.copies_var).pack(side="left", padx=4)
        ttk.Button(bottom, text="a seleccionados", command=self.set_copies_selected).pack(side="left")
        ttk.Label(bottom, text="   Doble clic en la columna Etiquetas para editar una fila.").pack(side="left")

        self.status = tk.StringVar(value="Abre un catálogo .xlsx o .csv para empezar.")
        ttk.Label(self, textvariable=self.status, padding=(10, 0, 10, 6)).pack(fill="x")

    # --- catálogo y filtros -------------------------------------------------

    def open_catalog(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Catálogo", "*.xlsx *.xlsm *.csv"),
                ("Excel", "*.xlsx *.xlsm"),
                ("CSV", "*.csv"),
            ]
        )
        if not path:
            return
        try:
            sheet = None
            if path.lower().endswith((".xlsx", ".xlsm")):
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
        except Exception as exc:  # cualquier otro fallo de lectura no debe tumbar la app
            messagebox.showerror("Error inesperado al leer el catálogo", f"{type(exc).__name__}: {exc}")
            return
        self.copies = {p.sku: p.stock for p in self.products}
        departments = sorted({p.department.strip() for p in self.products if p.department.strip()})
        self.department_box["values"] = (ALL, *departments)
        self.department_var.set(ALL)
        self.gender_var.set(ALL)
        self.search_var.set("")
        self.apply_filter()
        self.status.set(f"{len(self.products)} productos cargados de {path}")

    def _filters(self) -> dict:
        department = self.department_var.get()
        gender = GENDER_LABELS.get(self.gender_var.get())
        return {
            "department": None if department == ALL else department,
            "gender": gender,
            "search": self.search_var.get(),
        }

    def apply_filter(self):
        self._close_editor()
        self.visible = select(self.products, **self._filters())
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, p in enumerate(self.visible):
            self.tree.insert("", "end", iid=str(idx), values=self._row(p))
        self.update_preview()

    def _row(self, p) -> tuple:
        return (
            p.sku, p.barcode, p.brand, p.name, p.department, p.size, p.color,
            p.price_display, p.stock, self.copies_for(p),
        )

    def copies_for(self, p) -> int:
        return self.copies.get(p.sku, p.stock)

    def selected_products(self):
        return [self.visible[int(i)] for i in self.tree.selection()]

    # --- copias por fila ----------------------------------------------------

    def set_copies(self, products, value: int):
        for p in products:
            self.copies[p.sku] = max(0, int(value))
        skus = {p.sku for p in products}
        for idx, p in enumerate(self.visible):
            if p.sku in skus:
                self.tree.item(str(idx), values=self._row(p))
        self.update_preview()

    def use_stock(self):
        targets = self.selected_products() or self.visible
        for p in targets:
            self.copies[p.sku] = p.stock
        skus = {p.sku for p in targets}
        for idx, p in enumerate(self.visible):
            if p.sku in skus:
                self.tree.item(str(idx), values=self._row(p))
        self.update_preview()

    def set_copies_selected(self):
        sel = self.selected_products()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona una o más filas de la tabla.")
            return
        try:
            value = max(0, int(self.copies_var.get().strip()))
        except ValueError:
            messagebox.showwarning("Copias inválidas", "Escribe un número entero de 0 o más.")
            return
        self.set_copies(sel, value)

    def edit_copies(self, event):
        self._close_editor()
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        column = self.tree.identify_column(event.x)
        iid = self.tree.identify_row(event.y)
        if not iid or column != f"#{len(COLUMNS)}":
            return
        bbox = self.tree.bbox(iid, column)
        if not bbox:
            return
        x, y, w, h = bbox
        product = self.visible[int(iid)]
        var = tk.StringVar(value=str(self.copies_for(product)))
        entry = ttk.Entry(self.tree, textvariable=var, width=6)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        entry.select_range(0, "end")

        def commit(_event=None):
            if self._editor is not entry:
                return
            raw = var.get().strip()
            self._close_editor()
            try:
                self.set_copies([product], int(raw))
            except ValueError:
                pass  # texto no numérico: se conserva el valor anterior

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", lambda _e: self._close_editor())
        self._editor = entry

    def _close_editor(self):
        editor, self._editor = self._editor, None
        if editor is not None:
            editor.destroy()

    # --- vista previa -------------------------------------------------------

    def update_preview(self):
        self.canvas.delete("all")
        self.zpl_text.delete("1.0", "end")
        sel = self.selected_products()
        if not sel:
            self._preview_message("Selecciona un producto para ver su etiqueta.")
            return
        product = sel[0]
        try:
            elements = layout(product)
        except ValueError as exc:
            self._preview_message(f"No imprimible: {exc}")
            return
        draw(self.canvas, elements, PREVIEW_SCALE, (PREVIEW_PAD, PREVIEW_PAD))
        self.zpl_text.insert("1.0", build_label(product, max(1, self.copies_for(product))))

    def _preview_message(self, text: str):
        self.canvas.create_text(
            PREVIEW_PAD + LABEL_WIDTH * PREVIEW_SCALE / 2,
            PREVIEW_PAD + LABEL_HEIGHT * PREVIEW_SCALE / 2,
            text=text, fill="#777777", font=("Helvetica", 12),
        )

    # --- impresión ----------------------------------------------------------

    def print_selected(self):
        sel = self.selected_products()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona una o más filas de la tabla.")
            return
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Sin impresora", "Elige o escribe el nombre de la impresora.")
            return
        batch = plan_items([(p, self.copies_for(p)) for p in sel])
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
        except Exception as exc:  # cualquier otro fallo de impresión no debe tumbar la app
            messagebox.showerror("Error inesperado al imprimir", f"{type(exc).__name__}: {exc}")
            return
        try:
            save_settings({**load_settings(), "printer_name": printer})
        except OSError:
            pass  # recordar la impresora es opcional
        msg = f"Enviadas {batch.total_labels} etiquetas de {len(batch.items)} productos a {printer}."
        self.status.set(msg)
        messagebox.showinfo("Enviado", msg)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificación**

En Linux: `uv run --no-project --with openpyxl python -c "import ast; ast.parse(open('atlas_labels/gui.py', encoding='utf-8').read()); print('ok')"` y la suite completa (120 passed con T1 a T5 integradas, sin cambios por esta tarea).

En Windows (el usuario o el controlador, desde WSL): `python.exe -m atlas_labels.gui`. Comprobar: abrir `catalogo_2026-09-21.xlsx`; el desplegable Departamento muestra Accesorios, Blusas, Bolsas, Calzado, Chamarras, Pantalones, Playeras, Suéteres, Tenis; Género = Mujer deja solo SKU con `-MUJ`; la columna Etiquetas arranca igual a Stock; doble clic en Etiquetas edita y Enter guarda, Escape cancela; "Poner 2 a seleccionados" y "Usar existencia" actualizan la columna; la pestaña Etiqueta dibuja la etiqueta con barras y la pestaña ZPL muestra el texto; "Imprimir seleccionados" usa las copias de la columna.

- [ ] **Step 3: Commit**

```bash
git add atlas_labels/gui.py
git commit -m "atlas_labels: app v2 con filtros, copias por fila y vista previa gráfica

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Ejecutable de doble clic

**Files:**
- Create: `launch_gui.py`
- Create: `installers/labels/build_exe.ps1`
- Create: `installers/labels/README.md`
- Modify: `.gitignore`
- Modify: `atlas_labels/README.md` (sección "App de escritorio")

**Interfaces:**
- Consumes: `atlas_labels.gui.main`.
- Produces: `dist/Atlas Labels.exe` y `%USERPROFILE%\Desktop\Atlas Labels.lnk` al correr el script en Windows.

- [ ] **Step 1: Punto de entrada**

```python
# launch_gui.py
"""Punto de entrada absoluto para PyInstaller y para `python launch_gui.py`."""

from atlas_labels.gui import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Script de empaquetado**

```powershell
# installers/labels/build_exe.ps1
# Genera dist\Atlas Labels.exe (sin consola, un solo archivo) y un acceso directo en el escritorio.
# Uso, desde PowerShell en Windows:  .\installers\labels\build_exe.ps1
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

Write-Host "Instalando dependencias en el Python de Windows..."
python -m pip install --quiet --upgrade pyinstaller
python -m pip install --quiet -r requirements-labels.txt

Write-Host "Empaquetando..."
python -m PyInstaller --noconsole --onefile --clean --name "Atlas Labels" --collect-submodules atlas_labels launch_gui.py

$exe = Join-Path $root "dist\Atlas Labels.exe"
if (-not (Test-Path $exe)) { throw "No se generó $exe" }

$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "Atlas Labels.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = Split-Path $exe
$shortcut.Description = "Impresión de etiquetas Zebra desde el catálogo"
$shortcut.Save()

Write-Host "Ejecutable:     $exe"
Write-Host "Acceso directo: $lnk"
```

- [ ] **Step 3: README del instalador y ajustes**

```markdown
# Atlas Labels: ejecutable para Windows

Genera un `.exe` que abre la app de etiquetas con doble clic, sin terminal ni Python visible.

## Generar

En PowerShell, en la raíz del repo, con el Python de Windows instalado:

```powershell
.\installers\labels\build_exe.ps1
```

El script instala PyInstaller y las dependencias, produce `dist\Atlas Labels.exe` y deja el acceso directo `Atlas Labels` en el escritorio.

## Notas

- El `.exe` no está firmado; Windows Defender o el antivirus pueden pedir confirmación la primera vez. Si lo bloquea, agrega una exclusión para `dist\Atlas Labels.exe`.
- El binario pesa entre 15 y 25 MB porque incluye Python y Tkinter.
- Hay que regenerarlo cada vez que cambie el código de `atlas_labels/`.
- La impresora preferida se sigue guardando en `%USERPROFILE%\.atlas_labels.json`.
```

Agregar a `.gitignore`, bajo `build/`:

```
*.spec
```

En `atlas_labels/README.md`, en la sección "## App de escritorio", agregar al final:

```markdown
Para abrirla con doble clic sin terminal, genera el ejecutable con `installers\labels\build_exe.ps1` (ver `installers/labels/README.md`).
```

- [ ] **Step 4: Verificación**

En Linux: `uv run --no-project --with openpyxl python -c "import ast; ast.parse(open('launch_gui.py').read()); print('ok')"` y la suite completa sin cambios.

En Windows (desde WSL, el controlador): `powershell.exe -NoProfile -ExecutionPolicy Bypass -File installers/labels/build_exe.ps1`; comprobar que existe `dist/Atlas Labels.exe` y el `.lnk` en el escritorio; abrir el `.exe` y cargar el catálogo.

- [ ] **Step 5: Commit**

```bash
git add launch_gui.py installers/labels/build_exe.ps1 installers/labels/README.md .gitignore atlas_labels/README.md
git commit -m "atlas_labels: ejecutable de doble clic con PyInstaller y acceso directo

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
