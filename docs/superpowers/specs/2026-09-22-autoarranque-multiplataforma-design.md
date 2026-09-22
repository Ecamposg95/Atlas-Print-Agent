# Autoarranque multiplataforma del Atlas Print Agent: diseño

**Estado:** diseño aprobado por el dueño el 2026-09-22; pendiente escribir el plan de implementación.

**Relación con el spec del agente unificado:** esto implementa la sección 5.4 (*Instalación y autoarranque*) de
[`2026-09-21-atlas-print-agent-design.md`](2026-09-21-atlas-print-agent-design.md), y **solo esa**. La
reestructuración del paquete `atlas_print_agent/` (§5.1 de aquel spec) sigue pendiente y **no es requisito** de
esta entrega: se empaqueta el código legado tal como está.

---

## 1. Problema

El agente corre hoy en modo manual en las tres plataformas: la cajera busca un script, le da doble clic y deja
una ventana abierta toda la jornada. Si la PC se reinicia, no hay impresión hasta que alguien vuelva a abrirlo.

Existen desde el 2026-09-19 un instalador de servicio para Linux (`core/instalar-servicio-linux.sh`, systemd) y
otro para macOS (`core/instalar-servicio-mac.sh`, LaunchAgent), más un runbook de conversión. **Ninguna caja se
ha convertido.** El motivo, confirmado por el dueño el 2026-09-22, no es un error de esos scripts: **nunca se
llegaron a correr**, porque el procedimiento es impagable. El runbook exige ir en persona a cada sucursal, tener
la contraseña de sudo, ubicar la carpeta exacta que esa caja venía usando, y esperar a que se cree un entorno
virtual de Python en una PC de tienda. Nadie hace eso treinta veces.

En **Windows no existe nada**: `impresora_win.bat` es un lanzador en primer plano y el propio README del agente
advierte que tras reiniciar hay que volver a ejecutarlo.

La dependencia de Python en la máquina de destino es la pieza más frágil de todo el esquema, y es justamente la
que nunca se ha probado en campo.

## 2. Objetivo y criterios de aceptación

Que el agente arranque solo en Ubuntu, Windows y macOS, y que ponerlo en una caja sea **un paso**, no un
procedimiento.

Quien instala es el dueño o un técnico, en persona o por acceso remoto (decisión del 2026-09-22). Puede haber
sudo y comandos; lo que no puede haber es un runbook de veinte pasos.

Se considera terminado cuando:

1. En las tres plataformas, reiniciar la máquina deja el agente respondiendo en `https://127.0.0.1:9100/health`
   sin que nadie abra nada.
2. Matar el proceso del agente lo revive automáticamente.
3. **Reinstalar o actualizar el paquete no cambia el certificado**, así que el navegador de la caja no vuelve a
   pedir que se acepte.
4. El instalador **falla ruidosamente** si al terminar `/health` no responde.
5. La máquina de destino **no necesita Python**.
6. Los 30 tests de `legacy/tests/` siguen en su estado actual (27 pasan; los 3 de `BT:` y UNC siguen siendo el
   pendiente del agente unificado, ajeno a esta entrega).

## 3. Enfoques evaluados

**A. Binarios PyInstaller más instaladores nativos (adoptado).** Un ejecutable por sistema, empaquetado en
GitHub Actions, envuelto en `.deb`, `.pkg` y `.exe`, cada uno registrando el autoarranque propio de su sistema.
Elimina Python de la máquina de destino. Es el destino que ya fijaba el §5.4 del spec del agente unificado, así
que no es trabajo desechable. Dos hechos comprobados el 2026-09-22 lo abarataron: el repo es **público**, de modo
que GitHub Actions es gratis incluidos los runners de macOS; y ya existe un PyInstaller funcionando en este repo
(`installers/labels/build_exe.ps1`), o sea el camino está recorrido.

**B. Un comando por sistema sobre el Python actual.** Colapsar el runbook a un solo comando y agregar el Windows
que falta. Más barato y entregable en días, pero conserva la dependencia de Python y el venv en cada caja —la
parte frágil—, no resuelve las actualizaciones, y obliga a mantener tres scripts de shell que habría que
rehacer cuando llegara el empaquetado. Descartado.

