# Autoarranque multiplataforma del agente: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el agente de impresión arranque solo al prender la caja en Ubuntu, Windows y macOS, instalado con un
solo archivo (`.deb`, `.exe`, `.pkg`), sin Python en la máquina de destino, y con un ícono de doble clic que nunca
le pelea el puerto al agente que ya corre. La cajera deja de tocar la terminal.

**Architecture:** El código legado (`legacy/print_agent/core/main.py`) se empaqueta con PyInstaller casi tal cual.
Dos módulos nuevos junto a él: `agent_state.py` (dónde viven certificado, `agent.conf` y log, fuera de la carpeta
de instalación) y `lanzador.py` (punto de entrada del binario: sin argumentos es el ícono de doble clic que avisa
"ya está activo"; con `--servicio` es lo que corren systemd, launchd y el Programador de tareas). Cada sistema
tiene su envoltorio nativo bajo `installers/agent/`, y un workflow de GitHub Actions construye los cuatro
paquetes al empujar un tag `v*`.

**Tech Stack:** Python 3.12, FastAPI/uvicorn (ya existentes), PyInstaller 6 en modo carpeta (`--onedir`),
`dpkg-deb` + systemd, `pkgbuild`/`productbuild` + LaunchAgent, Inno Setup 6 + Programador de tareas, GitHub
Actions, pytest.

**Spec:** `docs/superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md`

## Global Constraints

- **La API v3 no cambia**: puerto `9100`, `https://127.0.0.1:9100`, mismos endpoints y respuestas. Solo cambia el
  valor de `version` en `/health` y `/diagnostics` (`"3.1.0"`).
- **El agente escucha solo en loopback** (`127.0.0.1` por omisión).
- **Cambios permitidos a `legacy/print_agent/core/main.py`** (excepción consciente al congelamiento, §5.2 del
  spec y rulings de este plan): directorio de estado, `agent.conf`, certificado en proceso, `VERSION = "3.1.0"`,
  entrada `run()`, y los dos guardas de binario congelado de la Task 3. Nada más.
- `generate_cert.py` solo gana el parámetro `cert_dir`; su comportamiento sin argumento no cambia.
- **Precedencia de configuración: variable de entorno > `agent.conf` > valor por omisión.** Claves:
  `ATLAS_AGENT_PORT`, `ATLAS_AGENT_ORIGINS`, `ATLAS_AGENT_HOST`. `ATLAS_AGENT_STATE_DIR` sobrescribe el directorio.
