# Etiquetas: los dos caminos

**Para el agente que retome esto en otra sesión.** Explica dónde está hoy la impresión de etiquetas, los dos
caminos que el dueño quiere que convivan, qué hay que averiguar antes de diseñar, y **exactamente qué habría que
modificar y dónde**. Decisión del dueño, 2026-09-22.

---

## 1. Lo que el dueño pidió, en sus palabras

> *"poder cargar desde un excel si descargo la app localmente, y/o usar una interfaz desde Atlas One"*

Los dos caminos, no uno **en vez del** otro. La app local no se va a jubilar: hay quien imprime etiquetas sin
sesión del POS abierta, y funciona hoy.

El dolor concreto que declaró, cuando se le preguntó qué estorba más: **exportar y abrir el xlsx**. No la
impresión, no la interfaz. El trámite del archivo, y que el archivo envejece sin que nadie se entere.

## 2. Dónde estamos hoy (2026-09-22)

`atlas_labels` son 1204 líneas repartidas en módulos de una sola responsabilidad, con 145 tests. **No habla con
la red**: lee un archivo del disco y escribe bytes en una cola local.

```
grep -rniE "requests|urllib|http|api" atlas_labels/*.py   →  vacío
```

Lo último que se agregó (commit `c4fa237`) es `discovery.py`: la app **carga sola el catálogo más reciente** que
encuentre en Descargas o en la última carpeta usada, y muestra de cuándo es — *"Catálogo del 21 de septiembre —
hace 1 día"*, en ámbar a los 2 días y en rojo a la semana. Eso quitó el paso de **buscar** el archivo y convirtió
"estoy imprimiendo con datos viejos" de error silencioso en aviso visible. **No quitó el paso de exportar**: eso
es lo que sigue.

## 3. La regla de oro, antes que cualquier diseño

**`zpl.py`, `barcode.py` y `render.py` son la única fuente de verdad de la etiqueta y se quedan en este repo.**

Son 331 líneas y la parte con más tests del proyecto: los codificadores EAN-13 y Code 128 están escritos a mano,
patrón por patrón (`CODE128_PATTERNS` son 106 patrones verificados uno a uno). `zpl.layout()` es además la única
fuente de la que salen *a la vez* el ZPL que se imprime y el dibujo de la vista previa — si divergen, la app
miente sobre lo que va a salir de la impresora.

**No reimplementes EAN-13 ni Code 128 en Atlas One.** Este repo existe porque el agente de impresión estaba
copiado en dos productos y las copias divergieron; repetir ese error con los codificadores de barras sería
exactamente la misma historia, con la diferencia de que un código de barras mal generado no se ve hasta que la
tienda no puede cobrar.

## 4. Lo que expone la API de Atlas One

Averiguado el 2026-09-22 leyendo `https://app.atlasone.com.mx/openapi.json` (el dueño lo descargó; el repo de
Atlas One **no está en esta máquina** — `Atlas-Rmazh` es el POS de otro cliente y no sirve de referencia).

**Existe un export hecho para etiquetas.** No hay que inventar nada:

| Endpoint | Para qué |
|---|---|
| `GET /api/products/export/labels.csv` | **El que importa.** Parámetros: `product_id` (opcional, uno solo), `only_with_stock` (bool, default `false`), cabecera `X-Organization-ID` |
| `GET /api/products/` | Listado paginado (`skip`/`limit`, default 100) con filtros por sucursal, marca y departamento |
| `GET /api/products/search` | Búsqueda (`q`), paginada |
| `GET /api/products/export/excel` | El export de catálogo completo — el `.xlsx` que hoy se descarga a mano |
| `GET /api/products/barcodes/missing-count`<br>`POST /api/products/barcodes/assign-missing` | Contar y asignar códigos de barras faltantes |

`atlas_labels` **ya lee CSV**, así que `labels.csv` se puede consumir con el `catalog.py` de hoy, sin cliente
nuevo. `only_with_stock=true` encaja además con que las copias por omisión sean la existencia.

> **Pendiente menor:** en este repo hay una nota de que asignar los códigos internos de la serie
> `2017000000xxx` era un trámite manual en Atlas One. Con `assign-missing` en la API puede que ya no lo sea.
> **Hay que verificarlo** —incluyendo si respeta esa serie— antes de seguir repitiendo la instrucción vieja.

### 4.1 Autenticación: el punto incómodo

El único esquema de seguridad declarado es **`OAuth2PasswordBearer`** con `tokenUrl: /api/auth/login`. El login
es `POST` en `application/x-www-form-urlencoded` con `username` y `password`, y devuelve `TokenWithUser`:
`access_token`, más `organization` (con su `id`, que es justo lo que pide la cabecera `X-Organization-ID`) y
`branch`.