**C. Contenedor.** Descartado: el acceso a CUPS y a USB desde un contenedor es penoso, y en Windows y macOS
exigiría Docker Desktop en la PC de una tienda.

## 4. Qué pasa en cada caja

El técnico llega con **un archivo** y sale con el agente corriendo y registrado al arranque.

| Sistema | Paso único | Lo que deja instalado |
|---|---|---|
| Ubuntu | `sudo apt install ./atlas-print-agent_<version>_amd64.deb` | Servicio systemd habilitado al arranque |
| macOS | doble clic en `atlas-print-agent-<version>.pkg` | `Atlas Print Agent.app` en `/Applications` + LaunchAgent cargado |
| Windows | doble clic en `atlas-print-agent-setup-<version>.exe` | Tarea programada al inicio de sesión + acceso directo |

Los tres instaladores **esperan a que `/health` responda y fallan ruidosamente si no lo hace**. El modo de fallo
de hoy —el técnico se va creyendo que quedó— deja de ser posible.

Los orígenes CORS dejan de ser un parámetro que el técnico deba recordar: se escriben en un archivo de
configuración (§7), no dentro de la unidad de servicio. Cambiar el dominio del POS más adelante ya no obliga a
reinstalar.

**No cambia** el puerto 9100, ni la API v3, ni que el navegador le hable a `https://localhost:9100`. La
compatibilidad hacia atrás es dura: ambos frontends tienen esa base quemada sin descubrimiento.

## 5. El binario y el directorio de estado

Un ejecutable por sistema, hecho con PyInstaller `--onefile` sobre `legacy/print_agent/core/main.py` tal cual,
sin reestructurarlo.

### 5.1 Por qué el código de hoy no sobrevive a PyInstaller

Tres líneas del agente actual rompen el empaquetado:

```python
_log_file = Path(__file__).parent / "agent.log"                  # main.py:88
cert_dir  = Path(__file__).parent / "certs"                      # main.py:348, 1314
subprocess.run([sys.executable, str(gen_script)], ...)           # main.py:1331
```

Bajo `--onefile`, `__file__` apunta a `_MEIPASS`: una carpeta temporal **distinta en cada arranque y borrada al
salir**. Sin cambios, el binario regeneraría el certificado cada vez que se prende la PC y la cajera tendría que
volver a aceptarlo en el navegador todas las mañanas —peor que hoy—, y el log se escribiría en un temporal que
desaparece. Peor aún: bajo PyInstaller `sys.executable` **es el propio agente**, así que esa tercera línea no
generaría un certificado: relanzaría el agente.

### 5.2 Los tres cambios en `main.py`

Junto con el número de versión (§8), son los únicos cambios al código congelado, y son los mismos que el agente
unificado necesitará igual: no son parche, sino el primer trozo de la migración, hecho donde hoy se puede
probar.

`legacy/print_agent/` está marcado como congelado en el `AGENTS.md` de este repo. Esta es una **excepción
consciente y acotada** a esa regla, no un descuido: cuatro cambios, todos necesarios para que exista un binario,
todos heredables por el agente unificado.

1. **Directorio de estado resuelto en ejecución**, no desde `__file__`:

