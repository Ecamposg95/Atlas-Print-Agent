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
