# Atlas Labels: app de escritorio v2

**Fecha:** 2026-09-21
**Estado:** diseño aprobado; pendiente plan de implementación.
**Base:** paquete `atlas_labels/` en `main` (spec `2026-09-21-etiquetas-zebra-design.md`).

## 1. Objetivo

Mejorar la app Tkinter `python -m atlas_labels.gui` con lo que pidió el usuario tras usarla con la Zebra GX420t:

1. Filtros por departamento y género además del buscador.
2. Copias editables por fila, por defecto iguales a la existencia.
3. Vista previa gráfica de la etiqueta dibujada localmente, sin internet.
4. Un ejecutable `.exe` que abre la app con doble clic.

Nada de esto cambia el CLI ni el contrato con el agente de impresión.

## 2. Catálogo: departamento y género

`Product` gana el campo `department: str = ""` con alias `departamento` en `catalog.ALIASES`. Se lee como texto y se recorta.

`Product.gender` es una propiedad derivada del SKU, la única señal que trae el export de Atlas One:

- `"Mujer"` si el SKU en mayúsculas termina en `-MUJ` o contiene `-MUJ-`.
- `"Hombre"` en cualquier otro caso. En la interfaz la opción se etiqueta "Hombre / sin especificar" para no afirmar más de lo que se sabe.

`catalog.select` gana dos parámetros opcionales `department: str | None` y `gender: str | None`; coinciden por igualdad exacta tras `strip()`, sin distinguir mayúsculas. `None` o cadena vacía significa "todos".

## 3. Codificadores de barras (`barcode.py`)

Se añaden dos codificadores puros que devuelven la secuencia de módulos como cadena de `"1"` (barra) y `"0"` (espacio):

- `encode_ean13(digits: str) -> str`: 13 dígitos con checksum válido → 95 módulos (guardas 101, 6 dígitos izquierdos con paridad según el primer dígito, guarda central 01010, 6 derechos en R, guarda 101).
- `encode_code128(data: str) -> str`: texto ASCII 32–126. Elige subconjuntos como el modo automático de Zebra: empieza en C si la cadena arranca con una corrida de 4 o más dígitos (o es toda dígitos y de longitud par), si no en B; dentro de la cadena, una corrida de 4 o más dígitos se codifica en C (si la corrida es impar, el primer dígito va en B y el resto en C) con cambio de subconjunto (`CODE C` = 99 desde B, `CODE B` = 100 desde C). Incluye START B (104) o START C (105), dígito de verificación módulo 103 y STOP (106, patrón de 13 módulos incluida la barra final). Cada símbolo son 11 módulos salvo STOP.

`code128_modules(data)` pasa a devolver `len(encode_code128(data))`, exacto. `BarcodeSpec.width_dots` no cambia de firma. La regla `^BY2` si `módulos * 2 <= 358`, si no `^BY1`, se mantiene (358 = 380 dots útiles menos 22, un símbolo Code 128 a `^BY2`, de margen por si la impresora empaqueta distinto). El ZPL sigue emitiendo `^BCN,48,Y,N,N,A`; la impresora aplica la misma regla de subconjuntos, así que el ancho impreso coincide con el calculado.

## 4. Layout como única fuente (`zpl.py`)

Se separa el layout del texto ZPL:

```python
@dataclass(frozen=True)
class Text:
    x: int; y: int; height: int; text: str; width: int | None = None; align: str = "L"  # "L" | "R"

@dataclass(frozen=True)
class Bars:
    x: int; y: int; height: int; bits: str; module_width: int; interpretation: str

def layout(product: Product, spec: BarcodeSpec | None = None) -> list[Text | Bars]
def build_label(product: Product, copies: int = 1, spec: BarcodeSpec | None = None) -> str
```

`layout` produce exactamente los elementos de hoy con las mismas coordenadas, recortes y omisiones (variante vacía, precio vacío). `build_label` recorre la lista: `Text` sin `width` → `^FOx,y^A0N,h,h^FDtexto^FS`; `Text` con `width` y `align="R"` → `^FOx,y^A0N,h,h^FBw,1,0,R^FDtexto^FS`; `Bars` → las dos líneas `^FO…^BY…` y `^BE`/`^BC` según `spec.kind`. Para que `build_label` sepa el tipo, `Bars` lleva también `kind: str` y `data: str`.

Los 17 tests de `test_zpl.py` no cambian y son la red de seguridad del refactor. Se agregan tests de `layout` (número y tipo de elementos, coordenadas, `bits` con longitud 95 para EAN-13).

## 5. Dibujo de la etiqueta (`render.py`)

`render.draw(canvas, elements, scale: float)` dibuja los elementos sobre un `tkinter.Canvas`:

- Fondo blanco de `408*scale` por `200*scale` con borde gris.
- `Text`: `create_text` con fuente `("Helvetica", -int(height * scale * 0.8))` (tamaño en píxeles negativo para Tk), anclaje `nw`; con `align="R"` se ancla `ne` en `x + width`.
- `Bars`: un `create_rectangle` negro por cada corrida de `"1"`, ancho `module_width * scale` por módulo, altura `height * scale`; debajo la línea legible `interpretation` centrada en fuente `("Helvetica", -int(12 * scale))`.

