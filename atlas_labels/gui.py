# atlas_labels/gui.py
"""Interfaz de escritorio: abre un catálogo, elige productos e imprime en lote."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .batch import plan
from .catalog import CatalogError, read_catalog, select, sheet_names
from .printer import PrinterError, list_printers, send_raw
from .settings import load_settings, resolve_printer, save_settings
from .zpl import build_batch, build_label

COLUMNS = ("SKU", "Código", "Marca", "Nombre", "Talla", "Color", "Precio", "Stock")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Atlas Labels")
        self.geometry("1200x700")
        self.products = []
        self.visible = []
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
        ttk.Combobox(top, width=34, textvariable=self.printer_var, values=printers).pack(side="left", padx=4)

        ttk.Label(top, text=" Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        ttk.Entry(top, width=28, textvariable=self.search_var).pack(side="left", padx=4)
        ttk.Button(top, text="Imprimir seleccionados", command=self.print_selected).pack(side="right")

        self.tree = ttk.Treeview(self, columns=COLUMNS, show="headings", selectmode="extended")
        for col in COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110, anchor="w")
        self.tree.column("Nombre", width=260)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.update_preview())

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        self.copies_mode = tk.StringVar(value="stock")
        ttk.Radiobutton(bottom, text="Copias = existencia", variable=self.copies_mode, value="stock").pack(side="left")
        ttk.Radiobutton(bottom, text="Copias fijas:", variable=self.copies_mode, value="fixed").pack(side="left", padx=(10, 2))
        self.copies_var = tk.StringVar(value="1")
        ttk.Spinbox(bottom, from_=1, to=999, width=6, textvariable=self.copies_var).pack(side="left")
        ttk.Label(bottom, text="  Vista previa ZPL:").pack(side="left", padx=(20, 4))
        self.preview = tk.Text(bottom, height=8, width=70)
        self.preview.pack(side="left", fill="x", expand=True)

        self.status = tk.StringVar(value="Abre un catálogo .xlsx o .csv para empezar.")
        ttk.Label(self, textvariable=self.status, padding=(10, 0, 10, 6)).pack(fill="x")

    # --- acciones -----------------------------------------------------------

    def open_catalog(self):
        path = filedialog.askopenfilename(
            filetypes=[("Catálogo", "*.xlsx *.csv"), ("Excel", "*.xlsx"), ("CSV", "*.csv")]
        )
        if not path:
            return
        try:
            sheet = None
            if path.lower().endswith(".xlsx"):
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
        self.search_var.set("")
        self.apply_filter()
        self.status.set(f"{len(self.products)} productos cargados de {path}")

    def apply_filter(self):
        self.visible = select(self.products, search=self.search_var.get())
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, p in enumerate(self.visible):
            self.tree.insert("", "end", iid=str(idx), values=(
                p.sku, p.barcode, p.brand, p.name, p.size, p.color, p.price_display, p.stock,
            ))

    def selected_products(self):
        return [self.visible[int(i)] for i in self.tree.selection()]

    def copies_override(self) -> int | None:
        if self.copies_mode.get() == "stock":
            return None
        try:
            return max(1, int(self.copies_var.get()))
        except ValueError:
            return 1

    def update_preview(self):
        self.preview.delete("1.0", "end")
        sel = self.selected_products()
        if not sel:
            return
        product = sel[0]
        copies = self.copies_override() or max(1, product.stock)
        try:
            self.preview.insert("1.0", build_label(product, copies))
        except ValueError as exc:
            self.preview.insert("1.0", f"No imprimible: {exc}")

    def print_selected(self):
        sel = self.selected_products()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona una o más filas de la tabla.")
            return
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Sin impresora", "Elige o escribe el nombre de la impresora.")
            return
        batch = plan(sel, self.copies_override())
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