| Sistema | Estado (certificado + `agent.conf`) | Log |
|---|---|---|
| Ubuntu | `/var/lib/atlas-print-agent/` (lo crea systemd con `StateDirectory=`) | journal + archivo rotativo |
| macOS | `~/Library/Application Support/AtlasPrintAgent/` | `~/Library/Logs/AtlasPrintAgent/` |
| Windows | `%LOCALAPPDATA%\AtlasPrintAgent\` | ahí mismo |

   La variable `ATLAS_AGENT_STATE_DIR` la sobrescribe, para poder probar sin ensuciar la máquina.

2. **Generación del certificado en proceso**: `import generate_cert` y llamar a `generate_self_signed_cert()`,
   en vez de lanzar un subproceso que bajo PyInstaller no existe. `generate_cert.py` recibe el directorio
   destino como parámetro en lugar de derivarlo de su propio `__file__`.

3. **El estado vive fuera de la carpeta de instalación.** Esto vale por sí solo: reinstalar o actualizar ya no
   toca el certificado, y desaparece la heurística `find_existing_certs` del instalador actual, que hoy rastrea
   el home con `find -maxdepth 6` buscando un `cert.pem` viejo.

El log rotativo (5 MB × 3) y el comportamiento del agente no cambian en nada más.

## 6. Autoarranque por sistema

El criterio es el mismo en los tres: **el agente tiene que ver las impresoras que ve la cajera.**

### 6.1 Ubuntu — servicio de sistema systemd

`After=network-online.target cups.service`, `Restart=always`, `RestartSec=5`,
`StateDirectory=atlas-print-agent` (systemd crea `/var/lib/atlas-print-agent` con el dueño correcto, sin que el
instalador toque permisos).

**Corre como el usuario de la caja, no como root** — se conserva tal cual la decisión que ya tomó el instalador
actual, que sustituye `User=`/`Group=` por el usuario destino (`instalar-servicio-linux.sh:292-293`) y lo agrega
al grupo `lpadmin`. El `%i` de la plantilla no es un especificador de systemd que se expanda solo: es un
marcador que ese script reemplaza por `sed`. El `.deb` hace lo mismo en su `postinst`, resolviendo el usuario
destino en vez de recibirlo por bandera.

Se conserva también el hardening de la plantilla (`NoNewPrivileges=true`, `ProtectSystem=true` — no lockdown
completo, porque el agente necesita los sockets de CUPS) y el agente **sigue escuchando solo en loopback**.

**Punto abierto a verificar en la implementación:** `/printers/install` y `/system/spooler-repair` ejecutan
`lpadmin` y `cupsenable`, cuya política por omisión en CUPS exige autenticación de administrador. Pertenecer al
grupo `lpadmin` **puede no bastar** desde un proceso no interactivo, que no tiene dónde escribir una contraseña.
Hay que probarlo en una caja real antes de dar el servicio por bueno. Si resulta que no basta, la salida
**no** es correr todo el agente como root, sino acotar el privilegio: una regla de `sudoers` limitada a
`lpadmin` y `cupsenable` para ese usuario. El resto del agente —que es el 99 % del uso: `/print`— no necesita
nada de esto y funciona como usuario normal.

Si esa caja no tiene sudo, se conserva el fallback de hoy —servicio de usuario— con el aviso de que ahí el
agente no podrá dar de alta colas.

### 6.2 macOS — LaunchAgent de usuario, más un `.app` de doble clic

Se mantiene la decisión ya tomada en el plist actual: **LaunchAgent de usuario, no LaunchDaemon**, porque ve la
misma cola de CUPS que la cajera y no necesita sudo. Se conservan `RunAtLoad`, `KeepAlive`,
`ThrottleInterval 5` y el `PATH` explícito (launchd no hereda el de la sesión y el agente llama `lp`, `lpstat`,
`lpadmin`, `lpinfo`).

**PyInstaller produce además un bundle `.app`**, y eso da las dos formas de arrancar que pidió el dueño el
2026-09-22, con un solo programa instalado:

- El `.pkg` instala **`Atlas Print Agent.app` en `/Applications`** y deja un alias en el Escritorio: el
  equivalente al `.exe` de Windows, doble clic y arranca.
- El **LaunchAgent apunta al binario que vive dentro de ese mismo `.app`**. No son dos copias.
- Doble clic con el agente ya corriendo **no le pelea el puerto 9100**: detecta que `/health` responde y muestra
  *"El agente ya está activo"* en un diálogo nativo (`osascript`). Es el mismo criterio que ya aplica
  `impresora_mac.sh`.

**Trampa propia del `.pkg`:** su script `postinstall` corre como root. Si escribe el plist sin más, lo deja en
el home de root y el agente no arranca nunca. Tiene que resolver el usuario de consola
(`stat -f %Su /dev/console`), escribir el plist en *su* home, ajustar el dueño, y cargarlo con
`launchctl asuser <uid> launchctl bootstrap gui/<uid>`. Es el mismo `Bootstrap failed: 5: Input/output error`
que el runbook ya documenta, en versión instalador.

**macOS 15 (Sequoia)** mostrará el aviso de *Elementos de inicio* la primera vez. Es lo esperado; desactivarlo
devuelve la caja al modo manual sin avisar a nadie, y así va dicho en el runbook.

### 6.3 Windows — tarea programada al inicio de sesión, no servicio

Un **servicio** de Windows corre en la sesión 0 y **no ve las impresoras instaladas por usuario**. Es una forma
silenciosa de que `/health` responda y no salga papel, y por eso este diseño se aparta de lo que decía el §5.4
del spec del agente unificado ("servicio de Windows (pywin32)").

En su lugar: **tarea programada** con la cuenta de la cajera, disparador *AtLogOn*, definida por XML
(`schtasks /create /xml`) con `RestartOnFailure` cada minuto y el máximo de reintentos que admita el
Programador, `StopIfGoingOnBatteries` y `DisallowStartIfOnBatteries` en falso (una caja puede estar en un
no-break), y sin límite de duración de ejecución.

Aun así es **más débil que `Restart=always` o `KeepAlive`**: el Programador de tareas reintenta un número finito
de veces, y si el agente muere más veces que eso, deja de levantarlo hasta el próximo inicio de sesión. Se
acepta a cambio de que imprima de verdad, que es el mismo criterio con el que en macOS se eligió LaunchAgent
sobre LaunchDaemon. Si en campo resulta que se agotan los reintentos, la salida es un vigilante propio, y eso
queda fuera de esta entrega.

Esto reemplaza a `impresora_win.bat`, que hoy es lo único que existe en Windows.

### 6.4 Los tres quedan con el mismo par

En los tres sistemas: **arranca solo, y además hay un ícono para arrancarlo a mano.**

| Sistema | Automático | Manual |
|---|---|---|
| Ubuntu | servicio systemd | `atlas-print-agent.desktop` (ya existe en el repo) instalado en el menú de aplicaciones |
| macOS | LaunchAgent | `Atlas Print Agent.app` en `/Applications` + alias en Escritorio |
| Windows | tarea al inicio de sesión | acceso directo en Menú Inicio y Escritorio |

En los tres, el lanzador manual **detecta que el agente ya está activo y lo dice**, en vez de pelear el puerto.

## 7. Los instaladores

Un solo formato de configuración para los tres: **`agent.conf` en el directorio de estado**, líneas
`CLAVE=valor`, con precedencia **variable de entorno > archivo > valor por omisión**. Una sola regla, en vez de
`EnvironmentFile` en Linux y otra cosa en macOS. Claves: `ATLAS_AGENT_PORT`, `ATLAS_AGENT_ORIGINS`,
`ATLAS_AGENT_HOST`.

| Paquete | Construido con | Qué hace su script | Qué pasa al desinstalar |
|---|---|---|---|
| `.deb` | `dpkg-deb` sobre un árbol preparado | `daemon-reload`, `enable --now`, espera `/health` | para y deshabilita; **`remove` conserva el estado**, `purge` borra `/var/lib/atlas-print-agent` |
| `.pkg` | `pkgbuild` + `productbuild` | resuelve el usuario de consola, instala el `.app`, escribe y carga el LaunchAgent, espera `/health` | script de desinstalación: `bootout`, borra el plist y el `.app` |
| `.exe` | Inno Setup | instala **por usuario** en `%LOCALAPPDATA%\Programs\AtlasPrintAgent` (sin UAC), crea la tarea, la arranca, espera `/health` | borra la tarea y el acceso directo |

## 8. CI y releases

`.github/workflows/release.yml`, disparado por tag `v*`, cuatro runners:

| Runner | Produce |
|---|---|
| `ubuntu-latest` | binario + `.deb` (amd64) |
| `macos-14` | `.app` + `.pkg` (Apple Silicon) |
| `macos-13` | `.app` + `.pkg` (Intel) |
| `windows-latest` | `.exe` |

Dos `.pkg` porque PyInstaller no produce un binario universal sin un Python universal.

Cada runner corre la **prueba de humo** del §5.6 del spec del agente unificado: arranca el binario recién
empaquetado, le pega a `/health`, lo mata. Un binario que no arranca no llega a la release.

El workflow **falla si el tag no coincide con la constante `VERSION` de `main.py`**, para que no se publique un
`v3.1.0` que se reporta como `3.0.0`.

**Esta entrega publica `v3.1.0`**, y por tanto `VERSION` en `main.py` pasa de `"3.0.0"` a `"3.1.0"`. Es un
cuarto cambio a ese archivo, además de los tres del §5.2; se anota aquí para que no aparezca como sorpresa en
el diff. El número es visible en `/health` y en `/diagnostics`, así que sirve para saber, desde el POS, si una
caja ya está convertida.

Los artefactos se nombran con sistema y arquitectura explícitos —`atlas-print-agent_3.1.0_amd64.deb`,
`atlas-print-agent-3.1.0-arm64.pkg`, `atlas-print-agent-3.1.0-x86_64.pkg`,
`atlas-print-agent-setup-3.1.0.exe`— porque quien instala en una Mac tiene que elegir entre dos, y en el cuerpo
de la release va una línea que diga cuál es cuál (Apple Silicon contra Intel). Elegir mal es un error que se
descubre hasta el doble clic.

## 9. Firma: SmartScreen y Gatekeeper

| | Qué verá quien instale | Rodeo | Arreglo de verdad |
|---|---|---|---|
| Windows | *"Windows protegió su PC"* (SmartScreen) | *Más información → Ejecutar de todas formas* | Certificado de firma de código OV/EV, del orden de cientos de dólares al año; el EV limpia SmartScreen desde el primer día, el OV tarda en ganar reputación |
| macOS | *"No se puede abrir porque Apple no puede comprobar…"* (Gatekeeper) | clic derecho → *Abrir*, o Ajustes → Privacidad y seguridad → *Abrir de todos modos* | Apple Developer Program (99 USD/año) más notarización en el propio workflow |
| Ubuntu | nada | — | — |

**Decisión: no firmar todavía.** Quien instala está presente y el rodeo es de un clic; pagar dos certificados
antes de que el mecanismo esté probado en campo es comprar tranquilidad en el orden equivocado. El workflow se
escribe de modo que **agregar la firma sea añadir un paso y dos secretos**, no rehacerlo.

El rodeo va documentado en el runbook **con captura de pantalla**: un técnico que ve "Windows protegió su PC" y
se echa para atrás es un despliegue perdido.

Que el antivirus marque ejecutables de PyInstaller es un **falso positivo conocido y frecuente**, no una rareza;
ya se vive con `Atlas Labels.exe`, donde se resolvió con una exclusión.

## 10. Verificación

Esto es lo que separa "escribimos instaladores" de "el autoarranque funciona".

### 10.1 Se prueba en la máquina de desarrollo

El WSL de esta máquina **corre systemd de verdad** (`systemctl is-system-running` → `running`), así que el
camino de Ubuntu se verifica aquí, no a ciegas:

- construir el binario, instalar el `.deb`, `systemctl is-enabled`;
- **matar el proceso y comprobar que revive en 5 s**;
- `curl -k https://127.0.0.1:9100/health`.