- Directorio de estado: Ubuntu `/var/lib/atlas-print-agent/`; macOS `~/Library/Application Support/AtlasPrintAgent/`
  (log en `~/Library/Logs/AtlasPrintAgent/`); Windows `%LOCALAPPDATA%\AtlasPrintAgent\`. Certificado en
  `<estado>/certs/cert.pem` y `<estado>/certs/key.pem`.
- **Reinstalar o actualizar nunca cambia el certificado.** Ningún instalador escribe sobre un `cert.pem` que ya
  exista en el directorio de estado.
- **Todo instalador espera a `/health` y falla ruidosamente si no responde.**
- Etiqueta launchd: `com.atlasone.print-agent`. Servicio systemd: `atlas-print-agent`. Tarea de Windows:
  `Atlas Print Agent`.
- Artefactos: `atlas-print-agent_<v>_amd64.deb`, `atlas-print-agent-<v>-arm64.pkg`,
  `atlas-print-agent-<v>-x86_64.pkg`, `atlas-print-agent-setup-<v>.exe`.
- Sin firma de código (§9 del spec).
- **Todo string visible al usuario en español.** Commits en español, imperativo, módulo al frente, terminando en
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. `git add <archivos>`, nunca `git add -A`.
- **No se edita ningún archivo de otro repo** (atlas-one, Atlas-Rmazh).
- Tests nuevos: `uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography --with pytest python -m pytest tests/agent -q`
- Tests legados: `uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography --with pytest python -m pytest legacy/tests -q`
  → **27 pasan, 3 fallan** (`BT:`, UNC y dominio propio sin variable). Ese estado no cambia.
- Tests de etiquetas: `uv run --no-project --with openpyxl --with pytest python -m pytest tests/labels -q` → 122 pasan.

## Rulings sobre el spec (se anotan en el spec en la Task 11)

1. **`--onedir` en vez de `--onefile`.** Con un instalador de por medio, `--onefile` no aporta nada y cuesta: se
   descomprime en un temporal en cada arranque, deja carpetas `_MEI*` huérfanas cada vez que el proceso muere por
   `kill -9` (que es justo lo que `Restart=always` y la prueba de revivir provocan), y en Windows son dos procesos
   (cargador + agente), de modo que matar al hijo deja vivo al padre y el Programador de tareas no se entera. El
   análisis del §5.1 sigue valiendo: en `--onedir` el `__file__` de `main` tampoco es una ruta real.
2. **Dos guardas más en `main.py`**: `Path(__file__).stat()` del banner revienta bajo PyInstaller (el archivo no
   existe), y el reintento de `pywin32_postinstall` con `sys.executable` relanzaría el propio agente.
3. **`run()` y `lanzador.py`.** El comportamiento "ya está activo" del §6.2/§6.4 necesita un punto de entrada que
   decida antes de arrancar uvicorn; el cuerpo de `if __name__ == "__main__"` pasa a `def run()`.
4. **En Linux el directorio se resuelve así**: `ATLAS_AGENT_STATE_DIR` > `$STATE_DIRECTORY` (lo pone systemd por
   `StateDirectory=`) > `/var/lib/atlas-print-agent` si existe y es escribible (el ícono de doble clic, corriendo
   como la cajera, usa el mismo certificado que el servicio) > `~/.local/state/atlas-print-agent` (desarrollo).
5. **Windows: además del disparador de inicio de sesión, uno cada minuto con `IgnoreNew`.** `RestartOnFailure`
   del Programador solo actúa si la tarea no logra lanzarse, no cuando el proceso muere. El disparador periódico
   es un vigilante sin código: si el agente vive, la instancia nueva se ignora; si murió, lo levanta en ≤ 60 s.
6. **Runners**: `macos-13` ya no existe; Intel se construye en `macos-15-intel`, Apple Silicon en `macos-15`. El
   `.deb` se construye en `ubuntu-22.04` (glibc 2.35), no en `ubuntu-latest`: un binario hecho en 24.04 no arranca
   en una caja con 22.04. **Mínimo soportado: Ubuntu 22.04.**
7. **El `.deb` instala en `/usr/lib/atlas-print-agent/`**, no en `/opt/atlas-print-agent/`, que es donde el
   instalador legado de sistema ponía su copia con venv.

## Review Focus

1. **`agent.conf` editado a mano en el Bloc de notas** (BOM UTF-8, finales CRLF, espacios, comillas) o con un
   puerto inválido (`91OO`): el agente debe arrancar igual, leyendo lo que sí sirve y con `9100` por omisión.
   → tests en la Task 1.
2. **Doble clic con el 9100 ocupado por otro programa que no es el agente**: no debe decir "ya está activo"; debe
   intentar arrancar y, al fallar, mostrar un error que diga dónde está el log. → tests en la Task 4.
3. **Binario con ventana (`--windowed`) en Windows y macOS**: `sys.stdout`/`sys.stderr` son `None` y uvicorn llama
   `isatty()` sobre ellos al configurar su log; sin guarda, el agente muere al arrancar sin dejar rastro.
   → test en la Task 4 y humo del binario en la Task 5 (en CI corre sobre el binario con ventana).
4. **Directorio de estado no escribible** (perfil de Windows de solo lectura, permisos rotos): importar el agente
   no debe reventar; arranca sin log en archivo y cae a HTTP si no puede crear el certificado. → test en la Task 3.
5. **Un certificado previo que ya está en el directorio de estado** (reinstalación, o la Mac que ya corrió el
   instalador legado de servicio, cuyo destino coincide con el nuevo directorio de estado): nada lo regenera ni lo
   reemplaza. → test de huella en la Task 3 y prueba de reinstalación en la Task 7.

---

## Estructura de archivos

| Archivo | Cambio | Responsabilidad |
|---|---|---|
| `legacy/print_agent/core/agent_state.py` | crear | Directorio de estado y de log por sistema; lectura de `agent.conf`; precedencia. Solo biblioteca estándar. |
| `legacy/print_agent/core/generate_cert.py` | modificar | Parámetro `cert_dir`. |
| `legacy/print_agent/core/main.py` | modificar | Usa `agent_state`; certificado en proceso; `run()`; guardas de binario congelado; `VERSION`. |
| `legacy/print_agent/core/lanzador.py` | crear | Entrada del binario: modo ícono (diálogos) y modo `--servicio`. |
| `legacy/tests/conftest.py` | crear | Aísla el directorio de estado para que los tests legados no escriban en el home. |
| `tests/agent/__init__.py`, `tests/agent/conftest.py` | crear | Rutas de importación y aislamiento del estado. |
| `tests/agent/test_agent_state.py` | crear | Resolución por sistema, `agent.conf`, precedencia, puerto. |
| `tests/agent/test_generate_cert.py` | crear | Generación en un directorio dado; no regenera uno válido. |
| `tests/agent/test_main_estado.py` | crear | `main.py` usa el directorio de estado y `agent.conf`. |
| `tests/agent/test_lanzador.py` | crear | Detección del agente, diálogos, modo servicio. |
| `tests/agent/test_empaquetado.py` | crear | `version_agente.py` y rutas de `construir.py`. |
| `installers/agent/requirements-build.txt` | crear | Versiones fijas para construir. |
| `installers/agent/version_agente.py` | crear | Lee `VERSION` de `main.py`; verifica el tag. |
| `installers/agent/construir.py` | crear | Corre PyInstaller para el sistema actual. |
| `installers/agent/humo.py` | crear | Arranca el binario, exige `/health` con la versión correcta, lo mata. |
| `installers/agent/linux/*` | crear | Unidad systemd, `.desktop`, `control`, `postinst`, `prerm`, `postrm`, `build_deb.sh`. |
| `installers/agent/mac/*` | crear | Plantilla del LaunchAgent, `scripts/preinstall`, `scripts/postinstall`, `desinstalar.sh`, `build_pkg.sh`. |
| `installers/agent/windows/*` | crear | `atlas-print-agent.iss`, `registrar.ps1`, `tarea.xml`. |
| `installers/agent/notas-release.md` | crear | Cuerpo de la release: qué archivo es para qué caja. |
| `installers/agent/README.md` | crear | Runbook de instalación, rodeos de SmartScreen/Gatekeeper, verificación. |
| `.github/workflows/release.yml` | crear | Pruebas, construcción en 4 runners, humo, release. |
| `AGENTS.md`, `README.md`, spec | modificar | Documentar lo nuevo y los rulings. |

---

### Task 1: `agent_state` — directorio de estado y `agent.conf`

**Files:**
- Create: `legacy/print_agent/core/agent_state.py`
- Create: `tests/agent/__init__.py` (vacío), `tests/agent/conftest.py`
- Test: `tests/agent/test_agent_state.py`

**Interfaces:**
- Produces:
  - `state_dir(system: str | None = None, env: Mapping[str, str] | None = None, home: Path | None = None, writable: Callable[[Path], bool] = _writable) -> Path`
  - `log_dir(system=None, env=None, home=None, writable=_writable) -> Path`
  - `read_conf(path: Path) -> dict[str, str]`
  - `load_config(state: Path, env: Mapping[str, str] | None = None) -> dict[str, str]`
  - `port(config: Mapping[str, str]) -> int`, `host(config: Mapping[str, str]) -> str`
  - Constantes `CONF_NAME = "agent.conf"`, `CONF_KEYS`, `DEFAULT_PORT = 9100`, `DEFAULT_HOST = "127.0.0.1"`,
    `LINUX_SYSTEM_STATE = Path("/var/lib/atlas-print-agent")`.

- [ ] **Step 1: Escribir `tests/agent/__init__.py` (vacío) y `tests/agent/conftest.py`**

```python
"""Rutas de importación y aislamiento para los tests del agente empaquetado.

El agente vive en legacy/print_agent/core como módulos sueltos (main, agent_state,
generate_cert, lanzador), y las herramientas de empaquetado en installers/agent.
Ninguno es un paquete, así que se agregan al sys.path.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CORE = RAIZ / "legacy" / "print_agent" / "core"
INSTALADORES = RAIZ / "installers" / "agent"

for _ruta in (CORE, INSTALADORES):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))


@pytest.fixture(autouse=True)
def _estado_aislado(tmp_path, monkeypatch):
    """Ningún test lee ni escribe el directorio de estado real de esta máquina."""
    monkeypatch.setenv("ATLAS_AGENT_STATE_DIR", str(tmp_path / "estado"))
    for clave in ("ATLAS_AGENT_PORT", "ATLAS_AGENT_ORIGINS", "ATLAS_AGENT_HOST", "STATE_DIRECTORY"):
        monkeypatch.delenv(clave, raising=False)
```

- [ ] **Step 2: Escribir los tests que fallan en `tests/agent/test_agent_state.py`**

```python
"""Dónde guarda el agente su estado y cómo lee agent.conf.

El certificado vive fuera de la carpeta de instalación para que reinstalar no lo
cambie: si cambia, la cajera vuelve a la pantalla de advertencia del navegador.
"""
from pathlib import Path

import agent_state

HOME = Path("/home/caja")
NUNCA = lambda _p: False  # noqa: E731
SIEMPRE = lambda _p: True  # noqa: E731


class TestStateDir:
    def test_la_variable_gana_en_cualquier_sistema(self):
        for sistema in ("Linux", "Darwin", "Windows"):
            env = {"ATLAS_AGENT_STATE_DIR": "/tmp/x", "STATE_DIRECTORY": "/var/lib/otro"}
            assert agent_state.state_dir(sistema, env, HOME, SIEMPRE) == Path("/tmp/x")

    def test_windows_usa_localappdata(self):
        env = {"LOCALAPPDATA": r"C:\Users\caja\AppData\Local"}
        assert agent_state.state_dir("Windows", env, HOME, NUNCA) == (
            Path(r"C:\Users\caja\AppData\Local") / "AtlasPrintAgent"
        )

    def test_windows_sin_localappdata_cae_al_perfil(self):
        assert agent_state.state_dir("Windows", {}, HOME, NUNCA) == (
            HOME / "AppData" / "Local" / "AtlasPrintAgent"
        )

    def test_mac_usa_application_support(self):
        assert agent_state.state_dir("Darwin", {}, HOME, SIEMPRE) == (
            HOME / "Library" / "Application Support" / "AtlasPrintAgent"
        )

    def test_linux_bajo_systemd_usa_state_directory(self):
        env = {"STATE_DIRECTORY": "/var/lib/atlas-print-agent"}
        assert agent_state.state_dir("Linux", env, HOME, NUNCA) == Path("/var/lib/atlas-print-agent")

    def test_linux_state_directory_con_varias_rutas_toma_la_primera(self):
        env = {"STATE_DIRECTORY": "/var/lib/a:/var/lib/b"}
        assert agent_state.state_dir("Linux", env, HOME, NUNCA) == Path("/var/lib/a")

    def test_linux_icono_usa_el_estado_del_servicio_si_puede_escribir(self):
        assert agent_state.state_dir("Linux", {}, HOME, SIEMPRE) == Path("/var/lib/atlas-print-agent")

    def test_linux_sin_servicio_usa_xdg_state(self):
        assert agent_state.state_dir("Linux", {}, HOME, NUNCA) == (
            HOME / ".local" / "state" / "atlas-print-agent"
        )
        env = {"XDG_STATE_HOME": "/data/estado"}
        assert agent_state.state_dir("Linux", env, HOME, NUNCA) == Path("/data/estado/atlas-print-agent")


class TestLogDir:
    def test_mac_separa_el_log(self):
        assert agent_state.log_dir("Darwin", {}, HOME, SIEMPRE) == HOME / "Library" / "Logs" / "AtlasPrintAgent"

    def test_con_la_variable_el_log_va_al_estado_tambien_en_mac(self):
        env = {"ATLAS_AGENT_STATE_DIR": "/tmp/x"}
        assert agent_state.log_dir("Darwin", env, HOME, SIEMPRE) == Path("/tmp/x")

    def test_linux_y_windows_loguean_en_el_estado(self):
        env = {"STATE_DIRECTORY": "/var/lib/atlas-print-agent"}
        assert agent_state.log_dir("Linux", env, HOME, NUNCA) == Path("/var/lib/atlas-print-agent")
        env = {"LOCALAPPDATA": "C:/L"}
        assert agent_state.log_dir("Windows", env, HOME, NUNCA) == Path("C:/L") / "AtlasPrintAgent"


class TestReadConf:
    def test_archivo_inexistente_es_vacio(self, tmp_path):
        assert agent_state.read_conf(tmp_path / "no-existe.conf") == {}

    def test_lee_claves_conocidas_e_ignora_el_resto(self, tmp_path):
        conf = tmp_path / "agent.conf"
        conf.write_text(
            "# comentario\n"
            "\n"
            "ATLAS_AGENT_ORIGINS=https://pos.micliente.com,https://otro.mx\n"
            "  ATLAS_AGENT_PORT = 9101  \n"
            "OTRA_COSA=1\n"
            "linea sin igual\n",
            encoding="utf-8",
        )
        assert agent_state.read_conf(conf) == {
            "ATLAS_AGENT_ORIGINS": "https://pos.micliente.com,https://otro.mx",
            "ATLAS_AGENT_PORT": "9101",
        }

    def test_tolera_bom_crlf_y_comillas_del_bloc_de_notas(self, tmp_path):
        conf = tmp_path / "agent.conf"
        conf.write_bytes(
            "\ufeffATLAS_AGENT_ORIGINS=\"https://pos.micliente.com\"\r\nATLAS_AGENT_HOST='127.0.0.1'\r\n".encode("utf-8")
        )
        assert agent_state.read_conf(conf) == {
            "ATLAS_AGENT_ORIGINS": "https://pos.micliente.com",
            "ATLAS_AGENT_HOST": "127.0.0.1",
        }

    def test_bytes_que_no_son_utf8_no_revientan(self, tmp_path):
        conf = tmp_path / "agent.conf"
        conf.write_bytes(b"ATLAS_AGENT_PORT=9100\n\xff\xfe\x00basura")
        assert agent_state.read_conf(conf) == {}

    def test_una_carpeta_en_lugar_del_archivo_no_revienta(self, tmp_path):
        (tmp_path / "agent.conf").mkdir()
        assert agent_state.read_conf(tmp_path / "agent.conf") == {}


class TestLoadConfig:
    def test_el_entorno_gana_al_archivo(self, tmp_path):
        (tmp_path / "agent.conf").write_text(
            "ATLAS_AGENT_ORIGINS=https://archivo.mx\nATLAS_AGENT_PORT=9101\n", encoding="utf-8"
        )
        env = {"ATLAS_AGENT_ORIGINS": "https://entorno.mx"}
        assert agent_state.load_config(tmp_path, env) == {
            "ATLAS_AGENT_ORIGINS": "https://entorno.mx",
            "ATLAS_AGENT_PORT": "9101",
        }

    def test_una_variable_vacia_no_tapa_al_archivo(self, tmp_path):
        (tmp_path / "agent.conf").write_text("ATLAS_AGENT_ORIGINS=https://archivo.mx\n", encoding="utf-8")
        env = {"ATLAS_AGENT_ORIGINS": "  "}
        assert agent_state.load_config(tmp_path, env)["ATLAS_AGENT_ORIGINS"] == "https://archivo.mx"

    def test_sin_archivo_ni_entorno_es_vacio(self, tmp_path):
        assert agent_state.load_config(tmp_path, {}) == {}


class TestPuertoYHost:
    def test_valores_por_omision(self):
        assert agent_state.port({}) == 9100
        assert agent_state.host({}) == "127.0.0.1"

    def test_puerto_valido(self):
        assert agent_state.port({"ATLAS_AGENT_PORT": " 9101 "}) == 9101

    def test_puerto_invalido_cae_al_de_omision(self):
        for malo in ("91OO", "", "0", "70000", "-5"):
            assert agent_state.port({"ATLAS_AGENT_PORT": malo}) == 9100

    def test_host_vacio_cae_al_de_omision(self):
        assert agent_state.host({"ATLAS_AGENT_HOST": " "}) == "127.0.0.1"
```

- [ ] **Step 3: Correr y ver que fallan**

Run: `uv run --no-project --with pytest python -m pytest tests/agent/test_agent_state.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'agent_state'`.

- [ ] **Step 4: Implementar `legacy/print_agent/core/agent_state.py`**

```python
"""Dónde vive el estado del agente y qué configuración aplica.

El certificado, agent.conf y el log viven FUERA de la carpeta de instalación:
así reinstalar o actualizar no toca el certificado y el navegador de la caja no
vuelve a pedir que se acepte. Ver
docs/superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md §5 y §7.

Solo biblioteca estándar: lo importan main.py y lanzador.py antes que FastAPI.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Callable, Mapping, Optional

APP_DIR_UNIX = "atlas-print-agent"
APP_DIR_MAC_WIN = "AtlasPrintAgent"
LINUX_SYSTEM_STATE = Path("/var/lib/atlas-print-agent")
CONF_NAME = "agent.conf"
CONF_KEYS = ("ATLAS_AGENT_PORT", "ATLAS_AGENT_ORIGINS", "ATLAS_AGENT_HOST")
DEFAULT_PORT = 9100
DEFAULT_HOST = "127.0.0.1"


def _writable(path: Path) -> bool:
    return path.is_dir() and os.access(path, os.W_OK)


def state_dir(
    system: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
    writable: Callable[[Path], bool] = _writable,
) -> Path:
    """Directorio del certificado y de agent.conf para este sistema."""
    system = system or platform.system()
    env = os.environ if env is None else env
    home = Path.home() if home is None else home

    override = env.get("ATLAS_AGENT_STATE_DIR", "").strip()
    if override:
        return Path(override)
    if system == "Windows":
        base = env.get("LOCALAPPDATA", "").strip()
        return (Path(base) if base else home / "AppData" / "Local") / APP_DIR_MAC_WIN
    if system == "Darwin":
        return home / "Library" / "Application Support" / APP_DIR_MAC_WIN
    # Linux. systemd exporta STATE_DIRECTORY cuando la unidad declara StateDirectory=.
    systemd_dir = env.get("STATE_DIRECTORY", "").split(":")[0].strip()
    if systemd_dir:
        return Path(systemd_dir)
    # El ícono de doble clic corre como la cajera, dueña de este directorio: así usa
    # el mismo certificado que el servicio en lugar de fabricar otro.
    if writable(LINUX_SYSTEM_STATE):
        return LINUX_SYSTEM_STATE
    xdg = env.get("XDG_STATE_HOME", "").strip()
    return (Path(xdg) if xdg else home / ".local" / "state") / APP_DIR_UNIX


def log_dir(
    system: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
    writable: Callable[[Path], bool] = _writable,
) -> Path:
    """Directorio del agent.log. Solo macOS lo separa del estado."""
    system = system or platform.system()
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    if system == "Darwin" and not env.get("ATLAS_AGENT_STATE_DIR", "").strip():
        return home / "Library" / "Logs" / APP_DIR_MAC_WIN
    return state_dir(system, env, home, writable)


def read_conf(path: Path) -> dict[str, str]:
    """Lee líneas CLAVE=valor. Nunca lanza: un agent.conf roto no debe tumbar al agente.

    Tolera lo que deja el Bloc de notas (BOM, CRLF) y comillas alrededor del valor.
    Solo se aceptan las claves de CONF_KEYS.
    """
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return {}
    conf: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key in CONF_KEYS:
            conf[key] = value
    return conf


def load_config(state: Path, env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """agent.conf del directorio de estado, con las variables de entorno encima.

    Una variable vacía cuenta como no puesta: las unidades de servicio viejas
    declaran ATLAS_AGENT_ORIGINS= sin valor y no deben tapar al archivo.
    """
    env = os.environ if env is None else env
    config = read_conf(Path(state) / CONF_NAME)
    for key in CONF_KEYS:
        value = env.get(key, "").strip()
        if value:
            config[key] = value
    return config


def port(config: Mapping[str, str]) -> int:
    try:
        value = int(config.get("ATLAS_AGENT_PORT", "").strip())
    except ValueError:
        return DEFAULT_PORT
    return value if 0 < value < 65536 else DEFAULT_PORT


def host(config: Mapping[str, str]) -> str:
    return config.get("ATLAS_AGENT_HOST", "").strip() or DEFAULT_HOST
```

- [ ] **Step 5: Correr y ver que pasan**

Run: `uv run --no-project --with pytest python -m pytest tests/agent/test_agent_state.py -q`
Expected: todos pasan.

- [ ] **Step 6: Commit**

```bash
git add legacy/print_agent/core/agent_state.py tests/agent/__init__.py tests/agent/conftest.py tests/agent/test_agent_state.py
git commit -m "agente: directorio de estado por sistema y agent.conf con precedencia

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `generate_cert` recibe el directorio destino

**Files:**
- Modify: `legacy/print_agent/core/generate_cert.py:26-32` (inicio de `generate_self_signed_cert`)
- Test: `tests/agent/test_generate_cert.py`

**Interfaces:**
- Produces: `generate_cert.generate_self_signed_cert(cert_dir: str | os.PathLike | None = None) -> None`. Con
  `None` conserva el comportamiento de hoy (`<carpeta de generate_cert.py>/certs`), que usan `impresora_*.sh`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
"""El certificado se genera en proceso, en el directorio que se le indique.

Bajo PyInstaller no existe un intérprete que lance generate_cert.py como script,
y la carpeta de generate_cert.py no es un lugar donde guardar nada.
"""
import hashlib
import os
import stat

import generate_cert


def _huella(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_genera_en_el_directorio_indicado_y_lo_crea(tmp_path):
    destino = tmp_path / "estado" / "certs"
    generate_cert.generate_self_signed_cert(destino)
    assert (destino / "cert.pem").is_file()
    assert (destino / "key.pem").is_file()


def test_la_llave_queda_solo_para_el_dueno(tmp_path):
    if os.name == "nt":
        return
    generate_cert.generate_self_signed_cert(tmp_path)
    assert stat.S_IMODE((tmp_path / "key.pem").stat().st_mode) == 0o600


def test_no_regenera_un_certificado_valido(tmp_path):
    generate_cert.generate_self_signed_cert(tmp_path)
    antes = _huella(tmp_path / "cert.pem")
    generate_cert.generate_self_signed_cert(tmp_path)
    assert _huella(tmp_path / "cert.pem") == antes


def test_acepta_str(tmp_path):
    generate_cert.generate_self_signed_cert(str(tmp_path / "c"))
    assert (tmp_path / "c" / "cert.pem").is_file()
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with cryptography --with pytest python -m pytest tests/agent/test_generate_cert.py -q`
Expected: FAIL con `TypeError: generate_self_signed_cert() takes 0 positional arguments but 1 was given`.

- [ ] **Step 3: Implementar.** Reemplazar el inicio de la función:

```python
def generate_self_signed_cert():
    cert_dir = os.path.join(os.path.dirname(__file__), "certs")
    if not os.path.exists(cert_dir):
```

por:

```python
def generate_self_signed_cert(cert_dir=None):
    # Sin argumento: la carpeta certs/ junto a este archivo, como siempre (modo manual).
    # El agente empaquetado pasa su directorio de estado (agent_state).
    if cert_dir is None:
        cert_dir = os.path.join(os.path.dirname(__file__), "certs")
    cert_dir = os.fspath(cert_dir)
    if not os.path.exists(cert_dir):
```

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run --no-project --with cryptography --with pytest python -m pytest tests/agent/test_generate_cert.py -q`
Expected: 4 pasan.

- [ ] **Step 5: Commit**

```bash
git add legacy/print_agent/core/generate_cert.py tests/agent/test_generate_cert.py
git commit -m "agente: generate_cert acepta el directorio destino

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `main.py` usa el directorio de estado

**Files:**
- Modify: `legacy/print_agent/core/main.py` (líneas 29, 50, 66-80, 84-104, 110, 114-117, 347-349, 1308-1391)
- Create: `legacy/tests/conftest.py`
- Test: `tests/agent/test_main_estado.py`

**Interfaces:**
- Consumes: `agent_state.state_dir()`, `agent_state.log_dir()`, `agent_state.load_config(Path)`,
  `agent_state.port(dict)`, `agent_state.host(dict)` (Task 1); `generate_cert.generate_self_signed_cert(cert_dir)` (Task 2).
- Produces (atributos de módulo de `main`): `STATE_DIR: Path`, `CERT_DIR: Path`, `_CONFIG: dict[str, str]`,
  `_log_file: Path`, `_CORS_ORIGINS: list[str]`, `VERSION = "3.1.0"`, `_ensure_certs() -> tuple[Path|None, Path|None]`,
  `run() -> None` (arranca uvicorn; bloquea hasta que termina; si uvicorn no puede tomar el puerto propaga `SystemExit`).

- [ ] **Step 1: Escribir los tests que fallan en `tests/agent/test_main_estado.py`**

```python
"""main.py guarda log y certificado en el directorio de estado y lee agent.conf.

Se importa por ruta con nombre único, igual que legacy/tests: el módulo lee su
configuración al importarse.
"""
import hashlib
import importlib.util
import itertools
import os
import sys
from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parents[2] / "legacy" / "print_agent" / "core" / "main.py"
_contador = itertools.count()


def _cargar():
    nombre = f"_main_estado_{next(_contador)}"
    spec = importlib.util.spec_from_file_location(nombre, MAIN)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def estado(tmp_path):
    return Path(os.environ["ATLAS_AGENT_STATE_DIR"])


def test_version(estado):
    assert _cargar().VERSION == "3.1.0"


def test_log_y_certificado_viven_en_el_estado(estado):
    mod = _cargar()
    assert mod.STATE_DIR == estado
    assert mod.CERT_DIR == estado / "certs"
    assert mod._log_file == estado / "agent.log"
    assert mod._log_file.exists()


def test_origenes_desde_agent_conf(estado):
    estado.mkdir(parents=True)
    (estado / "agent.conf").write_text("ATLAS_AGENT_ORIGINS=https://pos.micliente.com\n", encoding="utf-8")
    assert "https://pos.micliente.com" in _cargar()._CORS_ORIGINS


def test_el_entorno_gana_a_agent_conf(estado, monkeypatch):
    estado.mkdir(parents=True)
    (estado / "agent.conf").write_text("ATLAS_AGENT_ORIGINS=https://archivo.mx\n", encoding="utf-8")
    monkeypatch.setenv("ATLAS_AGENT_ORIGINS", "https://entorno.mx")
    origenes = _cargar()._CORS_ORIGINS
    assert "https://entorno.mx" in origenes
    assert "https://archivo.mx" not in origenes


def test_ensure_certs_genera_en_el_estado_y_no_lo_cambia_despues(estado):
    mod = _cargar()
    key, cert = mod._ensure_certs()
    assert cert == estado / "certs" / "cert.pem"
    assert key == estado / "certs" / "key.pem"
    huella = hashlib.sha256(cert.read_bytes()).hexdigest()
    # Otro arranque (un reinicio de la PC, una reinstalación) con el mismo estado.
    key2, cert2 = _cargar()._ensure_certs()
    assert hashlib.sha256(cert2.read_bytes()).hexdigest() == huella


def test_diagnostics_reporta_el_certificado_del_estado(estado):
    mod = _cargar()
    mod._ensure_certs()
    assert mod._cert_info()["exists"] is True


def test_estado_no_escribible_no_impide_importar(tmp_path, monkeypatch):
    # Un archivo donde debería haber un directorio: mkdir falla con OSError.
    tapon = tmp_path / "tapon"
    tapon.write_text("x")
    monkeypatch.setenv("ATLAS_AGENT_STATE_DIR", str(tapon / "estado"))
    mod = _cargar()
    assert mod._ensure_certs() == (None, None)


def test_run_existe():
    assert callable(_cargar().run)
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography --with pytest python -m pytest tests/agent/test_main_estado.py -q`
Expected: FAIL (`VERSION` es `"3.0.0"`, `STATE_DIR` no existe, etc.).

- [ ] **Step 3: Docstring (línea 29).** Reemplazar `  - Config por env vars: ATLAS_AGENT_HOST, ATLAS_AGENT_PORT.` por:

```python
  - Config: variables de entorno o agent.conf en el directorio de estado
    (ATLAS_AGENT_HOST, ATLAS_AGENT_PORT, ATLAS_AGENT_ORIGINS). El entorno gana.
  - Estado (certificado, agent.conf, log) fuera de la carpeta de instalación:
    ver agent_state.py.
```

- [ ] **Step 4: Importar `agent_state` y resolver el estado.** Justo después de `from pydantic import BaseModel`
  (línea 50) agregar:

```python

# El estado (certificado, agent.conf, log) vive fuera de la carpeta de instalación:
# bajo PyInstaller __file__ no es una ruta real, y reinstalar no debe tocar el
# certificado. Ver docs/superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md §5.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import agent_state  # noqa: E402

STATE_DIR = agent_state.state_dir()
CERT_DIR = STATE_DIR / "certs"
_CONFIG = agent_state.load_config(STATE_DIR)
```

- [ ] **Step 5: Guarda de `pywin32_postinstall` (líneas 72-80).** Reemplazar el `except ImportError as _e:` y
  todo lo que cuelga de él por este bloque (el `try/except` interno queda bajo el `else:`):

```python
    except ImportError as _e:
        if getattr(sys, "frozen", False):
            # En el binario sys.executable ES el agente: relanzarlo no instalaría nada.
            _WIN32_ERROR = f"pywin32 not available: {_e}"
        else:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pywin32_postinstall", "-install"],
                    check=True, capture_output=True,
                )
                import win32print as _win32print
                win32print = _win32print
            except Exception as _e2:
                _WIN32_ERROR = f"pywin32 not available: {_e2 or _e}"
```

- [ ] **Step 6: Log en el directorio de log (líneas 87-104).** Reemplazar:

```python
_log_file = Path(__file__).parent / "agent.log"
_file_handler = RotatingFileHandler(_log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
_file_handler.setFormatter(_LOG_FORMAT)
```

por:

```python
_log_file = agent_state.log_dir() / "agent.log"
try:
    _log_file.parent.mkdir(parents=True, exist_ok=True)
    _file_handler: Optional[logging.Handler] = RotatingFileHandler(
        _log_file, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    _file_handler.setFormatter(_LOG_FORMAT)
except OSError:
    # Sin log en archivo antes que sin agente: la consola/journal sigue recibiendo todo.
    _file_handler = None
```

  y reemplazar `logger.addHandler(_file_handler)` por:

```python
if _file_handler is not None:
    logger.addHandler(_file_handler)
```

- [ ] **Step 7: Versión y orígenes (líneas 110 y 115-117).** `VERSION = "3.0.0"` → `VERSION = "3.1.0"`. Y reemplazar:

```python
# Dominios extra vía env (separados por coma) para despliegues con dominio
# propio. Ej: ATLAS_AGENT_ORIGINS="https://pos.miempresa.com,https://app.atlasone.mx"
_ENV_ORIGINS = [o.strip() for o in os.environ.get("ATLAS_AGENT_ORIGINS", "").split(",") if o.strip()]
```

por:

```python
# Dominios extra (separados por coma) para despliegues con dominio propio, por
# variable de entorno o en agent.conf. Ej: ATLAS_AGENT_ORIGINS=https://pos.miempresa.com
_ENV_ORIGINS = [o.strip() for o in _CONFIG.get("ATLAS_AGENT_ORIGINS", "").split(",") if o.strip()]
```

- [ ] **Step 8: `_cert_info` (líneas 348-349).** Reemplazar:

```python
    cert_dir = Path(__file__).parent / "certs"
    cert_path = cert_dir / "cert.pem"
```

por:

```python
    cert_path = CERT_DIR / "cert.pem"
```

- [ ] **Step 9: `_ensure_certs` en proceso.** Reemplazar la función completa (líneas 1311-1341) por:

```python
def _ensure_certs() -> tuple[Optional[Path], Optional[Path]]:
    """Genera certs si faltan o están por vencer. Retorna (key, cert) o (None, None)."""
    key_file = CERT_DIR / "key.pem"
    cert_file = CERT_DIR / "cert.pem"

    need_generate = not (key_file.exists() and cert_file.exists())
    if not need_generate:
        # Chequeo de expiración
        info = _cert_info()
        if info.get("expires_in_days") is not None and info["expires_in_days"] <= 7:
            logger.info(f"SSL cert vence en {info['expires_in_days']} dias -> regenerando")
            need_generate = True

    if need_generate:
        # En proceso: bajo PyInstaller sys.executable es el agente, no un intérprete.
        try:
            logger.info(f"Generando certificados SSL en {CERT_DIR}...")
            import generate_cert
            generate_cert.generate_self_signed_cert(CERT_DIR)
        except Exception as e:
            logger.warning(f"Fallo generate_cert: {e}. Arrancara en HTTP.")
            return None, None

    if key_file.exists() and cert_file.exists():
        return key_file, cert_file
    return None, None
```

- [ ] **Step 10: `run()` (líneas 1344-1391).** Reemplazar `if __name__ == "__main__":` y el cálculo de puerto,
  host y fecha de build:

```python
if __name__ == "__main__":
    port = int(os.environ.get("ATLAS_AGENT_PORT", 9100))
    host = os.environ.get("ATLAS_AGENT_HOST", "127.0.0.1")

    # Version banner — helps identify legacy installs that were not updated.
    # IMPORTANT: ensure all stations run the same version shown here.
    _build_mtime = Path(__file__).stat().st_mtime
```

por:

```python
def run() -> None:
    """Arranca el agente y bloquea hasta que uvicorn termina."""
    port = agent_state.port(_CONFIG)
    host = agent_state.host(_CONFIG)

    # Version banner — helps identify legacy installs that were not updated.
    # IMPORTANT: ensure all stations run the same version shown here.
    # En el binario __file__ no existe en disco: la fecha es la del ejecutable.
    _build_src = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)
    try:
        _build_mtime = _build_src.stat().st_mtime
    except OSError:
        _build_mtime = time.time()
```

  El resto del cuerpo (banner, spooler, `_ensure_certs`, `uvicorn.run`, manejo de error) queda idéntico e indentado
  dentro de `run()`. Justo después de la línea `logger.info(f"Atlas Print Agent v{VERSION} -- ...")` agregar:

```python
    logger.info(f"Estado: {STATE_DIR}  Log: {_log_file}")
```

  Y al final del archivo:

```python


if __name__ == "__main__":
    run()
```

- [ ] **Step 11: Aislar los tests legados.** Crear `legacy/tests/conftest.py`:

```python
"""Desde 3.1.0 main.py guarda log, certificado y agent.conf en un directorio de estado.

Aquí apunta a un temporal para que importar el agente no escriba en el home de
quien corre los tests ni lea un agent.conf real, que podría cambiar el resultado
de los tests de CORS. No cambia qué tests pasan: siguen 27 y 3 fallan a propósito.
"""
import pytest


@pytest.fixture(autouse=True)
def _estado_aislado(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_AGENT_STATE_DIR", str(tmp_path / "estado"))
```

- [ ] **Step 12: Correr todo**

Run: `uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography --with pytest python -m pytest tests/agent -q`
Expected: todos pasan.

Run: `uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography --with pytest python -m pytest legacy/tests -q`
Expected: `3 failed, 27 passed` — los mismos tres de siempre (`test_sin_la_variable_el_dominio_propio_se_rechaza`,
`BT:Impresora 58`, `\\PC-CAJA\POS-80`).

- [ ] **Step 13: Arranque real en local**

Run: `ATLAS_AGENT_STATE_DIR=/tmp/claude-estado ATLAS_AGENT_PORT=9199 timeout 8 python3 legacy/print_agent/core/main.py` en
un venv con las dependencias (`uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography python legacy/print_agent/core/main.py`),
y en otra terminal `curl -sk https://127.0.0.1:9199/health`.
Expected: `{"status":"running","service":"Atlas POS Print Agent","version":"3.1.0",...}`, y existen
`/tmp/claude-estado/certs/cert.pem` y `/tmp/claude-estado/agent.log`.

- [ ] **Step 14: Commit**

```bash
git add legacy/print_agent/core/main.py legacy/tests/conftest.py tests/agent/test_main_estado.py
git commit -m "agente: estado fuera de la instalación, certificado en proceso y versión 3.1.0

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `lanzador` — el ícono de doble clic y el modo servicio

**Files:**
- Create: `legacy/print_agent/core/lanzador.py`
- Test: `tests/agent/test_lanzador.py`

**Interfaces:**
- Consumes: `agent_state.state_dir()`, `agent_state.load_config()`, `agent_state.port()` (Task 1); módulo `main`
  con `run()` y `_log_file` (Task 3).
- Produces:
  - `respuesta_es_agente(cuerpo: bytes) -> bool`
  - `agente_activo(puerto: int, timeout: float = 2.0) -> bool`
  - `comando_dialogo(sistema: str, titulo: str, mensaje: str, error: bool = False, hay=shutil.which) -> list[str] | None`
  - `mostrar_dialogo(titulo: str, mensaje: str, error: bool = False) -> None`
  - `main(argv: Sequence[str]) -> int` — sin `--servicio`: modo ícono; con `--servicio`: arranca sin diálogos.
  - Constantes `TITULO`, `MSG_YA_ACTIVO`, `MSG_INICIADO`, `MSG_NO_ARRANCO` (con `{log}`).
  - Es el script de entrada de PyInstaller (Task 5).

- [ ] **Step 1: Escribir los tests que fallan en `tests/agent/test_lanzador.py`**

```python
"""El ícono de doble clic nunca le pelea el puerto al agente que ya corre."""
import http.server
import io
import json
import socket
import sys
import threading
import types

import pytest

import lanzador


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def servidor_http():
    """Levanta un /health HTTP en un puerto libre con el cuerpo que se le pida."""
    servidores = []

    def levantar(cuerpo: bytes):
        class Manejador(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), Manejador)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servidores.append(srv)
        return srv.server_address[1]

    yield levantar
    for srv in servidores:
        srv.shutdown()


class TestRespuestaEsAgente:
    def test_health_del_agente(self):
        cuerpo = json.dumps({"status": "running", "service": "Atlas POS Print Agent", "version": "3.1.0"})
        assert lanzador.respuesta_es_agente(cuerpo.encode())

    def test_otro_servicio(self):
        assert not lanzador.respuesta_es_agente(b'{"service": "otra cosa"}')

    def test_basura(self):
        assert not lanzador.respuesta_es_agente(b"<html>hola</html>")
        assert not lanzador.respuesta_es_agente(b"\xff\xfe")
        assert not lanzador.respuesta_es_agente(b"[1, 2]")


class TestAgenteActivo:
    def test_responde_el_agente(self, servidor_http):
        puerto = servidor_http(b'{"service": "Atlas POS Print Agent"}')
        assert lanzador.agente_activo(puerto, timeout=1.0)

    def test_el_puerto_lo_tiene_otro_programa(self, servidor_http):
        puerto = servidor_http(b'{"service": "impostor"}')
        assert not lanzador.agente_activo(puerto, timeout=1.0)

    def test_nadie_escucha(self):
        assert not lanzador.agente_activo(_puerto_libre(), timeout=0.5)

    def test_ignora_el_proxy_del_sistema(self, servidor_http, monkeypatch):
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
        puerto = servidor_http(b'{"service": "Atlas POS Print Agent"}')
        assert lanzador.agente_activo(puerto, timeout=1.0)


class TestComandoDialogo:
    def test_mac_usa_osascript_y_escapa_comillas(self):
        cmd = lanzador.comando_dialogo("Darwin", "Título", 'Dice "hola"')
        assert cmd[0] == "osascript"
        assert 'Dice \\"hola\\"' in cmd[2]
        assert "with icon note" in cmd[2]

    def test_mac_error_usa_icono_de_alto(self):
        assert "with icon stop" in lanzador.comando_dialogo("Darwin", "T", "M", error=True)[2]

    def test_linux_prefiere_zenity(self):
        cmd = lanzador.comando_dialogo("Linux", "T", "M", hay=lambda p: p == "zenity")
        assert cmd[:2] == ["zenity", "--info"]
        assert lanzador.comando_dialogo("Linux", "T", "M", error=True, hay=lambda p: p == "zenity")[1] == "--error"

    def test_linux_sin_zenity_usa_notify_send(self):
        cmd = lanzador.comando_dialogo("Linux", "T", "M", hay=lambda p: p == "notify-send")
        assert cmd == ["notify-send", "T", "M"]

    def test_linux_sin_nada(self):
        assert lanzador.comando_dialogo("Linux", "T", "M", hay=lambda p: None) is None


class TestMain:
    @pytest.fixture
    def dialogos(self, monkeypatch):
        vistos = []
        monkeypatch.setattr(lanzador, "mostrar_dialogo", lambda t, m, error=False: vistos.append((m, error)))
        return vistos

    @pytest.fixture
    def agente_falso(self, monkeypatch):
        mod = types.SimpleNamespace(run=lambda: None, _log_file="/estado/agent.log", corridas=0)

        def run():
            mod.corridas += 1

        mod.run = run
        monkeypatch.setitem(sys.modules, "main", mod)
        return mod

    def test_icono_con_agente_activo_avisa_y_no_arranca(self, monkeypatch, dialogos, agente_falso):
        monkeypatch.setattr(lanzador, "agente_activo", lambda puerto, timeout=2.0: True)
        assert lanzador.main([]) == 0
        assert dialogos == [(lanzador.MSG_YA_ACTIVO, False)]
        assert agente_falso.corridas == 0

    def test_icono_sin_agente_lo_arranca(self, monkeypatch, dialogos, agente_falso):
        monkeypatch.setattr(lanzador, "agente_activo", lambda puerto, timeout=2.0: False)
        monkeypatch.setattr(lanzador, "_avisar_cuando_responda", lambda puerto: None)
        assert lanzador.main([]) == 0
        assert agente_falso.corridas == 1

    def test_icono_ignora_argumentos_de_finder(self, monkeypatch, dialogos, agente_falso):
        monkeypatch.setattr(lanzador, "agente_activo", lambda puerto, timeout=2.0: True)
        assert lanzador.main(["-psn_0_12345"]) == 0
        assert agente_falso.corridas == 0

    def test_icono_si_no_arranca_muestra_error_con_el_log(self, monkeypatch, dialogos, agente_falso):
        monkeypatch.setattr(lanzador, "agente_activo", lambda puerto, timeout=2.0: False)
        monkeypatch.setattr(lanzador, "_avisar_cuando_responda", lambda puerto: None)

        def puerto_ocupado():
            raise SystemExit(1)  # así sale uvicorn cuando no puede tomar el puerto

        agente_falso.run = puerto_ocupado
        assert lanzador.main([]) == 1
        assert dialogos == [(lanzador.MSG_NO_ARRANCO.format(log="/estado/agent.log"), True)]

    def test_servicio_no_mira_ni_muestra_nada(self, monkeypatch, dialogos, agente_falso):
        def no_debe_llamarse(*a, **k):
            raise AssertionError("el modo servicio no consulta /health")

        monkeypatch.setattr(lanzador, "agente_activo", no_debe_llamarse)
        assert lanzador.main(["--servicio"]) == 0
        assert agente_falso.corridas == 1
        assert dialogos == []

    def test_servicio_propaga_la_falla_para_que_el_supervisor_reintente(self, monkeypatch, dialogos, agente_falso):
        def puerto_ocupado():
            raise SystemExit(1)

        agente_falso.run = puerto_ocupado
        with pytest.raises(SystemExit):
            lanzador.main(["--servicio"])
        assert dialogos == []


def test_salidas_nulas_se_reemplazan(monkeypatch):
    # Así deja PyInstaller --windowed a sys.stdout y sys.stderr; uvicorn llama isatty().
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    lanzador._silenciar_salidas_nulas()
    assert sys.stdout is not None and sys.stdout.isatty() is False
    assert sys.stderr is not None and sys.stderr.isatty() is False


def test_salidas_reales_no_se_tocan(monkeypatch):
    real = io.StringIO()
    monkeypatch.setattr(sys, "stdout", real)
    lanzador._silenciar_salidas_nulas()
    assert sys.stdout is real
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with pytest python -m pytest tests/agent/test_lanzador.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'lanzador'`.

- [ ] **Step 3: Implementar `legacy/print_agent/core/lanzador.py`**

```python
"""Punto de entrada del agente empaquetado.

Dos modos, según quién lo abre:

- Sin argumentos — el ícono del Escritorio, del menú o el .app. Si el agente ya
  responde, lo dice en un diálogo y sale: la cajera que le da doble clic por
  costumbre no debe ver un error de puerto ocupado. Si no responde, lo arranca
  aquí mismo y avisa cuando ya se puede imprimir.
- `--servicio` — lo que corren systemd, launchd y el Programador de tareas.
  Arranca sin mirar nada y sin diálogos; si falla, sale con error para que el
  supervisor lo reintente.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional, Sequence

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import agent_state  # noqa: E402

TITULO = "Agente de Impresión Atlas"
SERVICIO_AGENTE = "Atlas POS Print Agent"
MSG_YA_ACTIVO = (
    "El agente de impresión ya está activo.\n\n"
    "No necesitas abrir nada más: abre el navegador y vende normal."
)
MSG_INICIADO = (
    "El agente de impresión está activo.\n\n"
    "Ya puedes imprimir desde el punto de venta. Puedes cerrar este aviso."
)
MSG_NO_ARRANCO = (
    "El agente de impresión no pudo arrancar.\n\n"
    "Puede que otro programa esté usando el puerto de impresión.\n"
    "Reinicia la computadora; si sigue igual, llama a soporte y menciona este archivo:\n\n{log}"
)


def respuesta_es_agente(cuerpo: bytes) -> bool:
    """True si el cuerpo es el /health de este agente y no de otro programa."""
    try:
        datos = json.loads(cuerpo.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False
    return isinstance(datos, dict) and datos.get("service") == SERVICIO_AGENTE


def agente_activo(puerto: int, timeout: float = 2.0) -> bool:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # ProxyHandler({}): un proxy corporativo en el entorno no debe interceptar 127.0.0.1.
    abridor = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx)
    )
    for esquema in ("https", "http"):
        try:
            with abridor.open(f"{esquema}://127.0.0.1:{puerto}/health", timeout=timeout) as r:
                if respuesta_es_agente(r.read(4096)):
                    return True
        except Exception:
            continue
    return False


def _applescript(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"')


def comando_dialogo(
    sistema: str,
    titulo: str,
    mensaje: str,
    error: bool = False,
    hay: Callable[[str], Optional[str]] = shutil.which,
) -> Optional[list[str]]:
    """Comando externo que muestra el diálogo, o None si no hay con qué (Windows usa ctypes)."""
    if sistema == "Darwin":
        icono = "stop" if error else "note"
        guion = (
            f'display dialog "{_applescript(mensaje)}" with title "{_applescript(titulo)}" '
            f'buttons {{"Aceptar"}} default button 1 with icon {icono}'
        )
        return ["osascript", "-e", guion]
    if sistema == "Linux":
        if hay("zenity"):
            return ["zenity", "--error" if error else "--info", f"--title={titulo}", f"--text={mensaje}", "--no-wrap"]
        if hay("notify-send"):
            return ["notify-send", titulo, mensaje]
    return None


def mostrar_dialogo(titulo: str, mensaje: str, error: bool = False) -> None:
    sistema = platform.system()
    if sistema == "Windows":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, mensaje, titulo, 0x10 if error else 0x40)
            return
        except Exception:
            pass
    cmd = comando_dialogo(sistema, titulo, mensaje, error)
    if cmd:
        try:
            subprocess.run(cmd, timeout=600, check=False)
            return
        except Exception:
            pass
    print(f"{titulo}: {mensaje}")


def _avisar_cuando_responda(puerto: int, espera: float = 60.0) -> None:
    limite = time.monotonic() + espera
    while time.monotonic() < limite:
        if agente_activo(puerto, timeout=1.0):
            mostrar_dialogo(TITULO, MSG_INICIADO)
            return
        time.sleep(0.5)


def _silenciar_salidas_nulas() -> None:
    # Con --windowed (Windows y el .app de macOS) sys.stdout y sys.stderr son None,
    # y uvicorn llama isatty() sobre ellos al configurar su log: sin esto el agente
    # muere al arrancar sin dejar rastro.
    for nombre in ("stdout", "stderr"):
        if getattr(sys, nombre) is None:
            setattr(sys, nombre, open(os.devnull, "w", encoding="utf-8"))


def main(argv: Sequence[str]) -> int:
    _silenciar_salidas_nulas()
    servicio = "--servicio" in argv
    puerto = agent_state.port(agent_state.load_config(agent_state.state_dir()))

    if not servicio:
        if agente_activo(puerto):
            mostrar_dialogo(TITULO, MSG_YA_ACTIVO)
            return 0
        threading.Thread(target=_avisar_cuando_responda, args=(puerto,), daemon=True).start()

    import main as agente

    if servicio:
        agente.run()
        return 0
    try:
        agente.run()
    except (Exception, SystemExit) as e:
        if isinstance(e, SystemExit) and e.code in (0, None):
            return 0
        mostrar_dialogo(TITULO, MSG_NO_ARRANCO.format(log=agente._log_file), error=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run --no-project --with pytest python -m pytest tests/agent/test_lanzador.py -q`
Expected: todos pasan.

- [ ] **Step 5: Probar a mano el modo ícono contra el agente real**

En una terminal: `ATLAS_AGENT_STATE_DIR=/tmp/claude-estado ATLAS_AGENT_PORT=9199 uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography python legacy/print_agent/core/lanzador.py --servicio`.
En otra: `ATLAS_AGENT_STATE_DIR=/tmp/claude-estado ATLAS_AGENT_PORT=9199 python3 legacy/print_agent/core/lanzador.py`.
Expected: la segunda imprime (o muestra, si hay zenity) `Agente de Impresión Atlas: El agente de impresión ya está activo...` y sale con 0.

- [ ] **Step 6: Commit**

```bash
git add legacy/print_agent/core/lanzador.py tests/agent/test_lanzador.py
git commit -m "agente: lanzador con modo ícono que avisa si ya está activo y modo servicio

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Construir el binario y la prueba de humo

**Files:**
- Create: `installers/agent/requirements-build.txt`, `installers/agent/version_agente.py`,
  `installers/agent/construir.py`, `installers/agent/humo.py`
- Test: `tests/agent/test_empaquetado.py`

**Interfaces:**
- Consumes: `lanzador.py` como script de entrada (Task 4); `VERSION` en `main.py` (Task 3).
- Produces:
  - `version_agente.leer_version(ruta: Path = MAIN) -> str`, `version_agente.tag_coincide(tag: str, version: str) -> bool`;
    CLI: `python installers/agent/version_agente.py` imprime la versión; `--verificar-tag vX.Y.Z` sale 1 si no coincide.
  - `construir.nombre(sistema: str | None = None) -> str`, `construir.binario(sistema: str | None = None) -> Path`,
    `construir.DIST = <raíz>/dist/agent`. Salida: Linux `dist/agent/atlas-print-agent/atlas-print-agent`;
    Windows `dist/agent/atlas-print-agent/atlas-print-agent.exe`; macOS `dist/agent/Atlas Print Agent.app`.
  - CLI `python installers/agent/humo.py` → sale 0 si el binario de `construir.binario()` responde `/health` con la
    versión de `main.py`.

- [ ] **Step 1: Escribir los tests que fallan en `tests/agent/test_empaquetado.py`**

```python
"""Herramientas de empaquetado: versión y rutas del binario."""
from pathlib import Path

import construir
import version_agente


def test_lee_la_version_de_main():
    assert version_agente.leer_version() == "3.1.0"


def test_lee_la_version_de_cualquier_archivo(tmp_path):
    f = tmp_path / "main.py"
    f.write_text('x = 1\nVERSION = "9.8.7"\n', encoding="utf-8")
    assert version_agente.leer_version(f) == "9.8.7"


def test_tag_coincide():
    assert version_agente.tag_coincide("v3.1.0", "3.1.0")
    assert not version_agente.tag_coincide("v3.1.1", "3.1.0")
    assert not version_agente.tag_coincide("3.1.0", "3.1.0")


def test_cli_verificar_tag(capsys):
    assert version_agente.main(["--verificar-tag", "v3.1.0"]) == 0
    assert version_agente.main(["--verificar-tag", "v9.9.9"]) == 1
    assert "no coincide" in capsys.readouterr().err


def test_rutas_del_binario_por_sistema():
    d = construir.DIST
    assert construir.binario("Linux") == d / "atlas-print-agent" / "atlas-print-agent"
    assert construir.binario("Windows") == d / "atlas-print-agent" / "atlas-print-agent.exe"
    assert construir.binario("Darwin") == (
        d / "Atlas Print Agent.app" / "Contents" / "MacOS" / "Atlas Print Agent"
    )


def test_argumentos_de_pyinstaller():
    args = construir.argumentos("Windows")
    assert "--onedir" in args and "--onefile" not in args
    assert "--windowed" in args
    assert args[-1].endswith("lanzador.py")
    for modulo in ("main", "agent_state", "generate_cert"):
        assert modulo in args
    assert "--windowed" not in construir.argumentos("Linux")
    assert "--osx-bundle-identifier" in construir.argumentos("Darwin")
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run --no-project --with pytest python -m pytest tests/agent/test_empaquetado.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'construir'`.

- [ ] **Step 3: `installers/agent/requirements-build.txt`**

```
# Dependencias para construir el binario del agente. Versiones fijas: el binario de
# una release debe poder reconstruirse igual. Las de runtime son las mismas que
# legacy/print_agent/core/requirements.txt.
fastapi==0.115.12
uvicorn[standard]==0.34.2
pydantic==2.11.3
cryptography==44.0.3
pywin32==308; sys_platform == 'win32'
pyinstaller==6.16.0
```

- [ ] **Step 4: `installers/agent/version_agente.py`**

```python
"""Lee VERSION de main.py sin importarlo y la compara con el tag de la release.

Así no se publica un v3.1.0 que en /health se reporta como 3.0.0.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

MAIN = Path(__file__).resolve().parents[2] / "legacy" / "print_agent" / "core" / "main.py"
_PATRON = re.compile(r'^VERSION = "([^"]+)"$', re.M)


def leer_version(ruta: Path = MAIN) -> str:
    m = _PATRON.search(Path(ruta).read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"No se encontró VERSION en {ruta}")
    return m.group(1)


def tag_coincide(tag: str, version: str) -> bool:
    return tag == f"v{version}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verificar-tag", metavar="TAG")
    a = p.parse_args(argv)
    version = leer_version()
    if a.verificar_tag is None:
        print(version)
        return 0
    if tag_coincide(a.verificar_tag, version):
        print(f"OK: {a.verificar_tag} coincide con VERSION = \"{version}\"")
        return 0
    print(
        f"El tag {a.verificar_tag} no coincide con VERSION = \"{version}\" de main.py. "
        "Sube VERSION o corrige el tag.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: `installers/agent/construir.py`**

```python
"""Empaqueta el agente con PyInstaller, en modo carpeta, para el sistema en el que corre.

Uso, desde la raíz del repo y con requirements-build.txt instalado:
    python installers/agent/construir.py

--onedir y no --onefile: con un instalador de por medio, --onefile solo cuesta
(descomprime en un temporal a cada arranque y deja carpetas _MEI huérfanas cada
vez que el proceso muere). Ver el plan 2026-09-28-autoarranque-multiplataforma.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parents[2]
CORE = RAIZ / "legacy" / "print_agent" / "core"
DIST = RAIZ / "dist" / "agent"
TRABAJO = RAIZ / "build" / "agent"


def nombre(sistema: Optional[str] = None) -> str:
    return "Atlas Print Agent" if (sistema or platform.system()) == "Darwin" else "atlas-print-agent"


def binario(sistema: Optional[str] = None) -> Path:
    sistema = sistema or platform.system()
    n = nombre(sistema)
    if sistema == "Darwin":
        return DIST / f"{n}.app" / "Contents" / "MacOS" / n
    return DIST / n / (n + (".exe" if sistema == "Windows" else ""))


def argumentos(sistema: Optional[str] = None) -> list[str]:
    sistema = sistema or platform.system()
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", nombre(sistema),
        "--paths", str(CORE),
        "--hidden-import", "main",
        "--hidden-import", "agent_state",
        "--hidden-import", "generate_cert",
        # uvicorn carga sus loops y protocolos por nombre: el análisis estático no los ve.
        "--collect-submodules", "uvicorn",
        "--distpath", str(DIST), "--workpath", str(TRABAJO), "--specpath", str(TRABAJO),
    ]
    if sistema in ("Windows", "Darwin"):
        args.append("--windowed")  # sin ventana de consola; el .app en macOS
    if sistema == "Darwin":
        args += ["--osx-bundle-identifier", "com.atlasone.print-agent"]
    args.append(str(CORE / "lanzador.py"))
    return args


def main() -> int:
    subprocess.run(argumentos(), check=True, cwd=RAIZ)
    b = binario()
    if not b.exists():
        print(f"No se generó {b}", file=sys.stderr)
        return 1
    print(b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: `installers/agent/humo.py`**

```python
"""Prueba de humo del binario recién construido: arranca, responde /health, muere.

Corre con un directorio de estado temporal y en el puerto 9199, para no chocar con
un agente real de la máquina. Un binario que no pasa esto no llega a la release.
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import construir
import version_agente

PUERTO = 9199
ESPERA = 60.0


def _health() -> dict | None:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))
    try:
        with abridor.open(f"https://127.0.0.1:{PUERTO}/health", timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return None


def main() -> int:
    binario = construir.binario()
    esperada = version_agente.leer_version()
    estado = Path(tempfile.mkdtemp(prefix="atlas-humo-"))
    env = {**os.environ, "ATLAS_AGENT_STATE_DIR": str(estado), "ATLAS_AGENT_PORT": str(PUERTO)}
    print(f"Arrancando {binario} (estado en {estado})")
    proc = subprocess.Popen([str(binario), "--servicio"], env=env)
    try:
        limite = time.monotonic() + ESPERA
        datos = None
        while time.monotonic() < limite and proc.poll() is None:
            datos = _health()
            if datos:
                break
            time.sleep(1)
        fallas = []
        if not datos:
            fallas.append(f"/health no respondió en {ESPERA:.0f} s (código de salida: {proc.poll()})")
        elif datos.get("version") != esperada:
            fallas.append(f"/health reporta versión {datos.get('version')!r}, se esperaba {esperada!r}")
        if not (estado / "certs" / "cert.pem").is_file():
            fallas.append("no se generó certs/cert.pem en el directorio de estado")
        if not (estado / "agent.log").is_file():
            fallas.append("no se escribió agent.log en el directorio de estado")
        if fallas:
            for f in fallas:
                print(f"✗ {f}", file=sys.stderr)
            log = estado / "agent.log"
            if log.is_file():
                print(log.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            return 1
        print(f"✓ {binario.name} responde: {datos}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Correr los tests**

Run: `uv run --no-project --with pytest python -m pytest tests/agent/test_empaquetado.py -q`
Expected: todos pasan.

- [ ] **Step 8: Construir y probar el binario de Linux en WSL.** El Python debe ser el del sistema (tiene
  `libpython3.12.so`, que PyInstaller necesita). La carpeta de trabajo va en el disco de Linux, no en `/mnt/c`:

```bash
uv venv /tmp/claude-agente-venv --python /usr/bin/python3.12
uv pip install --python /tmp/claude-agente-venv/bin/python -r installers/agent/requirements-build.txt
/tmp/claude-agente-venv/bin/python installers/agent/construir.py
/tmp/claude-agente-venv/bin/python installers/agent/humo.py
```

Expected: la última línea es `✓ atlas-print-agent responde: {'status': 'running', ..., 'version': '3.1.0', ...}`.
Si PyInstaller falla por un módulo faltante de uvicorn, agregar el `--hidden-import` que nombre el error a
`argumentos()` y a su test.

- [ ] **Step 9: Commit**

```bash
git add installers/agent/requirements-build.txt installers/agent/version_agente.py installers/agent/construir.py installers/agent/humo.py tests/agent/test_empaquetado.py
git commit -m "installers: binario del agente con PyInstaller y prueba de humo

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Paquete `.deb` para Ubuntu

**Files:**
- Create: `installers/agent/linux/atlas-print-agent.service`, `installers/agent/linux/atlas-print-agent.desktop`,
  `installers/agent/linux/control`, `installers/agent/linux/postinst`, `installers/agent/linux/prerm`,
  `installers/agent/linux/postrm`, `installers/agent/linux/build_deb.sh`

**Interfaces:**
- Consumes: `dist/agent/atlas-print-agent/` (Task 5); `version_agente.py`.
- Produces: `dist/atlas-print-agent_<versión>_amd64.deb`. En la caja deja: `/usr/lib/atlas-print-agent/`,
  `/usr/bin/atlas-print-agent`, `/usr/lib/systemd/system/atlas-print-agent.service`, drop-in
  `/etc/systemd/system/atlas-print-agent.service.d/usuario.conf`, `/usr/share/applications/atlas-print-agent.desktop`,
  `/var/lib/atlas-print-agent/{agent.conf,certs/}`.

- [ ] **Step 1: `installers/agent/linux/atlas-print-agent.service`**

```ini
[Unit]
Description=Agente de impresión Atlas (Atlas Print Agent)
After=network-online.target cups.service
Wants=network-online.target cups.service

[Service]
# User= y Group= los escribe postinst en atlas-print-agent.service.d/usuario.conf:
# el agente corre como la cajera para ver sus impresoras, no como root.
ExecStart=/usr/lib/atlas-print-agent/atlas-print-agent --servicio
# systemd crea /var/lib/atlas-print-agent con el dueño correcto y lo exporta en
# STATE_DIRECTORY. Ahí viven el certificado y agent.conf: reinstalar no los toca.
StateDirectory=atlas-print-agent
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=atlas-print-agent
# El agente llama lp, lpstat, lpadmin, lpinfo y cupsenable.
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# Hardening razonable; no lockdown completo porque necesita los sockets de CUPS.
NoNewPrivileges=true
ProtectSystem=true

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: `installers/agent/linux/atlas-print-agent.desktop`**

```ini
[Desktop Entry]
Type=Application
Version=1.0
Name=Agente de Impresión Atlas
Comment=Puente local de impresión para Atlas POS
Exec=/usr/bin/atlas-print-agent
Icon=printer
Terminal=false
Categories=Office;Printing;
StartupNotify=false
```

- [ ] **Step 3: `installers/agent/linux/control`**

```
Package: atlas-print-agent
Version: __VERSION__
Section: misc
Priority: optional
Architecture: amd64
Depends: cups, cups-client, cups-bsd, curl
Recommends: zenity
Maintainer: Atlas Technologies
Description: Agente local de impresión de Atlas POS
 Puente HTTPS en https://127.0.0.1:9100 entre el navegador de la caja y la
 impresora de tickets. Arranca solo al prender la computadora.
```

- [ ] **Step 4: `installers/agent/linux/postinst`**

```bash
#!/bin/bash
# postinst del .deb: deja el agente corriendo como la cajera y registrado al
# arranque. No declara éxito sin que /health responda.
#
# Usuario de la caja: ATLAS_AGENT_USER si se pasa
#   (sudo ATLAS_AGENT_USER=caja apt install ./atlas-print-agent_*.deb),
# si no quien corrió sudo, si no el dueño de la sesión abierta, si no el primer
# usuario humano.
set -u
SERVICIO=atlas-print-agent
ESTADO=/var/lib/atlas-print-agent
DROPIN=/etc/systemd/system/$SERVICIO.service.d

[ "${1:-}" = "configure" ] || exit 0

ok()   { echo "✓ $*"; }
aviso(){ echo "! $*"; }
falla(){
    echo
    echo "════════════════════════════════════════════════════════════"
    echo "  ✗ $*"
    echo "════════════════════════════════════════════════════════════"
    echo "  Revisa:  journalctl -u $SERVICIO -n 50 --no-pager"
    echo "  Tras corregir:  sudo dpkg --configure -a"
    exit 1
}

usuario_de_la_caja() {
    if [ -n "${ATLAS_AGENT_USER:-}" ]; then echo "$ATLAS_AGENT_USER"; return; fi
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then echo "$SUDO_USER"; return; fi
    local u
    u="$(loginctl list-sessions --no-legend 2>/dev/null | awk '$3 != "root" && $3 != "" {print $3; exit}')"
    if [ -n "$u" ]; then echo "$u"; return; fi
    getent passwd | awk -F: '$3 >= 1000 && $3 < 60000 {print $1; exit}'
}

[ -d /run/systemd/system ] || falla "Este sistema no corre systemd: no hay autoarranque que registrar."

USUARIO="$(usuario_de_la_caja)"
USUARIO="${USUARIO:-root}"
id "$USUARIO" >/dev/null 2>&1 || falla "El usuario '$USUARIO' no existe. Usa: sudo ATLAS_AGENT_USER=<usuario> apt install ./<paquete>.deb"
GRUPO="$(id -gn "$USUARIO")"
HOGAR="$(getent passwd "$USUARIO" | cut -d: -f6)"
ok "El agente correrá como '$USUARIO'."

# ── Grupo lpadmin, para dar de alta colas desde /printers/install ─────────────
if [ "$USUARIO" != root ] && getent group lpadmin >/dev/null && ! id -nG "$USUARIO" | grep -qw lpadmin; then
    usermod -aG lpadmin "$USUARIO" && ok "'$USUARIO' agregado al grupo lpadmin."
fi

# ── Apagar el modo manual y las instalaciones viejas ──────────────────────────
# Primero el envoltorio `while true` de impresora_linux.sh, luego el agente: si
# no, el envoltorio lo resucita y le pelea el 9100 al servicio.
matar() {
    local pids
    pids="$(pgrep -f "$1" 2>/dev/null | tr '\n' ' ')"
    [ -z "${pids// /}" ] && return 0
    echo "  Deteniendo $2 (PID: $pids)"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null; sleep 2
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null
    return 0
}
UNIDAD_VIEJA=/etc/systemd/system/$SERVICIO.service
if [ -f "$UNIDAD_VIEJA" ] && grep -q 'venv/bin/python3' "$UNIDAD_VIEJA"; then
    systemctl stop "$SERVICIO" 2>/dev/null
    mv "$UNIDAD_VIEJA" "$UNIDAD_VIEJA.legado-$(date +%Y%m%d%H%M%S)"
    ok "Servicio legado (con venv) retirado; su unidad quedó respaldada junto a ella."
fi
UNIDAD_USUARIO="$HOGAR/.config/systemd/user/$SERVICIO.service"
if [ -f "$UNIDAD_USUARIO" ]; then
    runuser -u "$USUARIO" -- env XDG_RUNTIME_DIR="/run/user/$(id -u "$USUARIO")" \
        systemctl --user disable --now "$SERVICIO" >/dev/null 2>&1
    mv "$UNIDAD_USUARIO" "$UNIDAD_USUARIO.legado-$(date +%Y%m%d%H%M%S)"
    ok "Servicio de usuario legado retirado."
fi
matar '(bash|sh|zsh) .*impresora_linux\.sh$' "la ventana del modo manual"
matar 'python3? .*core/main\.py$' "el agente manual"

# ── Certificado: se conserva el que el navegador ya aceptó ────────────────────
mkdir -p "$ESTADO/certs"
if [ -f "$ESTADO/certs/cert.pem" ] && [ -f "$ESTADO/certs/key.pem" ]; then
    ok "Certificado existente conservado (reinstalación o actualización)."
else
    PREVIO=""
    for d in /opt/atlas-print-agent/core/certs "$HOGAR/.local/share/atlas-print-agent/core/certs"; do
        if [ -f "$d/cert.pem" ] && [ -f "$d/key.pem" ]; then PREVIO="$d"; break; fi
    done
    if [ -z "$PREVIO" ] && [ -d "$HOGAR" ]; then
        # El caso de campo: el ZIP descomprimido en Descargas y usado por meses.
        c="$(find "$HOGAR" -maxdepth 6 -type f -name cert.pem -path '*/core/certs/*' \
              -printf '%T@ %h\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
        if [ -n "$c" ] && [ -f "$c/key.pem" ]; then PREVIO="$c"; fi
    fi
    if [ -n "$PREVIO" ]; then
        cp "$PREVIO/cert.pem" "$PREVIO/key.pem" "$ESTADO/certs/"
        ok "Certificado conservado desde $PREVIO: el navegador no pedirá aceptarlo de nuevo."
    else
        aviso "No había certificado previo: el agente generará uno nuevo."
        aviso "En esta caja habrá que aceptarlo una vez en https://127.0.0.1:9100/health"
    fi
fi
[ -f "$ESTADO/certs/key.pem" ] && chmod 600 "$ESTADO/certs/key.pem"

# ── agent.conf de ejemplo, solo si no existe ──────────────────────────────────
if [ ! -f "$ESTADO/agent.conf" ]; then
    cat > "$ESTADO/agent.conf" <<'EOF'
# Configuración del agente de impresión Atlas. Una línea CLAVE=valor.
# Las variables de entorno ganan sobre este archivo. Después de editarlo:
#   sudo systemctl restart atlas-print-agent
#
# Dominios extra del punto de venta, separados por coma. localhost,
# *.up.railway.app y (*.)atlasone.com.mx ya se aceptan sin escribir nada.
# ATLAS_AGENT_ORIGINS=https://pos.micliente.com
#
# ATLAS_AGENT_PORT=9100
EOF
fi
chown -R "$USUARIO:$GRUPO" "$ESTADO"

# ── Servicio ──────────────────────────────────────────────────────────────────
mkdir -p "$DROPIN"
printf '[Service]\nUser=%s\nGroup=%s\n' "$USUARIO" "$GRUPO" > "$DROPIN/usuario.conf"
systemctl daemon-reload
systemctl enable "$SERVICIO" >/dev/null 2>&1 || falla "No se pudo habilitar el servicio al arranque."
systemctl restart "$SERVICIO" || falla "El servicio no arrancó."

# ── Verificación real ─────────────────────────────────────────────────────────
PUERTO="$(sed -n 's/^[[:space:]]*ATLAS_AGENT_PORT[[:space:]]*=[[:space:]]*\([0-9]*\).*/\1/p' "$ESTADO/agent.conf" | tail -1)"
PUERTO="${PUERTO:-9100}"
HEALTH=""
for _ in $(seq 1 30); do
    sleep 1
    HEALTH="$(curl -sk --noproxy '*' --max-time 2 "https://127.0.0.1:$PUERTO/health" 2>/dev/null)"
    case "$HEALTH" in *'Atlas POS Print Agent'*) break ;; *) HEALTH="" ;; esac
