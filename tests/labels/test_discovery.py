"""Descubrimiento del catálogo más reciente y su antigüedad."""

from datetime import date

import pytest

from atlas_labels.discovery import (
    catalog_date,
    default_search_dirs,
    describe_age,
    find_latest_catalog,
)


def _touch(path, contenido="x"):
    path.write_text(contenido, encoding="utf-8")
    return path


class TestFindLatestCatalog:
    def test_elige_el_de_fecha_mas_reciente_en_el_nombre(self, tmp_path):
        _touch(tmp_path / "catalogo_2026-09-14.xlsx")
        nuevo = _touch(tmp_path / "catalogo_2026-09-21.xlsx")

        assert find_latest_catalog([tmp_path]) == nuevo

    def test_sin_catalogos_devuelve_none(self, tmp_path):
        assert find_latest_catalog([tmp_path]) is None

    def test_ignora_archivos_que_no_son_catalogo(self, tmp_path):
        _touch(tmp_path / "ventas_2026-09-21.xlsx")

        assert find_latest_catalog([tmp_path]) is None

    def test_ignora_extensiones_que_no_se_pueden_abrir(self, tmp_path):
        _touch(tmp_path / "catalogo_2026-09-21.pdf")

        assert find_latest_catalog([tmp_path]) is None

    def test_acepta_csv_y_xlsm(self, tmp_path):
        esperado = _touch(tmp_path / "catalogo_2026-09-21.csv")

        assert find_latest_catalog([tmp_path]) == esperado

    def test_busca_en_todos_los_directorios_dados(self, tmp_path):
        descargas = tmp_path / "Descargas"
        downloads = tmp_path / "Downloads"
        descargas.mkdir()
        downloads.mkdir()
        _touch(descargas / "catalogo_2026-09-14.xlsx")
        nuevo = _touch(downloads / "catalogo_2026-09-21.xlsx")

        assert find_latest_catalog([descargas, downloads]) == nuevo

    def test_un_directorio_inexistente_no_revienta(self, tmp_path):
        esperado = _touch(tmp_path / "catalogo_2026-09-21.xlsx")

        assert find_latest_catalog([tmp_path / "no-existe", tmp_path]) == esperado


class TestCatalogDate:
    def test_toma_la_fecha_del_nombre(self, tmp_path):
        archivo = _touch(tmp_path / "catalogo_2026-09-21.xlsx")

        assert catalog_date(archivo) == date(2026, 9, 21)

    def test_la_fecha_del_nombre_gana_sobre_la_del_archivo(self, tmp_path):
        """Copiar el archivo actualiza su mtime; la fecha del export no cambia."""
        archivo = _touch(tmp_path / "catalogo_2026-09-14.xlsx")
        import os, time

        os.utime(archivo, (time.time(), time.time()))

        assert catalog_date(archivo) == date(2026, 9, 14)

    def test_sin_fecha_en_el_nombre_usa_la_del_archivo(self, tmp_path):
        import os

        archivo = _touch(tmp_path / "catalogo.xlsx")
        momento = 1789000000  # 2026-09-08 aproximadamente, en UTC
        os.utime(archivo, (momento, momento))

        assert catalog_date(archivo) == date.fromtimestamp(momento)

    def test_una_fecha_imposible_en_el_nombre_cae_al_archivo(self, tmp_path):
        import os

        archivo = _touch(tmp_path / "catalogo_2026-13-45.xlsx")
        momento = 1789000000
        os.utime(archivo, (momento, momento))

        assert catalog_date(archivo) == date.fromtimestamp(momento)


class TestDescribeAge:
    def test_el_mismo_dia_dice_hoy(self):
        texto, severidad = describe_age(date(2026, 9, 22), hoy=date(2026, 9, 22))

        assert texto == "del 22 de septiembre — hoy"
        assert severidad == "ok"

    def test_un_dia_antes_dice_ayer(self):
        texto, severidad = describe_age(date(2026, 9, 21), hoy=date(2026, 9, 22))

        assert texto == "del 21 de septiembre — ayer"
        assert severidad == "ok"

    def test_entre_dos_y_seis_dias_avisa(self):
        texto, severidad = describe_age(date(2026, 9, 19), hoy=date(2026, 9, 22))

        assert texto == "del 19 de septiembre — hace 3 días"
        assert severidad == "aviso"

    def test_una_semana_o_mas_se_marca_viejo(self):
        _, severidad = describe_age(date(2026, 9, 15), hoy=date(2026, 9, 22))

        assert severidad == "viejo"

    def test_una_fecha_futura_no_se_trata_como_vieja(self):
        """El reloj de la caja puede estar atrasado; no queremos 'hace -2 días'."""
        texto, severidad = describe_age(date(2026, 9, 24), hoy=date(2026, 9, 22))

        assert texto == "del 24 de septiembre — hoy"
        assert severidad == "ok"

    @pytest.mark.parametrize(
        "mes,nombre",
        [(1, "enero"), (3, "marzo"), (8, "agosto"), (12, "diciembre")],
    )
    def test_los_meses_van_en_espanol(self, mes, nombre):
        texto, _ = describe_age(date(2026, mes, 5), hoy=date(2026, mes, 5))

        assert texto == f"del 5 de {nombre} — hoy"


class TestDefaultSearchDirs:
    def test_incluye_descargas_en_ingles_y_en_espanol(self, tmp_path):
        dirs = default_search_dirs(home=tmp_path)

        assert tmp_path / "Downloads" in dirs
        assert tmp_path / "Descargas" in dirs

    def test_la_ultima_carpeta_usada_va_primero(self, tmp_path):
        """Si el dueño guarda los catálogos en otro lado, ahí hay que mirar antes."""
        otra = tmp_path / "Catalogos"

        dirs = default_search_dirs(home=tmp_path, last_used=otra)

        assert dirs[0] == otra

    def test_no_repite_la_ultima_carpeta_si_ya_estaba(self, tmp_path):
        descargas = tmp_path / "Downloads"

        dirs = default_search_dirs(home=tmp_path, last_used=descargas)

        assert dirs.count(descargas) == 1
