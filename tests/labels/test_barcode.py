import pytest

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


def test_code128_modules_es_exacto_segun_subconjuntos():
    # 13 dígitos: START B + '2' + CODE C + 6 pares + check = 10 símbolos de 11 + STOP de 13
    assert code128_modules("2017000000014") == 10 * 11 + 13
    # 6 alfanuméricos en B: START B + 6 + check = 8 símbolos + STOP
    assert code128_modules("1A43KE") == 8 * 11 + 13
    # 12 dígitos: START C + 6 pares + check = 8 símbolos + STOP
    assert code128_modules("201700000001") == 8 * 11 + 13


def test_detect_codigo_largo_baja_a_modulo_1_y_advierte():
    spec = detect("ABCDEFGHIJKLMNOPQRST")  # 20 símbolos → 255 módulos → 510 dots
    assert spec.module_width == 1
    assert "angosto" in spec.warning


def test_detect_solo_asteriscos_y_espacios_devuelve_none():
    assert detect("* * *") is None
    assert detect("***   ***   ***") is None


def test_detect_quita_asteriscos_y_espacios_interiores():
    assert detect("*1A4 3KE*").data == "1A43KE"


from atlas_labels.barcode import (  # noqa: E402
    CODE128_PATTERNS,
    CODE128_STOP,
    CODE_C,
    START_B,
    START_C,
    encode_code128,
    encode_ean13,
)


def _bits(value: int) -> str:
    out, bar = "", True
    for w in CODE128_PATTERNS[value]:
        out += ("1" if bar else "0") * int(w)
        bar = not bar
    return out


def test_tabla_code128_es_consistente():
    assert len(CODE128_PATTERNS) == 106
    assert all(sum(int(w) for w in p) == 11 for p in CODE128_PATTERNS)
    assert sum(int(w) for w in CODE128_STOP) == 13
    assert _bits(0) == "11011001100"


def test_encode_code128_ab_en_subconjunto_b_con_checksum():
    # START B=104, 'A'=33, 'B'=34 → 104 + 33*1 + 34*2 = 205 → 205 % 103 = 102
    stop = "".join(("1" if i % 2 == 0 else "0") * int(w) for i, w in enumerate(CODE128_STOP))
    assert encode_code128("AB") == _bits(START_B) + _bits(33) + _bits(34) + _bits(102) + stop


def test_encode_code128_solo_digitos_pares_empieza_en_c():
    bits = encode_code128("1234")
    assert bits.startswith(_bits(START_C) + _bits(12) + _bits(34))
    assert len(bits) == 4 * 11 + 13  # START C, 12, 34, check + STOP


def test_encode_code128_corrida_impar_pone_primer_digito_en_b():
    bits = encode_code128("12345")
    assert bits.startswith(_bits(START_B) + _bits(ord("1") - 32) + _bits(CODE_C) + _bits(23) + _bits(45))


def test_encode_code128_corrida_corta_se_queda_en_b():
    bits = encode_code128("AB12CD")
    assert len(bits) == 8 * 11 + 13
    assert _bits(CODE_C) not in bits[: 3 * 11]


def test_encode_code128_rechaza_fuera_de_ascii():
    with pytest.raises(ValueError):
        encode_code128("ñ")


def test_encode_ean13_patron_conocido():
    bits = encode_ean13("2017000000013")
    assert len(bits) == 95
    assert bits == (
        "101"
        "0001101" "0011001" "0010001" "0100111" "0001101" "0100111"  # 0 1 7 0 0 0 con paridad LLGGLG
        "01010"
        "1110010" "1110010" "1110010" "1110010" "1100110" "1000010"  # 0 0 0 0 1 3 en R
        "101"
    )


def test_encode_ean13_rechaza_checksum_invalido():
    with pytest.raises(ValueError):
        encode_ean13("2017000000014")


def test_barcodespec_bits_y_width_dots_coinciden():
    spec = detect("2017000000013")
    assert spec.bits == encode_ean13("2017000000013")
    assert spec.width_dots == 190
    spec = detect("1A43KE")
    assert spec.bits == encode_code128("1A43KE")
    assert spec.width_dots == len(spec.bits) * 2
