"""Empaqueta el agente con PyInstaller, en modo carpeta, para el sistema en el que corre.

Uso, desde la raíz del repo y con requirements-build.txt instalado:
    python installers/agent/construir.py

--onedir y no --onefile: con un instalador de por medio, --onefile solo cuesta
(descomprime en un temporal a cada arranque y deja carpetas _MEI huérfanas cada
vez que el proceso muere). Ver el plan 2026-09-28-autoarranque-multiplataforma.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parents[2]
CORE = RAIZ / "legacy" / "print_agent" / "core"
DIST = RAIZ / "dist" / "agent"
TRABAJO = RAIZ / "build" / "agent"


def nombre(sistema: Optional[str] = None) -> str:
    return "Atlas Print Agent" if (sistema or platform.system()) == "Darwin" else "atlas-print-agent"


def binario(sistema: Optional[str] = None) -> Path:
    sistema = sistema or platform.system()
    n = nombre(sistema)
    if sistema == "Darwin":
        return DIST / f"{n}.app" / "Contents" / "MacOS" / n
    return DIST / n / (n + (".exe" if sistema == "Windows" else ""))


def argumentos(sistema: Optional[str] = None) -> list[str]:
    sistema = sistema or platform.system()
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", nombre(sistema),
        "--paths", str(CORE),
        "--hidden-import", "main",
        "--hidden-import", "agent_state",
        "--hidden-import", "generate_cert",
        # uvicorn carga sus loops y protocolos por nombre: el análisis estático no los ve.
        "--collect-submodules", "uvicorn",
        "--distpath", str(DIST), "--workpath", str(TRABAJO), "--specpath", str(TRABAJO),
    ]
    if sistema in ("Windows", "Darwin"):
        args.append("--windowed")  # sin ventana de consola; el .app en macOS
    if sistema == "Darwin":
        args += ["--osx-bundle-identifier", "com.atlasone.print-agent"]
    args.append(str(CORE / "lanzador.py"))
    return args


def main() -> int:
    subprocess.run(argumentos(), check=True, cwd=RAIZ)
    b = binario()
    if not b.exists():
        print(f"No se generó {b}", file=sys.stderr)
        return 1
    print(b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