done
[ -n "$HEALTH" ] || falla "El agente quedó instalado pero NO respondió en https://127.0.0.1:$PUERTO/health"

echo
echo "════════════════════════════════════════════════════════════"
echo "  ✓ Agente instalado y respondiendo"
echo "════════════════════════════════════════════════════════════"
echo "  $HEALTH"
echo "  Arranca solo al prender la PC. La cajera no tiene que abrir nada."
exit 0
```

- [ ] **Step 5: `installers/agent/linux/prerm` y `installers/agent/linux/postrm`**

`prerm`:

```bash
#!/bin/bash
# remove: se para y se quita del arranque. upgrade: solo se para; el postinst
# de la versión nueva lo vuelve a levantar.
set -u
case "${1:-}" in
    remove|deconfigure) systemctl disable --now atlas-print-agent >/dev/null 2>&1 || true ;;
    upgrade|failed-upgrade) systemctl stop atlas-print-agent >/dev/null 2>&1 || true ;;
esac
exit 0
```

`postrm`:

```bash
#!/bin/bash
# remove conserva /var/lib/atlas-print-agent (certificado y agent.conf): reinstalar
# no obliga a aceptar el certificado otra vez. purge lo borra.
set -u
case "${1:-}" in
    remove)
        rm -rf /etc/systemd/system/atlas-print-agent.service.d
        systemctl daemon-reload >/dev/null 2>&1 || true
        ;;
    purge)
        rm -rf /etc/systemd/system/atlas-print-agent.service.d /var/lib/atlas-print-agent
        systemctl daemon-reload >/dev/null 2>&1 || true
        ;;
