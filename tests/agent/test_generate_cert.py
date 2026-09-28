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
