import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import json
from pathlib import Path

import epis_multi
import Extractor
import Logo
import epis
import egresos


# ==========================================================
# SETTINGS STORAGE
# ==========================================================

CONFIG_FILE = Path("settings.json")


def load_settings():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_settings(settings_dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings_dict, f, indent=2, ensure_ascii=False)


settings = load_settings()


def set_entry(entry, key, path):
    entry.delete(0, tk.END)
    entry.insert(0, path)
    settings[key] = path
    save_settings(settings)


# ==========================================================
# PROJECT HELPERS (AUTO-DETECT + VALIDATION)
# ==========================================================

def find_project_root(start_path: str) -> Path:
    """
    Users sometimes select a parent folder. We try to locate a folder that contains:
    historias/, templates/, fotos/
    If not found, return the start path as-is.
    """
    if not start_path:
        return Path(".")

    start = Path(start_path)
    if not start.exists():
        return start

    candidates = [start]
    try:
        candidates += [p for p in start.glob("**/*") if p.is_dir()]
    except Exception:
        # In case of permission issues on huge directories
        return start

    for folder in candidates:
        if (folder / "historias").exists() and (folder / "templates").exists() and (folder / "fotos").exists():
            return folder

    return start


def validate_project_structure(project_root: Path) -> list[str]:
    """
    Returns a list of missing folder labels. Non-blocking; GUI decides whether to continue.
    """
    checks = [
        ("Historias NNAJ", project_root / "historias" / "NNAJ"),
        ("Historias Programas", project_root / "historias" / "programas"),
        ("Fotos Programas", project_root / "fotos" / "programas"),
        ("Templates", project_root / "templates"),
        ("Data", project_root / "data"),
    ]

    missing = [label for label, p in checks if not p.exists()]
    return missing


# ==========================================================
# MAIN WINDOW
# ==========================================================

root = tk.Tk()
root.title("Herramientas Padrinazgo")
root.geometry("950x700")
root.configure(bg="#f4f6f9")

style = ttk.Style()
style.theme_use("clam")

style.configure(".", font=("Segoe UI", 10))
style.configure("TFrame", background="#f4f6f9")
style.configure("TLabel", background="#f4f6f9")
style.configure("TButton", padding=6, relief="flat")

style.map("TButton", background=[("active", "#d9e1f2")])


# ==========================================================
# SIDEBAR
# ==========================================================

sidebar = tk.Frame(root, bg="#1f3b73", width=220)
sidebar.pack(side="left", fill="y")

content_container = ttk.Frame(root)
content_container.pack(side="right", expand=True, fill="both")


# ==========================================================
# SCROLLABLE CONTENT
# ==========================================================

canvas = tk.Canvas(content_container, highlightthickness=0)
scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=canvas.yview)

canvas.configure(yscrollcommand=scrollbar.set)

scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", expand=True, fill="both")

content_frame = ttk.Frame(canvas)
canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="n")


def resize_content(event):
    canvas.itemconfig(canvas_window, width=event.width)


def update_scrollregion(event=None):
    canvas.configure(scrollregion=canvas.bbox("all"))


canvas.bind("<Configure>", resize_content)
content_frame.bind("<Configure>", update_scrollregion)


def clear_frame():
    for widget in content_frame.winfo_children():
        widget.destroy()
    canvas.yview_moveto(0)


# ==========================================================
# SIDEBAR BUTTON
# ==========================================================

def sidebar_button(text, command):
    return tk.Button(
        sidebar,
        text=text,
        command=command,
        bg="#1f3b73",
        fg="white",
        relief="flat",
        anchor="w",
        padx=25,
        pady=12,
        font=("Segoe UI", 11),
        activebackground="#2d5bb7",
        activeforeground="white"
    )


# ==========================================================
# FILE HELPERS
# ==========================================================

def browse_excel(entry, key):
    path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
    if path:
        set_entry(entry, key, path)


def browse_folder(entry, key):
    path = filedialog.askdirectory()
    if path:
        set_entry(entry, key, path)


def browse_logo(entry, key):
    path = filedialog.askopenfilename(filetypes=[("PNG files", "*.png")])
    if path:
        set_entry(entry, key, path)


