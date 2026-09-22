# Atlas Print Agent

Agente de impresión unificado para los sistemas de Atlas Technologies (Atlas One, Atlas Rmazh y los que sigan). Corre en la PC del cajero, expone una API local en `https://localhost:9100` y escribe bytes ESC/POS en impresoras térmicas de 58 y 80 mm por USB, red o Bluetooth.

## Por qué existe este repo

Cada producto llevaba su propia copia del agente en `tools/print_agent/` y las copias ya habían divergido. Aquí se consolida en un solo proyecto, con el objetivo de que:

- Funcione en Ubuntu, Windows y macOS.
- Se instale con doble clic y arranque solo con el sistema, sin terminal.
- Bluetooth clásico (SPP) funcione de forma confiable.
- Sea seguro: emparejamiento navegador-agente y orígenes configurables, nada quemado en el código.
- Conserve la API v3 actual para que los frontends existentes no cambien.

El diseño completo, los hallazgos de la auditoría de ambos repos y el contrato de API están en [`docs/superpowers/specs/2026-09-21-atlas-print-agent-design.md`](docs/superpowers/specs/2026-09-21-atlas-print-agent-design.md).

## Estado

Fase de diseño. El código nuevo todavía no existe. Lo que hay:

| Ruta | Qué es |
|---|---|
| `legacy/print_agent/` | Agente v3.0.0 importado tal cual desde Atlas One (la versión más reciente). Sigue funcionando y sirve de referencia durante la migración. |
| `legacy/tests/` | Tests autocontenidos de CORS y validación de nombres de cola, importados de Rmazh. Contra la base de Atlas One fallan 3 de 30 a propósito: marcan lo que Rmazh acepta (`BT:`, UNC) y Atlas One no. El agente unificado debe pasarlos todos. |
| `docs/superpowers/specs/` | Diseño del proyecto unificado. |
| `docs/reference/` | Notas de campo sobre CUPS y térmicas en Ubuntu, runbook de autoarranque y auditoría de impresión offline. |
| `atlas_labels/` | Módulo de etiquetas ZPL para Zebra GX420t desde el catálogo Excel de Atlas One. CLI y app de escritorio. Independiente del agente; ver [`atlas_labels/README.md`](atlas_labels/README.md) y su [diseño](docs/superpowers/specs/2026-09-21-etiquetas-zebra-design.md). |

## Arquitectura (sin cambios respecto a v3)

```
Backend del producto ──(bytes ESC/POS en base64, sesión autenticada)──▶ Navegador
Navegador ──POST https://localhost:9100/print {printer_name, content_base64}──▶ Agente ──▶ Impresora
```

El agente nunca habla con el backend y el backend nunca habla con el agente. La generación del ticket se queda en cada producto; el agente solo entrega bytes al dispositivo.

## Correr el agente legado

Requiere Python 3.10 o superior.

```bash
cd legacy/print_agent/core
python -m venv venv && source venv/bin/activate   # en Windows: venv\Scripts\activate
pip install -r requirements.txt                     # requirements_linux.txt o requirements_mac.txt según el sistema
python main.py
```

Variables de entorno: `ATLAS_AGENT_HOST` (default `127.0.0.1`), `ATLAS_AGENT_PORT` (default `9100`), `ATLAS_AGENT_ORIGINS` (orígenes CORS adicionales separados por coma).

Los detalles de instalación por sistema están en `legacy/print_agent/README.md`.

## Correr los tests legados

```bash
uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography --with pytest \
  python -m pytest legacy/tests -q
```

Resultado esperado hoy: 27 pasan, 3 fallan (ver tabla de arriba).

## Etiquetas Zebra desde Excel

```bash
pip install -r requirements-labels.txt
python -m atlas_labels imprimir catalogo.xlsx --impresora "ZDesigner GX420t (EPL)" --dry-run
python -m atlas_labels.gui
```

Detalles en [`atlas_labels/README.md`](atlas_labels/README.md).

### Abrir la app en esta PC (Windows)

Doble clic en `C:\Users\ecamp\Devs\Atlas-Print-Agent\dist\Atlas Labels.exe`. No necesita terminal ni Python;
adentro se abre el catálogo que hayas descargado con el botón "Abrir catálogo".

Si cambia el código de `atlas_labels/`, hay que regenerar el .exe: en PowerShell, desde la raíz del repo,
`.\installers\labels\build_exe.ps1`.

## Siguientes pasos

1. Aprobar sección por sección el diseño del spec.
2. Escribir el plan de implementación.
3. Reestructurar el agente en el paquete `atlas_print_agent/` con backends CUPS, spooler de Windows y Bluetooth.
4. Empaquetar con PyInstaller e instaladores nativos (`.deb`, `.exe`, `.pkg`) desde GitHub Actions.
5. Cambiar el endpoint `download-agent` de cada producto para que redirija a las releases de este repo.
