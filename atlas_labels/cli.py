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
