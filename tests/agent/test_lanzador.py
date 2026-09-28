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