esac
exit 0
```

- [ ] **Step 6: `installers/agent/linux/build_deb.sh`**

```bash
#!/bin/bash
# Envuelve dist/agent/atlas-print-agent/ en dist/atlas-print-agent_<versión>_amd64.deb.
# Uso, desde la raíz y después de installers/agent/construir.py:
#   bash installers/agent/linux/build_deb.sh
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
AQUI="$RAIZ/installers/agent/linux"
VERSION="$(python3 "$RAIZ/installers/agent/version_agente.py")"
ORIGEN="$RAIZ/dist/agent/atlas-print-agent"
[ -f "$ORIGEN/atlas-print-agent" ] || { echo "Falta $ORIGEN: corre antes installers/agent/construir.py" >&2; exit 1; }

# El árbol se arma en un disco de Linux: en /mnt/c (NTFS) todo aparece con permisos
# 777 y dpkg-deb rechaza el directorio DEBIAN.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ARBOL="$TMP/atlas-print-agent"
mkdir -p "$ARBOL/DEBIAN" "$ARBOL/usr/lib" "$ARBOL/usr/bin" \
         "$ARBOL/usr/lib/systemd/system" "$ARBOL/usr/share/applications"
cp -r "$ORIGEN" "$ARBOL/usr/lib/atlas-print-agent"
chmod -R u=rwX,go=rX "$ARBOL/usr/lib/atlas-print-agent"
chmod 755 "$ARBOL/usr/lib/atlas-print-agent/atlas-print-agent"
ln -s /usr/lib/atlas-print-agent/atlas-print-agent "$ARBOL/usr/bin/atlas-print-agent"
install -m 644 "$AQUI/atlas-print-agent.service" "$ARBOL/usr/lib/systemd/system/"
install -m 644 "$AQUI/atlas-print-agent.desktop" "$ARBOL/usr/share/applications/"
sed "s/__VERSION__/$VERSION/" "$AQUI/control" > "$ARBOL/DEBIAN/control"
install -m 755 "$AQUI/postinst" "$AQUI/prerm" "$AQUI/postrm" "$ARBOL/DEBIAN/"
chmod 755 "$ARBOL/DEBIAN"

