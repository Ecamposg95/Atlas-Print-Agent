"""El agente local debe aceptar el dominio propio del despliegue.

Contexto: hasta ahora los orígenes permitidos estaban incrustados en el código
(`*-datax.up.railway.app`). Una sucursal servida desde un dominio propio —el
caso de la migración al VPS— **vende pero no imprime**: el navegador manda el
Origin del dominio nuevo y el agente lo rechaza en el preflight. El equipo de
Atlas One documentó exactamente ese fallo antes de mover a su cliente.

`ATLAS_AGENT_ORIGINS` (lista separada por comas) resuelve el caso sin recompilar
el agente ni tocar el regex.
"""
import importlib.util
import os
import re
import sys
from pathlib import Path

import pytest

AGENT = Path(__file__).resolve().parents[1] / "print_agent" / "core" / "main.py"


def _load_agent(env_origins=None):
    """Carga el módulo del agente con ATLAS_AGENT_ORIGINS controlado.

    Se importa por ruta y con nombre único por caso: el módulo lee la variable
    de entorno en tiempo de import, así que reusar el del sys.modules daría el
    valor del caso anterior.
    """
    prev = os.environ.get("ATLAS_AGENT_ORIGINS")
    if env_origins is None:
        os.environ.pop("ATLAS_AGENT_ORIGINS", None)
    else:
        os.environ["ATLAS_AGENT_ORIGINS"] = env_origins
    name = f"_agent_under_test_{abs(hash(str(env_origins)))}"
    try:
        spec = importlib.util.spec_from_file_location(name, AGENT)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.modules.pop(name, None)
        if prev is None:
            os.environ.pop("ATLAS_AGENT_ORIGINS", None)
        else:
            os.environ["ATLAS_AGENT_ORIGINS"] = prev


def _allows(mod, origin: str) -> bool:
    """True si el agente aceptaría ese Origin (lista explícita o regex)."""
    if origin in mod._CORS_ORIGINS:
        return True
    for mw in mod.app.user_middleware:
        rx = mw.kwargs.get("allow_origin_regex") if hasattr(mw, "kwargs") else None
        if rx and re.fullmatch(rx, origin):
            return True
    return False


@pytest.mark.skipif(not AGENT.exists(), reason="agente no presente")
class TestOrigenesDelAgente:
    def test_dominio_propio_se_acepta_via_env(self):
        """El caso de la migración: rmazh.atlasone.com.mx debe poder imprimir."""
        mod = _load_agent("https://rmazh.atlasone.com.mx")
        assert _allows(mod, "https://rmazh.atlasone.com.mx")

    def test_sin_la_variable_el_dominio_propio_se_rechaza(self):
        """Sin configurar, el comportamiento es el de hoy — nadie ajeno entra."""
        mod = _load_agent(None)
        assert not _allows(mod, "https://rmazh.atlasone.com.mx")

    def test_varios_dominios_separados_por_coma(self):
        mod = _load_agent("https://uno.example.com, https://dos.example.com")
        assert _allows(mod, "https://uno.example.com")
        assert _allows(mod, "https://dos.example.com")

    def test_entradas_vacias_o_espacios_se_ignoran(self):
        mod = _load_agent("  ,https://valido.example.com,  ,")
        assert _allows(mod, "https://valido.example.com")
        assert "" not in mod._CORS_ORIGINS
        assert all(o == o.strip() for o in mod._CORS_ORIGINS)

    def test_los_dominios_actuales_de_railway_siguen_funcionando(self):
        """No romper las 29 sucursales que hoy apuntan a Railway."""
        mod = _load_agent(None)
        for o in ("https://beta-datax.up.railway.app",
                  "https://qa-datax.up.railway.app",
                  "https://datax.up.railway.app"):
            assert _allows(mod, o), o

    def test_cualquier_subdominio_de_railway_se_acepta(self):
        """El regex se amplió: un rebrand del host no debe romper la impresión."""
        mod = _load_agent(None)
        assert _allows(mod, "https://atlas-one.up.railway.app")

    def test_localhost_sigue_permitido(self):
        mod = _load_agent(None)
        for o in ("http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:8080"):
            assert _allows(mod, o), o

    def test_un_dominio_ajeno_sigue_rechazado(self):
        """Ampliar orígenes no debe abrir la puerta a cualquiera: el agente
        imprime y abre el cajón sin autenticación."""
        mod = _load_agent("https://rmazh.atlasone.com.mx")
        for o in ("https://evil.example.com",
                  "https://rmazh.atlasone.com.mx.evil.com",
                  "http://rmazh.atlasone.com.mx"):
            assert not _allows(mod, o), o
