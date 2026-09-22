# Integrar el Atlas Print Agent desde otro repo

Contrato para quien trabaja en un producto que **consume** el agente de impresión — Atlas One, Atlas Rmazh,
Atlas Booking y los que sigan. Si en cambio vas a editar el agente mismo, lo tuyo es
[`../AGENTS.md`](../AGENTS.md).

---

## 1. El modelo mental, que es donde todos se equivocan

```
Backend del producto ──(bytes ESC/POS en base64, en una respuesta autenticada)──▶ Navegador
Navegador ──POST https://localhost:9100/print──▶ Agente ──bytes crudos──▶ Impresora térmica
```

**El agente nunca habla con tu backend y tu backend nunca habla con el agente.** El agente corre en la PC de la
caja, escucha solo en loopback y es inalcanzable desde internet. El único que los une es el navegador del cajero.

De ahí salen tres reglas que no se negocian:

| Responsabilidad | De quién | Por qué |
|---|---|---|
| Generar los bytes ESC/POS del ticket | **Tu backend** (`PosPrinter` o equivalente) | Depende de tu modelo de dominio: precios, sucursal, logo, etiqueta de caja/mayoreo. El agente no sabe nada de eso. |
| Entregar los bytes al dispositivo | El agente | Es un tubo de bytes. Recibe base64, lo escribe y punto. |
| Sellar el ticket como impreso | **Tu backend**, cuando el navegador confirma un 2xx del agente | El agente no tiene sesión ni sabe qué es un ticket. |

También se quedan en tu backend: el registro `PrintJob`, la autorización por PIN de reimpresiones y la
configuración de ticket por sucursal. **No propongas moverlos al agente.**

---

## 2. Contrato de API v3

Base: `https://localhost:9100` (el frontend la tiene quemada; ver §5). Sin autenticación: el agente confía en
escuchar solo en loopback más el permiso de red local del navegador.

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| GET | `/`, `/health` | — | `{status, service, version, os}` |
| GET | `/ping` | — | `"pong"` |
| GET | `/diagnostics` | — | cert, spooler/CUPS, colas, `issues[]`, `warnings[]`, `healthy` |
| GET | `/printers` | — | `{printers: string[]}` |
| **POST** | **`/print`** | `{printer_name, content_base64}` | `{status:"success", bytes, printer, job_id?}` |
| POST | `/printers/test-print` | `{printer_name, paper_width_mm}` | página de prueba |
| POST | `/printers/{name}/clear-queue` | — | `{status, cancelled_jobs}` |
| POST | `/drawer/open` | `{printer_name}` | pulso `ESC p 0 25 250` al cajón |
| GET | `/printers/detect` | — | `{candidates[], count}` (solo CUPS) |
| POST | `/printers/install` | `{uri, queue_name, set_default}` | alta de cola (solo CUPS) |
| POST | `/printers/{q}/pause`, `/resume`, `/uninstall` | — | administración CUPS |
| POST | `/system/setup`, `/system/spooler-repair` | — | reparación del sistema |
| OPTIONS | `/{path}` | — | preflight con `Access-Control-Allow-Private-Network: true` |

Límite: **3 MB de payload en base64** por `/print`.

Variables de entorno del agente: `ATLAS_AGENT_HOST` (default `127.0.0.1`), `ATLAS_AGENT_PORT` (default `9100`),
`ATLAS_AGENT_ORIGINS` (orígenes CORS extra, separados por coma).

---

## 3. La llamada, tal como debe quedar

```js
const AGENT_BASE = 'https://localhost:9100';

// 1. ¿Vive el agente? Hazlo antes de ofrecer "Imprimir", no después.
const vivo = await fetch(`${AGENT_BASE}/health`)
  .then(r => r.ok)
  .catch(() => false);

// 2. Los bytes vienen de TU backend, ya en base64.
const { content_base64 } = await api.get(`/api/printer/ticket/${ventaId}`);

// 3. El agente los escribe.
const res = await fetch(`${AGENT_BASE}/print`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ printer_name: impresoraElegida, content_base64 }),
});

// 4. Solo si el agente respondió 2xx, tu backend sella el ticket.
if (res.ok) await api.post(`/api/printer/confirm/${ventaId}`);
```

