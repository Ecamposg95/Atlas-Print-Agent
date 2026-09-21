# Atlas Print Agent: diseño del proyecto unificado

**Fecha:** 2026-09-21
**Estado:** enfoque A adoptado; pendiente detallar secciones de diseño y escribir el plan de implementación.

## 1. Problema

Atlas One y Atlas Rmazh llevan cada uno una copia del agente de impresión en `tools/print_agent/`. Cualquier arreglo hay que hacerlo dos veces y las copias ya divergieron. Además el agente actual tiene deuda que afecta a los cajeros en campo:

- Se arranca desde terminal o con un `.bat`/`.sh`. En Windows no queda instalado como servicio, así que tras reiniciar hay que volver a ejecutarlo a mano.
- Bluetooth no funciona. Rmazh bloquea desde el frontend cualquier impresora con prefijo `BT:` porque el agente nunca lo implementó.
- No hay autenticación entre navegador y agente. Cualquier página que pase el CORS puede imprimir.
- Un HTTP 200 significa que el spooler aceptó el trabajo, no que salió papel.
- Todo vive en un solo `main.py` de unas 1400 líneas, sin tests de las rutas que escriben a la impresora.
- Dominios CORS y marca "Atlas One" están quemados en el código y en los instaladores.

## 2. Objetivo

Un solo agente, versionado en este repositorio, que sirva a todos los productos de Atlas Technologies y que:

1. Funcione en Ubuntu, Windows y macOS. En campo predomina Ubuntu, hay algunas cajas Windows y pocas Mac.
2. Imprima por USB/red (CUPS o spooler de Windows) y por Bluetooth clásico (SPP) de forma confiable. Térmicas de 58 y 80 mm, predomina 80 mm.
3. Se instale con doble clic y arranque solo con el sistema. El cajero no toca la terminal.
4. Sea seguro: emparejamiento navegador-agente, orígenes configurables, sin nada quemado.
5. No rompa a los frontends actuales: misma API v3 en el puerto 9100.

## 3. Hallazgos de la auditoría de los dos repos

### 3.1 Los dos agentes son el mismo código

| | Atlas Rmazh | Atlas One |
|---|---|---|
| Ruta | `tools/print_agent/core/main.py` | `tools/print_agent/core/main.py` |
| Versión declarada | 3.0.0 | 3.0.0 |
| Líneas | 1143 | 1391 |
| Último cambio | 2026-09-08 | 2026-09-19 |
| Endpoints extra | ninguno | `/system/setup`, `/system/spooler-repair` |
| Instalador macOS launchd | no | sí (`instalar-servicio-mac.sh`, plist) |
| PPD genérico en Mac | no | sí (`_mac_generic_ppd_args`) |

La versión de Atlas One es la base del nuevo proyecto y está importada tal cual en `legacy/print_agent/`. No es un superconjunto estricto: Rmazh tiene dos diferencias que el agente unificado debe incorporar.

| Diferencia | Atlas Rmazh | Atlas One |
|---|---|---|
| Nombres de cola aceptados (`_QUEUE_NAME_RE`) | Admite prefijo `BT:` y UNC de un solo host (`\\PC-CAJA\POS-80`) para impresoras compartidas de Windows | Solo `[A-Za-z0-9_\-. ()]`; rechaza `BT:` y UNC |
| Orígenes CORS quemados | Solo `localhost` y `*.up.railway.app`; el dominio propio va por `ATLAS_AGENT_ORIGINS` | Además quema `(*.)atlasone.com.mx` |

En Rmazh el prefijo `BT:` solo pasa la validación; la escritura sigue yendo a `win32print` o `lp` con ese nombre, así que Bluetooth tampoco funciona ahí. El frontend lo bloquea antes de llamar al agente.

Los tests importados en `legacy/tests/` vienen de Rmazh y codifican su contrato. Corridos contra la base de Atlas One fallan 3 de 30, exactamente en esas dos diferencias. Se dejan fallando a propósito: son el criterio de aceptación de que el agente unificado cubre ambos productos.

### 3.2 El agente ya está desacoplado

`main.py` importa solo la librería estándar, `fastapi`, `uvicorn`, `pydantic` y `win32print` en Windows. No importa nada de `app/`. El acoplamiento es al revés, del repo hacia el agente:

- `app/routers/printer.py` genera el ZIP de descarga leyendo `tools/print_agent/` por ruta relativa.
- Dos tests por repo cargan `main.py` por ruta relativa. Los de Rmazh son autocontenidos y están importados en `legacy/tests/`. Los de Atlas One cruzan contra `PrinterSettings.tsx` y se quedan allá.
- El frontend tiene `AGENT_BASE = 'https://localhost:9100'` quemado, sin descubrimiento.

### 3.3 Contrato de API v3 que hay que conservar

| Método | Ruta | Cuerpo / respuesta |
|---|---|---|
| GET | `/`, `/health` | `{status, service, version, os}` |
| GET | `/ping` | `"pong"` |
| GET | `/diagnostics` | estado de cert, spooler/CUPS, colas, `issues[]`, `warnings[]`, `healthy` |
| GET | `/printers` | `{printers: string[]}` |
| POST | `/print` | `{printer_name, content_base64}` → `{status:"success", bytes, printer, job_id?}` |
| POST | `/printers/test-print` | `{printer_name, paper_width_mm}` |
| POST | `/printers/{name}/clear-queue` | `{status, cancelled_jobs}` |
| POST | `/drawer/open` | `{printer_name}` → envía `ESC p 0 25 250` |
| GET | `/printers/detect` | `{candidates[], count}` (CUPS) |
| POST | `/printers/install` | `{uri, queue_name, set_default}` (CUPS) |
| POST | `/printers/{q}/pause`, `/resume`, `/uninstall` | CUPS |
| POST | `/system/setup`, `/system/spooler-repair` | reparación del sistema |
| OPTIONS | `/{path}` | preflight con `Access-Control-Allow-Private-Network: true` |

