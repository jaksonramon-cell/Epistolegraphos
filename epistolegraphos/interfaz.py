"""Web interface (NiceGUI). Runs locally and opens in the browser."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from nicegui import run, ui

from . import __version__, cartas as mod_cartas, datos, render, utilidades
from .proyecto import Proyecto

DEMO = Path(__file__).resolve().parent.parent / "demo"
AJUSTES = Path.home() / ".epistolegraphos.json"
LEMA = "πρὶν δ᾽ ἂν τελευτήσῃ, ἐπισχεῖν, μηδὲ καλέειν κω ὄλβιον ἀλλ᾽ εὐτυχέα"

HERRAMIENTAS = {
    "historias": dict(ruta="/historias", icono="child_care", titulo="Cartas de historias",
                      texto="Noticias del niño o niña que apadrina cada donante. Un donante con varios ahijados recibe una sola carta.",
                      excel="padrinos_ninos"),
    "programa": dict(ruta="/programas", icono="diversity_3", titulo="Cartas de programa",
                     texto="Para quienes apoyan un programa completo en vez de un niño o niña.",
                     excel="padrinos_programa"),
    "egreso": dict(ruta="/egresos", icono="flight_takeoff", titulo="Cartas de egreso",
                   texto="Cuando un niño o niña termina su proceso y el padrino pasa a apoyar a otro niño o a un programa.",
                   excel="egresos"),
}


# ─── settings ─────────────────────────────────────────────────────────────────
def _leer_ajustes() -> dict:
    try:
        return json.loads(AJUSTES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_ajustes(**cambios):
    ajustes = _leer_ajustes() | cambios
    try:
        AJUSTES.write_text(json.dumps(ajustes, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def proyecto_actual() -> Proyecto:
    carpeta = _leer_ajustes().get("proyecto") or str(DEMO)
    if not Path(carpeta).is_dir():
        carpeta = str(DEMO)
    return Proyecto(carpeta)


def abrir_carpeta(ruta: Path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(ruta)])
        else:
            subprocess.Popen(["xdg-open", str(ruta)])
    except OSError:
        ui.notify(f"No se pudo abrir la carpeta: {ruta}", type="warning")


def comprimir(archivos: list[Path], destino: Path, base: Path) -> Path:
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for a in archivos:
            z.write(a, a.relative_to(base))
    return destino


# ─── layout ───────────────────────────────────────────────────────────────────
CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital@0;1&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  body { background: #f4f3ee; font-family: Inter, "Segoe UI", system-ui, sans-serif; color: #1f2523; }
  .q-drawer { background: #102a28 !important; }
  .marca { font-family: "EB Garamond", Georgia, serif; font-size: 30px; color: #f4f3ee; letter-spacing: .3px; line-height: 1; }
  .submarca { color: #8fb5b1; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; }
  .nav-item { color: #c9dbd8; border-radius: 10px; padding: 9px 14px; width: 100%; text-decoration: none; display: flex; gap: 12px; align-items: center; font-size: 14px; }
  .nav-item:hover { background: rgba(255,255,255,.06); color: #fff; }
  .nav-item.activo { background: rgba(228,87,46,.16); color: #fff; box-shadow: inset 3px 0 0 #e4572e; }
  .nav-titulo { color: #6f948f; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; margin: 18px 0 4px 14px; }
  .lema { font-family: "EB Garamond", Georgia, serif; font-style: italic; font-size: 12px; line-height: 1.35; color: #c9dbd8; opacity: .28; padding: 0 14px; user-select: none; }
  .lema:hover { opacity: .5; transition: opacity .6s; }
  .tarjeta { background: #fff; border-radius: 14px; border: 1px solid #e4e2da; box-shadow: 0 1px 2px rgba(16,42,40,.04); }
  .h-titulo { font-size: 26px; font-weight: 700; letter-spacing: -.01em; }
  .h-sub { color: #5d6866; font-size: 14px; }
  .paso { width: 26px; height: 26px; border-radius: 50%; background: #0b7a75; color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; flex: none; }
  .kpi-num { font-size: 30px; font-weight: 700; line-height: 1; }
  .kpi-et { font-size: 12px; color: #5d6866; text-transform: uppercase; letter-spacing: .08em; }
  .pagina-carta { box-shadow: 0 4px 20px rgba(0,0,0,.18); border-radius: 2px; }
  .q-table th { font-weight: 600; color: #5d6866; }
  .q-btn { text-transform: none; letter-spacing: 0; font-weight: 500; }
  .q-uploader { min-height: 0 !important; max-height: none; box-shadow: none; border-radius: 10px; }
  .q-uploader__list, .q-uploader__subtitle { display: none; }
  .q-uploader__header { background: #fff !important; color: #0b7a75 !important; border: 1px dashed #0b7a75; border-radius: 10px; }
</style>
"""