---

## 4. Errores: qué significa cada uno

| Síntoma | Causa real | Qué hacer |
|---|---|---|
| `fetch` falla y `/health` tampoco responde | El agente no está corriendo, o la PC se reinició y el launcher no era servicio | Ofrecer la descarga / instrucción de arranque desde la pantalla de ajustes |
| `/health` responde en la barra de direcciones pero el `fetch` falla en el preflight | Falta el **permiso de "Acceso a la red local" de Chrome** (es por sitio y por PC) | Guiar al cajero a concederlo. Cambiar el dominio del POS obliga a concederlo de nuevo en cada terminal |
| Error de certificado | Certificado autofirmado no aceptado en esa PC | Abrir `https://127.0.0.1:9100/health` una vez y continuar |
| CORS rechazado desde un dominio propio | Falta `ATLAS_AGENT_ORIGINS` | De fábrica entran `localhost`, `*.up.railway.app` y `*.atlasone.com.mx`. Cualquier otro dominio hay que declararlo, o **la sucursal vende pero no imprime** |
| 200 pero no sale papel | El spooler aceptó el trabajo con la impresora apagada | Conocido (auditoría 2026-09-07, hallazgo C-06). No lo "arregles" en el frontend; el estado real llegará con `GET /jobs/{job_id}` en el agente unificado |
| Nombre de cola rechazado | Validación con lista blanca (`_safe_queue_name`) | Hoy Atlas One rechaza el prefijo `BT:` y los nombres UNC que Rmazh sí acepta. El agente unificado aceptará ambos |

---

## 5. Lo que va a cambiar (y lo que no)

**No cambia:** las rutas, los cuerpos y las respuestas de la tabla de §2. Ambos frontends tienen
`https://localhost:9100` quemado sin descubrimiento, así que la compatibilidad hacia atrás es una restricción
dura del rediseño, no una preferencia.

**Sí cambia, cuando llegue el agente unificado:**

- `POST /print` devolverá **siempre** `job_id`, y habrá un `GET /jobs/{job_id}` para consultar el estado real en
  CUPS o en el spooler. Ahí se podrá distinguir "encolado" de "impreso".
- Habrá un **token de emparejamiento** generado en la instalación, que el frontend mandará como cabecera. Durante
  la transición el agente lo acepta como opcional, así que nada se rompe el día del cambio.
- Las colas **Bluetooth** aparecerán en `/printers` con prefijo `BT:` — se eligen igual que cualquier otra, sin
  cambios en el frontend.
- Tu backend **deja de generar el ZIP** del agente: `GET /api/printer/download-agent` pasa a redirigir a la
  release de GitHub de este repo. Ese endpoint es el único que tendrás que tocar.

---

## 6. Bloque para pegar en el `CLAUDE.md` / `AGENTS.md` de tu repo

```markdown
## Impresión de tickets

La impresión térmica la hace el **Atlas Print Agent**, un proceso aparte que corre en la PC de la caja
(repo: github.com/Ecamposg95/Atlas-Print-Agent). No está en este repo y no se modifica desde aquí.

- Este backend **genera los bytes ESC/POS** y los entrega en base64 al navegador. El agente solo los escribe.
- El navegador hace `POST https://localhost:9100/print {printer_name, content_base64}`. La base está quemada
  en el frontend: **no cambies rutas ni puertos.**
- El ticket se sella como impreso solo cuando el navegador confirma que el agente respondió 2xx.
- Un 200 del agente significa "el spooler lo aceptó", no "salió papel".
- Si el POS se sirve desde un dominio propio, la PC de la caja necesita `ATLAS_AGENT_ORIGINS` con ese dominio,
  o vende pero no imprime.

Contrato completo: `docs/integracion-agentes.md` del repo del agente.
```