**Atlas One sí tiene llaves de API** — `/api/platform/api-keys`, con `scopes`, listado por organización y
revocación. **Pero ningún endpoint del esquema declara una cabecera de API key**, y el único esquema de
seguridad es el bearer. Leído literalmente, eso significaría que una app de escritorio tendría que guardar
**usuario y contraseña** del dueño en una PC de almacén para poder renovar el token, que es un riesgo que no se
debe normalizar.

**Falta comprobarlo empíricamente**, porque el esquema no puede contestarlo: **¿se acepta una llave de API como
bearer?** Es un patrón común y no aparecería documentado. La prueba:

```bash
curl -s -o labels.csv -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer <LLAVE_DE_API>" \
  "https://app.atlasone.com.mx/api/products/export/labels.csv?only_with_stock=true"
```

- **200** → la app guarda una llave revocable con permisos acotados. Camino A despejado, sin tocar Atlas One.
- **401** → hay que pedir en Atlas One que las llaves sirvan para autenticar estos endpoints (§7). Mientras
  tanto, **no** guardar la contraseña del dueño: es preferible dejar la carga desde Excel y esperar.

### 4.2 Lo único que sigue sin saberse

**Qué columnas trae `labels.csv`.** El esquema no lo dice (el endpoint devuelve un archivo). Hay que descargar
uno y mirar su primera línea, y compararlo con lo que `catalog.map_columns()` espera: SKU, código de barras,
marca, nombre, departamento, talla, color, precio y existencia. Si faltan columnas, la diferencia se pide en
Atlas One (§7) o se rellena desde `/api/products/`.

## 5. Camino A — la app local trae el catálogo sola

**Es el camino corto y ataca el dolor declarado.** La app deja de depender de un archivo exportado a mano.

Qué tocar en este repo:

Con lo averiguado en el §4, es **más corto de lo que parecía**: `labels.csv` ya existe y `atlas_labels` ya lee
CSV. No hace falta un cliente de catálogo, solo una descarga autenticada que deje el archivo en disco y siga el
camino de hoy.

| Archivo | Cambio |
|---|---|
| `atlas_labels/source.py` (nuevo) | Descarga autenticada de `labels.csv`: bearer, `X-Organization-ID`, y guardar el archivo. Nada de parseo: eso ya lo hace `catalog.py` |
| `atlas_labels/catalog.py` | **Sin cambios** si las columnas coinciden (§4.2). `map_columns()` y `rows_to_products()` se reutilizan tal cual |
| `atlas_labels/settings.py` | Guardar URL base, credencial y `organization_id`, junto a `printer_name` y `last_catalog_dir` |
| `atlas_labels/gui.py` | Un botón "Actualizar desde Atlas One" al lado de "Abrir catálogo". El Excel **sigue funcionando igual**, y la carga automática de `discovery.py` tampoco cambia |
| `tests/labels/test_source.py` (nuevo) | Con respuestas HTTP de mentira, nunca contra la API real |

**No empezar esto hasta resolver el §4.1.** Si las llaves de API no sirven como bearer, la alternativa sería
guardar la contraseña del dueño en la PC de almacén, y eso no compensa ahorrarse una exportación manual.

**La frontera que no se cruza:** ningún módulo de lógica hace red, igual que hoy ninguno importa Tkinter ni toca
la impresora. `source.py` es la única frontera nueva, como `printer.py` es la de la impresora.

Nada de esto exige cambios en Atlas One **si** la API ya existe y admite un token.

## 6. Camino B — la interfaz vive en Atlas One

El premio: el catálogo ya está en su base de datos, así que imprimir etiquetas sería seleccionar productos en el
POS y darle a imprimir. Cero exportaciones, cero archivos, y sirve desde cualquier PC.

**El transporte ya está resuelto y esto sorprende a casi todos:** el agente de impresión recibe
`POST /print {printer_name, content_base64}` y escribe **bytes crudos** en una cola. ZPL son bytes crudos, y la
Zebra aparece en `/printers` como cualquier otra cola. Es decir, **Atlas One ya podría imprimir etiquetas hoy
por el agente, sin un solo cambio en el agente**.

> Advertencia sobre el spec: el §6 de
> [`superpowers/specs/2026-09-21-atlas-print-agent-design.md`](superpowers/specs/2026-09-21-atlas-print-agent-design.md)
> dice que las "impresoras de etiquetas ZPL/TSPL" están fuera de alcance. Eso se refiere a que el agente
> **entienda** esos formatos (plantillas, validación), no a transportar bytes. Transportar ZPL ya funciona.

