"""Dibuja los elementos de layout() en un canvas de Tk (o cualquier objeto compatible)."""

from __future__ import annotations

from .zpl import LABEL_HEIGHT, LABEL_WIDTH, Bars, Text

TEXT_FONT_FACTOR = 0.8  # altura ZPL → píxeles de fuente Tk, aproximado
INTERPRETATION_HEIGHT = 11


def draw(canvas, elements: list[Text | Bars], scale: float = 2.0, offset: tuple[int, int] = (0, 0)) -> None:
    ox, oy = offset
    canvas.create_rectangle(
        ox, oy, ox + LABEL_WIDTH * scale, oy + LABEL_HEIGHT * scale, fill="white", outline="#999999"
    )
    for el in elements:
        if isinstance(el, Bars):
            _draw_bars(canvas, el, scale, ox, oy)
        else:
            _draw_text(canvas, el, scale, ox, oy)


def _font(height: float, scale: float) -> tuple[str, int]:
    return ("Helvetica", -max(6, int(height * scale * TEXT_FONT_FACTOR)))


def _draw_text(canvas, el: Text, scale: float, ox: float, oy: float) -> None:
    font = _font(el.height, scale)
    if el.width is not None and el.align == "R":
        canvas.create_text((ox + (el.x + el.width) * scale), oy + el.y * scale, text=el.text, anchor="ne", font=font)
    else:
        canvas.create_text(ox + el.x * scale, oy + el.y * scale, text=el.text, anchor="nw", font=font)


def _draw_bars(canvas, el: Bars, scale: float, ox: float, oy: float) -> None:
    x0 = ox + el.x * scale
    top = oy + el.y * scale
    bottom = top + el.height * scale
    unit = el.module_width * scale
    i = 0
    while i < len(el.bits):
        if el.bits[i] != "1":
            i += 1
            continue
        j = i
        while j < len(el.bits) and el.bits[j] == "1":
            j += 1
        canvas.create_rectangle(x0 + i * unit, top, x0 + j * unit, bottom, fill="black", outline="")
        i = j
    center = x0 + len(el.bits) * unit / 2
    canvas.create_text(center, bottom + 2 * scale, text=el.interpretation, anchor="n", font=_font(INTERPRETATION_HEIGHT, scale))
