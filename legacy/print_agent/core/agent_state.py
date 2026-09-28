"""Dónde vive el estado del agente y qué configuración aplica.

El certificado, agent.conf y el log viven FUERA de la carpeta de instalación:
así reinstalar o actualizar no toca el certificado y el navegador de la caja no
vuelve a pedir que se acepte. Ver
docs/superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md §5 y §7.

Solo biblioteca estándar: lo importan main.py y lanzador.py antes que FastAPI.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Callable, Mapping, Optional

APP_DIR_UNIX = "atlas-print-agent"
APP_DIR_MAC_WIN = "AtlasPrintAgent"
LINUX_SYSTEM_STATE = Path("/var/lib/atlas-print-agent")
CONF_NAME = "agent.conf"
CONF_KEYS = ("ATLAS_AGENT_PORT", "ATLAS_AGENT_ORIGINS", "ATLAS_AGENT_HOST")
DEFAULT_PORT = 9100
DEFAULT_HOST = "127.0.0.1"


def _writable(path: Path) -> bool:
    return path.is_dir() and os.access(path, os.W_OK)


def state_dir(
    system: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
    writable: Callable[[Path], bool] = _writable,
) -> Path:
    """Directorio del certificado y de agent.conf para este sistema."""
    system = system or platform.system()
    env = os.environ if env is None else env
    home = Path.home() if home is None else home

    override = env.get("ATLAS_AGENT_STATE_DIR", "").strip()
    if override:
        return Path(override)
    if system == "Windows":
        base = env.get("LOCALAPPDATA", "").strip()
        return (Path(base) if base else home / "AppData" / "Local") / APP_DIR_MAC_WIN
    if system == "Darwin":
        return home / "Library" / "Application Support" / APP_DIR_MAC_WIN
    # Linux. systemd exporta STATE_DIRECTORY cuando la unidad declara StateDirectory=.
    systemd_dir = env.get("STATE_DIRECTORY", "").split(":")[0].strip()
    if systemd_dir:
        return Path(systemd_dir)
    # El ícono de doble clic corre como la cajera, dueña de este directorio: así usa
    # el mismo certificado que el servicio en lugar de fabricar otro.
    if writable(LINUX_SYSTEM_STATE):
        return LINUX_SYSTEM_STATE
    xdg = env.get("XDG_STATE_HOME", "").strip()
    return (Path(xdg) if xdg else home / ".local" / "state") / APP_DIR_UNIX


def log_dir(
    system: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
    writable: Callable[[Path], bool] = _writable,
) -> Path:
    """Directorio del agent.log. Solo macOS lo separa del estado."""
    system = system or platform.system()
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    if system == "Darwin" and not env.get("ATLAS_AGENT_STATE_DIR", "").strip():
        return home / "Library" / "Logs" / APP_DIR_MAC_WIN
    return state_dir(system, env, home, writable)


def read_conf(path: Path) -> dict[str, str]:
    """Lee líneas CLAVE=valor. Nunca lanza: un agent.conf roto no debe tumbar al agente.

    Tolera lo que deja el Bloc de notas (BOM, CRLF) y comillas alrededor del valor.
    Solo se aceptan las claves de CONF_KEYS.
    """
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return {}
    conf: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key in CONF_KEYS:
            conf[key] = value
    return conf


def load_config(state: Path, env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """agent.conf del directorio de estado, con las variables de entorno encima.

    Una variable vacía cuenta como no puesta: las unidades de servicio viejas
    declaran ATLAS_AGENT_ORIGINS= sin valor y no deben tapar al archivo.
    """
    env = os.environ if env is None else env
    config = read_conf(Path(state) / CONF_NAME)
    for key in CONF_KEYS:
        value = env.get(key, "").strip()
        if value:
            config[key] = value
    return config


def port(config: Mapping[str, str]) -> int:
    try:
        value = int(config.get("ATLAS_AGENT_PORT", "").strip())
    except ValueError:
        return DEFAULT_PORT
    return value if 0 < value < 65536 else DEFAULT_PORT


def host(config: Mapping[str, str]) -> str:
    return config.get("ATLAS_AGENT_HOST", "").strip() or DEFAULT_HOST