Variables de entorno actuales: `ATLAS_AGENT_HOST` (127.0.0.1), `ATLAS_AGENT_PORT` (9100), `ATLAS_AGENT_ORIGINS` (orígenes CORS extra).

### 3.4 Lo que se queda en cada backend

La generación de bytes ESC/POS (`app/pos_printer.py`, clase `PosPrinter`) depende del modelo de dominio de cada producto y no forma parte del agente. El agente es un tubo de bytes: recibe base64 y lo escribe en el dispositivo. Igual se quedan en el backend `PrintJob`, la autorización por PIN de reimpresiones y la configuración de ticket por sucursal.

## 4. Enfoques evaluados

**A. Python reestructurado más binarios empaquetados (adoptado).** Se conserva la lógica de `legacy/print_agent/` pero repartida en un paquete con módulos por responsabilidad. PyInstaller genera binarios por sistema en GitHub Actions. Se entregan instaladores nativos que registran el servicio y arrancan solo. Reutiliza el código probado en campo. Costo: binarios de 30 a 50 MB y necesidad de firmar el `.exe` para evitar falsos positivos de antivirus.

**B. Reescritura en Go.** Un binario estático pequeño y una sola librería para servicios en los tres sistemas. Descartado porque implica reescribir la interacción con CUPS y el spooler de Windows, que es justo lo que más costó afinar en campo.

**C. App de escritorio (Tauri/Electron).** Descartado: pesado, las cajas Ubuntu a veces no tienen escritorio, y la configuración ya vive en la pantalla de ajustes de cada frontend. Un ícono de bandeja se puede agregar después sobre A.

## 5. Diseño (enfoque A)

Las secciones siguientes se detallan y aprueban una por una antes de escribir el plan de implementación.

### 5.1 Estructura del paquete

```
atlas_print_agent/
  __main__.py          # entrada: python -m atlas_print_agent
  config.py            # carga de config (archivo + env), orígenes, puerto, token
  api/                 # rutas FastAPI, una por grupo: health, printers, print, drawer, system
  backends/
    base.py            # interfaz PrinterBackend: list(), write(bytes), status()
    cups.py            # Linux/macOS vía lp/lpstat/lpadmin
    winspool.py        # Windows vía win32print RAW
    bluetooth.py       # SPP por puerto serie (rfcomm / COM / tty)
  security/            # certs autofirmados, token de emparejamiento, CORS/PNA
  service/             # instalación como servicio: systemd, launchd, Windows service
  diagnostics.py
installers/
  linux/               # .deb (postinst instala y habilita el servicio)
  windows/             # Inno Setup .iss
  macos/               # .pkg
tests/
legacy/                # código importado tal cual, referencia hasta terminar la migración
docs/
```

### 5.2 Bluetooth

Bluetooth clásico SPP. La impresora se empareja desde el sistema y aparece como puerto serie. El backend `bluetooth.py` escribe los bytes con `pyserial` en `/dev/rfcomm*` (Ubuntu), `COM*` (Windows) o `/dev/tty.*` (macOS). El agente descubre puertos serie disponibles y los expone en `/printers` con prefijo `BT:` para que los frontends actuales los puedan elegir sin cambios. Reintentos con backoff y timeout de escritura, para que una impresora apagada devuelva error y no cuelgue la caja.

### 5.3 Seguridad

- Token de emparejamiento generado en la instalación, mostrado en la pantalla de ajustes del frontend una sola vez, enviado como cabecera en cada llamada. Fase de transición: el agente lo acepta como opcional hasta que ambos frontends lo manden.
- Orígenes CORS en archivo de configuración, sin dominios quemados. Los instaladores reciben los orígenes como parámetro.
- Cert TLS autofirmado igual que hoy, renovación automática.
- Validación de nombre de cola y de puerto serie con lista blanca, igual que `_safe_queue_name` actual.

### 5.4 Instalación y autoarranque

| Sistema | Paquete | Servicio | Logs |
|---|---|---|---|
| Ubuntu | `.deb` | systemd (system o user) | journal |
| Windows | `.exe` Inno Setup | servicio de Windows (pywin32) | archivo rotativo |
| macOS | `.pkg` | launchd LaunchAgent | `~/Library/Logs` |

Los backends de cada producto dejan de generar el ZIP y redirigen a la release de GitHub de este repo.

### 5.5 Confirmación de impresión

`/print` sigue devolviendo 200 al aceptar el trabajo, por compatibilidad. Se agrega `GET /jobs/{job_id}` para consultar el estado real en CUPS o el spooler, y el campo `job_id` se devuelve siempre.

### 5.6 Pruebas

- Unitarias de cada backend con el dispositivo simulado (puerto serie falso, `lp` falso).
- Contrato de API v3 con `TestClient`, incluidos CORS, PNA y validación de nombres (migrando `legacy/tests/`).
- Prueba de humo en CI que arranca el binario empaquetado y pega a `/health`.

## 6. Fuera de alcance de la primera versión

BLE (impresoras portátiles sin puerto serie), impresoras de etiquetas ZPL/TSPL, impresión de PDF, actualización automática, ícono de bandeja. Quedan como candidatos para versiones posteriores.
