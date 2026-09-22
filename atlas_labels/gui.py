"""Interfaz de escritorio: abre un catálogo, filtra, ajusta copias por fila e imprime en lote."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .batch import plan_items
from .catalog import CatalogError, read_catalog, select, sheet_names
from .printer import PrinterError, list_printers, send_raw
from .render import draw
from .settings import load_settings, resolve_printer, save_settings
from .zpl import LABEL_HEIGHT, LABEL_WIDTH, build_batch, build_label, layout

COLUMNS = ("SKU", "Código", "Marca", "Nombre", "Departamento", "Talla", "Color", "Precio", "Stock", "Etiquetas")
COLUMN_WIDTHS = {
    "SKU": 130, "Código": 120, "Marca": 120, "Nombre": 220, "Departamento": 100,
    "Talla": 50, "Color": 80, "Precio": 90, "Stock": 50, "Etiquetas": 70,
}
ALL = "Todos"
GENDER_LABELS = {"Hombre / sin especificar": "Hombre", "Mujer": "Mujer"}
PREVIEW_PAD = 10


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Atlas Labels")
        self.geometry("1400x800")
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self.products = []
        self.visible = []
        self.copies: dict[int, int] = {}  # id(producto) → etiquetas a imprimir; sobrevive a los filtros
        self._editor: ttk.Entry | None = None
        self._build_ui()

    # --- construcción -------------------------------------------------------

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Button(top, text="Abrir catálogo", command=self.open_catalog).pack(side="left")
        ttk.Label(top, text=" Impresora:").pack(side="left")
        self.printer_var = tk.StringVar(value=resolve_printer() or "")
        try:
            printers = list_printers()
        except PrinterError:
            printers = []
        ttk.Combobox(top, width=30, textvariable=self.printer_var, values=printers).pack(side="left", padx=4)
        ttk.Button(top, text="Imprimir seleccionados", command=self.print_selected).pack(side="right")

        filters = ttk.Frame(self, padding=(10, 0, 10, 6))
        filters.pack(fill="x")
        ttk.Label(filters, text="Departamento:").pack(side="left")
        self.department_var = tk.StringVar(value=ALL)
        self.department_box = ttk.Combobox(
            filters, width=22, textvariable=self.department_var, values=(ALL,), state="readonly"
        )
        self.department_box.pack(side="left", padx=4)
        ttk.Label(filters, text=" Género:").pack(side="left")
        self.gender_var = tk.StringVar(value=ALL)
        ttk.Combobox(
            filters, width=24, textvariable=self.gender_var, values=(ALL, *GENDER_LABELS), state="readonly"
        ).pack(side="left", padx=4)
        ttk.Label(filters, text=" Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(filters, width=28, textvariable=self.search_var).pack(side="left", padx=4)
        for var in (self.department_var, self.gender_var, self.search_var):
            var.trace_add("write", lambda *_: self.apply_filter())

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10)

        left = ttk.Frame(body)
        body.add(left, weight=1)
        self.tree = ttk.Treeview(left, columns=COLUMNS, show="headings", selectmode="extended")
        for col in COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=COLUMN_WIDTHS[col], anchor="w")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.update_preview())
        self.tree.bind("<Double-1>", self.edit_copies)

        right = ttk.Frame(body)
        body.add(right, weight=1)
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.tabs, background="#e6e6e6", highlightthickness=0)
        self.canvas.bind("<Configure>", lambda _e: self.update_preview())
        self.tabs.add(self.canvas, text="Etiqueta")
        self.zpl_text = tk.Text(self.tabs, width=60, height=20)
        self.tabs.add(self.zpl_text, text="ZPL")

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Usar existencia", command=self.use_stock).pack(side="left")
        ttk.Label(bottom, text="   Poner").pack(side="left")
        self.copies_var = tk.StringVar(value="1")
        ttk.Spinbox(bottom, from_=0, to=999, width=6, textvariable=self.copies_var).pack(side="left", padx=4)
        ttk.Button(bottom, text="a seleccionados", command=self.set_copies_selected).pack(side="left")
        ttk.Label(bottom, text="   Doble clic en la columna Etiquetas para editar una fila.").pack(side="left")

        self.status = tk.StringVar(value="Abre un catálogo .xlsx o .csv para empezar.")
        ttk.Label(self, textvariable=self.status, padding=(10, 0, 10, 6)).pack(fill="x")

        self.after(50, self.update_preview)

    # --- catálogo y filtros -------------------------------------------------

    def open_catalog(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Catálogo", "*.xlsx *.xlsm *.csv"),
                ("Excel", "*.xlsx *.xlsm"),
                ("CSV", "*.csv"),
            ]
        )
        if not path:
            return
        try:
            sheet = None
            if path.lower().endswith((".xlsx", ".xlsm")):
                names = sheet_names(path)
                if len(names) > 1:
                    sheet = simpledialog.askstring(
                        "Hoja", f"Hojas disponibles: {', '.join(names)}\nEscribe el nombre de la hoja:",
                        initialvalue=names[0], parent=self,
                    )
                    if sheet is None:
                        return
            self.products = read_catalog(path, sheet)
        except CatalogError as exc:
            messagebox.showerror("No se pudo leer el catálogo", str(exc))
            return
        except Exception as exc:  # cualquier otro fallo de lectura no debe tumbar la app
            messagebox.showerror("Error inesperado al leer el catálogo", f"{type(exc).__name__}: {exc}")
            return
        self.copies = {id(p): p.stock for p in self.products}
        departments = sorted({p.department.strip() for p in self.products if p.department.strip()})
        self.department_box["values"] = (ALL, *departments)
        self.department_var.set(ALL)
        self.gender_var.set(ALL)
        self.search_var.set("")
        self.apply_filter()
        self.status.set(f"{len(self.products)} productos cargados de {path}")

    def _filters(self) -> dict:
        department = self.department_var.get()
        gender = GENDER_LABELS.get(self.gender_var.get())
        return {
            "department": None if department == ALL else department,
            "gender": gender,
            "search": self.search_var.get(),
        }

    def apply_filter(self):
        self._close_editor()
        self.visible = select(self.products, **self._filters())
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, p in enumerate(self.visible):
            self.tree.insert("", "end", iid=str(idx), values=self._row(p))
        self.update_preview()

    def _row(self, p) -> tuple:
        return (
            p.sku, p.barcode, p.brand, p.name, p.department, p.size, p.color,
            p.price_display, p.stock, self.copies_for(p),
        )

    def copies_for(self, p) -> int:
        return self.copies.get(id(p), p.stock)

    def selected_products(self):
        return [self.visible[int(i)] for i in self.tree.selection()]

    # --- copias por fila ----------------------------------------------------

    def set_copies(self, products, value: int):
        for p in products:
            self.copies[id(p)] = max(0, int(value))
        ids = {id(p) for p in products}
        for idx, p in enumerate(self.visible):
            if id(p) in ids:
                self.tree.item(str(idx), values=self._row(p))
        self.update_preview()

    def use_stock(self):
        targets = self.selected_products() or self.visible
        for p in targets:
            self.copies[id(p)] = p.stock
        ids = {id(p) for p in targets}
        for idx, p in enumerate(self.visible):
            if id(p) in ids:
                self.tree.item(str(idx), values=self._row(p))
        self.update_preview()

    def set_copies_selected(self):
        sel = self.selected_products()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona una o más filas de la tabla.")
            return
        try:
            value = max(0, int(self.copies_var.get().strip()))
        except ValueError:
            messagebox.showwarning("Copias inválidas", "Escribe un número entero de 0 o más.")
            return
        self.set_copies(sel, value)

    def edit_copies(self, event):
        self._close_editor()
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        column = self.tree.identify_column(event.x)
        iid = self.tree.identify_row(event.y)
        if not iid or column != f"#{len(COLUMNS)}":
            return
        bbox = self.tree.bbox(iid, column)
        if not bbox:
            return
        x, y, w, h = bbox
        product = self.visible[int(iid)]
        var = tk.StringVar(value=str(self.copies_for(product)))
        entry = ttk.Entry(self.tree, textvariable=var, width=6)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        entry.select_range(0, "end")

        def commit(_event=None):
            if self._editor is not entry:
                return
            raw = var.get().strip()
            self._close_editor()
            try:
                self.set_copies([product], int(raw))
            except ValueError:
                pass  # texto no numérico: se conserva el valor anterior

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", lambda _e: self._close_editor())
        self._editor = entry

    def _close_editor(self):
        editor, self._editor = self._editor, None
        if editor is not None:
            editor.destroy()

    # --- vista previa -------------------------------------------------------

    def _preview_scale(self) -> float:
        w = max(1, self.canvas.winfo_width() - 2 * PREVIEW_PAD)
        h = max(1, self.canvas.winfo_height() - 2 * PREVIEW_PAD)
        return max(0.25, min(w / LABEL_WIDTH, h / LABEL_HEIGHT))

    def update_preview(self):
        self.canvas.delete("all")
        self.zpl_text.delete("1.0", "end")
        scale = self._preview_scale()
        sel = self.selected_products()
        if not sel:
            self._preview_message("Selecciona un producto para ver su etiqueta.", scale)
            return
        product = sel[0]
        try:
            elements = layout(product)
        except ValueError as exc:
            self._preview_message(f"No imprimible: {exc}", scale)
            return
        draw(self.canvas, elements, scale, (PREVIEW_PAD, PREVIEW_PAD))
        self.zpl_text.insert("1.0", build_label(product, max(1, self.copies_for(product))))

    def _preview_message(self, text: str, scale: float):
        self.canvas.create_text(
            PREVIEW_PAD + LABEL_WIDTH * scale / 2,
            PREVIEW_PAD + LABEL_HEIGHT * scale / 2,
            text=text, fill="#777777", font=("Helvetica", 12),
        )

    # --- impresión ----------------------------------------------------------

    def print_selected(self):
        sel = self.selected_products()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona una o más filas de la tabla.")
            return
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Sin impresora", "Elige o escribe el nombre de la impresora.")
            return
        batch = plan_items([(p, self.copies_for(p)) for p in sel])
        if not batch.items:
            messagebox.showwarning("Nada que imprimir", batch.summary())
            return
        if not messagebox.askokcancel("Confirmar impresión", f"{batch.summary()}\n\nImpresora: {printer}"):
            return
        try:
            send_raw(printer, build_batch(batch.items).encode("utf-8"))
        except PrinterError as exc:
            messagebox.showerror("Error de impresión", str(exc))
            return
        except Exception as exc:  # cualquier otro fallo de impresión no debe tumbar la app
            messagebox.showerror("Error inesperado al imprimir", f"{type(exc).__name__}: {exc}")
            return
        try:
            save_settings({**load_settings(), "printer_name": printer})
        except OSError:
            pass  # recordar la impresora es opcional
        msg = f"Enviadas {batch.total_labels} etiquetas de {len(batch.items)} productos a {printer}."
        self.status.set(msg)
        messagebox.showinfo("Enviado", msg)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
