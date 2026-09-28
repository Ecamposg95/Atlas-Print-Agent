"""Lee VERSION de main.py sin importarlo y la compara con el tag de la release.

Así no se publica un v3.1.0 que en /health se reporta como 3.0.0.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

MAIN = Path(__file__).resolve().parents[2] / "legacy" / "print_agent" / "core" / "main.py"
_PATRON = re.compile(r'^VERSION = "([^"]+)"$', re.M)


def leer_version(ruta: Path = MAIN) -> str:
    m = _PATRON.search(Path(ruta).read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"No se encontró VERSION en {ruta}")
    return m.group(1)


def tag_coincide(tag: str, version: str) -> bool:
    return tag == f"v{version}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verificar-tag", metavar="TAG")
    a = p.parse_args(argv)
    version = leer_version()
    if a.verificar_tag is None:
        print(version)
        return 0
    if tag_coincide(a.verificar_tag, version):
        print(f"OK: {a.verificar_tag} coincide con VERSION = \"{version}\"")
        return 0
    print(
        f"El tag {a.verificar_tag} no coincide con VERSION = \"{version}\" de main.py. "
        "Sube VERSION o corrige el tag.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
