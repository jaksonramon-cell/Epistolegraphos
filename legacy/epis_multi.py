# Epistolēgraphos Multi-Donor Generator (GUI-ready)

import re
import shutil
import unicodedata
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import markdown
from pypdf import PdfReader, PdfWriter


# ─────────────────────────────────────────────────────────────
# PATH CONFIGURATION
# ─────────────────────────────────────────────────────────────

def configurar_rutas(project_root=None, manual_paths=None):

    if manual_paths:
        paths = {k: Path(v) for k, v in manual_paths.items()}

    elif project_root:

        root = Path(project_root)

        paths = {
            "DATA_PATH": root / "data",
            "TEMPLATES_PATH": root / "templates",
            "CHILD_STORIES_PATH": root / "historias/NNAJ",
            "PROGRAM_STORIES_PATH": root / "historias/programas",
            "PROGRAM_PHOTOS_PATH": root / "fotos/programas",
            "PROGRAM_PDF_PATH": root / "historias" / "PDF programas",
            "OUTPUT_BASE_PATH": root / "Cartas_Listas/pdf/multi",
            "OUTPUT_LOG_PATH": root / "Cartas_Listas/logs",
            "ROOT": root,
        }

    else:
        raise ValueError("Debe especificar project_root o manual_paths")

    paths["OUTPUT_BASE_PATH"].mkdir(parents=True, exist_ok=True)
    paths["OUTPUT_LOG_PATH"].mkdir(parents=True, exist_ok=True)

    return paths


# ─────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────

def read_text(path: Path):
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def normalize_simple(text: str):
    if not isinstance(text, str):
        return ""

    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^a-zA-Z0-9]+", "", text)

    return text.lower().strip()


def find_file(name: str, base_dir: Path, ext: str):
    if not name or not base_dir.exists():
        return None

    for f in base_dir.rglob(f"*.{ext}"):
        if normalize_simple(f.stem) == normalize_simple(name):
            return f

    return None


def markdown_to_html(text):
    return markdown.markdown(text, extensions=["extra", "sane_lists"]) if text else ""


def safe_filename(name: str):
    name = re.sub(r"[^\w]+", "_", str(name))
    return re.sub(r"_+", "_", name).strip("_") or "unknown"


def render_text_with_context(text: str, context: dict, env):
    try:
        return env.from_string(text or "").render(**context)
    except Exception:
        return text or ""


def human_join(items):
    items = [str(x).strip() for x in items if str(x).strip()]
    if len(items) == 0:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} y {items[1]}"
    return ", ".join(items[:-1]) + f" y {items[-1]}"


