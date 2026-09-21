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
        lines.append(f"^BCN,{BARCODE_HEIGHT},Y,N,N,A^FD{spec.data}^FS")
    return lines


def build_label(product: Product, copies: int = 1, spec: BarcodeSpec | None = None) -> str:
    spec = spec if spec is not None else detect(product.barcode)
    if spec is None:
        raise ValueError(f"{product.sku or product.name}: sin código de barras")

    variant = fit_text(
        " / ".join(x for x in (zpl_safe(product.size), zpl_safe(product.color)) if x),
        15,
        TEXT_WIDTH,
    )

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
    price = fit_text(product.price_display, 22, PRICE_WIDTH)
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
