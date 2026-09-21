# Etiquetas Zebra desde Excel: diseño de `atlas_labels`

**Fecha:** 2026-09-21
**Estado:** diseño aprobado; pendiente plan de implementación.

## 1. Problema

Eleven Boutique imprime etiquetas de producto (51 x 25 mm) en una Zebra GX420t por USB desde una PC Windows, sin ZebraDesigner. Existe un prototipo (`Eleven_Label_Printer_Starter/`, app Tkinter de un archivo) que lee CSV, genera ZPL y lo manda RAW con `win32print`. Le falta lo que se usa a diario:

- Leer el Excel que exporta Atlas One (`catalogo_YYYY-MM-DD.xlsx`), cuyas columnas no coinciden con las del CSV del prototipo.
- Imprimir varios productos de una vez, con copias según existencia.
- Funcionar fuera de Windows.
- Tests.

Además el prototipo tiene defectos de layout: recorta por número de caracteres y no por ancho físico, usa `…` (no existe en las fuentes ZPL nativas), y el precio va a coordenada fija sin alinear a la derecha, así que se encima con el SKU en precios largos.

## 2. Objetivo

Un paquete `atlas_labels/` en este repo, independiente del agente de impresión, con:

1. Lector de catálogo `.xlsx` y `.csv` que reconoce tanto el export de Atlas One como el CSV del prototipo.
2. Generador ZPL para 51 x 25 mm a 203 dpi con el layout del prototipo corregido.
3. Envío RAW en Windows (`win32print`) y en Linux/macOS (`lp -o raw`).
4. Un CLI para lotes y una app Tkinter para selección visual, ambos sobre la misma lógica.
5. Tests unitarios que corren sin impresora.

La lógica queda lista para exponerse después como endpoint del agente, pero eso no forma parte de esta versión.

## 3. Datos de entrada

### 3.1 Export de Atlas One

Hoja `Plantilla`, 45 columnas. Las que usa la etiqueta:

| Columna | Tipo observado | Uso |
|---|---|---|
| `SKU` | texto | SKU legible |
| `Nombre` | texto | nombre del producto |
| `Marca` | texto | marca |
| `Codigo Barras` | texto: EAN-13 (`2017000000013`) o libre (`*1A43KE*`) | código de barras |
| `Precio Base` | entero o decimal | precio |
| `Stock` | entero | copias por defecto |
| `Color` | texto, puede ir vacío | variante |
| `Talla` | texto, puede ir vacío | variante |

Las demás columnas (costo, tiers de precio, empaques) se ignoran. Hay una segunda hoja `Listas_Validacion` que no se lee.

### 3.2 CSV del prototipo

Campos `SKU, CODIGO_BARRAS, MARCA, PRODUCTO, NOMBRE_VENTA, TALLA, COLOR, PRECIO, PRECIO_TEXTO, CANTIDAD`.

### 3.3 Mapeo de columnas

Los encabezados se normalizan (minúsculas, sin acentos, sin espacios ni guiones bajos) y se resuelven por alias. Primer alias que exista gana.

| Campo `Product` | Alias (normalizados) |
|---|---|
| `sku` | `sku` |
| `name` | `nombreventa`, `nombre`, `producto` |
| `brand` | `marca` |
| `barcode` | `codigobarras`, `barcode`, `codigo` |
| `price` | `preciotexto`, `preciobase`, `precio` |
| `stock` | `stock`, `cantidad`, `existencia` |
| `color` | `color` |
| `size` | `talla` |

`sku` y `name` son obligatorios; si falta alguno, el lector falla con un mensaje que lista los encabezados encontrados. Los demás son opcionales y quedan vacíos.

Toda celda se lee como texto (`str(valor).strip()`), incluido el código de barras, para no perder ceros iniciales. Los números se convierten después, en su campo: `price` a `Decimal` si parsea (acepta `1800`, `1800.5`, `$1,800.00`), `stock` a entero, y si no parsea queda `0`. Las filas sin SKU y sin nombre se saltan.

Por defecto se lee la primera hoja del libro; `--hoja` o el selector de la app permiten otra.

## 4. Modelo