# ==========================================================
# PDF TOOL
# ==========================================================

def show_pdf_tool():
    clear_frame()

    card = ttk.Frame(content_frame, padding=25)
    card.pack(pady=25)

    ttk.Label(card, text="Extractor de Cartas PDF",
              font=("Segoe UI", 16, "bold")).pack(pady=10)

    def add_field(label_text, key=None, browse_command=None):
        ttk.Label(card, text=label_text).pack()
        entry = ttk.Entry(card, width=60)
        entry.pack(pady=4)

        if key and key in settings:
            entry.insert(0, settings[key])

        if browse_command:
            ttk.Button(card, text="Buscar",
                       command=lambda: browse_command(entry, key)).pack(pady=4)

        return entry

    excel_entry = add_field("Archivo Excel:", "pdf_excel", browse_excel)
    pdf_entry = add_field("Carpeta de PDFs:", "pdf_folder", browse_folder)
    output_entry = add_field("Carpeta de salida:", "pdf_output", browse_folder)
    sheet_entry = add_field("Nombre de la hoja:")
    column_entry = add_field("Nombre de la columna:")

    ttk.Button(
        card,
        text="▶ Ejecutar extracción",
        width=35,
        command=lambda: run_pdf_tool(
            excel_entry.get(),
            pdf_entry.get(),
            output_entry.get(),
            sheet_entry.get(),
            column_entry.get()
        )
    ).pack(pady=20)


