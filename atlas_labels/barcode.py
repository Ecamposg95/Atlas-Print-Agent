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