**La prueba que valida el §5 entero:** sacar la huella SHA-256 de `cert.pem`, reinstalar el paquete encima y
comprobar que **la huella no cambió**. Eso es, literalmente, "la cajera no vuelve a aceptar nada". Si pasa, el
diseño del directorio de estado está bien; si falla, está mal y se ve al instante.

Windows se verifica en la PC del dueño: construir el `.exe`, instalarlo, cerrar sesión y volver a entrar, y
confirmar que el agente ya está arriba sin abrir nada.

### 10.2 Se prueba en la Mac del dueño

Hay una Mac disponible, hoy corriendo el agente desde bash (dato del 2026-09-22), así que macOS **sí se
verifica** contra una máquina real — con la mano del dueño, no la de un CI:

- instalar el `.pkg`, cerrar sesión, volver a entrar;
- `launchctl print gui/$(id -u)/com.atlasone.print-agent` → **`state = running`** (el comando devuelve 0 también
  con el servicio cargado pero caído; lo que hay que leer es `state`);
- `curl -k https://127.0.0.1:9100/health`;
- doble clic en el `.app` con el agente ya corriendo → debe decir *"ya está activo"*, no fallar por el puerto;
- impresión de prueba de punta a punta desde el POS: que `/health` responda no garantiza que salga papel.

