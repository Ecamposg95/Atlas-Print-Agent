import openpyxl
import pytest


@pytest.fixture
def make_xlsx(tmp_path):
    """Crea un .xlsx con una o varias hojas: make_xlsx({"Hoja": [headers, row, ...]})."""

    def _make(sheets: dict, name: str = "catalogo.xlsx"):
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for title, rows in sheets.items():
            ws = wb.create_sheet(title)
            for row in rows:
                ws.append(row)
        path = tmp_path / name
        wb.save(path)
        return path

    return _make


ATLAS_HEADERS = ["SKU", "Nombre", "Descripcion", "Marca", "Codigo Barras", "Precio Base", "Stock", "Color", "Talla"]