Lo único que falta, entonces, es **quién genera el ZPL** sin duplicar los codificadores (§3). Tres opciones, en
orden de preferencia:

**B1. `atlas_labels` se vuelve un paquete instalable (recomendado).** Se publica desde este repo —PyPI, o
instalación directa desde git con una etiqueta de versión— y el backend de Atlas One lo declara como dependencia
y llama a `zpl.build_label(product)`. Una sola implementación, versionada, y este repo sigue siendo el dueño de
la etiqueta. Coste: hay que separar el paquete de la GUI en el empaquetado (la GUI usa Tkinter y el backend no
lo quiere), y montar publicación de versiones.

**B2. Un endpoint de etiquetas en el agente.** El agente crecería un `POST /labels/print` que recibe productos y
genera el ZPL. Se descarta: contradice frontalmente el principio de que **el agente es un tubo de bytes** y que
la generación vive en el backend de cada producto — el mismo principio que sostiene el diseño de los tickets.
Meterle lógica de dominio al agente es empezar a deshacer la razón de ser de este repo.

**B3. Un servicio aparte que genere ZPL.** Correcto en teoría y desproporcionado en la práctica: una pieza más
que desplegar y vigilar, para 331 líneas de lógica pura sin estado.

## 7. Cambios requeridos en otros repos

**Restricción del proyecto: desde este repo no se modifica ningún archivo de otro proyecto.** Lo que deba
cambiar allá se documenta aquí y lo ejecuta alguien en ese repo. Esto aplica aunque el repo esté en la misma
máquina.

> Estas peticiones están también en [`peticiones-a-atlas-one.md`](peticiones-a-atlas-one.md) (peticiones 4 a 6),
> redactadas para el agente que trabaje en Atlas One. Ese es el documento que se le pasa a alguien de allá; este
> es el razonamiento de por qué. Si cambian aquí, hay que actualizarlas allá.

| Repo | Qué habría que hacer | Cuándo |
|---|---|---|
| `atlas-one` (backend) | **Solo si la prueba del §4.1 devuelve 401:** aceptar las llaves de `/api/platform/api-keys` como credencial en `/api/products/export/labels.csv` (y, idealmente, en `/api/products/*`). Hoy el único esquema es el bearer de sesión, lo que obligaría a guardar la contraseña del dueño en una PC de almacén | Requisito del camino A |
| `atlas-one` (backend) | **Solo si faltan columnas** en `labels.csv` (§4.2): agregar las que la etiqueta necesita y no vengan | Requisito del camino A |
| `atlas-one` (backend) | Declarar `atlas_labels` como dependencia y llamar a `zpl.build_label()`. **Nunca reimplementar los codificadores de barras** (§3) | Requisito del camino B1 |
| `atlas-one` (frontend) | Pantalla de selección de productos que arme el lote y mande el ZPL al agente por `POST https://localhost:9100/print`. El contrato está en [`integracion-agentes.md`](integracion-agentes.md) | Requisito del camino B |
| `atlas-one` (frontend) | La Zebra aparece en `/printers` junto a las térmicas de ticket. Hay que **dejar elegir cuál es cuál**: mandar ZPL a una térmica de tickets imprime basura, y al revés también | Requisito del camino B |

## 8. Lo que no hay que hacer

- **Reimplementar EAN-13 o Code 128 en otro repo** (§3). Es el error que originó este proyecto, repetido.
- **Meter lógica de etiquetas en el agente de impresión** (§6, B2). El agente es un tubo de bytes.
- **Quitar la carga desde Excel.** El dueño pidió explícitamente que los dos caminos convivan.
- **Hacer red desde los módulos de lógica.** `source.py` es la frontera, igual que `printer.py`.
- **Tocar archivos de `atlas-one` o `Atlas-Rmazh` desde este repo** (§7).

## 9. Estado y siguiente paso

| | |
|---|---|
| Hecho | Carga automática del catálogo más reciente y aviso de antigüedad (`discovery.py`, commit `c4fa237`) |
| Hecho | Averiguado qué expone la API de Atlas One (§4): `labels.csv` ya existe, y el camino A se acorta a una descarga autenticada |
| Decidido | Los dos caminos conviven; `zpl`/`barcode`/`render` se quedan aquí como única fuente de verdad |
| Bloqueado | El camino A, por dos cosas: si una llave de API sirve como bearer (§4.1) y qué columnas trae el CSV (§4.2). **Ambas se contestan con un solo `curl`** |
| Siguiente paso | Correr el `curl` del §4.1 con una llave de API y, con el resultado, diseñar el camino A con la skill de brainstorming |