### 10.3 Tests automatizados que se agregan

- Resolución del directorio de estado por sistema, con la plataforma simulada, sin tocar disco real.
- Parseo de `agent.conf` y su precedencia (entorno > archivo > default).
- Humo por plataforma en CI (§8).
- Los 30 de `legacy/tests/` siguen en su estado actual: 27 pasan, 3 fallan a propósito.

## 11. Migración de las cajas que hoy están en modo manual

Ninguna caja está convertida, pero varias corren el modo manual —incluida la Mac—, y ahí hay un certificado que
el navegador de esa caja **ya aceptó**. Perderlo significa que la cajera vuelva a pasar por la pantalla de
advertencia del navegador.

El instalador, en los tres sistemas:

1. Busca un `cert.pem` / `key.pem` previo en las rutas conocidas del modo manual y, si lo encuentra, lo **copia
   al nuevo directorio de estado** antes de arrancar. Si no, genera uno nuevo y lo dice.
2. **Mata el envoltorio del modo manual** —ese `while true` que relanza el agente cada 5 s— antes de levantar el
   servicio. Si sigue vivo, le pelea el puerto 9100 y `/health` puede acabar respondiendo desde el agente manual
   mientras el servicio se reinicia en bucle; el runbook ya documenta esa confusión como la más cara de depurar.