mkdir -p "$RAIZ/dist"
SALIDA="$RAIZ/dist/atlas-print-agent_${VERSION}_amd64.deb"
dpkg-deb --root-owner-group --build "$ARBOL" "$SALIDA"
echo "$SALIDA"
```

- [ ] **Step 7: Revisar los scripts y construir**

Run: `bash -n installers/agent/linux/postinst installers/agent/linux/prerm installers/agent/linux/postrm installers/agent/linux/build_deb.sh && (command -v shellcheck >/dev/null && shellcheck -S warning installers/agent/linux/postinst installers/agent/linux/prerm installers/agent/linux/postrm installers/agent/linux/build_deb.sh || echo "shellcheck no instalado")`
Expected: sin errores de sintaxis; sin advertencias de shellcheck (o el aviso de que no está).

Run: `bash installers/agent/linux/build_deb.sh && dpkg-deb --info dist/atlas-print-agent_3.1.0_amd64.deb && dpkg-deb --contents dist/atlas-print-agent_3.1.0_amd64.deb | head -20`
Expected: `Version: 3.1.0`, `Depends: cups, cups-client, cups-bsd, curl`; el contenido lista
`./usr/lib/atlas-print-agent/atlas-print-agent`, `./usr/lib/systemd/system/atlas-print-agent.service`,
`./usr/bin/atlas-print-agent -> /usr/lib/atlas-print-agent/atlas-print-agent`.

- [ ] **Step 8: Commit** (marcando los scripts como ejecutables en git: en `/mnt/c` el bit no se detecta solo)

```bash
git add installers/agent/linux/
git add --chmod=+x installers/agent/linux/postinst installers/agent/linux/prerm installers/agent/linux/postrm installers/agent/linux/build_deb.sh
git commit -m "installers: paquete .deb con servicio systemd como la cajera y migración del certificado

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Verificar el `.deb` en el WSL (systemd real)

