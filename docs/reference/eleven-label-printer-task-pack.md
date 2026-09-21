# TASK PACK — ELEVEN LABEL PRINTER v1

## Contexto
Eleven Boutique necesita imprimir etiquetas desde CSV/Excel sin ZebraDesigner Professional. Impresora: Zebra GX420t USB en Windows. Etiqueta: 51 x 25 mm. Resolución esperada: 203 dpi.

## Objetivo
Construir una aplicación local Windows que:
- cargue CSV y XLSX;
- muestre productos;
- busque por SKU, código, marca o nombre;
- permita seleccionar registros;
- permita cantidad manual o tomar CANTIDAD/Existencia;
- genere ZPL para 51 x 25 mm;
- envíe RAW ZPL a la Zebra;
- muestre errores entendibles.

## Stack
- Python 3.11+
- Tkinter inicialmente
- pywin32 / win32print
- pandas/openpyxl para XLSX en v1.1
- SQLite para historial en v1.1

## Datos
Campos base:
SKU
CODIGO_BARRAS
MARCA
PRODUCTO
NOMBRE_VENTA
TALLA
COLOR
PRECIO
PRECIO_TEXTO
CANTIDAD
GENERO
MODELO
MATERIAL

CODIGO_BARRAS siempre debe tratarse como string.

## Layout
Etiqueta horizontal 51 x 25 mm.
Jerarquía:
1. Marca
2. Nombre de venta
3. Talla / Color
4. Barcode Code 128
5. Código legible
6. SKU
7. Precio

Debe adaptarse a campos vacíos y recortar nombres largos sin salirse del área.

## ZPL
Usar:
^PW408
^LL200
^CI28
^PQn

Code 128 para el MVP.

## MVP
- Importar CSV.
- Tabla de productos.
- Búsqueda.
- Selección de fila.
- Cantidad manual.
- Botón 'Usar existencia'.
- Vista previa textual del ZPL.
- Configuración del nombre de impresora.
- Impresión RAW.
- Manejo de errores.

## v1.1
- selección múltiple;
- impresión por lote;
- checkboxes;
- soporte XLSX;
- vista previa gráfica;
- guardar impresora preferida;
- SQLite con historial;
- reimpresión;
- validación de códigos;
- perfiles de plantilla.

## Integración Atlas ONE
Crear posteriormente un servicio local:
POST /print/label
POST /print/batch
GET /printers
GET /health

Payload:
{
  "sku": "MM-BLUS-MC-MUJ",
  "barcode": "2017000000822",
  "brand": "Miu Miu",
  "name": "Blusa manga corta",
  "size": "",
  "color": "",
  "price": "$1,500.00",
  "copies": 3
}

## Criterios de aceptación
- Abre el CSV real.
- No pierde dígitos ni ceros iniciales.
- Imprime físicamente en 51 x 25 mm.
- Barcode escaneable.
- Precio y SKU legibles.
- 5 copias producen exactamente 5 etiquetas.
- No falla con campos vacíos.
- La aplicación no se cierra ante errores de impresora.
- Se puede cambiar el nombre de impresora sin tocar código.

## Prioridad
1. Confiabilidad de impresión.
2. Correcto layout físico.
3. UX.
4. Impresión por lote.
5. Integración Atlas ONE.
