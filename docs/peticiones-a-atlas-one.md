# Peticiones a Atlas One (y a Atlas Rmazh)

**Para el agente que trabaja en el repo de Atlas One o de Atlas Rmazh.** Esta es la lista completa de lo que el
proyecto **Atlas-Print-Agent** necesita de ustedes. Es el único documento que hace falta leer para eso: lo demás
de este repo es contexto.

> **Por qué llega así y no como un PR:** el dueño (2026-09-22) puso como regla que desde Atlas-Print-Agent no se
> modifique ningún archivo de otro proyecto, ni siquiera cuando el repo está en la misma máquina. Los cambios en
> sus productos los decide y los ejecuta él, o ustedes. Esto es una petición, no un parche.

**Nada de esta lista es urgente ni rompe nada hoy.** Si no se hace, todo sigue funcionando como hasta ahora; lo
que no llega es la mejora. Cada petición dice qué pasa si se ignora.

---

## Tabla de estado

| # | Petición | Repos | Estado | Bloquea |
|---|---|---|---|---|
| 1 | `download-agent` redirige a las releases | `atlas-one`, `Atlas-Rmazh` | Esperando a que existan las releases | Distribución del agente nuevo |
| 2 | Ajustar `test_print_agent_bundle.py` | `atlas-one`, `Atlas-Rmazh` | Va junto con la #1 | — |
| 3 | Texto de `PrinterSettings.tsx` | `atlas-one` | Va junto con la #1 | — |
| 4 | Llaves de API válidas como bearer | `atlas-one` | **Sin confirmar**: falta una prueba | Que la app de etiquetas traiga el catálogo sola |
| 5 | Columnas de `labels.csv` | `atlas-one` | **Sin confirmar**: falta ver el CSV | Lo mismo que la #4 |
| 6 | Pregunta sobre `assign-missing` | `atlas-one` | Pregunta, no cambio | — |

---

## Contexto en dos líneas

**Atlas-Print-Agent** (github.com/Ecamposg95/Atlas-Print-Agent, público) unifica el agente de impresión que
estaba copiado en `tools/print_agent/` de sus dos repos, y además contiene `atlas_labels`, la herramienta que
imprime etiquetas de producto en una Zebra a partir del catálogo que ustedes exportan.

El agente es y seguirá siendo **un tubo de bytes**: recibe base64 y lo escribe en la impresora. La generación de
los bytes ESC/POS del ticket se queda en el backend de cada producto. El contrato de la API v3 está en
[`integracion-agentes.md`](integracion-agentes.md) y **no va a cambiar de forma incompatible** — sabemos que sus
frontends tienen `https://localhost:9100` quemado sin descubrimiento.

---

## Petición 1 — `download-agent` redirige a las releases

**Repos:** `atlas-one` y `Atlas-Rmazh`. **Archivo:** `app/routers/printer.py`.

Hoy `GET /api/printer/download-agent?platform=windows|linux|mac` arma un ZIP leyendo `tools/print_agent/` por
ruta relativa. Cuando existan las releases de Atlas-Print-Agent, ese endpoint debe **redirigir** al artefacto de
la release que corresponda a la plataforma:

| Plataforma | Artefacto |
|---|---|
| Ubuntu | `atlas-print-agent_<version>_amd64.deb` |
| macOS Apple Silicon | `atlas-print-agent-<version>-arm64.pkg` |
| macOS Intel | `atlas-print-agent-<version>-x86_64.pkg` |
| Windows | `atlas-print-agent-setup-<version>.exe` |

Ojo con macOS: **son dos artefactos** y hay que elegir según la arquitectura, o dar a elegir.

**Por qué importa:** esos paquetes instalan el agente **con autoarranque**. Hoy la cajera tiene que abrir un
script cada mañana y dejar una ventana abierta toda la jornada; si la PC se reinicia, no hay impresión hasta que
alguien lo note. El diseño completo está en
[`superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md`](superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md).

**Si se ignora:** la pantalla `/printer-settings` sigue entregando el agente viejo en modo manual, y conviven dos
mecanismos en campo — el peor escenario para depurar.

**`tools/print_agent/` puede quedarse donde está** hasta que las releases estén probadas en campo. Quitarlo es un
paso posterior y separado.

## Petición 2 — Ajustar `test_print_agent_bundle.py`

**Repos:** ambos. **Archivo:** `tests/test_print_agent_bundle.py`.

Ese test afirma hoy los **nombres de los scripts** que cita la interfaz y el contenido del ZIP por plataforma. Al
pasar a redirección debe afirmar la **URL de la release** y que se elige el artefacto correcto por plataforma.

**Por qué importa, y esto no es teórico:** ese test existe porque un renombrado al español dejó la pantalla
citando archivos inexistentes **durante dos meses**, lo que hizo inalcanzable el autoarranque. Si lo borran al
cambiar el endpoint en vez de adaptarlo, se pierde la red que ya salvó a este proyecto una vez.

## Petición 3 — Texto de `PrinterSettings.tsx`

**Repo:** `atlas-one` (frontend).

El texto debe pasar de "descarga y ejecuta el script" a "descarga e instala", y **desaparecer la instrucción de
dejar la ventana abierta**.