La diferencia con hoy: esto ocurre **una sola vez, en la conversión**. De ahí en adelante el estado vive fuera
de la carpeta de instalación y ninguna actualización lo toca.

## 12. Cambios requeridos en otros repos

**Restricción del proyecto (dueño, 2026-09-22): desde este repo no se modifica ningún archivo de otro
proyecto.** Lo que deba cambiar allá se documenta aquí con precisión suficiente para que alguien lo ejecute sin
volver a preguntar.

Cuando existan las releases, `atlas-one` y `Atlas-Rmazh` deben cambiar lo siguiente. Nada de esto es requisito
para que el autoarranque funcione: sin ello, la pantalla `/printer-settings` simplemente sigue entregando el
agente viejo en modo manual, y conviven dos mecanismos.

| Repo | Archivo | Cambio | Riesgo si se olvida |
|---|---|---|---|
| `atlas-one` y `Atlas-Rmazh` | `app/routers/printer.py` | `GET /api/printer/download-agent?platform=windows\|linux\|mac` deja de armar el ZIP leyendo `tools/print_agent/` por ruta relativa, y pasa a **redirigir** al artefacto correspondiente de la release de este repo (`.deb`, `.pkg` según arquitectura, `.exe`) | La pantalla sigue entregando el modo manual; dos mecanismos conviviendo en campo |
| `atlas-one` y `Atlas-Rmazh` | `tests/test_print_agent_bundle.py` | Ese test afirma hoy los **nombres de los scripts** que cita la UI y el contenido del ZIP por plataforma. Al pasar a redirección debe afirmar la **URL de la release** y la elección de artefacto por plataforma | Se pierde la red que ya salvó una vez a este proyecto: un renombrado al español dejó la pantalla citando archivos inexistentes durante dos meses, lo que hizo inalcanzable el autoarranque |
| `atlas-one` (frontend) | `PrinterSettings.tsx` | El texto deja de decir "descarga y ejecuta el script" y pasa a "descarga e instala". **Desaparece la instrucción de dejar la ventana abierta** | La cajera sigue el texto viejo y deja una ventana peleándole el puerto 9100 al servicio recién instalado |

Nota: `tools/print_agent/` puede quedarse en ambos repos como está hasta que las releases estén probadas en
campo. Quitarlo es un paso posterior y separado.

## 13. Fuera de alcance de esta entrega

Actualización automática del agente (por ahora se reinstala el paquete); firma y notarización (§9); ícono de
bandeja; BLE; empaquetar la app de etiquetas del mismo modo —tiene sentido, es otra entrega—; un vigilante
propio en Windows si los reintentos del Programador de tareas resultan insuficientes (§6.3); y la
reestructuración del paquete `atlas_print_agent/` del §5.1 del spec del agente unificado, que sigue siendo el
siguiente paso grande y no es requisito de esto.

**Arquitecturas:** se publica `.deb` solo para **amd64**. Ubuntu en ARM (una caja sobre Raspberry Pi, por
ejemplo) queda fuera hasta que exista una; agregarlo después es añadir un runner a la matriz, no rediseñar
nada. En macOS sí se publican las dos arquitecturas desde el primer día, porque las Mac de campo pueden ser
Intel o Apple Silicon indistintamente.
