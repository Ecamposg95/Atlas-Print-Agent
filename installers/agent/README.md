# Instalar el agente de impresión en una caja

Un archivo por sistema. Se instala una vez, en persona o por acceso remoto, y desde ahí **el agente arranca solo
al prender la computadora**: la cajera no abre terminal ni deja ventanas abiertas. Si por costumbre le da doble
clic al ícono, el agente le dice *"ya está activo"* en vez de pelear el puerto.

Diseño: [`docs/superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md`](../../docs/superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md).

## 1. Qué archivo usar

Los paquetes salen de la [última release](https://github.com/Ecamposg95/Atlas-Print-Agent/releases/latest)
(o, antes de publicarla, de los *artifacts* del run de Actions del PR).

| Caja | Archivo | Cómo se instala |
|---|---|---|
| Ubuntu 22.04 o más nuevo (64 bits) | `atlas-print-agent_<versión>_amd64.deb` | `sudo apt install ./atlas-print-agent_<versión>_amd64.deb` |
| Mac con chip Apple (M1, M2, M3, M4…) | `atlas-print-agent-<versión>-arm64.pkg` | doble clic |
| Mac con procesador Intel | `atlas-print-agent-<versión>-x86_64.pkg` | doble clic |
| Windows 10 u 11 | `atlas-print-agent-setup-<versión>.exe` | doble clic |

**¿Mac con chip Apple o Intel?** Menú  → *Acerca de esta Mac*: *Chip Apple M…* es `arm64`; *Procesador Intel*
es `x86_64`.

Los tres instaladores **esperan a que `https://127.0.0.1:9100/health` responda con la versión recién instalada y
avisan con un error si no**. Si el instalador terminó sin error, el agente nuevo está corriendo.

**Qué hacen con el modo manual.** Detienen la ventana de `impresora_*.sh` / `impresora_win.bat`, toman el
certificado de la carpeta que la caja usaba (para que el navegador no vuelva a pedir aceptarlo) y **convierten el
lanzador viejo en un atajo al agente nuevo** (el original queda como `.retirado`). Si la cajera le da doble clic
por costumbre, ve *"El agente de impresión ya está activo"* en vez de levantar un segundo agente. En Windows esto
importa de verdad: el `.bat` viejo mataba lo que tuviera el puerto 9100.

**Si el certificado no aparece** (el instalador dice *"No había certificado previo"* en una caja que ya imprimía),
cópialo a mano de `<carpeta-del-agente-viejo>/core/certs/` al directorio de estado (§5) **antes** de instalar, o
después y reinicia el agente. La carpeta del agente viejo se ve en la ventana de la terminal que la cajera deja
abierta.

## 2. Ubuntu

**No uses el botón de descarga de Atlas One**: todavía entrega el agente viejo (un ZIP con `impresora_linux.sh`).
Baja el `.deb` de la release directo en la caja:

```bash
cd ~/Descargas
wget https://github.com/Ecamposg95/Atlas-Print-Agent/releases/download/v3.1.0/atlas-print-agent_3.1.0_amd64.deb
sudo apt update
sudo apt install ./atlas-print-agent_3.1.0_amd64.deb
```

- La nota `N: La descarga está siendo realizada en un sandbox como superusuario…` es normal al instalar un `.deb`
  desde tu carpeta personal; no es un error.
- Probado en campo el 2026-09-28 en Ubuntu 24.04: instala, responde, y tras reiniciar el agente ya está arriba sin
  abrir nada.

- Corre como **el usuario que ejecutó `sudo`**. Si la cajera es otro usuario:
  `sudo ATLAS_AGENT_USER=<usuario-de-la-caja> apt install ./atlas-print-agent_3.1.0_amd64.deb`.
- Detiene solo el modo manual (`impresora_linux.sh`) y conserva su certificado si lo encuentra en el home.
- Si termina con `✗ El agente quedó instalado pero NO respondió`: `journalctl -u atlas-print-agent -n 50 --no-pager`,
  corregir, y `sudo dpkg --configure -a`.
- Estado: `systemctl status atlas-print-agent`. Desinstalar: `sudo apt remove atlas-print-agent` (conserva el
  certificado); `sudo apt purge atlas-print-agent` borra también `/var/lib/atlas-print-agent`.
- El ícono *Agente de Impresión Atlas* queda en el menú de aplicaciones.

### 2.1 Colas de impresora en Ubuntu (térmica y Zebra)

En Linux el agente imprime con `lp -d <cola> -` **sin** `-o raw` (`main.py`, `_print_unix`), así que **cada
impresora necesita una cola CUPS raw**. Ubuntu da de alta sola las impresoras USB, pero **con driver**: a la
Zebra le crea `ZTC-GX420t` con el driver ZPL de CUPS, que filtra el ZPL que manda Atlas One. Esa cola no sirve.

```bash
sudo lpinfo -v                     # debe listar usb://Zebra... y la térmica (p. ej. usb://SPRT/SP-EP...)
ZEBRA=$(sudo lpinfo -v | grep -o 'usb://Zebra[^ ]*' | head -1)
sudo lpadmin -p zebra -E -v "$ZEBRA" -m raw
ls /etc/cups/ppd/                  # una cola raw NO tiene .ppd; las que sí tienen, llevan driver
sudo lpadmin -x ZTC-GX420t         # borrar la cola automática con driver
printf '^XA^FO50,50^A0N,50,50^FDPRUEBA^FS^XZ' | lp -d zebra -     # prueba directa
```

Hallazgos de campo (Eleven Boutique, Ubuntu 24.04, 2026-09-29):

- **Si la Zebra no aparece en `lpinfo -v`, mira `lsusb` antes que CUPS.** Si tampoco sale ahí (ID `0a5f`,
  `Zebra Technologies ZTC GX420t`), es físico. En esa caja cambiar el cable no bastó: **era el puerto USB**.
  Conectada en otro puerto apareció al instante.
- La térmica SPRT sale en `lsusb` como `0483:5720 STMicroelectronics Mass Storage Device`. El nombre engaña,
  pero es la impresora.
- Quedan colas duplicadas por impresora (la automática de Ubuntu, la del asistente del POS y la manual). **Antes
  de borrar una, revisa cuál tiene configurada el POS**: `thermal80`, por ejemplo, la crea el asistente.
- `/printers/detect` no conoce ni la Zebra ni la SPRT y les sugiere a las dos el nombre `thermal80` con papel de
  80 mm. Crea las colas a mano, con nombres distintos.

## 3. macOS

1. **Si esa Mac ya imprime en modo manual**, copiar antes su certificado para que el navegador no vuelva a pedir
   aceptarlo. macOS puede negarle al instalador leer Descargas o Escritorio, así que no hay que confiar en que lo
   encuentre solo. En Terminal, con la ruta de la carpeta donde vive hoy el agente:

   ```bash
   mkdir -p ~/Library/Application\ Support/AtlasPrintAgent/certs
   cp <carpeta-del-agente>/core/certs/*.pem ~/Library/Application\ Support/AtlasPrintAgent/certs/
   ```

   y **cerrar la ventana de Terminal donde corre `impresora_mac.sh`**.
2. **Instalar con la sesión de la cajera abierta**: el LaunchAgent queda en el usuario que tenga la pantalla.
   Doble clic en el `.pkg`. Como no está firmado, macOS dirá que *no puede comprobar el desarrollador*: cerrar el
   aviso y ir a **Ajustes del Sistema → Privacidad y seguridad → (abajo) "Abrir de todos modos"** e ingresar la
   contraseña. En macOS 15 el truco de clic derecho → *Abrir* ya no basta; en versiones anteriores también sirve.
3. La primera vez, macOS 15 muestra el aviso *"Elementos de inicio agregados"*. **No desactivarlo**: si se apaga,
   la Mac vuelve a quedar sin agente al iniciar sesión, sin avisar a nadie.

Comprobar: `launchctl print gui/$(id -u)/com.atlasone.print-agent | grep state` → `state = running` (el comando
devuelve 0 también cuando está caído; lo que cuenta es `state`), y `curl -k https://127.0.0.1:9100/health`.

Queda `Atlas Print Agent` en Aplicaciones y un alias en el Escritorio.
Desinstalar: `sudo "/Library/Application Support/AtlasPrintAgent/desinstalar.sh"` (agregar `--purgar` para borrar
también certificado y log).

## 4. Windows

1. Iniciar sesión **con la cuenta de la cajera** (la instalación es por usuario, no pide administrador).
2. Si esa PC corre hoy `impresora_win.bat`, no hace falta cerrarlo: el instalador lo detiene y conserva el
   certificado si lo encuentra en el perfil del usuario.
3. Doble clic en el `.exe`. Como no está firmado, aparece **"Windows protegió su PC"**: *Más información →
   Ejecutar de todas formas*.
4. Si el antivirus lo marca, es el falso positivo conocido de PyInstaller (igual que `Atlas Labels.exe`): agregar
   una exclusión para `%LOCALAPPDATA%\Programs\AtlasPrintAgent`.

Queda una tarea **Atlas Print Agent** en el Programador de tareas: arranca al iniciar sesión y, además, cada
minuto revisa que siga vivo (si ya corre, no hace nada). Acceso directo en el Escritorio y en el menú Inicio.
Si el instalador avisa que el agente no respondió, el detalle está en `%LOCALAPPDATA%\AtlasPrintAgent\instalador.log`.
Desinstalar: *Configuración → Aplicaciones → Agente de Impresión Atlas*.

## 5. Dónde vive cada cosa

| Sistema | Programa | Estado (certificado + `agent.conf`) | Log |
|---|---|---|---|
| Ubuntu | `/usr/lib/atlas-print-agent/` | `/var/lib/atlas-print-agent/` | `journalctl -u atlas-print-agent` y `agent.log` en el estado |
| macOS | `/Applications/Atlas Print Agent.app` | `~/Library/Application Support/AtlasPrintAgent/` | `~/Library/Logs/AtlasPrintAgent/` |
| Windows | `%LOCALAPPDATA%\Programs\AtlasPrintAgent\` | `%LOCALAPPDATA%\AtlasPrintAgent\` | ahí mismo |

El estado vive **fuera** de la carpeta del programa: reinstalar o actualizar nunca cambia el certificado.

`agent.conf` son líneas `CLAVE=valor` (`ATLAS_AGENT_ORIGINS`, `ATLAS_AGENT_PORT`, `ATLAS_AGENT_HOST`). Una
variable de entorno con el mismo nombre gana sobre el archivo.

## 6. Cambiar el dominio del POS

`localhost`, `*.up.railway.app` y `(*.)atlasone.com.mx` se aceptan sin configurar nada. Para otro dominio, editar
`agent.conf` en el directorio de estado:

```
ATLAS_AGENT_ORIGINS=https://pos.micliente.com
```

y reiniciar el agente (Ubuntu: `sudo systemctl restart atlas-print-agent`; Mac y Windows: cerrar sesión y volver
a entrar). No hace falta reinstalar.

## 7. Verificación después de instalar

1. `https://127.0.0.1:9100/health` responde con `"version":"3.1.0"`.
2. Reiniciar la computadora y, **sin abrir nada**, `/health` vuelve a responder.
3. Doble clic en el ícono → *"El agente de impresión ya está activo"*.
4. **Imprimir un ticket real desde el POS**: que `/health` responda no garantiza que salga papel.

## 8. Punto abierto en Ubuntu

`/printers/install` y `/system/spooler-repair` ejecutan `lpadmin` y `cupsenable`. Desde el servicio, pertenecer
al grupo `lpadmin` puede no bastar, porque CUPS pide autenticación y el servicio no tiene dónde escribirla. Si en
campo falla, la salida es una regla de `sudoers` limitada a esos dos comandos para el usuario de la caja (spec
§6.1), **no** correr el agente como root. Imprimir (`/print`) no necesita nada de esto.

## 9. Construir localmente

```bash
# Linux (WSL). Python del sistema: PyInstaller necesita libpython, que el Python de uv no trae.
uv venv /tmp/agente-venv --python /usr/bin/python3.12
uv pip install --python /tmp/agente-venv/bin/python -r installers/agent/requirements-build.txt
/tmp/agente-venv/bin/python installers/agent/construir.py
/tmp/agente-venv/bin/python installers/agent/humo.py
bash installers/agent/linux/build_deb.sh
```

En macOS, lo mismo con `bash installers/agent/mac/build_pkg.sh` al final. En Windows, `construir.py` y luego
Inno Setup 6 sobre `installers/agent/windows/atlas-print-agent.iss` con `ATLAS_VERSION` definida. Lo normal es
dejar que lo haga el workflow `release-agente` al empujar un tag `vX.Y.Z` (debe coincidir con `VERSION` de
`main.py`).
