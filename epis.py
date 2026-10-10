import csv
import re
import shutil
import tempfile
from pypdf import PdfReader, PdfWriter
import unicodedata
import sys
import time
import os
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import markdown

# ─── PATHS ───────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data"
TEMPLATES_PATH = BASE_DIR / "templates"
OUTPUT_PDF_PATH = BASE_DIR / "Cartas_Listas" / "pdf"
OUTPUT_LOG_PATH = BASE_DIR / "Cartas_Listas" / "logs"
CHILD_STORIES_PATH = BASE_DIR / "historias" / "NNAJ"
PROGRAM_STORIES_PATH = BASE_DIR / "historias" / "programas"
CHILD_PHOTOS_PATH = BASE_DIR / "fotos" / "nnaj"
PROGRAM_PHOTOS_PATH = BASE_DIR / "fotos" / "programas"
PROGRAM_PDF_PATH = BASE_DIR / "historias" / "PDF programas"
TEMPLATE_FILE = "letter_template.html"
LOG_FILE = OUTPUT_LOG_PATH / "epistolegraphos_single_log.csv"

DATA_PATH_OVERRIDE = None
GUI_PROGRESS_CALLBACK = None
LETTER_MODE = "endyear"

# ─── UTILITIES ─────────────────────────────────────────────────────────────
def clean_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and pd.isna(val):
        return ""
    if isinstance(val, str) and val.strip().lower() == "nan":
        return ""
    return str(val).strip()

def read_text(path: Path) -> str:
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""

def normalize_simple(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^a-zA-Z0-9 _.-]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def slugify(text: str) -> str:
    return re.sub(r"_+", "_", normalize_simple(text).lower().replace(" ", "_")).strip("_")

def find_file(name: str, base_dir: Path, ext: str) -> Path | None:
    if not name or not base_dir.exists():
        return None
    name_norm = normalize_simple(name)
    for f in base_dir.rglob(f"*.{ext}"):
        if normalize_simple(f.stem) == name_norm:
            return f
    return None

def markdown_to_html(text: str) -> str:
    return markdown.markdown(text, extensions=["extra", "sane_lists"]) if text else ""

def render_text_with_context(text: str, context: dict, env: Environment) -> str:
    try:
        return env.from_string(text or "").render(**context)
    except Exception:
        return text or ""

def log_row(writer, **kw):
    writer.writerow({
        "sheet": kw.get("sheet", ""),
        "donor": kw.get("donor", ""),
        "child": kw.get("child", ""),
        "program": kw.get("program", ""),
        "status": kw.get("status", ""),
        "issues": kw.get("issues", ""),
        "output": kw.get("output", ""),
    })