**Por qué importa:** si la cajera sigue el texto viejo después de instalar el servicio, deja un proceso
peleándole el puerto 9100 al agente recién instalado. `/health` acaba respondiendo desde el proceso equivocado
mientras el servicio se reinicia en bucle. Es la confusión más cara de depurar que tiene documentada este
proyecto.

---

## Petición 4 — Llaves de API válidas como credencial de `labels.csv`

**Repo:** `atlas-one` (backend). **Estado: sin confirmar — puede que ya funcione.**

Leyendo `openapi.json` vemos que:

- El único esquema de seguridad declarado es `OAuth2PasswordBearer` (`tokenUrl: /api/auth/login`).
- Existen llaves de API en `/api/platform/api-keys`, con `scopes`, listado por organización y revocación.
- **Ningún endpoint declara una cabecera de API key**, así que no sabemos si una llave se acepta como bearer.

**Lo que pedimos, si y solo si la prueba de abajo devuelve 401:** que una llave de `/api/platform/api-keys` sirva
como credencial en `GET /api/products/export/labels.csv` (e idealmente en `/api/products/*`).

```bash
curl -s -o labels.csv -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer <LLAVE_DE_API>" \
  "https://app.atlasone.com.mx/api/products/export/labels.csv?only_with_stock=true"
```

**Por qué importa:** queremos que la app de etiquetas traiga el catálogo sola, sin que nadie exporte un `.xlsx` a
mano. Con lo declarado hoy, la única forma sería guardar **usuario y contraseña del dueño** en una PC de almacén
para poder renovar el token. Eso no lo vamos a hacer: preferimos dejar la carga desde Excel antes que normalizar
una credencial personal guardada en una máquina de tienda. Una llave con scopes y revocable resuelve el problema
entero.

**Si se ignora:** la app de etiquetas sigue dependiendo de que alguien exporte el catálogo a mano. Funciona, pero
el archivo envejece y salen etiquetas con precios viejos. (Ya mitigado en parte: la app avisa de la antigüedad
del catálogo, pero avisar no es resolver.)

## Petición 5 — Columnas de `labels.csv`

**Repo:** `atlas-one` (backend). **Estado: sin confirmar — probablemente no haya nada que hacer.**

`GET /api/products/export/labels.csv` ya existe y `atlas_labels` ya lee CSV, así que puede que encaje tal cual.
Lo que la etiqueta necesita por producto:

| Campo | Uso en la etiqueta |
|---|---|
| SKU | Identificación y filtros |
| Código de barras | **El código impreso.** 13 dígitos con checksum válido → EAN-13; cualquier otro texto → Code 128 |
| Marca, Nombre | Líneas de texto |
| Departamento | Filtro de la app |
| Talla, Color | Líneas de texto |
| Precio | Línea de precio |
| Existencia (stock) | **Copias por omisión:** se imprime una etiqueta por unidad en existencia |

**Lo que pedimos, solo si faltan columnas:** agregarlas al CSV. Si las trae todas, esta petición se cierra sin
cambios.

## Petición 6 — Pregunta sobre `assign-missing`

**Repo:** `atlas-one`. **Es una pregunta, no un cambio.**

Vemos `GET /api/products/barcodes/missing-count` y `POST /api/products/barcodes/assign-missing`. En este proyecto
está registrado que asignar los códigos internos de la serie **EAN-13 con prefijo `20170000`** era un trámite
manual del dueño: tomar el mayor base de 12 dígitos usado, sumar 1, recalcular el checksum.

**La pregunta:** ¿`assign-missing` hace exactamente eso y respeta esa serie? Si sí, la instrucción que seguimos
repitiendo está obsoleta y debemos dejar de repetirla. Si no —si asigna de otra serie o de otro modo— hay que
saberlo, porque un código que no escanea en el POS no se descubre hasta que la tienda no puede cobrar.

---

## Cómo responder

**No hay canal automático entre los repos, a propósito.** Lo que funcione:

- Contestarle al dueño directamente; él trae la respuesta a este repo.
- O, si tienen acceso, abrir un issue en github.com/Ecamposg95/Atlas-Print-Agent.

Lo que **no** hay que hacer: modificar Atlas-Print-Agent desde su repo para "dejar la respuesta ahí". La regla
corre en las dos direcciones.

## Lo que no hay que hacer, en ningún caso

- **Reimplementar EAN-13 o Code 128 en Atlas One.** Los codificadores viven en `atlas_labels/barcode.py`
  (106 patrones de Code 128 verificados uno a uno) y son la única fuente de verdad. Si alguna vez la interfaz de
  etiquetas vive en Atlas One, la forma correcta es consumir ese paquete, no copiarlo. **Este repo existe porque
  el agente de impresión estaba copiado en dos productos y las copias divergieron.** El razonamiento completo
  está en [`etiquetas-desde-atlas-one.md`](etiquetas-desde-atlas-one.md).
- **Meterle lógica de etiquetas al agente de impresión.** Es un tubo de bytes y así se queda.
- **Romper la API v3 del agente.** Sus frontends tienen la base quemada sin descubrimiento.
