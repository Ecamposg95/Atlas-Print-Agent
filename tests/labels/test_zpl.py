from decimal import Decimal

import pytest

from atlas_labels.model import Product
from atlas_labels.zpl import (
    LABEL_HEIGHT,
    LABEL_WIDTH,
    build_batch,
    build_label,
    build_test_label,
    fit_text,
    text_width,
    zpl_safe,
)


def _p(**kw):
    base = dict(sku="CH-PLAY-EP-CH", name="Playera estampada premium", brand="Chrome Hearts",
                barcode="2017000000013", price=Decimal("1800"), stock=3, color="Negro", size="M")
    base.update(kw)
    return Product(**base)


def test_zpl_safe_reemplaza_caracteres_de_control():
    assert zpl_safe("a^b~c") == "a b c"
    assert zpl_safe(None) == ""


def test_text_width_estima_por_altura():
    assert text_width("abcd", 20) == 44  # 4 * 20 * 0.55


def test_fit_text_recorta_por_ancho_sin_elipsis_unicode():
    out = fit_text("Nombre extremadamente largo para la etiqueta", 18, 200)
    assert "…" not in out
    assert out.endswith("..")
    assert text_width(out, 18) <= 200


def test_fit_text_deja_intacto_lo_que_cabe():
    assert fit_text("Corto", 18, 384) == "Corto"


def test_build_label_estructura_basica():
    zpl = build_label(_p(), copies=5)
    assert zpl.startswith("^XA")
    assert zpl.rstrip().endswith("^XZ")
    for cmd in (f"^PW{LABEL_WIDTH}", f"^LL{LABEL_HEIGHT}", "^CI28", "^PQ5"):
        assert cmd in zpl


def test_build_label_ean13_usa_be_y_centra():
    zpl = build_label(_p())
    assert "^BEN,48,Y,N^FD2017000000013^FS" in zpl
    assert "^FO109,76^BY2,2,48" in zpl  # (408 - 190) // 2 = 109


def test_build_label_code128_usa_bc_con_texto_limpio():
    zpl = build_label(_p(barcode="*1A43KE*"))
    assert "^BCN,48,Y,N,N,A^FD1A43KE^FS" in zpl


def test_build_label_code128_de_13_digitos_cabe_en_la_etiqueta():
    from atlas_labels.barcode import detect

    spec = detect("2017000000014")  # checksum inválido → Code 128
    zpl = build_label(_p(barcode="2017000000014"))
    line = next(l for l in zpl.splitlines() if ",76^BY" in l)
    x = int(line[len("^FO"):].split(",", 1)[0])
    assert x + spec.width_dots <= LABEL_WIDTH


def test_build_label_precio_alineado_a_la_derecha_con_fb():
    zpl = build_label(_p())
    assert "^FO246,162^A0N,22,22^FB150,1,0,R^FD$1,800.00^FS" in zpl


def test_build_label_sin_precio_omite_campo():
    zpl = build_label(_p(price=None, price_text=""))
    assert "^FB150" not in zpl


def test_build_label_variante_talla_color():
    assert "^FDM / Negro^FS" in build_label(_p())
    assert "^FDNegro^FS" in build_label(_p(size=""))
    assert ",56^" not in build_label(_p(size="", color=""))


def test_build_label_variante_larga_se_recorta_a_384():
    zpl = build_label(_p(size="Talla única extra grande", color="Verde esmeralda con detalles dorados y bordado"))
    line = next(l for l in zpl.splitlines() if l.startswith("^FO12,56^"))
    text = line.split("^FD", 1)[1].removesuffix("^FS")
    assert text.endswith("..")
    assert text_width(text, 15) <= 384


def test_build_label_escapa_y_recorta_textos():
    zpl = build_label(_p(name="X" * 80, brand="Ma^rca"))
    assert "Ma rca" in zpl
    assert "X" * 80 not in zpl
    assert "…" not in zpl


def test_build_label_copias_minimo_uno():
    assert "^PQ1" in build_label(_p(), copies=0)


def test_build_label_sin_codigo_lanza_valueerror():
    with pytest.raises(ValueError):
        build_label(_p(barcode=""))


def test_build_batch_concatena_bloques():
    out = build_batch([(_p(), 2), (_p(sku="OTRO"), 1)])
    assert out.count("^XA") == 2
    assert out.count("^XZ") == 2
    assert "^PQ2" in out and "^PQ1" in out
    assert out.endswith("\n")


def test_build_test_label_es_valido():
    zpl = build_test_label()
    assert "^XA" in zpl and "^BEN" in zpl and "ATLAS TECH" in zpl
