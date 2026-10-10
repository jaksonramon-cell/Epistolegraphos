"""HTML -> PDF, batch generation, the print file and the run log."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd
import pymupdf
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape

from .cartas import Carta
from .proyecto import Proyecto

PLANTILLAS = Path(__file__).parent / "plantillas"


def entorno(proyecto: Proyecto) -> Environment:
    """Bundled templates, overridable by a project's own plantillas/ folder."""
    cargadores = [FileSystemLoader(PLANTILLAS)]
    if proyecto.ruta("plantillas").is_dir():
        cargadores.insert(0, FileSystemLoader(proyecto.ruta("plantillas")))
    return Environment(loader=ChoiceLoader(cargadores), autoescape=select_autoescape(["html"]))


def html_de(proyecto: Proyecto, carta: Carta, env: Environment | None = None) -> str:
    env = env or entorno(proyecto)
    marca = {n: (p.as_uri() if (p := proyecto.marca(n)) else None) for n in ("logo", "firma", "qr")}
    return env.get_template("carta.html").render(carta=carta, f=carta.principal, config=proyecto.config, **marca)


def _pdf(html: str, base: str, destino: str | None = None) -> tuple[int, bytes | None]:
    """Runs in a worker process. Returns (pages, pdf bytes when no destination is given)."""
    from weasyprint import HTML

    documento = HTML(string=html, base_url=base).render()
    if destino:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        documento.write_pdf(destino)
        return len(documento.pages), None
    return len(documento.pages), documento.write_pdf()


def vista_previa(proyecto: Proyecto, carta: Carta, escala: float = 1.4) -> list[bytes]:
    """PNG images of every page of one letter, for the preview panel."""
    _, datos = _pdf(html_de(proyecto, carta), str(proyecto.carpeta))
    with pymupdf.open(stream=datos, filetype="pdf") as doc:
        return [pagina.get_pixmap(matrix=pymupdf.Matrix(escala, escala)).tobytes("png") for pagina in doc]


@dataclass
class Resultado:
    carpeta: Path
    generadas: int = 0
    omitidas: int = 0
    fallidas: int = 0
    cancelado: bool = False
    impresion: list[Path] = field(default_factory=list)
    registro: Path | None = None
    segundos: float = 0.0


Progreso = Callable[[int, int, str], None]


def generar(proyecto: Proyecto, cartas: list[Carta], carpeta: Path, progreso: Progreso | None = None,
            cancelar: threading.Event | None = None, procesos: int | None = None,
            incluir_con_error: bool = False) -> Resultado:
    """Writes one PDF per letter (in parallel), one merged print file per sheet for the physical
    letters, and registro.xlsx with what happened to every donor."""
    inicio = time.time()
    resultado = Resultado(carpeta)
    env = entorno(proyecto)
    progreso = progreso or (lambda *_: None)
    cancelar = cancelar or threading.Event()

    filas_registro = []
    trabajos = []
    for carta in cartas:
        fila = {
            "hoja": carta.hoja, "tipo": carta.tipo, "id_padrino": carta.principal.id_padrino,
            "padrino": carta.padrino, "canal": "digital" if carta.digital else "física",
            "ninos": ", ".join(carta.ninos), "programas": ", ".join(carta.programas),
            "estado": carta.estado, "detalle": "; ".join(carta.errores + carta.avisos),
            "archivo": "", "paginas": 0,
        }
        filas_registro.append(fila)
        if carta.errores and not incluir_con_error:
            fila["estado"] = "omitida"
            resultado.omitidas += 1
            continue
        trabajos.append((carta, fila, carpeta / carta.archivo()))

    total = len(trabajos)
    procesos = procesos or max(1, min(8, (os.cpu_count() or 2) - 1))
    hechas = 0

    def terminado(carta, fila, destino, paginas=0, error=None):
        nonlocal hechas
        hechas += 1
        if error:
            fila["estado"] = "falló"
            fila["detalle"] = f"{fila['detalle']}; {error}".strip("; ")
            resultado.fallidas += 1
        else:
            fila["archivo"] = str(destino.relative_to(carpeta))
            fila["paginas"] = paginas
            resultado.generadas += 1
        progreso(hechas, total, carta.padrino)

    base = str(proyecto.carpeta)
    if procesos > 1 and total > 3:
        with ProcessPoolExecutor(max_workers=procesos) as pool:
            futuros = {pool.submit(_pdf, html_de(proyecto, c, env), base, str(d)): (c, f, d) for c, f, d in trabajos}
            for futuro in as_completed(futuros):
                c, f, d = futuros[futuro]
                if cancelar.is_set():
                    for pendiente in futuros:
                        pendiente.cancel()
                    resultado.cancelado = True
                    break
                try:
                    terminado(c, f, d, futuro.result()[0])
                except Exception as e:  # noqa: BLE001 - one bad letter must not stop the batch
                    terminado(c, f, d, error=str(e))
    else:
        for c, f, d in trabajos:
            if cancelar.is_set():
                resultado.cancelado = True
                break
            try:
                terminado(c, f, d, _pdf(html_de(proyecto, c, env), base, str(d))[0])
            except Exception as e:  # noqa: BLE001
                terminado(c, f, d, error=str(e))

    if not resultado.cancelado:
        resultado.impresion = _archivos_de_impresion(carpeta, trabajos)
    resultado.registro = carpeta / "registro.xlsx"
    carpeta.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas_registro).to_excel(resultado.registro, index=False)
    resultado.segundos = time.time() - inicio
    return resultado


def _archivos_de_impresion(carpeta: Path, trabajos) -> list[Path]:
    """All physical letters of a sheet in one PDF, with a bookmark per donor (the splitter can use them)."""
    por_hoja: dict[Path, list[tuple[str, Path]]] = {}
    for carta, fila, destino in trabajos:
        if not carta.digital and fila["archivo"]:
            por_hoja.setdefault(destino.parent.parent, []).append((carta.padrino, destino))
    salidas = []
    for hoja, cartas in por_hoja.items():
        salida = hoja / "impresion_fisicas.pdf"
        with pymupdf.open() as unido:
            indice = []
            for nombre, ruta in cartas:
                indice.append([1, nombre, unido.page_count + 1])
                with pymupdf.open(ruta) as doc:
                    unido.insert_pdf(doc)
            unido.set_toc(indice)
            unido.save(salida, garbage=3, deflate=True)
        salidas.append(salida)
    return salidas