def run_pdf_tool(excel, pdf_folder, output, sheet, column):
    try:
        summary = Extractor.extraer_cartas(
            excel_file=excel,
            pdf_folder=pdf_folder,
            output_folder=output,
            sheet_name=sheet,
            column_name=column
        )

        messagebox.showinfo(
            "Proceso finalizado",
            f"Coincidencias: {summary.total_matches}\n"
            f"No encontrados: {len(summary.unmatched_names)}\n\n"
            f"Log:\n{summary.log_file}"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


# ==========================================================
# LOGO TOOL
# ==========================================================

def show_logo_tool():
    clear_frame()

    card = ttk.Frame(content_frame, padding=25)
    card.pack(pady=25)

    ttk.Label(card, text="Aplicar Logo a Imágenes",
              font=("Segoe UI", 16, "bold")).pack(pady=10)

    def add_field(label_text, key=None, browse_command=None):
        ttk.Label(card, text=label_text).pack()
        entry = ttk.Entry(card, width=60)
        entry.pack(pady=4)

        if key and key in settings:
            entry.insert(0, settings[key])

        if browse_command:
            ttk.Button(card, text="Buscar",
                       command=lambda: browse_command(entry, key)).pack(pady=4)

        return entry

    folder_entry = add_field("Carpeta de imágenes:", "logo_folder", browse_folder)
    logo_entry = add_field("Archivo logo:", "logo_file", browse_logo)

    overwrite_var = tk.BooleanVar()

    ttk.Checkbutton(card, text="Sobrescribir originales",
                    variable=overwrite_var).pack(pady=10)

    ttk.Button(
        card,
        text="▶ Aplicar logo",
        width=35,
        command=lambda: run_logo_tool(
            folder_entry.get(),
            logo_entry.get(),
            overwrite_var.get()
        )
    ).pack(pady=20)


def run_logo_tool(folder, logo, overwrite):
    try:
        summary = Logo.add_logo_to_folder(
            input_folder=folder,
            logo_path=logo,
            overwrite=overwrite
        )

        messagebox.showinfo(
            "Proceso finalizado",
            f"Procesadas: {summary['processed']}\n"
            f"Omitidas: {summary['skipped']}\n\n"
            f"Salida:\n{summary['output_folder']}"
        )

    except Exception as e:
        messagebox.showerror("Error", str(e))


# ==========================================================
# EGRESOS TOOL (GUI)
# ==========================================================

def show_egresos_tool():

    clear_frame()

    card = ttk.Frame(content_frame, padding=20)
    card.pack(pady=10)

    ttk.Label(
        card,
        text="Generador de Cartas de Egreso",
        font=("Segoe UI", 14, "bold")
    ).pack(pady=10)

    column_vars = {}

    def create_selector(key, label):
        ttk.Label(card, text=label).pack()
        var = tk.StringVar()
        combo = ttk.Combobox(card, textvariable=var, width=57)
        combo.pack(pady=3)
        column_vars[key] = combo

    def cargar_columnas_excel(path):
        try:
            import pandas as pd
            df = pd.read_excel(path)
            cols = df.columns.tolist()
            for combo in column_vars.values():
                combo["values"] = cols
        except Exception as e:
            messagebox.showerror("Error al leer Excel", str(e))

    ttk.Label(card, text="Archivo Excel").pack()
    excel_entry = ttk.Entry(card, width=60)
    excel_entry.pack(pady=3)

    def seleccionar_excel():
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if path:
            excel_entry.delete(0, tk.END)
            excel_entry.insert(0, path)
            cargar_columnas_excel(path)

    ttk.Button(card, text="Buscar", command=seleccionar_excel).pack(pady=5)

    ttk.Label(card, text="Columnas del Excel").pack(pady=(15, 5))

    create_selector("primer_nombre_anterior", "Primer nombre del niño anterior")
    create_selector("nuevo_nino", "Nuevo niño asignado")
    create_selector("programa", "Programa / Aldea")
    create_selector("nombre_padrino", "Nombre completo del padrino")
    create_selector("primer_nombre_padrino", "Primer nombre del padrino")
    create_selector("direccion", "Dirección")
    create_selector("ciudad", "Ciudad")
    create_selector("departamento", "Departamento")
    create_selector("tratamiento", "Tratamiento")

    def run_egresos():
        try:
            mapa = {k: v.get() for k, v in column_vars.items()}
            summary = egresos.generar_cartas(excel_entry.get(), mapa)

            messagebox.showinfo(
                "Proceso finalizado",
                f"Cartas generadas: {summary['total_generadas']}\n"
                f"Errores: {len(summary.get('errores', []))}\n\n"
                f"Salida:\n{summary.get('output_dir', '')}"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    ttk.Button(
        card,
        text="▶ Generar Cartas de Egreso",
        width=35,
        command=run_egresos
    ).pack(pady=20)


# ==========================================================
# CARTAS MULTI DONANTE (GUI)
# ==========================================================

def show_cartas_multi_tool():

    clear_frame()

    card = ttk.Frame(content_frame, padding=20)
    card.pack(pady=10)

    ttk.Label(
        card,
        text="Generador de Cartas Múltiples",
        font=("Segoe UI", 14, "bold")
    ).pack(pady=10)

    mode_var = tk.StringVar(value="auto")

    ttk.Label(card, text="Modo de configuración").pack(pady=(10, 5))

    # ---- Project folder
    ttk.Label(card, text="Carpeta del proyecto Epistolegraphos").pack()
    project_entry = ttk.Entry(card, width=60)
    project_entry.pack(pady=3)

    def browse_project():
        path = filedialog.askdirectory()
        if path:
            project_entry.delete(0, tk.END)
            project_entry.insert(0, path)

    project_button = ttk.Button(card, text="Buscar", command=browse_project)
    project_button.pack(pady=5)

    # ---- Excel
    ttk.Label(card, text="Archivo Excel multi-donante").pack(pady=(15, 0))
    excel_entry = ttk.Entry(card, width=60)
    excel_entry.pack(pady=3)

    def browse_excel_local():
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if path:
            excel_entry.delete(0, tk.END)
            excel_entry.insert(0, path)

    ttk.Button(card, text="Buscar", command=browse_excel_local).pack(pady=5)

    # ---- Manual folders (hidden unless manual)
    manual_frame = ttk.Frame(card)

    def add_manual_field(label):
        ttk.Label(manual_frame, text=label).pack()
        entry = ttk.Entry(manual_frame, width=60)
        entry.pack(pady=3)

        def browse():
            path = filedialog.askdirectory()
            if path:
                entry.delete(0, tk.END)
                entry.insert(0, path)

        ttk.Button(manual_frame, text="Buscar", command=browse).pack(pady=3)
        return entry

    historias_nnaj = add_manual_field("Historias NNAJ")
    historias_prog = add_manual_field("Historias Programas")
    fotos_prog = add_manual_field("Fotos Programas")
    templates = add_manual_field("Templates")
    output = add_manual_field("Carpeta de salida")

    def toggle_mode():
        if mode_var.get() == "manual":
            manual_frame.pack(pady=10)
            project_entry.configure(state="disabled")
            project_button.configure(state="disabled")
        else:
            manual_frame.pack_forget()
            project_entry.configure(state="normal")
            project_button.configure(state="normal")

    ttk.Radiobutton(
        card,
        text="Automático (usar carpeta del proyecto)",
        variable=mode_var,
        value="auto",
        command=toggle_mode
    ).pack(anchor="w")

    ttk.Radiobutton(
        card,
        text="Manual (seleccionar carpetas)",
        variable=mode_var,
        value="manual",
        command=toggle_mode
    ).pack(anchor="w")

    toggle_mode()

    # ---- Progress
    ttk.Label(card, text="Progreso").pack(pady=10)
    progress = ttk.Progressbar(card, length=400)
    progress.pack()
    progress_label = ttk.Label(card, text="")
    progress_label.pack()

    def update_progress(current, total):
        try:
            percent = int((current / total) * 100) if total else 0
        except Exception:
            percent = 0
        progress["value"] = percent
        progress_label.config(text=f"{current} / {total} donantes")
        root.update_idletasks()

    # ---- Run
    def run_generator():

        def task():
            try:
                if mode_var.get() == "auto":
                    project_root = find_project_root(project_entry.get())
                    missing = validate_project_structure(project_root)
                    if missing:
                        msg = (
                            "⚠ Algunas carpetas del proyecto no se encontraron:\n\n"
                            + "\n".join(missing)
                            + "\n\n¿Continuar de todas formas?"
                        )
                        if not messagebox.askyesno("Advertencia", msg):
                            return

                    summary = epis_multi.generar_cartas_multi(
                        project_root=str(project_root),
                        excel_path=excel_entry.get(),
                        progress_callback=update_progress
                    )
                else:
                    manual_paths = {
                        "CHILD_STORIES_PATH": historias_nnaj.get(),
                        "PROGRAM_STORIES_PATH": historias_prog.get(),
                        "PROGRAM_PHOTOS_PATH": fotos_prog.get(),
                        "TEMPLATES_PATH": templates.get(),
                        "OUTPUT_BASE_PATH": output.get()
                    }

                    summary = epis_multi.generar_cartas_multi(
                        project_root=None,
                        excel_path=excel_entry.get(),
                        manual_paths=manual_paths,
                        progress_callback=update_progress
                    )

                root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Proceso finalizado",
                        f"Cartas generadas: {summary.get('total_generadas', '')}\n\n"
                        f"Salida:\n{summary.get('output_folder', '')}"
                    )
                )
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=task, daemon=True).start()

    ttk.Button(
        card,
        text="▶ Generar Cartas",
        width=35,
        command=run_generator
    ).pack(pady=20)