Esta tarea no escribe código; es la compuerta del §10.1 del spec. **Necesita `sudo`**: el implementador le pide al
dueño que corra cada comando con `!` en el prompt y lee la salida. Si algo falla, se corrige en la Task 6 y se
repite desde el Step 1.

**Files:** ninguno (se anota el resultado en la Task 11).

- [ ] **Step 1: Instalar**

Run: `! sudo apt install -y ./dist/atlas-print-agent_3.1.0_amd64.deb`
Expected: termina en `✓ Agente instalado y respondiendo` con el JSON de `/health` y `"version":"3.1.0"`.

- [ ] **Step 2: Registrado al arranque y corriendo como la cajera**

Run: `systemctl is-enabled atlas-print-agent && systemctl show atlas-print-agent -p User -p ActiveState && ls -l /var/lib/atlas-print-agent/certs`
Expected: `enabled`, `User=ecamposg`, `ActiveState=active`, `cert.pem` y `key.pem` con dueño `ecamposg` y `key.pem` en `-rw-------`.

- [ ] **Step 3: Matar el proceso y ver que revive en ≤ 5 s** (criterio 2)

Run: `! sudo kill -9 $(systemctl show -p MainPID --value atlas-print-agent); sleep 7; curl -sk https://127.0.0.1:9100/health`
Expected: responde el JSON otra vez; `systemctl show -p NRestarts atlas-print-agent` subió en 1.

- [ ] **Step 4: La prueba que valida el §5 entero — reinstalar no cambia el certificado** (criterio 3)

```bash
sha256sum /var/lib/atlas-print-agent/certs/cert.pem
! sudo apt install -y --reinstall ./dist/atlas-print-agent_3.1.0_amd64.deb
sha256sum /var/lib/atlas-print-agent/certs/cert.pem
```

Expected: las dos huellas son idénticas y el postinst dice `Certificado existente conservado`.

- [ ] **Step 5: El ícono con el agente ya corriendo**

Run: `/usr/bin/atlas-print-agent; echo "salida=$?"`
Expected: `Agente de Impresión Atlas: El agente de impresión ya está activo...` (o el diálogo de zenity) y `salida=0`, sin error de puerto.

- [ ] **Step 6: Falla ruidosa** (criterio 4). Ocupar el puerto con otro programa y reinstalar:

```bash
! sudo systemctl stop atlas-print-agent
python3 -m http.server 9100 --bind 127.0.0.1 &   # impostor en el 9100
! sudo apt install -y --reinstall ./dist/atlas-print-agent_3.1.0_amd64.deb; echo "apt=$?"
kill %1
! sudo dpkg --configure -a
```

Expected: el primer `apt` termina con `✗ El agente quedó instalado pero NO respondió` y `apt=100`; tras matar al
impostor, `dpkg --configure -a` termina en `✓ Agente instalado y respondiendo`.

- [ ] **Step 7: Desinstalar conserva el estado; purgar lo borra**

```bash
! sudo apt remove -y atlas-print-agent
ls /var/lib/atlas-print-agent/certs    # siguen ahí
! sudo apt install -y ./dist/atlas-print-agent_3.1.0_amd64.deb   # misma huella que en el Step 4
```

Expected: tras `remove` el certificado sigue; tras reinstalar la huella es la misma del Step 4. **No** purgar en
esta máquina salvo que el dueño lo pida.

- [ ] **Step 8: Reinicio real** (criterio 1). Desde PowerShell de Windows: `wsl --shutdown`; abrir de nuevo la
  terminal de WSL y, sin arrancar nada: `curl -sk https://127.0.0.1:9100/health`.
Expected: responde.

---

### Task 8: Paquete `.pkg` para macOS

**Files:**
- Create: `installers/agent/mac/com.atlasone.print-agent.plist`, `installers/agent/mac/scripts/preinstall`,
  `installers/agent/mac/scripts/postinstall`, `installers/agent/mac/desinstalar.sh`, `installers/agent/mac/build_pkg.sh`

**Interfaces:**
- Consumes: `dist/agent/Atlas Print Agent.app` (Task 5, en un runner de macOS); `version_agente.py`.
- Produces: `dist/atlas-print-agent-<versión>-<arm64|x86_64>.pkg`. En la Mac deja `/Applications/Atlas Print Agent.app`,
  `/Library/Application Support/AtlasPrintAgent/{desinstalar.sh,com.atlasone.print-agent.plist}` (plantilla),
  `~/Library/LaunchAgents/com.atlasone.print-agent.plist`, `~/Library/Application Support/AtlasPrintAgent/`,
  alias `~/Desktop/Atlas Print Agent`.

- [ ] **Step 1: `installers/agent/mac/com.atlasone.print-agent.plist`** (plantilla; `__HOME__` lo sustituye postinstall)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!--
  LaunchAgent del agente de impresión Atlas. Plantilla: el postinstall del .pkg
  sustituye la ruta del home y lo escribe en ~/Library/LaunchAgents/.
  De USUARIO, no LaunchDaemon: ve la misma cola de CUPS que la cajera.
  Los orígenes CORS no van aquí sino en agent.conf del directorio de estado.
-->
<plist version="1.0">
<dict>
  <key>Label</key><string>com.atlasone.print-agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Applications/Atlas Print Agent.app/Contents/MacOS/Atlas Print Agent</string>
    <string>--servicio</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <!-- launchd no hereda el PATH de la sesión; el agente llama lp, lpstat, lpadmin, lpinfo. -->
    <key>PATH</key><string>/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>__HOME__/Library/Logs/AtlasPrintAgent/agent.out.log</string>
  <key>StandardErrorPath</key><string>__HOME__/Library/Logs/AtlasPrintAgent/agent.err.log</string>
</dict>
</plist>
```

- [ ] **Step 2: `installers/agent/mac/scripts/preinstall`**

```bash
#!/bin/bash
# Corre como root antes de copiar el .app: baja el agente que esté corriendo
# (servicio legado o nuevo, y el modo manual) para no pisar un binario en uso.
set -u
LABEL=com.atlasone.print-agent
USUARIO="$(stat -f %Su /dev/console)"
if [ -n "$USUARIO" ] && [ "$USUARIO" != root ] && [ "$USUARIO" != loginwindow ]; then
    UIDC="$(id -u "$USUARIO")"
    launchctl bootout "gui/$UIDC/$LABEL" 2>/dev/null
fi
# Primero el envoltorio `while true` de impresora_mac.sh, luego el agente manual.
for patron in '(bash|sh|zsh) .*impresora_mac\.sh$' 'python3? .*core/main\.py$'; do
    pkill -f "$patron" 2>/dev/null
done
sleep 2
for patron in '(bash|sh|zsh) .*impresora_mac\.sh$' 'python3? .*core/main\.py$'; do
    pkill -9 -f "$patron" 2>/dev/null
done
exit 0
```

- [ ] **Step 3: `installers/agent/mac/scripts/postinstall`**

```bash
#!/bin/bash
# Corre como root. Todo lo que es "de la cajera" (LaunchAgent, estado, log,
# alias) va en SU home, no en el de root: si no, el agente no arranca nunca.
set -u
LABEL=com.atlasone.print-agent
APP="/Applications/Atlas Print Agent.app"
PLANTILLA="/Library/Application Support/AtlasPrintAgent/com.atlasone.print-agent.plist"

falla() {
    echo "✗ $*"
    echo "  Revisa: /var/log/install.log y ~/Library/Logs/AtlasPrintAgent/"
    exit 1
}

USUARIO="$(stat -f %Su /dev/console)"
if [ -z "$USUARIO" ] || [ "$USUARIO" = root ] || [ "$USUARIO" = loginwindow ]; then
    falla "No hay una cajera con sesión abierta. Inicia sesión con su usuario y vuelve a instalar."
fi
UIDC="$(id -u "$USUARIO")"
GRUPO="$(id -gn "$USUARIO")"
HOGAR="$(dscl . -read "/Users/$USUARIO" NFSHomeDirectory | awk '{print $2}')"
ESTADO="$HOGAR/Library/Application Support/AtlasPrintAgent"
LOGS="$HOGAR/Library/Logs/AtlasPrintAgent"
PLIST="$HOGAR/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$ESTADO/certs" "$LOGS" "$HOGAR/Library/LaunchAgents"

# ── Certificado: se conserva el que el navegador ya aceptó ────────────────────
# El instalador legado de servicio usaba este mismo directorio, así que en una
# Mac ya convertida el certificado ya está donde debe.
if [ -f "$ESTADO/certs/cert.pem" ] && [ -f "$ESTADO/certs/key.pem" ]; then
    echo "✓ Certificado existente conservado."
else
    PREVIO=""
    for d in "$ESTADO" "$HOGAR/Downloads/print_agent/core/certs" "$HOGAR/Descargas/print_agent/core/certs"; do
        if [ -f "$d/cert.pem" ] && [ -f "$d/key.pem" ]; then PREVIO="$d"; break; fi
    done
    if [ -z "$PREVIO" ]; then
        # macOS puede negarle al instalador leer Descargas o Escritorio (privacidad).
        # Si eso pasa, esto no encuentra nada y el runbook dice cómo copiarlo antes.
        c="$(find "$HOGAR" -maxdepth 6 -type f -name cert.pem -path '*/core/certs/*' -print0 2>/dev/null \
              | xargs -0 stat -f '%m %N' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
        if [ -n "$c" ] && [ -f "$(dirname "$c")/key.pem" ]; then PREVIO="$(dirname "$c")"; fi
    fi
    if [ -n "$PREVIO" ]; then
        cp "$PREVIO/cert.pem" "$PREVIO/key.pem" "$ESTADO/certs/"
        echo "✓ Certificado conservado desde $PREVIO."
    else
        echo "! No había certificado previo: el agente generará uno nuevo."
        echo "  Habrá que aceptarlo una vez en https://127.0.0.1:9100/health"
    fi
