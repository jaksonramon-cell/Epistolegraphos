import os
from dataclasses import dataclass
from typing import List

import fitz  # PyMuPDF
import pandas as pd
from rapidfuzz import fuzz


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass
class ExtractionSummary:
    total_names: int
    total_pdfs_processed: int
    total_matches: int
    unmatched_names: List[str]
    log_file: str


# ==========================================================
# VALIDATION
# ==========================================================

def _validate_inputs(
    excel_file: str,
    pdf_folder: str,
    sheet_name: str,
    column_name: str
) -> List[str]:

    if not os.path.isfile(excel_file):
        raise FileNotFoundError(f"Excel file not found: {excel_file}")

    if not os.path.isdir(pdf_folder):
        raise NotADirectoryError(f"PDF folder not found: {pdf_folder}")

    pdf_files = [
        f for f in os.listdir(pdf_folder)
        if f.lower().endswith(".pdf")
    ]

    if not pdf_files:
        raise ValueError(f"No PDF files found in folder: {pdf_folder}")

    try:
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
    except ValueError:
        raise ValueError(
            f"Sheet '{sheet_name}' not found in {excel_file}"
        )

    if column_name not in df.columns:
        raise ValueError(
            f"Column '{column_name}' not found in sheet '{sheet_name}'"
        )

    return pdf_files


# ==========================================================
# LOAD NAMES
# ==========================================================

def _load_names(
    excel_file: str,
    sheet_name: str,
    column_name: str
) -> List[str]:

    df = pd.read_excel(excel_file, sheet_name=sheet_name)

    return (
        df[column_name]
        .dropna()
        .astype(str)
        .tolist()
    )


# ==========================================================
# MAIN EXTRACTION FUNCTION
# ==========================================================

def extraer_cartas(
    excel_file: str,
    pdf_folder: str,
    output_folder: str,
    sheet_name: str = "nombres",
    column_name: str = "nombres",
    fuzzy_threshold: int = 80
) -> ExtractionSummary:

    # ---------------- VALIDATION ----------------
    pdf_files = _validate_inputs(
        excel_file,
        pdf_folder,
        sheet_name,
        column_name
    )

    # ---------------- PREPARE OUTPUT ----------------
    os.makedirs(output_folder, exist_ok=True)
    log_path = os.path.join(output_folder, "match_log.xlsx")

    names = _load_names(
        excel_file,
        sheet_name,
        column_name
    )

    log_data = []
    matched_names = set()

    # ---------------- PROCESS PDFs ----------------
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_folder, pdf_file)
        doc = fitz.open(pdf_path)

        for name in names:
            if name in matched_names:
                continue

            name_lower = name.lower()

            for i in range(0, len(doc), 2):
                page = doc[i]
                blocks = page.get_text("blocks")
                page_height = page.rect.height
                top_third = page_height / 3

                top_blocks = [
                    b for b in blocks
                    if b[1] < top_third
                ]

                top_text = " ".join(
                    b[4] for b in top_blocks
                ).lower()

                ratio = fuzz.partial_ratio(
                    name_lower,
                    top_text
                )

                if ratio >= fuzzy_threshold:
                    new_doc = fitz.open()
                    new_doc.insert_pdf(
                        doc,
                        from_page=i,
                        to_page=i + 1
                    )

                    safe_name = "".join(
                        c for c in name
                        if c.isalnum() or c in (" ", "_", "-")
                    ).rstrip()

                    out_path = os.path.join(
                        output_folder,
                        f"{safe_name}.pdf"
                    )

                    new_doc.save(out_path)
                    new_doc.close()

                    log_data.append({
                        "nombre": name,
                        "status": f"MATCHED ({ratio}%)",
                        "source_pdf": pdf_file
                    })

                    matched_names.add(name)
                    break

        doc.close()

    # ---------------- FINALIZE LOG ----------------
    for name in names:
        if name not in matched_names:
            log_data.append({
                "nombre": name,
                "status": "NOT FOUND",
                "source_pdf": None
            })

    log_df = pd.DataFrame(log_data)
    log_df.to_excel(log_path, index=False)

    # ---------------- SUMMARY ----------------
    total_names = len(names)
    total_pdfs = len(pdf_files)
    total_matches = len(matched_names)
    unmatched_list = [
        n for n in names
        if n not in matched_names
    ]

    return ExtractionSummary(
        total_names=total_names,
        total_pdfs_processed=total_pdfs,
        total_matches=total_matches,
        unmatched_names=unmatched_list,
        log_file=log_path
    )