# atlas_labels

Imprime etiquetas de producto de 51 x 25 mm en una Zebra GX420t (203 dpi) a partir del catálogo que exporta Atlas One (`catalogo_YYYY-MM-DD.xlsx`) o de un CSV.

## Requisitos

- Python 3.10 o superior.
- `pip install -r requirements-labels.txt` (openpyxl; pywin32 solo en Windows).
- La impresora debe estar en **modo ZPL**. El nombre de la cola de Windows puede ser `ZDesigner GX420t (EPL)`, eso no importa: se imprime en RAW. Si la etiqueta de prueba no sale, la impresora está en EPL; cámbiala a ZPL con Zebra Setup Utilities.
- En Linux/macOS la cola debe existir en CUPS; se imprime con `lp -o raw`.

## Línea de comandos

```bash
python -m atlas_labels impresoras
python -m atlas_labels prueba --impresora "ZDesigner GX420t (EPL)"
python -m atlas_labels imprimir catalogo.xlsx --impresora "ZDesigner GX420t (EPL)" --dry-run
python -m atlas_labels imprimir catalogo.xlsx --sku CH-PLAY-EP-CH,CH-PLAY-EP-M --copias 2
python -m atlas_labels imprimir catalogo.xlsx --buscar "chrome" --hoja Plantilla
python -m atlas_labels previsualizar catalogo.xlsx --sku CH-PLAY-EP-CH
```

- Copias por defecto = columna `Stock`; las filas con 0 se omiten. `--copias N` fija N para todas.
- Filas sin código de barras se omiten y se listan en el resumen.
- Impresora: `--impresora`, luego la variable `ATLAS_LABELS_PRINTER`, luego la guardada por la app en `~/.atlas_labels.json`.

## App de escritorio

```bash
python -m atlas_labels.gui
```

Abre el catálogo, busca, selecciona varias filas (Ctrl o Shift), elige copias por existencia o fijas y pulsa "Imprimir seleccionados". La impresora elegida se recuerda.

## Columnas que se reconocen

| Campo | Encabezados aceptados (sin importar acentos, mayúsculas ni espacios) |
|---|---|
| SKU (obligatorio) | `SKU` |
| Nombre (obligatorio) | `NOMBRE_VENTA`, `Nombre`, `PRODUCTO` |
| Marca | `Marca` |
| Código de barras | `Codigo Barras`, `CODIGO_BARRAS`, `Barcode`, `Codigo` |
| Precio | `PRECIO_TEXTO`, `Precio Base`, `PRECIO` |
| Existencia | `Stock`, `CANTIDAD`, `Existencia` |
| Color | `Color` |
| Talla | `Talla` |

Trece dígitos con checksum válido se imprimen como EAN-13; cualquier otro texto como Code 128 (se quitan asteriscos y espacios).

## Uso en esta PC (Zebra por USB en Windows, repo abierto desde WSL)

La impresora está conectada al host Windows, así que el CLI y la app deben correr con el **Python de Windows**, no con el de WSL. Desde una terminal de WSL:

```bash
cd /mnt/c/Users/ecamp/Devs/Atlas-Print-Agent
python.exe -m pip install -r requirements-labels.txt      # una sola vez
python.exe -m atlas_labels impresoras                     # debe listar "ZDesigner GX420t (EPL)"
python.exe -m atlas_labels prueba --impresora "ZDesigner GX420t (EPL)"
PYTHONIOENCODING=utf-8 python.exe -m atlas_labels imprimir "C:\Users\ecamp\Downloads\catalogo_2026-09-21.xlsx" --dry-run --impresora "ZDesigner GX420t (EPL)"
python.exe -m atlas_labels.gui
```

- Las rutas de archivos van en formato Windows (`C:\...`) porque las abre el Python de Windows.
- `PYTHONIOENCODING=utf-8` evita que los acentos salgan como `�` cuando la salida pasa por la terminal de WSL. Desde PowerShell no hace falta.
- Para no escribir `--impresora` cada vez: `export ATLAS_LABELS_PRINTER="ZDesigner GX420t (EPL)"` en WSL, o `$env:ATLAS_LABELS_PRINTER="ZDesigner GX420t (EPL)"` en PowerShell. La app la guarda sola tras la primera impresión.
- Antes de un lote grande corre siempre `--dry-run`: el export completo de Atlas One genera cientos de etiquetas (copias = Stock). Usa `--sku` o `--buscar` para acotar, o `--copias N` para fijar copias.

## Tests

```bash
uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q
```