El módulo importa `tkinter` solo dentro de la función para que el resto del paquete siga sin depender de Tk. No tiene tests automáticos; la geometría que sí se prueba está en `layout`.

## 6. Lote por fila (`batch.py`)

```python
def plan_items(items: list[tuple[Product, int]]) -> BatchPlan
def plan(products: list[Product], copies: int | None = None) -> BatchPlan  # usa plan_items
```

`plan_items` omite con `sin existencia` si copias ≤ 0 y con `sin código` si `detect` es `None`, recoge advertencias y llena `items`. Los 5 tests de `plan` no cambian; se añaden tests de `plan_items`.

## 7. App (`gui.py`)

Barra superior: "Abrir catálogo", Impresora (desplegable editable), Departamento (desplegable con "Todos" más los valores del catálogo ordenados), Género ("Todos", "Hombre / sin especificar", "Mujer"), Buscar. Cualquier cambio vuelve a filtrar con `select(..., department=, gender=, search=)`.

Tabla: columnas `SKU, Código, Marca, Nombre, Departamento, Talla, Color, Precio, Stock, Etiquetas`. `Etiquetas` arranca igual a `Stock` al cargar el catálogo y se guarda en un `dict[str, int]` por SKU que sobrevive a los filtros. Doble clic sobre la celda `Etiquetas` abre un `ttk.Entry` superpuesto; Enter o perder el foco guarda (entero ≥ 0, si no se ignora), Escape cancela. Botones bajo la tabla: "Usar existencia" (repone `Stock` en las filas seleccionadas, o en todas si no hay selección) y "Poner N a seleccionados" con un spinbox.

Vista previa: un `ttk.Notebook` con dos pestañas. "Etiqueta": canvas que se ajusta al espacio disponible; la escala se calcula del tamaño real del canvas (mínimo 0.25) y se redibuja en `<Configure>`, dibuja `layout` del primer producto seleccionado con `render.draw`; sin selección o sin código muestra el mensaje en gris. "ZPL": el texto crudo de `build_label`, como hoy.

"Imprimir seleccionados": arma `plan_items` con las copias de la columna `Etiquetas` de las filas seleccionadas, muestra el resumen con omitidos, pide confirmación y manda un solo trabajo. Guardar la impresora preferida sigue envuelto en `try/except OSError`.

Toda cadena visible en español. La app nunca se cierra por un error de lectura o impresión (se conservan los `except Exception` con diálogo).

## 8. Ejecutable (`installers/labels/`)

- `launch_gui.py` en la raíz del repo: `from atlas_labels.gui import main; main()`. Sirve de punto de entrada absoluto para PyInstaller y para `python launch_gui.py`.
- `installers/labels/build_exe.ps1`: instala `pyinstaller` y `requirements-labels.txt` en el Python de Windows, ejecuta `pyinstaller --noconsole --onefile --name "Atlas Labels" --collect-submodules atlas_labels launch_gui.py`, y crea `%USERPROFILE%\Desktop\Atlas Labels.lnk` apuntando a `dist\Atlas Labels.exe` con `WScript.Shell`. Imprime la ruta final.
- `installers/labels/README.md`: cómo generar el `.exe`, dónde queda, y que el antivirus puede marcar el binario sin firma.
- `dist/` y `build/` ya están en `.gitignore`; se añade `*.spec` generado por PyInstaller.

Verificación manual: doble clic en el acceso directo abre la app, abre el catálogo e imprime una etiqueta.

## 9. Pruebas

- `test_model.py`: `gender` para `X-MUJ`, `X-MUJ-2`, `X-MEZ`, `x-muj` en minúsculas.
- `test_catalog.py`: `department` mapeado desde `Departamento`; `select` por departamento y género.
- `test_barcode.py`: `encode_ean13("2017000000013")` mide 95, empieza en `101`, termina en `101`, guarda central en la posición 45; `encode_code128("1A43KE")` empieza con START B, checksum correcto verificado a mano, longitud `11*(n+2)+13`; `encode_code128("2017000000014")` empieza con START C y mide `11*(7+2)+13 = 112`; corrida corta de dígitos (`AB12CD`) se queda en B; `code128_modules` coincide con `len(encode_code128(...))`; el test de "13 dígitos cabe en la etiqueta" se mantiene.
- `test_zpl.py`: los 17 existentes intactos; `layout` devuelve `[Text marca, Text nombre, Text variante, Bars, Text sku, Text precio]` para el producto de prueba, omite variante y precio vacíos, `Bars.bits` mide 95 para EAN-13.
- `test_batch.py`: `plan_items` con copias 0, sin código, y mezcla.

## 10. Fuera de alcance

Filtros guardados, historial de impresiones, integración con el POS, firma del `.exe`, empaquetado para Linux/macOS.
