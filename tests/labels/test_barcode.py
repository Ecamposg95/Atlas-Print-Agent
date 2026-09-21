from atlas_labels.barcode import (
    MAX_CODE128_CHARS,
    code128_modules,
    detect,
    ean13_checksum_ok,
)


def test_checksum_ean13_valido():
    assert ean13_checksum_ok("2017000000013")


def test_checksum_ean13_invalido():
    assert not ean13_checksum_ok("2017000000014")
    assert not ean13_checksum_ok("12345")
    assert not ean13_checksum_ok("20170000000A3")


def test_detect_ean13():
    spec = detect("2017000000013")
    assert spec.kind == "EAN13"
    assert spec.data == "2017000000013"
    assert spec.module_width == 2
    assert spec.width_dots == 190


def test_detect_ean13_con_checksum_malo_va_a_code128():
    assert detect("2017000000014").kind == "CODE128"


def test_detect_quita_asteriscos_y_espacios():
    spec = detect(" *1A43KE* ")
    assert spec.kind == "CODE128"
    assert spec.data == "1A43KE"
    assert spec.module_width == 2
    assert spec.warning == ""


def test_detect_descarta_caracteres_no_ascii_y_de_control_zpl():
    assert detect("AB^C~Dñ").data == "ABCD"


def test_detect_vacio_o_solo_basura_devuelve_none():
    assert detect("") is None
    assert detect("   ") is None
    assert detect("**") is None
    assert detect(None) is None


def test_detect_recorta_a_20_y_advierte():
    spec = detect("A" * 25)
    assert len(spec.data) == MAX_CODE128_CHARS
    assert "recortado" in spec.warning


def test_code128_modules_pares_de_digitos_cuentan_uno():
    # 13 dígitos: 6 pares + 1 suelto = 7 símbolos → 11*7 + 35 = 112
    assert code128_modules("2017000000014") == 112
    # "1A43KE" → símbolos 1, A, 43, K, E = 5 → 11*5 + 35 = 90
    assert code128_modules("1A43KE") == 90


def test_detect_codigo_largo_baja_a_modulo_1_y_advierte():
    spec = detect("ABCDEFGHIJKLMNOPQRST")  # 20 símbolos → 255 módulos → 510 dots
    assert spec.module_width == 1
    assert "angosto" in spec.warning


def test_detect_solo_asteriscos_y_espacios_devuelve_none():
    assert detect("* * *") is None
    assert detect("***   ***   ***") is None


def test_detect_quita_asteriscos_y_espacios_interiores():
    assert detect("*1A4 3KE*").data == "1A43KE"