def marco(activo: str):
    """Drawer with navigation; returns nothing, the caller adds the page content after it."""
    ui.add_head_html(CSS)
    ui.colors(primary="#0b7a75", secondary="#102a28", accent="#e4572e", positive="#2e8b57", negative="#c0392b", warning="#e0a030")
    with ui.left_drawer(value=True, fixed=True).props("width=260 bordered=false").classes("p-0"):
        with ui.column().classes("h-full w-full justify-between no-wrap p-4"):
            with ui.column().classes("w-full gap-1"):
                with ui.column().classes("gap-1 px-3 pt-3 pb-4"):
                    ui.label("Epistolēgraphos").classes("marca")
                    ui.label("cartas a padrinos").classes("submarca")
                _enlace("/", "home", "Inicio", activo == "inicio")
                ui.label("Cartas").classes("nav-titulo")
                for clave_h, h in HERRAMIENTAS.items():
                    _enlace(h["ruta"], h["icono"], h["titulo"], activo == clave_h)
                ui.label("Utilidades").classes("nav-titulo")
                _enlace("/dividir", "call_split", "Dividir PDF", activo == "dividir")
                _enlace("/logo", "branding_watermark", "Logo en fotos", activo == "logo")
            with ui.column().classes("w-full gap-2 pb-2"):
                ui.label(LEMA).classes("lema").tooltip("Heródoto, Historias I.32")
                ui.label(f"v{__version__}").classes("text-[11px] px-4").style("color:#4f716d")


def _enlace(ruta: str, icono: str, texto: str, activo: bool):
    with ui.link(target=ruta).classes("nav-item" + (" activo" if activo else "")):
        ui.icon(icono).classes("text-[20px]")
        ui.label(texto)


def contenido():
    return ui.column().classes("w-full max-w-[1150px] mx-auto px-8 py-8 gap-6")


def encabezado(titulo: str, sub: str):
    with ui.column().classes("gap-1"):
        ui.label(titulo).classes("h-titulo")
        ui.label(sub).classes("h-sub")


def paso(n: int, titulo: str):
    with ui.row().classes("items-center gap-3"):
        ui.html(f'<span class="paso">{n}</span>')
        ui.label(titulo).classes("text-[17px] font-semibold")


def kpi(numero, etiqueta: str, color: str = "#1f2523"):
    with ui.column().classes("tarjeta px-5 py-4 gap-2 min-w-[140px] flex-1"):
        ui.label(str(numero)).classes("kpi-num").style(f"color:{color}")
        ui.label(etiqueta).classes("kpi-et")


