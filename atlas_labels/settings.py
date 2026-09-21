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
