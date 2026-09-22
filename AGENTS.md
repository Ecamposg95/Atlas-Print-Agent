# AGENTS.md — cómo trabajar en este repo

Guía para cualquier agente de IA que edite código **aquí dentro**. Si en cambio trabajas en un repo que
*consume* el agente de impresión (Atlas One, Atlas Rmazh, Atlas Booking), lo tuyo es
[`docs/integracion-agentes.md`](docs/integracion-agentes.md), no este archivo.

## Qué es este repo en tres líneas

Dos herramientas de impresión para tiendas de Atlas Technologies, sin relación entre sí más que el objetivo:
**`legacy/print_agent/`** es el agente HTTPS local que escribe tickets ESC/POS desde el navegador de la caja, y
**`atlas_labels/`** es el paquete que convierte el catálogo Excel de Atlas One en etiquetas ZPL para una Zebra
GX420t. El agente está en migración hacia un paquete unificado; las etiquetas están terminadas y en uso diario.

## Qué puedes tocar y qué no

| Ruta | Regla |
|---|---|
| `atlas_labels/`, `tests/labels/` | **Desarrollo normal.** Aquí es donde se trabaja hoy. |
| `installers/labels/` | Tocar solo junto con un cambio de empaquetado. Tras cambiar `atlas_labels/` hay que **regenerar el `.exe`**. |
| `legacy/print_agent/` | **Congelado.** Es la referencia de campo durante la migración: se lee, no se le agregan features. Un arreglo aquí solo si algo está roto en producción hoy. |
| `legacy/tests/` | **No los "arregles".** 3 de 30 fallan a propósito (ver más abajo). |
| `docs/superpowers/specs/` | Diseños aprobados. Si la implementación se aparta del spec, se actualiza el spec y se anota el *ruling*. |
| `dist/`, `build/`, `*.spec` | Ignorados por git. No los versiones. |

## Comandos

```bash
# Tests de etiquetas — 122 pasan
uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q

# Tests del agente legado — 27 pasan, 3 fallan a propósito
uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography --with pytest \
  python -m pytest legacy/tests -q

# Agente en local
cd legacy/print_agent/core && python main.py     # https://127.0.0.1:9100

# App de etiquetas
python -m atlas_labels.gui
python -m atlas_labels imprimir catalogo.xlsx --dry-run --impresora "ZDesigner GX420t (EPL)"

# Regenerar el .exe (PowerShell, desde la raíz)
.\installers\labels\build_exe.ps1
```

## Invariantes: romper uno rompe producción

1. **La API v3 del agente es compatible hacia atrás, sin excepción.** Los frontends de Atlas One y Rmazh tienen
   `AGENT_BASE = 'https://localhost:9100'` **quemado en el código**, sin descubrimiento. Un endpoint renombrado
   deja cajas sin imprimir y no hay forma de avisarles. El contrato completo está en
   [`docs/integracion-agentes.md`](docs/integracion-agentes.md).
2. **El agente no genera tickets.** Recibe base64 y lo escribe en el dispositivo. La clase `PosPrinter` que arma
   los bytes ESC/POS vive en el backend de cada producto porque depende de su modelo de dominio, y ahí se queda.
   Lo mismo con `PrintJob`, el PIN de reimpresión y la configuración de ticket por sucursal.
3. **`zpl.layout()` es la única fuente de verdad de la etiqueta.** `zpl.build_label()` la traduce a ZPL y
   `render.draw()` la dibuja en el canvas. Si agregas un elemento en uno solo de los dos, la vista previa deja de
   corresponder a lo que sale impreso — que es exactamente el bug que la v2 vino a matar.
4. **Los 3 tests legados que fallan son el criterio de aceptación de la migración, no basura.** Marcan lo que
   Rmazh acepta y Atlas One todavía no: prefijo `BT:` para Bluetooth, nombres UNC (`\\PC-CAJA\POS-80`) y el
   rechazo de un dominio propio sin `ATLAS_AGENT_ORIGINS`. El agente unificado debe pasar los 30 — **y aun así
   eso no basta**: ver el punto siguiente.
5. **No hagas verde el test de `BT:` añadiendo `:` al regex.** Ese test afirma que el nombre pasa la
   *validación*, no que se imprima. **Hoy no existe transporte Bluetooth**: cero referencias a `serial`,
   `rfcomm` o `bluetooth` en `main.py`, y la escritura siempre acaba en `win32print.OpenPrinter(nombre)` o
   `lp -d nombre`. Ampliar el regex convertiría un 400 visible en un fallo silencioso de spooler — el producto
   quedaría peor y el test, verde. Bluetooth necesita el backend del §5.2 del diseño del agente unificado.
   Confirmado el 2026-09-22 a partir de un análisis del agente de Atlas One.