def ensure_log_header(log_path: Path):
    header = ["sheet", "donor", "child", "program", "status", "issues", "output"]
    write_header = not log_path.exists()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    f = log_path.open("a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=header)
    if write_header:
        w.writeheader()
    return f, w

def safe_filename(name: str) -> str:
    return re.sub(r"_+", "_", normalize_simple(name).replace(" ", "_")).strip("_") or "unknown"

def deaccent_lower(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return s.lower()

def progress_bar(current, total, bar_length=40):
    if GUI_PROGRESS_CALLBACK:
        GUI_PROGRESS_CALLBACK(current, total)
        return

    percent = current / total if total else 0
    arrow = "=" * int(round(percent * bar_length)) + ">"
    spaces = " " * max(0, bar_length - len(arrow))
    sys.stdout.write(f"\rProgress: [{arrow}{spaces}] {int(percent * 100)}%")
    sys.stdout.flush()

# ─── HELPERS ───────────────────────────────────────────────────────────────
def load_child_photo(child: str, program: str):
    base = CHILD_PHOTOS_PATH / program
    photo = find_file(child, base, "jpg")
    caption = read_text(find_file(child, base, "txt"))
    return photo, caption

def resolve_program_pdf(program: str) -> Path | None:
    """
    Finds a ready-made program PDF in historias/PDF programas.

    Example:
    - 'Programa Chocó'   -> Programa_Choco.pdf
    - 'Programa Guajira' -> Programa_Guajira.pdf
    """
    if not program or not PROGRAM_PDF_PATH.exists():
        return None

    target = normalize_simple(program)

    for pdf in PROGRAM_PDF_PATH.glob("*.pdf"):
        stem_normalized = normalize_simple(pdf.stem).replace("_", " ")
        if stem_normalized == target:
            return pdf

    return None

def fill_program_pdf(
    pdf_source: Path,
    out_path: Path,
    donor_data: dict,
) -> tuple[Path, list[str]]:
    """
    Fill form fields in a program PDF with donor data, then flatten.

    Field names expected in the PDF form (created in Acrobat):
        nombre_padrino  tratamiento  direccion  ciudad  departamento

    Returns (out_path, warnings) where warnings lists any issues found.
    """
    warnings = []

    reader = PdfReader(str(pdf_source))

    # Check whether this PDF actually has form fields
    fields = reader.get_fields() or {}
    known_fields = {"nombre_padrino", "tratamiento", "direccion", "ciudad", "departamento"}
    found_fields = known_fields & set(fields.keys())

    if not found_fields:
        # No recognised fields — copy as-is and warn
        shutil.copy2(pdf_source, out_path)
        warnings.append(
            f"El PDF '{pdf_source.name}' no tiene campos de formulario reconocidos. "
            f"Se copió sin rellenar. Agrega los campos en Acrobat con los nombres: "
            f"{', '.join(sorted(known_fields))}"
        )
        return out_path, warnings

    writer = PdfWriter()
    writer.append(reader)

    # Build the field update dict (only fields that exist in this PDF)
    field_values = {
        "nombre_padrino": donor_data.get("nombre_padrino", ""),
        "tratamiento":    donor_data.get("tratamiento", ""),
        "direccion":      donor_data.get("direccion", ""),
        "ciudad":         donor_data.get("ciudad", ""),
        "departamento":   donor_data.get("departamento", ""),
    }
    update = {k: v for k, v in field_values.items() if k in fields}

    writer.update_page_form_field_values(writer.pages[0], update, auto_regenerate=False)

    # Flatten: mark all fields as read-only so they render as plain text
    for page in writer.pages:
        if "/Annots" in page:
            for annot in page["/Annots"]:
                annot_obj = annot.get_object()
                annot_obj.update({"/Ff": 1})  # ReadOnly flag

    with open(out_path, "wb") as f:
        writer.write(f)

    return out_path, warnings


def copy_program_letter(
    program: str,
    donor: str,
    output_folder: Path,
    donor_data: dict = None,
) -> tuple[Path, list[str]]:
    pdf_source = resolve_program_pdf(program)
    if not pdf_source:
        raise FileNotFoundError(
            f"No se encontró el PDF del programa para '{program}' en {PROGRAM_PDF_PATH}"
        )

    donor_safe = safe_filename(donor)
    out_path = output_folder / f"{donor_safe}.pdf"

    if donor_data:
        return fill_program_pdf(pdf_source, out_path, donor_data)
    else:
        shutil.copy2(pdf_source, out_path)
        return out_path, []

# ─── MAIN ───────────────────────────────────────────────────────────────────
def main():
    OUTPUT_PDF_PATH.mkdir(parents=True, exist_ok=True)
    (OUTPUT_PDF_PATH / "physical").mkdir(parents=True, exist_ok=True)
    (OUTPUT_PDF_PATH / "digital").mkdir(parents=True, exist_ok=True)
    OUTPUT_LOG_PATH.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(TEMPLATES_PATH), autoescape=False)
    template_name = "letter_template_midyear.html" if LETTER_MODE == "midyear" else TEMPLATE_FILE
    template = env.get_template(template_name)

    excel_path = DATA_PATH_OVERRIDE if DATA_PATH_OVERRIDE else DATA_PATH / "data_ejemplo.xlsx"

    xls = pd.ExcelFile(excel_path)
    log_f, writer = ensure_log_header(LOG_FILE)

    try:
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df.columns = df.columns.str.strip()

            key = deaccent_lower(sheet_name)
            is_digital = "digital" in key

            total_rows = len(df)
            if not GUI_PROGRESS_CALLBACK:
                print(f"\nProcessing sheet: {sheet_name} ({total_rows} rows)\n")

            for idx, row in df.iterrows():
                progress_bar(idx + 1, total_rows)

                issues = []
                donor = clean_str(row.get("nombre_padrino"))
                child = clean_str(row.get("Nombre_NNAJ"))
                program = clean_str(row.get("AldeaPrograma"))

                # Blank child means program donor row
                is_program_letter = child == ""

                direccion = clean_str(row.get("Direccion"))
                ciudad = clean_str(row.get("Ciudad"))
                departamento = clean_str(row.get("Departamento"))

                # If the sheet is digital, suppress address lines
                if is_digital:
                    direccion = ""
                    ciudad = ""
                    departamento = ""

                context = {
                    "Saludo": clean_str(row.get("Saludo")),
                    "nombre_padrino": donor,
                    "Direccion": direccion,
                    "Ciudad": ciudad,
                    "Departamento": departamento,
                    "Nombre_NNAJ": child,
                    "AldeaPrograma": program,
                    "is_digital": is_digital
                }
                # Folder structure: program → child (if applicable)
                base_folder = OUTPUT_PDF_PATH / ("digital" if is_digital else "physical")
                program_folder = base_folder / safe_filename(program or "SinPrograma")

                if not is_program_letter:
                    program_folder = program_folder / safe_filename(child or "SinNombre")

                program_folder.mkdir(parents=True, exist_ok=True)

                donor_safe = safe_filename(donor)
                out_path = program_folder / f"{donor_safe}.pdf"

                # ── PROGRAM DONORS: COPY READY-MADE PDF (fill form fields) ──
                if is_program_letter:
                    try:
                        donor_data = {
                            "nombre_padrino": donor,
                            "tratamiento":    clean_str(row.get("Saludo", "")),
                            "direccion":      direccion,
                            "ciudad":         ciudad,
                            "departamento":   departamento,
                        }
                        out_path, fill_warnings = copy_program_letter(
                            program, donor, program_folder, donor_data=donor_data
                        )
                        for w in fill_warnings:
                            issues.append(w)
                        status = "OK" if not fill_warnings else "WARN"
                    except Exception as e:
                        issues.append(f"Program PDF error: {e}")
                        status = "ERROR"

                    log_row(
                        writer,
                        sheet=sheet_name,
                        donor=donor,
                        child="",
                        program=program,
                        status=status,
                        issues="; ".join(issues),
                        output=str(out_path),
                    )

                    time.sleep(0.02)
                    continue

                # ── CHILD DONORS: GENERATE HTML LETTER ──────────────────────
                intro_raw = read_text(DATA_PATH / "intro_nnaj.txt")
                outro_raw = read_text(DATA_PATH / "outro_nnaj.txt")

                s1_raw = read_text(find_file(child, CHILD_STORIES_PATH, "txt")) or ""
                s2_raw = read_text(find_file(f"{program}1", PROGRAM_STORIES_PATH, "txt")) or ""
                s3_raw = read_text(find_file(f"{program}2", PROGRAM_STORIES_PATH, "txt")) or ""

                intro = markdown_to_html(render_text_with_context(intro_raw, context, env))
                outro = markdown_to_html(render_text_with_context(outro_raw, context, env))
                historia_1 = markdown_to_html(render_text_with_context(s1_raw, context, env))
                historia_2 = markdown_to_html(render_text_with_context(s2_raw, context, env))
                historia_3 = markdown_to_html(render_text_with_context(s3_raw, context, env))

                program_photos_base = PROGRAM_PHOTOS_PATH

                program_photo_1 = find_file(f"{program}1", program_photos_base, "jpg")
                program_photo_2 = find_file(f"{program}2", program_photos_base, "jpg")                
                caption_programa_1 = read_text(find_file(f"{program}1", program_photos_base, "txt")) or ""
                caption_programa_2 = read_text(find_file(f"{program}2", program_photos_base, "txt")) or ""
                child_photo = None
                caption_child = ""

                if LETTER_MODE == "midyear":
                    child_photo, caption_child = load_child_photo(child, program)
                    program_photo_2 = None

                html_rendered = template.render(
                    **context,
                    intro=intro,
                    historia_1=historia_1,
                    historia_2=historia_2,
                    historia_3=historia_3,
                    child_photo=child_photo.resolve().as_uri() if child_photo else None,
                    program_photo_1=program_photo_1.resolve().as_uri() if program_photo_1 else None,
                    program_photo_2=program_photo_2.resolve().as_uri() if program_photo_2 else None,                    
                    caption_child=caption_child,
                    caption_programa_1=caption_programa_1,
                    caption_programa_2=caption_programa_2,
                    header_image=(TEMPLATES_PATH / "header.png").resolve().as_uri(),
                    signature_image=(TEMPLATES_PATH / "firma.png").resolve().as_uri(),
                    outro=outro,
                )

                (OUTPUT_LOG_PATH / f"{donor_safe}.html").write_text(html_rendered, encoding="utf-8")

                try:
                    HTML(string=html_rendered, base_url=str(BASE_DIR)).write_pdf(out_path)
                    status = "OK"
                except Exception as e:
                    issues.append(f"WeasyPrint error: {e}")
                    status = "ERROR"

                log_row(
                    writer,
                    sheet=sheet_name,
                    donor=donor,
                    child=child,
                    program=program,
                    status=status,
                    issues="; ".join(issues),
                    output=str(out_path),
                )

                time.sleep(0.02)

            if not GUI_PROGRESS_CALLBACK:
                print("\n")

    finally:
        log_f.close()

    try:
        os.startfile(OUTPUT_PDF_PATH)
    except Exception:
        pass

# ─── GUI ENTRY POINT ───────────────────────────────────────────────────────
def run_from_gui(project_folder, excel_file, progress_callback=None, letter_mode="endyear"):
    global DATA_PATH, TEMPLATES_PATH, OUTPUT_PDF_PATH, OUTPUT_LOG_PATH
    global CHILD_STORIES_PATH, PROGRAM_STORIES_PATH, PROGRAM_PDF_PATH
    global CHILD_PHOTOS_PATH, PROGRAM_PHOTOS_PATH
    global DATA_PATH_OVERRIDE, GUI_PROGRESS_CALLBACK, LETTER_MODE, LOG_FILE
    base = Path(project_folder)

    DATA_PATH = base / "data"
    TEMPLATES_PATH = base / "templates"
    OUTPUT_PDF_PATH = base / "Cartas_Listas" / "pdf"
    OUTPUT_LOG_PATH = base / "Cartas_Listas" / "logs"

    CHILD_STORIES_PATH = base / "historias" / "NNAJ"
    PROGRAM_STORIES_PATH = base / "historias" / "programas"
    PROGRAM_PDF_PATH = base / "historias" / "PDF programas"
    CHILD_PHOTOS_PATH = base / "fotos" / "nnaj"
    PROGRAM_PHOTOS_PATH = base / "fotos" / "programas"
    LOG_FILE = OUTPUT_LOG_PATH / "epistolegraphos_single_log.csv"

    DATA_PATH_OVERRIDE = Path(excel_file)
    GUI_PROGRESS_CALLBACK = progress_callback
    LETTER_MODE = letter_mode

    main()

if __name__ == "__main__":
    main()