# ─── home ─────────────────────────────────────────────────────────────────────
@ui.page("/")
def inicio():
    marco("inicio")
    proyecto = proyecto_actual()
    with contenido():
        encabezado("Inicio", "Elija la carpeta del proyecto y la herramienta que necesita.")

        with ui.column().classes("tarjeta p-6 w-full gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label("Proyecto").classes("kpi-et")
                    ui.label(proyecto.config.get("organizacion", "")).classes("text-[20px] font-semibold")
                if proyecto.carpeta == DEMO.resolve():
                    ui.badge("DATOS DE DEMOSTRACIÓN · FICTICIOS", color="accent").classes("px-3 py-1")
            with ui.row().classes("w-full items-end gap-3"):
                ruta = ui.input("Carpeta del proyecto", value=str(proyecto.carpeta)).classes("flex-1").props("outlined dense")

                def abrir():
                    if not Path(ruta.value).expanduser().is_dir():
                        ui.notify("Esa carpeta no existe", type="negative")
                        return
                    _guardar_ajustes(proyecto=str(Path(ruta.value).expanduser().resolve()))
                    ui.navigate.reload()

                def usar_demo():
                    _guardar_ajustes(proyecto=str(DEMO))
                    ui.navigate.reload()

                ui.button("Abrir", icon="folder_open", on_click=abrir).props("unelevated")
                ui.button("Usar demo", on_click=usar_demo).props("flat")
                ui.button(icon="launch", on_click=lambda: abrir_carpeta(proyecto.carpeta)).props("flat round").tooltip("Abrir en el explorador")

            faltan = proyecto.faltantes()
            cuentas = [
                (len(proyecto.ninos), "historias de niños"),
                (len(proyecto.programas), "programas"),
                (len(proyecto.egresos), "textos de egreso"),
                (len(proyecto.excels()), "archivos Excel"),
            ]
            with ui.row().classes("w-full gap-3"):
                for n, et in cuentas:
                    kpi(n, et)
            if faltan:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning", color="warning")
                    ui.label("Faltan carpetas: " + ", ".join(faltan)).classes("text-[13px]")

        with ui.row().classes("w-full gap-4 no-wrap max-md:flex-wrap"):
            for h in HERRAMIENTAS.values():
                with ui.link(target=h["ruta"]).classes("tarjeta p-6 flex-1 no-underline text-inherit hover:shadow-md transition-all"):
                    ui.icon(h["icono"], size="28px", color="primary")
                    ui.label(h["titulo"]).classes("text-[17px] font-semibold mt-3")
                    ui.label(h["texto"]).classes("h-sub mt-1")

        with ui.column().classes("tarjeta p-6 w-full gap-3"):
            ui.label("Cómo funciona").classes("text-[17px] font-semibold")
            for n, t in enumerate([
                "Cada fila del Excel es un padrino con un niño, niña o programa. Los encabezados se reconocen aunque cambien de nombre.",
                "Las historias, fotos y textos salen de la carpeta del proyecto. Los textos aceptan variables como {{ primer_nombre }} y concuerdan en género y número.",
                "Antes de generar, la revisión muestra cada carta y lo que le falta. Nada se imprime a ciegas.",
                "Se genera un PDF por padrino, un archivo de impresión por hoja con marcadores, y un registro en Excel.",
            ], 1):
                with ui.row().classes("items-start gap-3 no-wrap"):
                    ui.html(f'<span class="paso">{n}</span>')
                    ui.label(t).classes("text-[14px] pt-[3px]")


# ─── letter tools ─────────────────────────────────────────────────────────────
TEXTO_ESTADO = {"ok": "Lista", "aviso": "Revisar", "error": "Falta algo"}


def pagina_cartas(tipo: str):
    h = HERRAMIENTAS[tipo]
    marco(tipo)
    proyecto = proyecto_actual()
    estado = {"cartas": [], "progreso": (0, 0, ""), "cancelar": threading.Event(), "resultado": None}

    with contenido():
        encabezado(h["titulo"], h["texto"])

        # step 1: data
        with ui.column().classes("tarjeta p-6 w-full gap-4"):
            paso(1, "Datos")
            excels = {str(p): p.name for p in proyecto.excels()}
            sugerido = next((p for p in excels if h["excel"] in Path(p).stem), next(iter(excels), None))
            with ui.row().classes("w-full items-center gap-3"):
                selector = ui.select(excels, value=sugerido, label="Archivo Excel").classes("flex-1").props("outlined dense")

                async def subir(e):
                    destino = proyecto.ruta("datos", e.file.name)
                    await e.file.save(destino)
                    selector.options[str(destino)] = destino.name
                    selector.update()
                    selector.value = str(destino)
                    ui.notify(f"{destino.name} copiado a datos/")

                ui.upload(on_upload=subir, auto_upload=True, label="Subir Excel").props('accept=".xlsx" flat bordered').classes("w-[220px]")
            hojas_fila = ui.row().classes("gap-2 flex-wrap")
            hojas_sel: dict[str, ui.checkbox] = {}

            def cargar_hojas():
                hojas_fila.clear()
                hojas_sel.clear()
                if not selector.value:
                    return
                with hojas_fila:
                    ui.label("Hojas:").classes("h-sub self-center")
                    for nombre in datos.hojas_de(Path(selector.value)):
                        hojas_sel[nombre] = ui.checkbox(nombre, value=not nombre.upper().startswith("TEST"))

            selector.on_value_change(lambda: cargar_hojas())
            cargar_hojas()

        # step 2: review
        with ui.column().classes("tarjeta p-6 w-full gap-4"):
            with ui.row().classes("w-full items-center justify-between"):
                paso(2, "Revisión")
                boton_revisar = ui.button("Revisar cartas", icon="fact_check").props("unelevated")
            resumen = ui.row().classes("w-full gap-3")
            with ui.row().classes("w-full items-center gap-4") as filtros:
                solo_problemas = ui.switch("Solo cartas con avisos o errores")
                buscar = ui.input(placeholder="Buscar padrino o niño").props("dense outlined clearable").classes("w-[280px]")
                ui.label("Haga clic en una fila para ver la carta.").classes("h-sub ml-auto")
            filtros.set_visibility(False)
            columnas = [
                {"name": "padrino", "label": "Padrino", "field": "padrino", "align": "left", "sortable": True},
                {"name": "para", "label": "Niños / programa", "field": "para", "align": "left"},
                {"name": "hoja", "label": "Hoja", "field": "hoja", "align": "left", "sortable": True},
                {"name": "canal", "label": "Canal", "field": "canal", "align": "left", "sortable": True},
                {"name": "estado", "label": "Estado", "field": "estado", "align": "left", "sortable": True},
                {"name": "detalle", "label": "Detalle", "field": "detalle", "align": "left", "classes": "text-[12px] text-gray-600", "style": "white-space: normal; max-width: 340px"},
            ]
            tabla = ui.table(columns=columnas, rows=[], row_key="i", pagination=12).classes("w-full").props("flat")
            tabla.add_slot("body-cell-estado", """
                <q-td :props="props">
                  <q-badge :color="{ok:'positive',aviso:'warning',error:'negative'}[props.value]" rounded class="px-2">
                    {{ {ok:'Lista',aviso:'Revisar',error:'Falta algo'}[props.value] }}
                  </q-badge>
                </q-td>""")
            tabla.set_visibility(False)

        def filas_tabla():
            texto = (buscar.value or "").lower()
            filas = []
            for i, c in enumerate(estado["cartas"]):
                if solo_problemas.value and c.estado == "ok":
                    continue
                para = ", ".join(c.ninos) or ", ".join(c.programas)
                if texto and texto not in c.padrino.lower() and texto not in para.lower():
                    continue
                filas.append({"i": i, "padrino": c.padrino, "para": para, "hoja": c.hoja,
                              "canal": "Digital" if c.digital else "Física", "estado": c.estado,
                              "detalle": "; ".join(c.errores + c.avisos)})
            return filas

        def refrescar_tabla():
            tabla.rows = filas_tabla()
            tabla.update()

        solo_problemas.on_value_change(refrescar_tabla)
        buscar.on_value_change(refrescar_tabla)

        async def revisar():
            hojas = [n for n, cb in hojas_sel.items() if cb.value]
            if not selector.value or not hojas:
                ui.notify("Elija un archivo y al menos una hoja", type="warning")
                return
            boton_revisar.props("loading")
            try:
                ruta = Path(selector.value)

                def construir():
                    filas, faltantes = [], []
                    for hoja in hojas:
                        leida = datos.leer_hoja(ruta, hoja)
                        filas += leida.filas
                        faltantes += [f"{hoja}: falta la columna «{c}»" for c in leida.columnas_faltantes]
                    return mod_cartas.construir(proyecto_actual(), tipo, filas), faltantes

                cartas, faltantes = await run.io_bound(construir)
            except Exception as e:  # noqa: BLE001 - show it, don't crash the page
                ui.notify(f"No se pudo leer el archivo: {e}", type="negative", multi_line=True)
                return
            finally:
                boton_revisar.props(remove="loading")
            for f in faltantes:
                ui.notify(f, type="negative")
            estado["cartas"] = cartas
            cuenta = Counter(c.estado for c in cartas)
            resumen.clear()
            with resumen:
                kpi(len(cartas), "cartas")
                kpi(sum(not c.digital for c in cartas), "físicas")
                kpi(sum(c.digital for c in cartas), "digitales")
                kpi(cuenta["aviso"], "para revisar", "#b7791f")
                kpi(cuenta["error"], "con faltantes", "#c0392b")
            filtros.set_visibility(True)
            tabla.set_visibility(True)
            refrescar_tabla()
            seccion_generar.set_visibility(bool(cartas))

        boton_revisar.on_click(revisar)

        # preview
        with ui.dialog().props("maximized=false") as dialogo, ui.card().classes("w-[900px] max-w-[95vw] p-0"):
            with ui.row().classes("w-full items-center justify-between px-5 py-3 border-b"):
                titulo_previa = ui.label().classes("font-semibold")
                ui.button(icon="close", on_click=dialogo.close).props("flat round dense")
            cuerpo_previa = ui.column().classes("w-full items-center gap-6 p-6 bg-[#e9e8e3] max-h-[80vh] overflow-auto")

        async def previa(e):
            carta = estado["cartas"][e.args[1]["i"]]
            titulo_previa.text = f"{carta.padrino} · {TEXTO_ESTADO[carta.estado]}"
            cuerpo_previa.clear()
            with cuerpo_previa:
                for m in carta.errores:
                    ui.label(f"⚠ {m}").classes("text-negative text-[13px]")
                ui.spinner(size="lg")
            dialogo.open()
            try:
                paginas = await run.io_bound(render.vista_previa, proyecto_actual(), carta)
            except Exception as ex:  # noqa: BLE001
                cuerpo_previa.clear()
                with cuerpo_previa:
                    ui.label(f"No se pudo dibujar la carta: {ex}").classes("text-negative")
                return
            cuerpo_previa.clear()
            with cuerpo_previa:
                for m in carta.errores + carta.avisos:
                    ui.label(f"⚠ {m}").classes("text-[13px]").style("color:#8a5a00")
                for png in paginas:
                    ui.html(f'<img class="pagina-carta" style="width:760px;max-width:100%;display:block" '
                            f'src="data:image/png;base64,{base64.b64encode(png).decode()}">')

        tabla.on("rowClick", previa)

        # step 3: generate
        with ui.column().classes("tarjeta p-6 w-full gap-4") as seccion_generar:
            paso(3, "Generar")
            incluir = ui.checkbox("Generar también las cartas con faltantes (no recomendado)")
            with ui.row().classes("items-center gap-3"):
                boton_generar = ui.button("Generar PDFs", icon="picture_as_pdf").props("unelevated size=md")
                boton_cancelar = ui.button("Cancelar", on_click=lambda: estado["cancelar"].set()).props("flat color=negative")
                boton_cancelar.set_visibility(False)
            barra = ui.linear_progress(value=0, show_value=False).props("rounded size=10px color=accent")
            texto_progreso = ui.label().classes("h-sub")
            barra.set_visibility(False)
            final = ui.column().classes("w-full gap-3")
        seccion_generar.set_visibility(False)

        def tic():
            hechas, total, nombre = estado["progreso"]
            if total:
                barra.value = hechas / total
                texto_progreso.text = f"{hechas} de {total} · {nombre}"

        temporizador = ui.timer(0.25, tic, active=False)

        async def generar():
            cartas = estado["cartas"]
            if not cartas:
                return
            estado["cancelar"].clear()
            estado["progreso"] = (0, 0, "")
            carpeta = proyecto.salida / f"{tipo}_{datetime.now():%Y-%m-%d_%H%M%S}"
            boton_generar.props("loading")
            boton_cancelar.set_visibility(True)
            barra.set_visibility(True)
            final.clear()
            temporizador.activate()
            try:
                resultado = await run.io_bound(
                    render.generar, proyecto_actual(), cartas, carpeta,
                    lambda h_, t, n: estado.__setitem__("progreso", (h_, t, n)),
                    estado["cancelar"], None, incluir.value,
                )
            except Exception as e:  # noqa: BLE001
                ui.notify(f"Error al generar: {e}", type="negative", multi_line=True)
                return
            finally:
                temporizador.deactivate()
                tic()
                boton_generar.props(remove="loading")
                boton_cancelar.set_visibility(False)
            with final:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("cancel" if resultado.cancelado else "task_alt", size="26px",
                            color="negative" if resultado.cancelado else "positive")
                    ui.label(("Cancelado: " if resultado.cancelado else "")
                             + f"{resultado.generadas} cartas generadas en {resultado.segundos:.0f} s"
                             + (f" · {resultado.omitidas} omitidas" if resultado.omitidas else "")
                             + (f" · {resultado.fallidas} fallidas" if resultado.fallidas else "")).classes("text-[16px] font-semibold")
                ui.label(str(carpeta)).classes("h-sub font-mono text-[12px]")
                with ui.row().classes("gap-2"):
                    ui.button("Abrir carpeta", icon="folder_open", on_click=lambda: abrir_carpeta(carpeta)).props("unelevated")
                    if resultado.registro:
                        ui.button("Registro (Excel)", icon="table_view",
                                  on_click=lambda: ui.download.file(resultado.registro)).props("outline")
                    for archivo in resultado.impresion:
                        ui.button(f"Impresión · {archivo.parent.name}", icon="print",
                                  on_click=lambda a=archivo: ui.download.file(a)).props("outline")

        boton_generar.on_click(generar)


@ui.page("/historias")
def historias():
    pagina_cartas("historias")


@ui.page("/programas")
def programas():
    pagina_cartas("programa")


@ui.page("/egresos")
def egresos():
    pagina_cartas("egreso")


# ─── utilities ────────────────────────────────────────────────────────────────
@ui.page("/dividir")
def dividir():
    marco("dividir")
    proyecto = proyecto_actual()
    estado = {"pdf": None}
    with contenido():
        encabezado("Dividir PDF", "Separa un PDF con muchas cartas en un archivo por padrino. "
                                  "Usa los marcadores del archivo de impresión; si no los hay, busca los nombres en cada página.")
        with ui.column().classes("tarjeta p-6 w-full gap-4"):
            paso(1, "PDF de origen")
            etiqueta = ui.label("Ningún archivo").classes("h-sub")

            async def subir(e):
                destino = proyecto.salida / "dividir" / "entrada" / e.file.name
                await e.file.save(destino)
                estado["pdf"] = destino
                etiqueta.text = e.file.name

            ui.upload(on_upload=subir, auto_upload=True, label="Subir PDF").props('accept=".pdf" flat bordered').classes("w-[260px]")
            paso(2, "Nombres (opcional)")
            nombres = ui.textarea(placeholder="Un nombre por línea. Déjelo vacío si el PDF tiene marcadores.").classes("w-full").props("outlined autogrow")
            umbral = ui.slider(min=70, max=100, value=90).props("label-always").classes("w-[320px]")
            ui.label("Exigencia de coincidencia del nombre (%)").classes("h-sub -mt-2")
            boton = ui.button("Dividir", icon="call_split").props("unelevated")
            salida = ui.column().classes("w-full gap-2")

        async def ejecutar():
            if not estado["pdf"]:
                ui.notify("Suba un PDF primero", type="warning")
                return
            lista = [n.strip() for n in (nombres.value or "").splitlines() if n.strip()] or None
            carpeta = proyecto.salida / "dividir" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
            boton.props("loading")
            try:
                r = await run.io_bound(utilidades.dividir_pdf, estado["pdf"], carpeta, lista, int(umbral.value))
            except Exception as e:  # noqa: BLE001
                ui.notify(str(e), type="negative")
                return
            finally:
                boton.props(remove="loading")
            salida.clear()
            with salida:
                ui.label(f"{len(r.archivos)} archivos (por {r.metodo})"
                         + (f" · {len(r.sin_encontrar)} nombres sin encontrar" if r.sin_encontrar else "")).classes("font-semibold")
                if r.sin_encontrar:
                    ui.label("Sin encontrar: " + ", ".join(r.sin_encontrar)).classes("text-negative text-[13px]")
                zip_ = comprimir(r.archivos, carpeta / "cartas.zip", carpeta) if r.archivos else None
                with ui.row().classes("gap-2"):
                    ui.button("Abrir carpeta", icon="folder_open", on_click=lambda: abrir_carpeta(carpeta)).props("unelevated")
                    if zip_:
                        ui.button("Descargar ZIP", icon="download", on_click=lambda: ui.download.file(zip_)).props("outline")

        boton.on_click(ejecutar)


@ui.page("/logo")
def logo():
    marco("logo")
    proyecto = proyecto_actual()
    entrada = proyecto.salida / "logo" / "entrada" / datetime.now().strftime("%Y%m%d%H%M%S")
    estado = {"fotos": [], "logo": proyecto.marca("logo")}
    with contenido():
        encabezado("Logo en fotos", "Pone el logo en una esquina de cada foto. Los originales no se modifican.")
        with ui.row().classes("w-full gap-6 no-wrap max-md:flex-wrap items-start"):
            with ui.column().classes("tarjeta p-6 flex-1 gap-4"):
                paso(1, "Fotos")
                cuenta = ui.label("0 fotos").classes("h-sub")

                async def subir_foto(e):
                    destino = entrada / e.file.name
                    await e.file.save(destino)
                    estado["fotos"].append(destino)
                    cuenta.text = f"{len(estado['fotos'])} fotos"
                    if len(estado["fotos"]) == 1:
                        await actualizar_previa()

                ui.upload(on_upload=subir_foto, auto_upload=True, multiple=True, label="Subir fotos").props('accept="image/*" flat bordered').classes("w-full")
                paso(2, "Logo")
                etiqueta_logo = ui.label(estado["logo"].name if estado["logo"] else "Sin logo").classes("h-sub")

                async def subir_logo(e):
                    destino = entrada / ("logo_" + e.file.name)
                    await e.file.save(destino)
                    estado["logo"] = destino
                    etiqueta_logo.text = e.file.name
                    await actualizar_previa()

                ui.upload(on_upload=subir_logo, auto_upload=True, label="Otro logo (PNG)").props('accept=".png" flat bordered').classes("w-full")
                paso(3, "Posición")
                esquina = ui.toggle({k: k.replace("-", " ") for k in utilidades.ESQUINAS}, value="arriba-izquierda").props("dense no-caps")
                tamano = ui.slider(min=10, max=45, value=26).props("label-always")
                ui.label("Ancho del logo (% de la foto)").classes("h-sub -mt-2")
                boton = ui.button("Aplicar a todas", icon="auto_fix_high").props("unelevated")
                salida = ui.column().classes("w-full gap-2")
            with ui.column().classes("tarjeta p-6 flex-1 gap-3 items-center"):
                ui.label("Vista previa").classes("kpi-et self-start")
                previa = ui.image().classes("w-full rounded")

        async def actualizar_previa():
            if not estado["fotos"] or not estado["logo"]:
                return
            from PIL import Image

            datos_jpg = await run.io_bound(utilidades.poner_logo, estado["fotos"][0].read_bytes(), Image.open(estado["logo"]),
                                           esquina.value, tamano.value / 100)
            previa.set_source("data:image/jpeg;base64," + base64.b64encode(datos_jpg).decode())

        esquina.on_value_change(actualizar_previa)
        tamano.on("change", actualizar_previa)

        async def aplicar():
            if not estado["fotos"] or not estado["logo"]:
                ui.notify("Suba fotos y un logo", type="warning")
                return
            carpeta = proyecto.salida / "logo" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
            boton.props("loading")
            try:
                hechas, fallidas = await run.io_bound(utilidades.poner_logo_en_carpeta, estado["fotos"], estado["logo"], carpeta,
                                                      esquina=esquina.value, proporcion=tamano.value / 100)
            finally:
                boton.props(remove="loading")
            salida.clear()
            with salida:
                ui.label(f"{len(hechas)} fotos listas" + (f" · {len(fallidas)} con error" if fallidas else "")).classes("font-semibold")
                for f in fallidas:
                    ui.label(f).classes("text-negative text-[12px]")
                zip_ = comprimir(hechas, carpeta / "fotos_con_logo.zip", carpeta) if hechas else None
                with ui.row().classes("gap-2"):
                    ui.button("Abrir carpeta", icon="folder_open", on_click=lambda: abrir_carpeta(carpeta)).props("unelevated")
                    if zip_:
                        ui.button("Descargar ZIP", icon="download", on_click=lambda: ui.download.file(zip_)).props("outline")

        boton.on_click(aplicar)


def iniciar(puerto: int = 8080, abrir_navegador: bool = True):
    ui.run(title="Epistolēgraphos", favicon="✉️", port=puerto, reload=False, show=abrir_navegador,
           language="es", dark=False)
