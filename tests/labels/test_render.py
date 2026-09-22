from atlas_labels.render import draw
from atlas_labels.zpl import LABEL_HEIGHT, LABEL_WIDTH, Bars, Text


class FakeCanvas:
    def __init__(self):
        self.rects = []
        self.texts = []

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        self.rects.append((x1, y1, x2, y2, kw))

    def create_text(self, x, y, **kw):
        self.texts.append((x, y, kw))


def test_draw_fondo_a_escala_con_offset():
    c = FakeCanvas()
    draw(c, [], scale=2, offset=(10, 10))
    assert c.rects[0][:4] == (10, 10, 10 + LABEL_WIDTH * 2, 10 + LABEL_HEIGHT * 2)
    assert c.rects[0][4]["fill"] == "white"


def test_draw_texto_izquierda_y_derecha():
    c = FakeCanvas()
    draw(c, [Text(12, 8, 22, "Marca"), Text(246, 162, 22, "$1,800.00", 150, "R")], scale=2)
    left, right = c.texts
    assert (left[0], left[1], left[2]["anchor"], left[2]["text"]) == (24, 16, "nw", "Marca")
    assert (right[0], right[1], right[2]["anchor"]) == ((246 + 150) * 2, 324, "ne")
    assert left[2]["font"] == ("Helvetica", -35)  # int(22 * 2 * 0.8)


def test_draw_barras_por_corridas_y_linea_legible():
    c = FakeCanvas()
    bars = Bars(100, 76, 48, "1101", 2, "1234", "CODE128", "1234")
    draw(c, [bars], scale=2)
    black = [r for r in c.rects if r[4].get("fill") == "black"]
    # corridas "11" (módulos 0-1) y "1" (módulo 3); unit = 2*2 = 4 px
    assert [(r[0], r[2]) for r in black] == [(200, 208), (212, 216)]
    assert all((r[1], r[3]) == (152, 152 + 96) for r in black)
    label = c.texts[-1]
    assert label[2]["text"] == "1234" and label[2]["anchor"] == "n"
    assert label[0] == 200 + 4 * 4 / 2 and label[1] == 152 + 96 + 4