fi
[ -f "$ESTADO/certs/key.pem" ] && chmod 600 "$ESTADO/certs/key.pem"

if [ ! -f "$ESTADO/agent.conf" ]; then
    cat > "$ESTADO/agent.conf" <<'EOF'
# Configuración del agente de impresión Atlas. Una línea CLAVE=valor.
# Después de editarlo: cierra sesión y vuelve a entrar.
#
# Dominios extra del punto de venta, separados por coma. localhost,
# *.up.railway.app y (*.)atlasone.com.mx ya se aceptan sin escribir nada.
# ATLAS_AGENT_ORIGINS=https://pos.micliente.com
EOF
fi

# ── LaunchAgent ───────────────────────────────────────────────────────────────
sed "s|__HOME__|$HOGAR|g" "$PLANTILLA" > "$PLIST" || falla "No se pudo escribir $PLIST"
chown -R "$USUARIO:$GRUPO" "$ESTADO" "$LOGS"
chown "$USUARIO:$GRUPO" "$PLIST" "$HOGAR/Library/LaunchAgents"
chmod 644 "$PLIST"

launchctl asuser "$UIDC" launchctl bootout "gui/$UIDC/$LABEL" 2>/dev/null
SALIDA="$(launchctl asuser "$UIDC" launchctl bootstrap "gui/$UIDC" "$PLIST" 2>&1)" \
    || falla "launchctl bootstrap falló: $SALIDA"

# ── Alias en el Escritorio (el equivalente al acceso directo de Windows) ──────
ln -sfn "$APP" "$HOGAR/Desktop/Atlas Print Agent" 2>/dev/null \
    && chown -h "$USUARIO:$GRUPO" "$HOGAR/Desktop/Atlas Print Agent" \
    || echo "! No se pudo crear el alias en el Escritorio; el agente está en Aplicaciones."

# ── Verificación real ─────────────────────────────────────────────────────────
for _ in $(seq 1 30); do
    sleep 1
    H="$(curl -sk --noproxy '*' --max-time 2 https://127.0.0.1:9100/health 2>/dev/null)"
    case "$H" in *'Atlas POS Print Agent'*) echo "✓ Agente respondiendo: $H"; exit 0 ;; esac
done
falla "El agente quedó instalado pero NO respondió en https://127.0.0.1:9100/health"
```

- [ ] **Step 4: `installers/agent/mac/desinstalar.sh`**

```bash
#!/bin/bash
# Desinstala el agente de impresión Atlas de esta Mac.
#   sudo "/Library/Application Support/AtlasPrintAgent/desinstalar.sh"            conserva certificado y agent.conf
#   sudo "/Library/Application Support/AtlasPrintAgent/desinstalar.sh" --purgar   también los borra
set -u
[ "$(id -u)" -eq 0 ] || { echo "Corre con sudo." >&2; exit 1; }
LABEL=com.atlasone.print-agent
USUARIO="$(stat -f %Su /dev/console)"
UIDC="$(id -u "$USUARIO")"
HOGAR="$(dscl . -read "/Users/$USUARIO" NFSHomeDirectory | awk '{print $2}')"
launchctl bootout "gui/$UIDC/$LABEL" 2>/dev/null
rm -f "$HOGAR/Library/LaunchAgents/$LABEL.plist" "$HOGAR/Desktop/Atlas Print Agent"
rm -rf "/Applications/Atlas Print Agent.app"
if [ "${1:-}" = "--purgar" ]; then
    rm -rf "$HOGAR/Library/Application Support/AtlasPrintAgent" "$HOGAR/Library/Logs/AtlasPrintAgent"