6. **Todo string visible al usuario va en español.** Es personal de tienda, no desarrolladores.

## Convenciones

- **Commits en español**, en imperativo y con el módulo al frente: `atlas_labels: copias por fila ligadas al
  producto y no al SKU`. Cada commit termina con la línea `Co-Authored-By:` del modelo que lo escribió.
- **TDD.** Test que falla, luego implementación. Las suites de este repo se escribieron así y se mantienen así.
- **Ningún módulo de lógica importa Tkinter ni toca la impresora.** `catalog`, `barcode`, `zpl`, `batch` y
  `render` se prueban con dobles; `printer` y `gui` son la única frontera con el sistema.
- **Diseño antes de código.** Feature nueva → spec en `docs/superpowers/specs/YYYY-MM-DD-<tema>-design.md`,
  aprobado por el dueño, luego plan, luego implementación.
- Módulos pequeños con una sola responsabilidad. Si un archivo crece mucho, está haciendo de más.

## Trampas conocidas (ya nos costaron tiempo)

- **La Zebra en modo EPL.** Que la cola de Windows se llame `ZDesigner GX420t (EPL)` da igual — se imprime en
  RAW. Pero si no sale nada, la impresora está físicamente en EPL y hay que cambiarla con Zebra Setup Utilities.
  Antes de depurar código, descarta esto.
- **Desde WSL, usa `python.exe`.** La Zebra cuelga del host Windows: el CLI y la app corren con el Python de
  Windows, con rutas `C:\...` y `PYTHONIOENCODING=utf-8` para que los acentos no salgan como `�`.
- **`--dry-run` antes de cualquier lote.** Las copias por defecto son la columna `Stock`; el export completo de
  Atlas One son cientos de etiquetas y papel real.
- **Los worktrees de subagentes parten de `main`, no de la rama actual**, y no pueden escribir fuera del
  worktree. Dale al agente un `git reset --hard <head-de-integración>` como primer paso y que deje su reporte
  dentro del worktree.
- **`git push` suele quedar bloqueado por el clasificador de permisos**, aun con autorización explícita. Deja el
  commit hecho y pide al dueño que corra `! git push origin main`.
- **200 no significa que salió papel.** Con la térmica apagada, Windows encola y el agente responde éxito. Es un
  hallazgo conocido (auditoría 2026-09-07, C-06), no algo que acabes de descubrir.
- **El género del catálogo se infiere del SKU**, porque el export no trae el dato: termina en `-MUJ` o contiene
  `-MUJ-` → "Mujer"; cualquier otro caso cuenta como "Hombre / sin especificar".

## El dato maestro no vive aquí

Los códigos de barras internos del catálogo (serie EAN-13 con prefijo `20170000`) son propiedad de **Atlas One**
(`app.atlasone.com.mx`), un repo aparte. Corregir el `.xlsx` exportado hace que la etiqueta se imprima, **pero no
que el producto escanee en el POS**. Cuando asignes o corrijas un código, avisa que falta el paso manual en Atlas
One antes de dar el trabajo por cerrado.

## Dónde seguir leyendo

| Documento | Para qué |
|---|---|
| [`README.md`](README.md) | Panorama y uso de las dos herramientas. |
| [`docs/integracion-agentes.md`](docs/integracion-agentes.md) | Contrato para los repos que consumen el agente. |
| [`docs/etiquetas-desde-atlas-one.md`](docs/etiquetas-desde-atlas-one.md) | Los dos caminos de las etiquetas (Excel local y UI en Atlas One), qué falta averiguar y qué tocar dónde. **Léelo antes de proponer mover las etiquetas a otro repo.** |
| [`docs/peticiones-a-atlas-one.md`](docs/peticiones-a-atlas-one.md) | Lo que este proyecto necesita de Atlas One y Rmazh, consolidado. **Cuando descubras que algo depende de otro repo, se anota ahí — no se va a arreglarlo allá.** |
| [`legacy/print_agent/README.md`](legacy/print_agent/README.md) | Operación real del agente v3: API, logs, errores del spooler. |
| [`atlas_labels/README.md`](atlas_labels/README.md) | CLI, mapeo de columnas del catálogo, uso desde WSL. |
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | Diseños aprobados de las tres piezas. |
| [`docs/reference/`](docs/reference/) | Notas de campo: CUPS en Ubuntu, autoarranque, impresión offline. |