def resolve_program_pdf(program: str, program_pdf_path: Path):
    if not program or not program_pdf_path.exists():
        return None

    target = normalize_simple(program)

    for pdf in program_pdf_path.glob("*.pdf"):
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

    Field names expected in the PDF (created in Acrobat):
        nombre_padrino  tratamiento  direccion  ciudad  departamento

    Returns (out_path, warnings).
    """
    warnings = []

    reader = PdfReader(str(pdf_source))
    fields = reader.get_fields() or {}
    known_fields = {"nombre_padrino", "tratamiento", "direccion", "ciudad", "departamento"}
    found_fields = known_fields & set(fields.keys())

    if not found_fields:
        shutil.copy2(pdf_source, out_path)
        warnings.append(
            f"El PDF '{pdf_source.name}' no tiene campos de formulario reconocidos. "
            f"Se copió sin rellenar. Agrega los campos en Acrobat con los nombres: "
            f"{', '.join(sorted(known_fields))}"
        )
        return out_path, warnings

    writer = PdfWriter()
    writer.append(reader)

    field_values = {
        "nombre_padrino": donor_data.get("nombre_padrino", ""),
        "tratamiento":    donor_data.get("tratamiento", ""),
        "direccion":      donor_data.get("direccion", ""),
        "ciudad":         donor_data.get("ciudad", ""),
        "departamento":   donor_data.get("departamento", ""),
    }
    update = {k: v for k, v in field_values.items() if k in fields}

    writer.update_page_form_field_values(writer.pages[0], update, auto_regenerate=False)

    for page in writer.pages:
        if "/Annots" in page:
            for annot in page["/Annots"]:
                annot_obj = annot.get_object()
                annot_obj.update({"/Ff": 1})

    with open(out_path, "wb") as f:
        writer.write(f)

    return out_path, warnings


def copy_program_letter(
    program: str,
    donor: str,
    output_folder: Path,
    program_pdf_path: Path,
    donor_data: dict = None,
) -> tuple[Path, list[str]]:
    pdf_source = resolve_program_pdf(program, program_pdf_path)

    if not pdf_source:
        raise FileNotFoundError(
            f"No se encontró el PDF del programa para '{program}' en {program_pdf_path}"
        )

    donor_safe = safe_filename(donor)
    out_path = output_folder / f"{donor_safe}.pdf"

    if donor_data:
        return fill_program_pdf(pdf_source, out_path, donor_data)
    else:
        shutil.copy2(pdf_source, out_path)
        return out_path, []


def merge_pdfs(output_path, pdf_list):

    writer = PdfWriter()

    for pdf in pdf_list:

        reader = PdfReader(str(pdf))

        for page in reader.pages:
            writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)


# ─────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────

def generar_cartas_multi(project_root=None,
                         manual_paths=None,
                         excel_path=None,
                         progress_callback=None,
                         letter_mode="endyear"):

    paths = configurar_rutas(project_root, manual_paths)

    DATA_PATH = paths["DATA_PATH"]
    TEMPLATES_PATH = paths["TEMPLATES_PATH"]
    CHILD_STORIES_PATH = paths["CHILD_STORIES_PATH"]
    PROGRAM_STORIES_PATH = paths["PROGRAM_STORIES_PATH"]
    PROGRAM_PHOTOS_PATH = paths["PROGRAM_PHOTOS_PATH"]
    PROGRAM_PDF_PATH = paths["PROGRAM_PDF_PATH"]
    OUTPUT_BASE_PATH = paths["OUTPUT_BASE_PATH"]
    ROOT = paths.get("ROOT", Path("."))

    TEMPLATE_FILE = (
        "letter_template_multi_midyear.html"
        if letter_mode == "midyear"
        else "letter_template_multi.html"
    )

    env = Environment(loader=FileSystemLoader(TEMPLATES_PATH), autoescape=False)
    template = env.get_template(TEMPLATE_FILE)

    data_file = Path(excel_path) if excel_path else DATA_PATH / "data_multi_audit.xlsx"

    if not data_file.exists():
        raise FileNotFoundError(f"Missing Excel file: {data_file}")

    xls = pd.ExcelFile(data_file)
    total_generadas = 0

    for sheet_name in xls.sheet_names:

        key = normalize_simple(sheet_name)
        is_digital = "digital" in key

        df = pd.read_excel(xls, sheet_name=sheet_name)

        for col in ["nombre_padrino", "Nombre_NNAJ", "AldeaPrograma", "Direccion", "Ciudad", "Departamento", "Saludo"]:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .replace("nan", "")
                    .str.strip()
                )

        sheet_output_path = OUTPUT_BASE_PATH / safe_filename(sheet_name)
        sheet_output_path.mkdir(parents=True, exist_ok=True)

        grouped = df.groupby("nombre_padrino", dropna=False)
        total_donors = len(grouped)

        for idx, (donor, group) in enumerate(grouped, 1):

            if progress_callback:
                progress_callback(idx, total_donors)

            donor = str(donor).strip()
            if not donor:
                continue

            base_row = group.iloc[0]

            saludo = base_row.get("Saludo", "Querido(a) patrocinador(a),")
            direccion = base_row.get("Direccion", "")
            ciudad = base_row.get("Ciudad", "")
            departamento = base_row.get("Departamento", "")

            if is_digital:
                direccion = ""
                ciudad = ""
                departamento = ""

            children = [
                str(c).strip()
                for c in group["Nombre_NNAJ"].unique()
                if pd.notna(c) and str(c).strip() != "" and str(c).strip().lower() != "nan"
            ]

            programs = [
                str(p).strip()
                for p in group["AldeaPrograma"].unique()
                if pd.notna(p) and str(p).strip() != "" and str(p).strip().lower() != "nan"
            ]

            # PROGRAM ONLY DONOR
            if len(children) == 0:

                if len(programs) == 0:
                    continue

                program = programs[0]
                donor_data = {
                    "nombre_padrino": donor,
                    "tratamiento":    saludo,
                    "direccion":      direccion,
                    "ciudad":         ciudad,
                    "departamento":   departamento,
                }
                _, fill_warnings = copy_program_letter(
                    program, donor, sheet_output_path, PROGRAM_PDF_PATH,
                    donor_data=donor_data,
                )
                if fill_warnings:
                    for w in fill_warnings:
                        print(f"[WARN] {donor}: {w}")
                total_generadas += 1
                continue

            # INTRO VARIABLES
            children_text = human_join(children)

            program_groups = {}
            for child in children:
                match = group.loc[group["Nombre_NNAJ"] == child, "AldeaPrograma"]
                if match.empty:
                    continue
                child_program = str(match.iloc[0]).strip()
                program_groups.setdefault(child_program, []).append(child)

            parts = []
            for program, kids in program_groups.items():
                kid_text = human_join(kids)
                parts.append(f"{kid_text} en el Programa {program}")

            all_list = human_join(parts)

            intro_html = markdown_to_html(
                render_text_with_context(
                    read_text(DATA_PATH / "intro_multi.txt"),
                    {
                        "nombre_padrino": donor,
                        "all_list": all_list,
                        "children_text": children_text,
                    },
                    env,
                )
            )

            outro_html = markdown_to_html(
                render_text_with_context(
                    read_text(DATA_PATH / "outro_multi.txt"),
                    {"nombre_padrino": donor},
                    env,
                )
            )

            # STORIES
            stories = []
            programs_already_added = set()

            ordered_programs = []
            program_to_children = {}

            for child in children:
                match = group.loc[group["Nombre_NNAJ"] == child, "AldeaPrograma"]
                if match.empty:
                    continue
                child_program = str(match.iloc[0]).strip()

                if child_program not in program_to_children:
                    program_to_children[child_program] = []
                    ordered_programs.append(child_program)

                program_to_children[child_program].append(child)

            for child_program in ordered_programs:

                for child in program_to_children[child_program]:
                    story_path = find_file(child, CHILD_STORIES_PATH, "txt")
                    if not story_path:
                        continue

                    story_html = markdown_to_html(
                        render_text_with_context(
                            read_text(story_path),
                            {"Nombre_NNAJ": child},
                            env,
                        )
                    )

                    stories.append({
                        "type": "child",
                        "name": child,
                        "html": story_html,
                        "photo": None,
                        "caption": "",
                    })

                if child_program not in programs_already_added:
                    programs_already_added.add(child_program)

                    for i in (1, 2):
                        story_path = find_file(f"{child_program}{i}", PROGRAM_STORIES_PATH, "txt")
                        photo_path = find_file(f"{child_program}{i}", PROGRAM_PHOTOS_PATH, "jpg")
                        caption_text = read_text(find_file(f"{child_program}{i}", PROGRAM_PHOTOS_PATH, "txt"))

                        if story_path:
                            story_html = markdown_to_html(
                                render_text_with_context(
                                    read_text(story_path),
                                    {"AldeaPrograma": child_program},
                                    env,
                                )
                            )

                            stories.append({
                                "type": "program",
                                "name": f"{child_program}{i}",
                                "html": story_html,
                                "photo": photo_path.resolve().as_uri() if photo_path else None,
                                "caption": caption_text or "",
                            })

            context = {
                "Saludo": saludo,
                "nombre_padrino": donor,
                "Direccion": direccion,
                "Ciudad": ciudad,
                "Departamento": departamento,
                "stories": stories,
                "intro": intro_html,
                "outro": outro_html,
                "header_image": (TEMPLATES_PATH / "header.png").resolve().as_uri(),
                "signature_image": (TEMPLATES_PATH / "firma.png").resolve().as_uri(),
                "is_digital": is_digital,
            }

            donor_safe = safe_filename(donor)

            temp_html_pdf = sheet_output_path / f"{donor_safe}_temp.pdf"

            html_rendered = template.render(**context)

            HTML(string=html_rendered, base_url=str(ROOT)).write_pdf(temp_html_pdf)

            program_only_rows = group[
                group["Nombre_NNAJ"].astype(str).str.strip().isin(["", "nan"])
            ]

            program_only_programs = [
                str(p).strip()
                for p in program_only_rows["AldeaPrograma"].unique()
                if pd.notna(p) and str(p).strip() != ""
            ]

            pdfs_to_merge = [temp_html_pdf]

            for program in program_only_programs:
                program_pdf = resolve_program_pdf(program, PROGRAM_PDF_PATH)
                if program_pdf:
                    # Fill form fields into a temp file, then merge that
                    donor_data = {
                        "nombre_padrino": donor,
                        "tratamiento":    saludo,
                        "direccion":      direccion,
                        "ciudad":         ciudad,
                        "departamento":   departamento,
                    }
                    import tempfile as _tf
                    with _tf.NamedTemporaryFile(suffix=".pdf", delete=False) as _tmp:
                        tmp_prog_path = Path(_tmp.name)
                    filled_path, fill_warnings = fill_program_pdf(
                        program_pdf, tmp_prog_path, donor_data
                    )
                    if fill_warnings:
                        for w in fill_warnings:
                            print(f"[WARN] {donor}: {w}")
                    pdfs_to_merge.append(filled_path)

            final_pdf = sheet_output_path / f"{donor_safe}.pdf"

            merge_pdfs(final_pdf, pdfs_to_merge)

            temp_html_pdf.unlink(missing_ok=True)

            total_generadas += 1

    return {
        "total_generadas": total_generadas,
        "output_folder": str(OUTPUT_BASE_PATH),
    }


if __name__ == "__main__":
    generar_cartas_multi(project_root=".")