```python
@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    brand: str = ""
    barcode: str = ""
    price: Decimal | None = None
    price_text: str = ""     # texto original si no parseó como número
    stock: int = 0
    color: str = ""
    size: str = ""
```

`price_display` es una propiedad: `$1,800.00` si hay `price`, si no `price_text` tal cual, si no cadena vacía.

## 5. Código de barras (`barcode.py`)

`detect(text) -> BarcodeSpec | None`:

1. Se limpia el texto: quitar espacios y asteriscos en extremos.
2. Trece dígitos con checksum EAN válido → `EAN13`.
3. Cualquier otro texto no vacío → `CODE128` con los caracteres imprimibles ASCII (32 a 126); se descartan los demás. Máximo 20 caracteres; si excede, se recorta y se reporta como advertencia.
4. Vacío → `None`. La fila se omite en la impresión y se reporta como "sin código".

Trece dígitos con checksum inválido van a Code 128, no fallan.

Ancho del Code 128: se estima en módulos como `11 * simbolos + 35`, donde los dígitos en pares cuentan como un símbolo (subconjunto C) y el resto uno por carácter, más 3 símbolos de inicio, verificación y paro. Si `modulos * 2` cabe en 380 dots se usa `^BY2`; si no, `^BY1` y se reporta advertencia de que el código puede costar trabajo escanear. EAN-13 siempre va en `^BY2` (95 módulos = 190 dots).

## 6. ZPL (`zpl.py`)

Constantes: 203 dpi, `^PW408`, `^LL200`, `^CI28`. Se manda en UTF-8 para que acentos y `ñ` salgan con `^CI28`.

Layout (misma jerarquía que el prototipo):

| y (dots) | Contenido | Fuente | Ancho máximo (dots) |
|---|---|---|---|
| 8 | marca | A0N,22,22 | 384 |
| 34 | nombre | A0N,18,18 | 384 |
| 56 | talla / color (se omite si ambos vacíos) | A0N,15,15 | 384 |
| 76 | barcode con texto legible, alto 48, `^BY2` | EAN-13: `^BEN,48,Y,N`; Code 128: `^BCN,48,Y,N,N` | |
| 168 | SKU | A0N,14,14 | 240 |
| 162 | precio, alineado a la derecha con `^FB150,1,0,R` | A0N,22,22 | 150 |

Reglas:

- Escape: `^` y `~` en cualquier texto se reemplazan por espacio.
- Recorte por ancho: el ancho estimado de una cadena en fuente `A0` es `len * altura * 0.55` dots (factor calibrado sobre la fuente escalable de Zebra; se deja como constante ajustable). Si excede el ancho máximo se recorta hasta que quepa y se agrega `..`.
- Precio y SKU ya no se pueden encimar: el precio ocupa los 150 dots derechos y el SKU los 240 izquierdos.
- `copies` va en `^PQ`; mínimo 1.
- Un producto = un bloque `^XA … ^XZ`. `build_batch(items: list[tuple[Product, int]]) -> str` concatena los bloques.

## 7. Envío (`printer.py`)

- `list_printers() -> list[str]`: Windows con `win32print.EnumPrinters`; otros sistemas con `lpstat -a`.
- `send_raw(printer_name: str, data: bytes) -> None`: Windows con `OpenPrinter/StartDocPrinter("RAW")/WritePrinter`; otros con `lp -d NAME -o raw` recibiendo los bytes por stdin. El nombre de cola se valida con la misma lista blanca del agente (`[A-Za-z0-9_\-. ()]`).
- Errores se lanzan como `PrinterError` con mensaje en español (impresora no encontrada, pywin32 ausente, `lp` ausente, fallo del spooler). Nunca se traga la excepción.
- El lote completo va en un solo trabajo RAW.

Nota operativa que va al README: la GX420t debe estar en modo ZPL. La cola de Windows puede llamarse `ZDesigner GX420t (EPL)`; el nombre del driver no importa en RAW, pero si la impresora está configurada en EPL no imprime nada. El subcomando `prueba` sirve para verificarlo.

## 8. Selección y copias (`catalog.py` + `cli.py`)

`select(products, skus=None, search=None)`: filtra por lista exacta de SKU y/o por texto contenido en SKU, código, marca o nombre (sin distinguir mayúsculas).

