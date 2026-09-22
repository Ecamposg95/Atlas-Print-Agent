# TASK PACK — ATLAS ONE → ATLAS-PRINT-AGENT (2026-09-22)

## Para quién es

Para el agente que trabaja en el repo de **Atlas One**. Son cinco tareas que desbloquean trabajo en
**Atlas-Print-Agent** (github.com/Ecamposg95/Atlas-Print-Agent, público). Cuatro son de **averiguar**, una sola
es de cambiar código.

El contexto completo está en [`peticiones-a-atlas-one.md`](peticiones-a-atlas-one.md); este pack es la versión
ejecutable, ordenada por cuánto desbloquea. **T1 y T2 salen del mismo comando y son las que más valen.**

## Reglas del intercambio

- **No modifiques nada en Atlas-Print-Agent.** La regla del dueño (2026-09-22) corre en las dos direcciones: ese
  repo no toca el tuyo y el tuyo no toca ese. Las respuestas se reportan, no se commitean allá.
- **No pegues credenciales en la respuesta.** Ni llaves de API, ni tokens, ni contraseñas. Ninguna tarea las
  necesita en el reporte.
- **No pegues datos de productos reales.** De T2 se necesita **solo la primera línea** del CSV (los nombres de
  las columnas), nunca filas de datos.
- **T4 no se prueba ejecutando.** Es un `POST` que escribe en la base. Se contesta leyendo el código.

## Prioridad

| # | Tarea | Tipo | Desbloquea |
|---|---|---|---|
| **T1** | ¿Una llave de API sirve como bearer? | Averiguar (1 comando) | **Que la app de etiquetas traiga el catálogo sola** |
| **T2** | Columnas de `labels.csv` | Averiguar (mismo comando) | Lo mismo que T1 |
| T3 | Confirmar las dos afirmaciones sobre Bluetooth | Leer código | Cerrar un hallazgo a medio verificar |
| T4 | Qué hace `assign-missing` | Leer código | Saber si una instrucción manual está obsoleta |
| T5 | Que la UI no ofrezca Bluetooth | **Cambiar código** | Nada nuestro; afecta a cajas reales hoy |

---

## T1 — ¿Una llave de API sirve como credencial bearer?

**Por qué importa.** Queremos que la app de etiquetas descargue el catálogo sola y se acabe el "exporta el xlsx a
mano". Según `openapi.json`, el único esquema de seguridad es `OAuth2PasswordBearer`, y ningún endpoint declara
cabecera de API key. Si las llaves no sirven, la única vía sería guardar **usuario y contraseña del dueño** en
una PC de almacén — y eso no lo vamos a hacer. Preferimos dejar la carga desde Excel.

**Pasos.**

1. Crea (o toma) una llave en `/api/platform/api-keys` con los scopes mínimos para leer productos.
2. Corre esto — es un `GET`, no escribe nada:

```bash
curl -s -o labels.csv -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer <LLAVE_DE_API>" \
  "https://app.atlasone.com.mx/api/products/export/labels.csv?only_with_stock=true"
```

3. Si da **401**, repítelo con un token de sesión normal (de las DevTools del navegador) para separar las dos
   cosas: "la llave no sirve" es distinto de "el endpoint no funciona".

**Qué reportar:** el código HTTP de cada intento. **La llave y el token no.**

**Si da 401 con llave y 200 con sesión:** ahí tienes una petición de cambio para Atlas One — que las llaves de
`/api/platform/api-keys` valgan como credencial en `/api/products/export/labels.csv` y, idealmente, en
`/api/products/*`. No la implementes sin consultarlo con el dueño; es una decisión de seguridad suya.

## T2 — Columnas de `labels.csv`

**Por qué importa.** `atlas_labels` ya lee CSV. Si las columnas encajan con lo que espera, **no hay que escribir
ningún cliente de catálogo**: se descarga el archivo y sigue el flujo de hoy.

**Pasos.** Del `labels.csv` que bajó T1:

```bash
head -1 labels.csv
wc -l labels.csv
```

**Qué reportar:** esa primera línea completa y el número de filas. **Ninguna fila de datos.**

**Contra qué se compara** (lo que la etiqueta necesita por producto):

| Campo | Para qué |
|---|---|
| SKU | Identificación y filtros |
| Código de barras | **Lo que se imprime.** 13 dígitos con checksum válido → EAN-13; cualquier otro texto → Code 128 |
| Marca, Nombre | Líneas de texto |
| Departamento | Filtro de la app |
| Talla, Color | Líneas de texto |
| Precio | Línea de precio |
| Existencia (stock) | **Copias por omisión:** una etiqueta por unidad en existencia |

Si falta alguno, dilo: se rellena desde `/api/products/` o se pide agregarlo al CSV.

## T3 — Confirmar las dos afirmaciones sobre Bluetooth

**Por qué importa.** Tu análisis del 2026-09-22 se verificó contra el código de Atlas-Print-Agent y **es
correcto**: no hay transporte Bluetooth, cero referencias a `serial`, `rfcomm` o `bluetooth`, y la escritura
siempre acaba en `win32print.OpenPrinter(nombre)` o `lp -d nombre`. Pero quedaron **dos mitades sin verificar**,
porque desde ese repo no se leyó el tuyo:

