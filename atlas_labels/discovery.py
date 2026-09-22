"""Encuentra el catálogo exportado más reciente y dice de cuándo es.

El export de Atlas One se llama `catalogo_YYYY-MM-DD.xlsx` y cae en la carpeta de
descargas. Sin esto, la app espera a que alguien navegue hasta el archivo, y nada
avisa cuando se está imprimiendo con un catálogo de la semana pasada.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Iterable

EXTENSIONS = (".xlsx", ".xlsm", ".csv")
PREFIXES = ("catalogo", "catálogo")
# La fecha del export, en el nombre: catalogo_2026-09-21.xlsx
_DATE_IN_NAME = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# Días de antigüedad a partir de los cuales el catálogo se marca en la interfaz.
AVISO_DESDE = 2
VIEJO_DESDE = 7


def _is_catalog(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith(PREFIXES) and path.suffix.lower() in EXTENSIONS


def catalog_date(path) -> date:
    """Fecha del catálogo: la del nombre si la trae, si no la del archivo.

    La del nombre manda porque copiar o mover el archivo actualiza su mtime, y
    eso haría pasar por nuevo un export viejo.
    """
    path = Path(path)
    match = _DATE_IN_NAME.search(path.name)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    return date.fromtimestamp(path.stat().st_mtime)


def find_latest_catalog(directories: Iterable) -> Path | None:
    """El catálogo más reciente de esos directorios, o None si no hay ninguno."""
    candidates = []
    for directory in directories:
        directory = Path(directory)
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue  # No existe, o no se puede leer: no es un error, solo no hay nada ahí.
        for entry in entries:
            if entry.is_file() and _is_catalog(entry):
                candidates.append(entry)

    if not candidates:
        return None
    return max(candidates, key=lambda p: (catalog_date(p), p.stat().st_mtime))


def default_search_dirs(home=None, last_used=None) -> list[Path]:
    """Dónde buscar el catálogo, en orden de preferencia.

    `last_used` va primero porque si alguien guarda los catálogos fuera de
    Descargas, ese es el lugar donde de verdad están.
    """
    home = Path.home() if home is None else Path(home)
    dirs = [home / "Downloads", home / "Descargas"]
    if last_used is not None:
        last_used = Path(last_used)
        dirs = [last_used] + [d for d in dirs if d != last_used]
    return dirs


def describe_age(catalog_day: date, hoy: date) -> tuple[str, str]:
    """Texto legible y severidad ('ok', 'aviso', 'viejo') de la antigüedad."""
    days = max((hoy - catalog_day).days, 0)  # El reloj de la caja puede estar atrasado.

    if days == 0:
        cuando = "hoy"
    elif days == 1:
        cuando = "ayer"
    else:
        cuando = f"hace {days} días"

    if days >= VIEJO_DESDE:
        severidad = "viejo"
    elif days >= AVISO_DESDE:
        severidad = "aviso"
    else:
        severidad = "ok"

    return f"del {catalog_day.day} de {MESES[catalog_day.month - 1]} — {cuando}", severidad
