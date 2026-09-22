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
    department: str = ""

    @property
    def price_display(self) -> str:
        if self.price is not None:
            return f"${self.price:,.2f}"
        return self.price_text

    @property
    def gender(self) -> str:
        """Derivado del SKU: el export de Atlas One marca las prendas de mujer con -MUJ."""
        sku = self.sku.upper()
        return "Mujer" if sku.endswith("-MUJ") or "-MUJ-" in sku else "Hombre"


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
