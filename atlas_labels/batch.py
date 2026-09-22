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
