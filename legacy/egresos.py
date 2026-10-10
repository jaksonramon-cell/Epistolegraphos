import pandas as pd
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import re
import unicodedata
import sys


# =====================================================
# PATH HANDLING (DEV + EXE SAFE)
# =====================================================

if getattr(sys, 'frozen', False):
    # Running as EXE
    BASE_DIR = Path(sys._MEIPASS)                 # bundled resources
    APP_DIR = Path(sys.executable).parent         # where exe lives
else:
    # Running in Python
    BASE_DIR = Path(__file__).parent
    APP_DIR = BASE_DIR

TEMPLATE_DIR = BASE_DIR / "Estilos"
TEMPLATE_NAME = "estilos.html"
TXT_DIR = BASE_DIR / "Egresos_txt"

# OUTPUT always next to executable (never inside _MEIPASS)
OUTPUT_DIR = APP_DIR / "Egresos_listos"


# =====================================================
# UTILITIES
# =====================================================

def normalizar_nombre_archivo(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto))
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-zA-Z0-9 ]", "", texto)
    return texto.strip().replace(" ", "_")


def resaltar_primer_nombre(texto: str, nombre: str) -> str:
    if not nombre:
        return texto

    patron = r"\b" + re.escape(nombre.strip()) + r"\b"
    reemplazo = f'<span class="highlight-name">{nombre}</span>'

    return re.sub(patron, reemplazo, texto, count=1)


def construir_parrafo_final(nuevo_nino: str, programa: str):
    es_nino = bool(nuevo_nino and nuevo_nino.strip())

    if es_nino:
        cierre = (
            "En la siguiente página conocerás sus sueños, intereses y pasatiempos. "
            "En los próximos meses recibirás actualizaciones sobre su progreso "
            "y el impacto de tu apoyo en su vida, su familia y su comunidad."
        )
    else:
        cierre = (
            "En la siguiente página conocerás más acerca de este territorio "
            "y sobre cómo a través de tu apoyo generamos impacto positivo en la vida "
            "de los niños, las niñas, las familias y la comunidad de este lugar."
        )

    return es_nino, cierre


# =====================================================
# MAIN ENGINE
# =====================================================

def generar_cartas(ruta_excel: str, mapa_columnas: dict):

    OUTPUT_DIR.mkdir(exist_ok=True)

    df = pd.read_excel(ruta_excel)

    entorno = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    plantilla = entorno.get_template(TEMPLATE_NAME)

    total_generadas = 0
    errores = []

    for _, fila in df.iterrows():
        try:
            primer_nombre_anterior = str(
                fila[mapa_columnas["primer_nombre_anterior"]]
            ).strip()

            # --- Safe NaN handling ---
            valor_nuevo_nino = fila[mapa_columnas["nuevo_nino"]]
            valor_programa = fila[mapa_columnas["programa"]]

            nuevo_nino = "" if pd.isna(valor_nuevo_nino) else str(valor_nuevo_nino).strip()
            programa = "" if pd.isna(valor_programa) else str(valor_programa).strip()

            direccion_original = str(
                fila[mapa_columnas["direccion"]]
            ).strip()

            # --- Digital detection ---
            direccion_lower = direccion_original.lower().strip()
            es_digital = direccion_lower in ["envío digital", "envio digital"]

            direccion_para_carta = "" if es_digital else direccion_original

            # --- Load TXT ---
            archivo_txt = TXT_DIR / (
                normalizar_nombre_archivo(primer_nombre_anterior) + ".txt"
            )

            if not archivo_txt.exists():
                errores.append(f"Falta TXT: {archivo_txt.name}")
                continue

            texto_base = archivo_txt.read_text(encoding="utf-8").strip()

            # Highlight once
            texto_resaltado = resaltar_primer_nombre(
                texto_base, primer_nombre_anterior
            )

            # Split paragraphs (one line = one paragraph)
            lineas = texto_resaltado.splitlines()

            parrafos_html = [
                f"<p>{linea.strip()}</p>"
                for linea in lineas
                if linea.strip()
            ]

            parrafo_formateado = "\n".join(parrafos_html)

            # --- Final paragraph logic ---
            es_nino, cierre = construir_parrafo_final(nuevo_nino, programa)

            contexto = {
                "Tratamiento": fila[mapa_columnas["tratamiento"]],
                "Nombre_completo_padrino": fila[mapa_columnas["nombre_padrino"]],
                "Primer_nombre_padrino": fila[mapa_columnas["primer_nombre_padrino"]],
                "Direccion": direccion_para_carta,
                "Ciudad": fila[mapa_columnas["ciudad"]],
                "Departamento": fila[mapa_columnas["departamento"]],
                "es_digital": es_digital,
                "Parrafo_Egreso": parrafo_formateado,
                "nuevo_nino": nuevo_nino,
                "programa": programa,
                "is_child": es_nino,
                "context_cierre": cierre
            }

            html_renderizado = plantilla.render(**contexto)

            # --- Folder routing ---
            if es_digital:
                carpeta_base = OUTPUT_DIR / "Envío Digital"
            else:
                carpeta_base = OUTPUT_DIR

            carpeta_destino = carpeta_base / normalizar_nombre_archivo(
                primer_nombre_anterior
            )
            carpeta_destino.mkdir(parents=True, exist_ok=True)

            nombre_pdf = (
                normalizar_nombre_archivo(
                    contexto["Nombre_completo_padrino"]
                ) + ".pdf"
            )

            ruta_salida = carpeta_destino / nombre_pdf

            HTML(
                string=html_renderizado,
                base_url=str(TEMPLATE_DIR)
            ).write_pdf(ruta_salida)

            total_generadas += 1

        except Exception as e:
            errores.append(str(e))

    return {
        "total_generadas": total_generadas,
        "errores": errores,
        "output_dir": str(OUTPUT_DIR)
    }