# ==========================================================
# LETTER GENERATOR (GUI)
# ==========================================================

def show_letter_tool():

    clear_frame()

    card = ttk.Frame(content_frame, padding=25)
    card.pack(pady=25)

    ttk.Label(
        card,
        text="Generador de Cartas",
        font=("Segoe UI", 16, "bold")
    ).pack(pady=10)

    mode_var = tk.StringVar(value="auto")

    ttk.Label(card, text="Modo de configuración").pack(pady=(10, 5))

    ttk.Label(card, text="Carpeta proyecto Epistolegraphos:").pack()
    project_entry = ttk.Entry(card, width=60)
    project_entry.pack(pady=4)

    def browse_project():
        path = filedialog.askdirectory()
        if path:
            project_entry.delete(0, tk.END)
            project_entry.insert(0, path)

    project_button = ttk.Button(card, text="Buscar", command=browse_project)
    project_button.pack(pady=4)

    ttk.Label(card, text="Archivo Excel:").pack()
    excel_entry = ttk.Entry(card, width=60)
    excel_entry.pack(pady=4)

    def browse_excel_local():
        path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if path:
            excel_entry.delete(0, tk.END)
            excel_entry.insert(0, path)

    ttk.Button(card, text="Buscar", command=browse_excel_local).pack(pady=4)

    manual_frame = ttk.Frame(card)

    def add_manual_field(label):
        ttk.Label(manual_frame, text=label).pack()
        entry = ttk.Entry(manual_frame, width=60)
        entry.pack(pady=3)

        def browse():
            path = filedialog.askdirectory()
            if path:
                entry.delete(0, tk.END)
                entry.insert(0, path)

        ttk.Button(manual_frame, text="Buscar", command=browse).pack(pady=3)
        return entry

    historias_nnaj = add_manual_field("Historias NNAJ")
    historias_prog = add_manual_field("Historias Programas")
    fotos_prog = add_manual_field("Fotos Programas")
    templates = add_manual_field("Templates")
    output = add_manual_field("Carpeta de salida")

    def toggle_mode():
        if mode_var.get() == "manual":
            manual_frame.pack(pady=10)
            project_entry.configure(state="disabled")
            project_button.configure(state="disabled")
        else:
            manual_frame.pack_forget()
            project_entry.configure(state="normal")
            project_button.configure(state="normal")

    ttk.Radiobutton(
        card,
        text="Automático (usar carpeta del proyecto)",
        variable=mode_var,
        value="auto",
        command=toggle_mode
    ).pack(anchor="w")

    ttk.Radiobutton(
        card,
        text="Manual (seleccionar carpetas)",
        variable=mode_var,
        value="manual",
        command=toggle_mode
    ).pack(anchor="w")

    toggle_mode()

    ttk.Label(card, text="Progreso").pack(pady=10)
    progress = ttk.Progressbar(card, length=400)
    progress.pack()
    progress_label = ttk.Label(card, text="")
    progress_label.pack()

    def update_progress(current, total):
        try:
            percent = int((current / total) * 100) if total else 0
        except Exception:
            percent = 0
        progress["value"] = percent
        progress_label.config(text=f"{current} / {total} cartas generadas")
        root.update_idletasks()

    def run_generator():

        def task():
            try:
                if mode_var.get() == "auto":
                    project_root = find_project_root(project_entry.get())
                    missing = validate_project_structure(project_root)
                    if missing:
                        msg = (
                            "⚠ Algunas carpetas del proyecto no se encontraron:\n\n"
                            + "\n".join(missing)
                            + "\n\n¿Continuar de todas formas?"
                        )
                        if not messagebox.askyesno("Advertencia", msg):
                            return

                    epis.run_from_gui(
                        str(project_root),
                        excel_entry.get(),
                        progress_callback=update_progress
                    )
                else:
                    manual_paths = {
                        "CHILD_STORIES_PATH": historias_nnaj.get(),
                        "PROGRAM_STORIES_PATH": historias_prog.get(),
                        "PROGRAM_PHOTOS_PATH": fotos_prog.get(),
                        "TEMPLATES_PATH": templates.get(),
                        "OUTPUT_BASE_PATH": output.get()
                    }

                    epis.run_from_gui(
                        project_root=None,
                        excel_path=excel_entry.get(),
                        manual_paths=manual_paths,
                        progress_callback=update_progress
                    )

                root.after(
                    0,
                    lambda: messagebox.showinfo("Proceso finalizado", "Cartas generadas correctamente")
                )
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=task, daemon=True).start()

    ttk.Button(
        card,
        text="▶ Generar Cartas",
        width=35,
        command=run_generator
    ).pack(pady=20)


# ==========================================================
# SIDEBAR BUTTONS
# ==========================================================

sidebar_button("Extractor PDF", show_pdf_tool).pack(fill="x")
sidebar_button("Aplicar Logo", show_logo_tool).pack(fill="x")
sidebar_button("Cartas de Egreso", show_egresos_tool).pack(fill="x")
sidebar_button("Generador de Cartas", show_letter_tool).pack(fill="x")
sidebar_button("Cartas Multi Donante", show_cartas_multi_tool).pack(fill="x")


# ==========================================================
# START SCREEN
# ==========================================================

show_pdf_tool()
root.mainloop()