`plan(products, copies=None) -> BatchPlan`: para cada producto decide copias y motivo de omisión:

- copias = `copies` si se dio override, si no `stock`.
- Se omite si copias ≤ 0 (motivo `sin existencia`) o sin barcode (motivo `sin código`).

`BatchPlan` tiene `items: list[(Product, copies)]`, `skipped: list[(Product, motivo)]`, `total_labels`.

## 9. CLI (`cli.py`, `python -m atlas_labels`)

```
imprimir ARCHIVO [--impresora N] [--copias N] [--sku A,B] [--buscar TEXTO] [--hoja H] [--dry-run]
previsualizar ARCHIVO --sku A [--copias N] [--hoja H]      # ZPL a stdout
impresoras
prueba [--impresora N]                                     # etiqueta fija de verificación
```

- `imprimir` muestra el resumen del plan (productos, etiquetas totales, omitidos con motivo), imprime y termina con código 0. Con `--dry-run` solo muestra el resumen. Sin nada que imprimir sale con código 1 y lo dice.
- Impresora: `--impresora` > variable `ATLAS_LABELS_PRINTER` > `printer_name` en `~/.atlas_labels.json` > error pidiendo una.
- Toda salida en español.

## 10. App Tkinter (`gui.py`)

Evolución del prototipo:

- Botón "Abrir catálogo" acepta `.xlsx` y `.csv`; si el libro tiene varias hojas, pregunta cuál.
- Impresora en lista desplegable alimentada por `list_printers()`, editable. La última elegida se guarda en `~/.atlas_labels.json`.
- Tabla con selección múltiple (`selectmode="extended"`), búsqueda que filtra por SKU, código, marca y nombre.
- Copias: opción "Usar existencia" (default) o número fijo para toda la selección.
- Vista previa ZPL del primer producto seleccionado.
- "Imprimir seleccionados" arma el `BatchPlan`, muestra el resumen con omitidos antes de mandar, y al terminar confirma cuántas etiquetas se enviaron.
- Errores de lectura o impresión salen en `messagebox`; la app no se cierra.

La GUI no tiene tests automáticos; su lógica de negocio vive en los módulos que sí los tienen.

## 11. Pruebas (`tests/labels/`)

- `test_catalog.py`: xlsx generado con openpyxl en el test con los encabezados de Atlas One; CSV con los del prototipo; encabezados faltantes; ceros iniciales conservados; precio `$1,800.00` y `1800` parsean igual; filas vacías se saltan.
- `test_barcode.py`: EAN-13 válido, EAN-13 con checksum malo → Code 128, `*1A43KE*` → `1A43KE`, vacío → `None`, recorte a 20.
- `test_zpl.py`: bloque contiene `^PW408`, `^LL200`, `^CI28`, `^PQn`; escape de `^~`; nombre largo se recorta y no contiene `…`; precio con `^FB`; variante omitida si vacía; `build_batch` concatena N bloques.
- `test_printer.py`: `send_raw` en no-Windows invoca `lp -d NAME -o raw` con los bytes en stdin (subprocess falso); nombre de cola inválido lanza `PrinterError`; sin `lp` lanza `PrinterError`.
- `test_cli.py`: `--dry-run` sobre un xlsx de prueba imprime el resumen correcto y no llama a `send_raw`.

Se corren con `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q`.

## 12. Dependencias y empaquetado

`openpyxl` para xlsx; `pywin32` solo en Windows. `requirements-labels.txt` en la raíz. Sin pandas. La app se lanza con `python -m atlas_labels.gui`. Empaquetar con PyInstaller queda para después, junto con el agente.

## 13. Fuera de alcance

Historial en SQLite y reimpresión, vista previa gráfica de la etiqueta, perfiles de plantilla o tamaños distintos de 51 x 25, endpoint `/labels` en el agente, EAN-8 y UPC-A. Se anotan como candidatos para la siguiente versión.

## 14. Migración del prototipo

`Eleven_Label_Printer_Starter/` se elimina del árbol una vez que `atlas_labels/` cubra lo que hacía. Su `TASK_PACK.md` se conserva como `docs/reference/eleven-label-printer-task-pack.md` por el contexto de negocio y la integración futura con Atlas One.