fi
pkgutil --forget com.atlasone.print-agent >/dev/null 2>&1
rm -rf "/Library/Application Support/AtlasPrintAgent"
echo "✓ Agente desinstalado."
```

- [ ] **Step 5: `installers/agent/mac/build_pkg.sh`**

```bash
#!/bin/bash
# Envuelve dist/agent/Atlas Print Agent.app en dist/atlas-print-agent-<versión>-<arq>.pkg.
# Corre en macOS (runner de CI o la Mac del dueño), después de construir.py.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../../.." && pwd)"
AQUI="$RAIZ/installers/agent/mac"
VERSION="$(python3 "$RAIZ/installers/agent/version_agente.py")"
ARQ="$(uname -m)"   # arm64 o x86_64
APP="$RAIZ/dist/agent/Atlas Print Agent.app"
[ -d "$APP" ] || { echo "Falta $APP: corre antes installers/agent/construir.py" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
RAIZ_PKG="$TMP/raiz"
SOPORTE="$RAIZ_PKG/Library/Application Support/AtlasPrintAgent"
mkdir -p "$RAIZ_PKG/Applications" "$SOPORTE" "$TMP/scripts"
cp -R "$APP" "$RAIZ_PKG/Applications/"
install -m 755 "$AQUI/desinstalar.sh" "$SOPORTE/"
install -m 644 "$AQUI/com.atlasone.print-agent.plist" "$SOPORTE/"
install -m 755 "$AQUI/scripts/preinstall" "$AQUI/scripts/postinstall" "$TMP/scripts/"

# pkgbuild marca los .app como reubicables por omisión: si alguien movió el .app,
# el instalador actualizaría esa copia y el LaunchAgent apuntaría a la vieja.
pkgbuild --analyze --root "$RAIZ_PKG" "$TMP/componentes.plist"
plutil -replace 0.BundleIsRelocatable -bool NO "$TMP/componentes.plist"

pkgbuild --root "$RAIZ_PKG" --component-plist "$TMP/componentes.plist" \
         --scripts "$TMP/scripts" --identifier com.atlasone.print-agent \
         --version "$VERSION" --install-location / "$TMP/componente.pkg"
mkdir -p "$RAIZ/dist"
SALIDA="$RAIZ/dist/atlas-print-agent-$VERSION-$ARQ.pkg"
productbuild --package "$TMP/componente.pkg" "$SALIDA"
echo "$SALIDA"
```

- [ ] **Step 6: Revisión estática local** (en WSL no hay `pkgbuild`; se construye en CI, Task 10)

Run: `bash -n installers/agent/mac/scripts/preinstall installers/agent/mac/scripts/postinstall installers/agent/mac/desinstalar.sh installers/agent/mac/build_pkg.sh && python3 -c "import plistlib; plistlib.load(open('installers/agent/mac/com.atlasone.print-agent.plist','rb')); print('plist OK')"`
Expected: sin errores; `plist OK`. Con shellcheck disponible: `shellcheck -S warning` sobre los cuatro, sin advertencias.

- [ ] **Step 7: Commit**

```bash
git add installers/agent/mac/
git add --chmod=+x installers/agent/mac/scripts/preinstall installers/agent/mac/scripts/postinstall installers/agent/mac/desinstalar.sh installers/agent/mac/build_pkg.sh
git commit -m "installers: paquete .pkg de macOS con LaunchAgent de la cajera y alias en el Escritorio

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Instalador `.exe` para Windows

**Files:**
- Create: `installers/agent/windows/atlas-print-agent.iss`, `installers/agent/windows/registrar.ps1`,
  `installers/agent/windows/tarea.xml`

**Interfaces:**
- Consumes: `dist/agent/atlas-print-agent/` (Task 5, en Windows); variable de entorno `ATLAS_VERSION` con la versión.
- Produces: `dist/atlas-print-agent-setup-<versión>.exe`. En la PC deja `%LOCALAPPDATA%\Programs\AtlasPrintAgent\`,
  la tarea `Atlas Print Agent`, accesos directos en Menú Inicio y Escritorio, y `%LOCALAPPDATA%\AtlasPrintAgent\`.
  `registrar.ps1 -Exe <ruta>` sale 0 solo si `/health` responde; `registrar.ps1 -Quitar` baja y borra la tarea.

- [ ] **Step 1: `installers/agent/windows/tarea.xml`** (plantilla; `__USUARIO__` y `__EXE__` los sustituye `registrar.ps1`; sin declaración XML a propósito: `Register-ScheduledTask -Xml` recibe una cadena y una declaración `UTF-16` en una cadena lo hace fallar)

```xml
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Arranca el agente de impresión Atlas al iniciar sesión y lo vuelve a levantar si se cae.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>__USUARIO__</UserId>
    </LogonTrigger>
    <!-- Vigilante sin código: cada minuto intenta arrancarlo; con IgnoreNew, si ya
         corre no pasa nada. RestartOnFailure no cubre que el proceso muera. -->
    <TimeTrigger>
      <Repetition>
        <Interval>PT1M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>__USUARIO__</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>__EXE__</Command>
      <Arguments>--servicio</Arguments>
    </Exec>
  </Actions>
</Task>
```

- [ ] **Step 2: `installers/agent/windows/registrar.ps1`**

```powershell
# Registra el agente de impresión Atlas en el Programador de tareas de ESTA cuenta
# y no declara éxito sin que /health responda. Lo llama el instalador (Inno Setup).
#   registrar.ps1 -Exe "C:\...\atlas-print-agent.exe"
#   registrar.ps1 -Quitar
# Tarea y no servicio: un servicio corre en la sesión 0 y no ve las impresoras
# instaladas por usuario (spec §6.3).
param([string]$Exe, [switch]$Quitar)
$ErrorActionPreference = "Stop"
$Tarea = "Atlas Print Agent"
$Estado = Join-Path $env:LOCALAPPDATA "AtlasPrintAgent"
New-Item -ItemType Directory -Force -Path $Estado | Out-Null
$Bitacora = Join-Path $Estado "instalador.log"
function Anotar([string]$m) { $l = "$(Get-Date -Format s)  $m"; Write-Output $l; Add-Content -Path $Bitacora -Value $l -Encoding UTF8 }

function Detener-Agente {
    Get-ScheduledTask -TaskName $Tarea -ErrorAction SilentlyContinue | Stop-ScheduledTask -ErrorAction SilentlyContinue
    Get-Process -Name "atlas-print-agent" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

if ($Quitar) {
    Detener-Agente
    Unregister-ScheduledTask -TaskName $Tarea -Confirm:$false -ErrorAction SilentlyContinue
    Anotar "Tarea '$Tarea' eliminada."
    exit 0
}

# 1. Modo manual: primero la ventana de impresora_win.bat (su :loop relanza el
#    agente cada 5 s), luego el python del agente.
Detener-Agente
$procesos = Get-CimInstance Win32_Process
$procesos | Where-Object { $_.Name -eq "cmd.exe" -and $_.CommandLine -match "impresora_win\.bat" } |
    ForEach-Object { Anotar "Deteniendo la ventana del modo manual (PID $($_.ProcessId))"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$procesos | Where-Object { $_.Name -match "^pythonw?\.exe$" -and $_.CommandLine -match "core\\main\.py" } |
    ForEach-Object { Anotar "Deteniendo el agente manual (PID $($_.ProcessId))"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 2. Certificado: se conserva el que el navegador ya aceptó.
$Certs = Join-Path $Estado "certs"
if ((Test-Path (Join-Path $Certs "cert.pem")) -and (Test-Path (Join-Path $Certs "key.pem"))) {
    Anotar "Certificado existente conservado."
} else {
    $previo = Get-ChildItem -Path $env:USERPROFILE -Filter "cert.pem" -Recurse -Depth 6 -File -ErrorAction SilentlyContinue |
        Where-Object { $_.DirectoryName -match "\\core\\certs$" -and (Test-Path (Join-Path $_.DirectoryName "key.pem")) } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($previo) {
        New-Item -ItemType Directory -Force -Path $Certs | Out-Null
        Copy-Item (Join-Path $previo.DirectoryName "cert.pem"), (Join-Path $previo.DirectoryName "key.pem") -Destination $Certs
        Anotar "Certificado conservado desde $($previo.DirectoryName)."
    } else {
        Anotar "No había certificado previo: el agente generará uno nuevo (habrá que aceptarlo una vez en el navegador)."
    }
}

# 3. agent.conf de ejemplo, solo si no existe.
$Conf = Join-Path $Estado "agent.conf"
if (-not (Test-Path $Conf)) {
    @(
        "# Configuración del agente de impresión Atlas. Una línea CLAVE=valor.",
        "# Después de editarlo: cierra sesión y vuelve a entrar.",
        "#",
        "# Dominios extra del punto de venta, separados por coma. localhost,",
        "# *.up.railway.app y (*.)atlasone.com.mx ya se aceptan sin escribir nada.",
        "# ATLAS_AGENT_ORIGINS=https://pos.micliente.com"
    ) | Set-Content -Path $Conf -Encoding UTF8
}
$Puerto = 9100
$linea = Select-String -Path $Conf -Pattern "^\s*ATLAS_AGENT_PORT\s*=\s*(\d+)" | Select-Object -Last 1
if ($linea) { $Puerto = [int]$linea.Matches[0].Groups[1].Value }

# 4. Tarea programada.
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$xml = Get-Content -Raw -Path (Join-Path $PSScriptRoot "tarea.xml")
$xml = $xml.Replace("__USUARIO__", [System.Security.SecurityElement]::Escape($usuario))
$xml = $xml.Replace("__EXE__", [System.Security.SecurityElement]::Escape($Exe))
Register-ScheduledTask -TaskName $Tarea -Xml $xml -Force | Out-Null
Start-ScheduledTask -TaskName $Tarea
Anotar "Tarea '$Tarea' registrada para $usuario y arrancada."

# 5. Verificación real.
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $r = & curl.exe -sk --noproxy "*" --max-time 2 "https://127.0.0.1:$Puerto/health" 2>$null
    if ($r -match "Atlas POS Print Agent") { Anotar "Agente respondiendo: $r"; exit 0 }
}
$dueno = Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($dueno) { Anotar "El puerto $Puerto lo tiene otro programa: $((Get-Process -Id $dueno.OwningProcess).ProcessName)" }
Anotar "El agente NO respondió en https://127.0.0.1:$Puerto/health"
exit 1
```

- [ ] **Step 3: `installers/agent/windows/atlas-print-agent.iss`**

```pascal
; Instalador del agente de impresión Atlas para Windows.
; Por usuario, sin UAC: instala en %LOCALAPPDATA%\Programs\AtlasPrintAgent y registra
; una tarea programada al inicio de sesión (registrar.ps1).
; Compilar desde la raíz, con ATLAS_VERSION definida:
;   $env:ATLAS_VERSION = python installers\agent\version_agente.py
;   & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" installers\agent\windows\atlas-print-agent.iss

#define Version GetEnv("ATLAS_VERSION")
#if Version == ""
  #error "Define ATLAS_VERSION antes de compilar"
#endif

[Setup]
AppId={{28FFA762-984A-4E97-8200-EAA05330F3BD}
AppName=Agente de Impresión Atlas
AppVersion={#Version}
AppPublisher=Atlas Technologies
DefaultDirName={localappdata}\Programs\AtlasPrintAgent
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\..\dist
OutputBaseFilename=atlas-print-agent-setup-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Agente de Impresión Atlas
UninstallDisplayIcon={app}\atlas-print-agent.exe
CloseApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\..\..\dist\agent\atlas-print-agent\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "registrar.ps1"; DestDir: "{app}\instalador"; Flags: ignoreversion
Source: "tarea.xml"; DestDir: "{app}\instalador"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Agente de Impresión Atlas"; Filename: "{app}\atlas-print-agent.exe"
Name: "{userdesktop}\Agente de Impresión Atlas"; Filename: "{app}\atlas-print-agent.exe"

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\instalador\registrar.ps1"" -Quitar"; Flags: runhidden waituntilterminated; RunOnceId: "QuitarTarea"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  // Una actualización no puede reemplazar el .exe mientras corre.
  Exec('taskkill.exe', '/F /IM atlas-print-agent.exe', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Codigo: Integer;
  Parametros: String;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := 'Arrancando el agente y comprobando que responda...';
    Parametros := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\instalador\registrar.ps1') +
                  '" -Exe "' + ExpandConstant('{app}\atlas-print-agent.exe') + '"';
    if (not Exec('powershell.exe', Parametros, '', SW_HIDE, ewWaitUntilTerminated, Codigo)) or (Codigo <> 0) then
      MsgBox('El agente quedó instalado pero NO respondió en https://127.0.0.1:9100/health.' + #13#10 + #13#10 +
             'La caja todavía no imprime. Revisa este archivo y llama a soporte:' + #13#10 +
             ExpandConstant('{localappdata}\AtlasPrintAgent\instalador.log'),
             mbCriticalError, MB_OK);
  end;
end;
```

- [ ] **Step 4: Revisión estática local**

Run: `python3 -c "import xml.etree.ElementTree as E; E.parse('installers/agent/windows/tarea.xml'); print('xml OK')"`
Expected: `xml OK`.

Desde PowerShell de Windows (no requiere instalar nada):
`powershell.exe -NoProfile -Command "$null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'installers\agent\windows\registrar.ps1'), [ref]$null, [ref]$e); if ($e) { $e; exit 1 } else { 'ps1 OK' }"`
Expected: `ps1 OK`. (El `.exe` se compila en CI —Task 10— o en la PC del dueño —Task 12.)

- [ ] **Step 5: Commit**

```bash
git add installers/agent/windows/
git commit -m "installers: instalador de Windows por usuario con tarea al iniciar sesión y vigilante por minuto

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Workflow de release en GitHub Actions

**Files:**
- Create: `.github/workflows/release.yml`, `installers/agent/notas-release.md`

**Interfaces:**
- Consumes: todo lo anterior (`version_agente.py --verificar-tag`, `construir.py`, `humo.py`, `build_deb.sh`,
  `build_pkg.sh`, `atlas-print-agent.iss`).
- Produces: con un tag `v*`, una release con los cuatro artefactos; con `workflow_dispatch`, los mismos artefactos
  como *artifacts* del run, sin publicar nada.

- [ ] **Step 1: `installers/agent/notas-release.md`**

```markdown
## ¿Qué archivo descargo?

| Caja | Archivo | Cómo se instala |
|---|---|---|
| Ubuntu 22.04 o más nuevo (PC normal, 64 bits) | `atlas-print-agent_<versión>_amd64.deb` | `sudo apt install ./atlas-print-agent_<versión>_amd64.deb` |
| Mac con chip Apple (M1, M2, M3, M4…) | `atlas-print-agent-<versión>-arm64.pkg` | doble clic |
| Mac con procesador Intel | `atlas-print-agent-<versión>-x86_64.pkg` | doble clic |
| Windows 10 u 11 | `atlas-print-agent-setup-<versión>.exe` | doble clic |

**¿Mac con chip Apple o Intel?** Menú  → *Acerca de esta Mac*: si dice *Chip Apple M…* es `arm64`; si dice
*Procesador Intel* es `x86_64`. Elegir mal se descubre hasta el doble clic.

Los instaladores no están firmados: Windows mostrará *"Windows protegió su PC"* (→ *Más información* →
*Ejecutar de todas formas*) y macOS pedirá abrirlo con clic derecho → *Abrir*. Detalles en
`installers/agent/README.md`.
```

- [ ] **Step 2: `.github/workflows/release.yml`**

```yaml
name: release-agente

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  pruebas:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: El tag coincide con VERSION de main.py
        if: startsWith(github.ref, 'refs/tags/')
        run: python installers/agent/version_agente.py --verificar-tag "$GITHUB_REF_NAME"
      - run: pip install -r installers/agent/requirements-build.txt pytest
      - run: python -m pytest tests/agent -q

  construir:
    needs: pruebas
    strategy:
      fail-fast: false
      matrix:
        include:
          - { os: ubuntu-22.04,   sistema: linux }    # glibc 2.35: corre en Ubuntu 22.04 y más nuevos
          - { os: macos-15,       sistema: mac }      # Apple Silicon
          - { os: macos-15-intel, sistema: mac }      # Intel
          - { os: windows-latest, sistema: windows }
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r installers/agent/requirements-build.txt
      - run: python installers/agent/construir.py
      - name: Prueba de humo del binario
        run: python installers/agent/humo.py

      - name: Paquete .deb
        if: matrix.sistema == 'linux'
        run: bash installers/agent/linux/build_deb.sh

      - name: Paquete .pkg
        if: matrix.sistema == 'mac'
        run: bash installers/agent/mac/build_pkg.sh

      - name: Instalador .exe
        if: matrix.sistema == 'windows'
        shell: pwsh
        run: |
          $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
          if (-not (Test-Path $iscc)) { choco install innosetup -y --no-progress }
          $env:ATLAS_VERSION = python installers/agent/version_agente.py
          & $iscc installers\agent\windows\atlas-print-agent.iss
          if ($LASTEXITCODE -ne 0) { throw "ISCC falló" }

      - uses: actions/upload-artifact@v4
        with:
          name: paquete-${{ matrix.os }}
          if-no-files-found: error
          path: |
            dist/*.deb
            dist/*.pkg
            dist/*.exe

  publicar:
    needs: construir
    if: startsWith(github.ref, 'refs/tags/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          path: paquetes
          merge-multiple: true
      - name: Crear la release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          ls -l paquetes
          gh release create "$GITHUB_REF_NAME" paquetes/* \
            --repo "$GITHUB_REPOSITORY" \
            --title "Agente de impresión $GITHUB_REF_NAME" \
            --notes-file installers/agent/notas-release.md
```

- [ ] **Step 3: Validar el YAML**

Run: `uv run --no-project --with pyyaml python -c "import yaml; d=yaml.safe_load(open('.github/workflows/release.yml')); print(sorted(d['jobs']))"`
Expected: `['construir', 'publicar', 'pruebas']`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml installers/agent/notas-release.md
git commit -m "ci: release del agente con .deb, dos .pkg y .exe, con humo por plataforma

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: Correr el workflow sin publicar.** `git push` suele quedar bloqueado para el agente: pedir al dueño
  `! git push origin main` y luego `! gh workflow run release-agente --ref main`. Revisar con
  `gh run list --workflow release-agente --limit 1` y `gh run view <id> --log-failed`.
Expected: los cuatro jobs de `construir` en verde con su prueba de humo; `publicar` se salta (no es tag). Si un
runner falla, se corrige en la task dueña del archivo y se vuelve a correr. Si Actions no reconoce
`macos-15-intel`, sustituir por la etiqueta Intel vigente que liste la documentación de runners de GitHub y anotarlo
en el ruling 6.

---

### Task 11: Runbook y documentación

**Files:**
- Create: `installers/agent/README.md`
- Modify: `AGENTS.md` (tabla "Qué puedes tocar", Comandos), `README.md` (sección del agente),
  `docs/superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md` (estado y rulings)

- [ ] **Step 1: `installers/agent/README.md`** con estas secciones, en este orden, en español:
  1. **Qué archivo usar** — la tabla de `notas-release.md`.
  2. **Ubuntu** — `sudo apt install ./atlas-print-agent_<v>_amd64.deb`; si el usuario de la caja no es quien corre
     sudo: `sudo ATLAS_AGENT_USER=<usuario> apt install ./...`; qué significa el `✗` final y
     `journalctl -u atlas-print-agent -n 50 --no-pager`; `sudo dpkg --configure -a` tras corregir.
  3. **macOS** — clic derecho → *Abrir* para saltar Gatekeeper (o Ajustes → Privacidad y seguridad → *Abrir de
     todos modos*); el aviso de *Elementos de inicio* de macOS 15 que **no** se debe desactivar; **antes de instalar
     en una Mac que ya imprime en modo manual**, copiar el certificado para que el instalador lo encuentre aunque
     macOS le niegue leer Descargas:
     `mkdir -p ~/Library/Application\ Support/AtlasPrintAgent/certs && cp <carpeta del agente>/core/certs/*.pem ~/Library/Application\ Support/AtlasPrintAgent/certs/`;
     comprobar con `launchctl print gui/$(id -u)/com.atlasone.print-agent | grep state` → `state = running`;
     desinstalar con `sudo "/Library/Application Support/AtlasPrintAgent/desinstalar.sh"`.
  4. **Windows** — *Windows protegió su PC* → *Más información* → *Ejecutar de todas formas*; exclusión del
     antivirus si marca el `.exe` (falso positivo conocido de PyInstaller, igual que `Atlas Labels.exe`); la tarea
     `Atlas Print Agent` en el Programador de tareas; el vigilante de un minuto; `instalador.log`.
     Espacio reservado para las dos capturas de pantalla, que se toman en la Task 12.
  5. **Dónde vive cada cosa** — tabla de directorios de estado y log por sistema, `agent.conf` y su precedencia.
  6. **Cambiar el dominio del POS** — editar `agent.conf` y reiniciar el servicio; no se reinstala.
  7. **Verificación** — los comandos de la Task 7 (Ubuntu) y los del §10.2 del spec (Mac).
  8. **Punto abierto** — si `/printers/install` falla desde el servicio en Ubuntu por falta de autenticación de
     CUPS, la salida es una regla de `sudoers` limitada a `lpadmin` y `cupsenable` (spec §6.1), no correr como root.
  9. **Construir localmente** — los comandos del Step 8 de la Task 5 y `build_deb.sh`.

- [ ] **Step 2: `AGENTS.md`.** En la tabla "Qué puedes tocar y qué no", agregar la fila:

```markdown
| `installers/agent/`, `tests/agent/` | **Desarrollo normal.** Empaquetado y autoarranque del agente (`.deb`, `.pkg`, `.exe`). `lanzador.py` y `agent_state.py` en `legacy/print_agent/core/` son parte de esto. |
```

  y cambiar la fila de `legacy/print_agent/` a:

```markdown
| `legacy/print_agent/` | **Congelado**, salvo la excepción acotada del autoarranque (spec 2026-09-22 §5.2 y rulings del plan 2026-09-28): directorio de estado, `agent.conf`, certificado en proceso, `run()`, versión. Un arreglo aquí solo si algo está roto en producción hoy. |
```

  En "Comandos" agregar:

```bash
# Tests del agente empaquetado
uv run --no-project --with fastapi --with uvicorn --with pydantic --with cryptography --with pytest \
  python -m pytest tests/agent -q

# Binario y prueba de humo (Python del sistema, no el de uv: PyInstaller necesita libpython)
python installers/agent/construir.py && python installers/agent/humo.py
bash installers/agent/linux/build_deb.sh
```

  y reemplazar el comentario del agente en local por
  `cd legacy/print_agent/core && python main.py     # https://127.0.0.1:9100 — estado en ~/.local/state/atlas-print-agent`.
  En "Trampas conocidas" agregar: **"Una release se publica empujando un tag `vX.Y.Z` que coincida con `VERSION`
  de `main.py`; el workflow falla si no."**

- [ ] **Step 3: `README.md`.** En la sección del agente, cambiar la instrucción de arranque manual por: "En una caja
  se instala con el paquete de su sistema desde la última release (ver `installers/agent/README.md`) y arranca solo.
  El modo manual con `impresora_*.sh` / `impresora_win.bat` queda para cajas sin convertir."

- [ ] **Step 4: Spec.** Cambiar la línea de estado a
  `**Estado:** diseño aprobado el 2026-09-22; plan en docs/superpowers/plans/2026-09-28-autoarranque-multiplataforma.md.`
  y agregar al final una sección `## 14. Rulings de la implementación` con los siete rulings del plan, copiados tal
  cual, más el resultado de la Task 7 (fecha y "verificado en WSL: revive, huella estable, falla ruidosa").

- [ ] **Step 5: Correr las tres suites**

Run: los tres comandos de tests de Global Constraints.
Expected: `tests/agent` todo verde; `legacy/tests` 27 pasan y 3 fallan (los de siempre); `tests/labels` 122 pasan.

- [ ] **Step 6: Commit**

```bash
git add installers/agent/README.md AGENTS.md README.md docs/superpowers/specs/2026-09-22-autoarranque-multiplataforma-design.md
git commit -m "docs: runbook de instalación del agente y rulings del autoarranque

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Verificación en campo y release `v3.1.0` (con el dueño)

No se puede hacer desde esta máquina: la térmica cuelga de otra PC Windows, y la Mac es del dueño. El implementador
prepara la lista, el dueño la ejecuta, y el resultado se anota en el spec (§14) y en la memoria del proyecto.

- [ ] **Step 1: Windows, en la PC donde está conectada la térmica.** Descargar el `.exe` del run de la Task 10;
  instalar (tomar las dos capturas de SmartScreen para el runbook); confirmar el acceso directo; **cerrar sesión y
  volver a entrar** sin abrir nada → `https://127.0.0.1:9100/health` responde; matar `atlas-print-agent.exe` en el
  Administrador de tareas → vuelve en ≤ 60 s; doble clic en el acceso directo → *"ya está activo"*; **imprimir un
  ticket real desde el POS** (que `/health` responda no garantiza papel).
- [ ] **Step 2: Mac del dueño.** Copiar antes el certificado del modo manual (runbook §3); instalar el `.pkg` de su
  arquitectura; cerrar sesión y volver a entrar; `launchctl print gui/$(id -u)/com.atlasone.print-agent | grep state`
  → `state = running`; `curl -k https://127.0.0.1:9100/health`; el navegador **no** vuelve a pedir aceptar el
  certificado; doble clic en el `.app` → *"ya está activo"*; ticket real desde el POS.
- [ ] **Step 3: Publicar.** Con los Steps 1 y 2 en verde, el dueño corre `! git tag v3.1.0 && git push origin v3.1.0`.
  El workflow verifica el tag contra `VERSION`, construye, corre el humo y publica la release.
- [ ] **Step 4: Anotar** en el spec §14 fecha y resultado de cada plataforma, y actualizar la memoria
  `project-autoarranque-multiplataforma.md` (estado: implementado; qué quedó verificado dónde; pendiente de campo
  de `lpadmin` en Ubuntu). Recordar que las peticiones 1 a 3 de `docs/peticiones-a-atlas-one.md` (redirigir la
  descarga a la release) ya se pueden ejecutar del lado de Atlas One — se avisan, no se editan desde aquí.
