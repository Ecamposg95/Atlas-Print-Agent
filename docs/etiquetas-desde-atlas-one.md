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

## 4. Lo que hay que averiguar antes de diseñar nada

**No se sabe qué expone la API de Atlas One.** El dueño no lo tenía claro el 2026-09-22 y el repo de Atlas One
**no está en esta máquina** (`app.atlasone.com.mx`, repositorio aparte; `Atlas-Rmazh` es el POS de otro cliente,
no sirve como referencia).

Primer paso de quien retome esto — pedir al dueño que corra esto, o correrlo si hay acceso:

```bash
curl -s https://app.atlasone.com.mx/openapi.json | python3 -m json.tool | grep -iE '"/api/.*(product|catalog|inventor)'
```

Y con ello contestar tres preguntas, que son las que deciden el diseño:

1. ¿Hay un endpoint que liste productos con los campos que la etiqueta necesita — SKU, código de barras, marca,
   nombre, departamento, talla, color, precio, existencia?
2. ¿Se puede autenticar un programa externo (token/llave), o todo está detrás de la cookie de sesión del
   navegador?
3. ¿Hay paginación, y cuántos productos son? (El catálogo de referencia ronda los miles de filas.)

**Si la respuesta a 1 o 2 es que no,** el trabajo se convierte en "agregar eso en Atlas One", que es un cambio en
otro repo y se documenta (§7), no se hace desde aquí.

## 5. Camino A — la app local trae el catálogo sola

**Es el camino corto y ataca el dolor declarado.** La app deja de depender de un archivo exportado a mano.

Qué tocar en este repo:

| Archivo | Cambio |
|---|---|
| `atlas_labels/source.py` (nuevo) | Cliente HTTP del catálogo de Atlas One: autenticación, paginación, y traducción de la respuesta a `list[Product]` |
| `atlas_labels/catalog.py` | Nada de red aquí. `rows_to_products()` y el mapeo de columnas ya existen y se reutilizan; `source.py` los alimenta |
| `atlas_labels/settings.py` | Guardar la URL base y el token, junto a `printer_name` y `last_catalog_dir` |
| `atlas_labels/gui.py` | Un botón "Actualizar desde Atlas One" al lado de "Abrir catálogo". El Excel **sigue funcionando igual** |
| `tests/labels/test_source.py` (nuevo) | Con respuestas HTTP de mentira, nunca contra la API real |

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

Ninguno de estos cambios se puede detallar más hasta contestar las preguntas del §4. Lo que **sí** se sabe:

| Repo | Qué habría que hacer | Cuándo |
|---|---|---|
| `atlas-one` (backend) | Un endpoint de catálogo consumible por un programa externo, con autenticación por token, paginado, devolviendo los campos que la etiqueta necesita (§4.1). **Puede que ya exista** — comprobar antes de construir nada | Requisito del camino A |
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
| Decidido | Los dos caminos conviven; `zpl`/`barcode`/`render` se quedan aquí como única fuente de verdad |
| Bloqueado | Todo lo demás, hasta contestar las tres preguntas del §4 sobre la API de Atlas One |
| Siguiente paso | Correr el `curl` del §4 y, con la respuesta, diseñar el camino A con la skill de brainstorming |