1. **En Rmazh:** ¿`_QUEUE_NAME_RE` en `tools/print_agent/` acepta el prefijo `BT:`? Se dedujo de un test
   importado, no de su `main.py`.
2. **En el frontend:** ¿`PrinterSettings.tsx` guarda realmente `BT:<nombre>` y ofrece elegir impresoras
   Bluetooth? Se dedujo del docstring de un test.

**Pasos.** Leer, no cambiar:

```bash
grep -rn "_QUEUE_NAME_RE\|BT:" tools/print_agent/
grep -rn "BT:" src/ --include=*.tsx --include=*.ts
```

**Qué reportar:** el regex literal de Rmazh, y si la UI ofrece o no las Bluetooth.

**Atajo que NO debes tomar:** en `legacy/tests/` del otro repo hay un test que afirma que `BT:Impresora 58` pasa
la validación de nombres. Hacerlo verde **ampliando el regex no arregla nada**: cambiaría un error visible
(HTTP 400) por un fallo silencioso de spooler. Ese test afirma validación, no impresión.

## T4 — ¿Qué hace exactamente `assign-missing`?

**Por qué importa.** En Atlas-Print-Agent está registrado que asignar los códigos internos de la serie **EAN-13
con prefijo `20170000`** era un trámite manual del dueño: tomar el mayor base de 12 dígitos en uso, sumar 1,
recalcular el checksum. Si `POST /api/products/barcodes/assign-missing` ya hace eso, esa instrucción está
obsoleta y se está repitiendo de más.

**⚠️ No lo ejecutes para averiguarlo.** Es un `POST` que escribe códigos de barras en productos reales. Un código
mal asignado no se descubre hasta que la tienda no puede cobrar. **Contéstalo leyendo el código.**

**Qué reportar:** ¿respeta la serie `20170000`? ¿Cómo elige el siguiente número? ¿Recalcula el checksum EAN-13?
¿Es por organización?

## T5 — Que la UI no ofrezca impresoras Bluetooth

**El único cambio de código de este pack, y el único que afecta a usuarios hoy.**

Mientras el agente no tenga transporte Bluetooth, la pantalla de impresoras **no debería dejar elegir una**, o
debería avisar claramente de que no imprimirá tickets. Hoy la cajera puede emparejarla, verla en la lista,
seleccionarla y descubrir que no sale papel, sin ninguna pista del porqué.

**Esto es reversible y temporal.** El §5.2 del diseño del agente unificado contempla Bluetooth clásico SPP con
`pyserial` sobre `/dev/rfcomm*`, `COM*` o `/dev/tty.*`, y las colas aparecerán en `/printers` con prefijo `BT:`
— **se elegirán igual que cualquier otra, sin cambios en el frontend**. Cuando eso exista, revertir T5 es quitar
el aviso.

**Consúltalo con el dueño antes de hacerlo:** decide él si prefiere ocultar la opción o solo advertir.

---

## Lo que NO hay que hacer todavía

Las peticiones **1, 2 y 3** de [`peticiones-a-atlas-one.md`](peticiones-a-atlas-one.md) —redirigir
`download-agent` a las releases, ajustar `test_print_agent_bundle.py` y cambiar el texto de
`PrinterSettings.tsx`— **esperan a que existan las releases del agente**. Todavía no existen. Hacerlas ahora deja
la pantalla apuntando al vacío.

Y en ningún caso, ni ahora ni después:

- **Reimplementar EAN-13 o Code 128 en Atlas One.** Viven en `atlas_labels/barcode.py` y son la única fuente de
  verdad. Ese repo existe precisamente porque el agente estaba copiado en dos productos y las copias
  divergieron.
- **Meterle lógica de etiquetas al agente de impresión.** Es un tubo de bytes.
- **Romper la API v3 del agente.** Los frontends tienen `https://localhost:9100` quemado sin descubrimiento.

## Plantilla de respuesta

Contéstale al dueño con esto y él lo trae al otro repo:

```
T1 — llave de API como bearer:  HTTP ___   (con token de sesión: HTTP ___)
T2 — primera línea de labels.csv:
     <pegar aquí, solo la línea de encabezados>
     filas: ___
T3 — regex de Rmazh: ___________
     ¿la UI ofrece impresoras Bluetooth?: sí / no
T4 — assign-missing: ¿serie 20170000? sí/no   ¿cómo elige el siguiente?: ______
     ¿recalcula checksum EAN-13?: sí/no
T5 — ¿se aplicó?: sí / no / pendiente de decisión del dueño
```

## Criterios de aceptación del pack

- T1 y T2 contestadas con códigos HTTP reales y la línea de encabezados: **con eso se diseña e implementa el
  camino completo de etiquetas.**
- T3 y T4 contestadas leyendo código, sin ejecutar nada que escriba.
- Ninguna credencial ni dato de producto real en la respuesta.
- Cero commits en Atlas-Print-Agent.
