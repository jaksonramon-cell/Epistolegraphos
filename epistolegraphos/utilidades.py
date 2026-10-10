"""The two small tools: split a merged print PDF into one file per donor, and stamp a logo on photos."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps
from rapidfuzz import fuzz

from .gramatica import clave, sin_tildes


def _archivo_seguro(nombre: str) -> str:
    return re.sub(r"[^\w\- ]+", "", sin_tildes(nombre)).strip() or "sin_nombre"


# ─── PDF splitter ───────────────────────────────────────────────────────────────
@dataclass
class Division:
    archivos: list[Path] = field(default_factory=list)
    sin_encontrar: list[str] = field(default_factory=list)
    metodo: str = ""


def dividir_pdf(pdf: Path, carpeta: Path, nombres: list[str] | None = None, umbral: int = 90) -> Division:
    """Splits a merged PDF into one file per letter.

    With bookmarks (the print files this app generates have one per donor) those are used.
    Otherwise each name is looked for in the top third of every page: a page where a name
    appears starts that donor's letter, which runs until the next start page. Letters can have
    any number of pages (the old tool assumed exactly two).
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    resultado = Division()
    with pymupdf.open(pdf) as doc:
        inicios: list[tuple[int, str]] = []
        marcadores = [(pagina - 1, titulo) for nivel, titulo, pagina in doc.get_toc() if nivel == 1]
        if marcadores and not nombres:
            inicios = marcadores
            resultado.metodo = "marcadores"
        else:
            if not nombres:
                raise ValueError("El PDF no tiene marcadores: indique la lista de nombres.")
            resultado.metodo = "nombres"
            cabeceras = []
            for pagina in doc:
                alto = pagina.rect.height / 3
                texto = " ".join(b[4] for b in pagina.get_text("blocks") if b[1] < alto)
                cabeceras.append([clave(linea) for linea in texto.splitlines() if linea.strip()])
            usados = set()
            for nombre in nombres:
                objetivo = clave(nombre)
                mejor, puntaje = None, 0
                for i, lineas in enumerate(cabeceras):
                    if i in usados:
                        continue
                    for linea in lineas:
                        s = fuzz.ratio(objetivo, linea)
                        if s > puntaje:
                            mejor, puntaje = i, s
                if mejor is not None and puntaje >= umbral:
                    usados.add(mejor)
                    inicios.append((mejor, nombre))
                else:
                    resultado.sin_encontrar.append(nombre)
            inicios.sort()

        for k, (inicio, nombre) in enumerate(inicios):
            fin = inicios[k + 1][0] - 1 if k + 1 < len(inicios) else doc.page_count - 1
            destino = carpeta / f"{_archivo_seguro(nombre)}.pdf"
            n = 2
            while destino in resultado.archivos:  # two donors with the same name
                destino = carpeta / f"{_archivo_seguro(nombre)} ({n}).pdf"
                n += 1
            with pymupdf.open() as nuevo:
                nuevo.insert_pdf(doc, from_page=inicio, to_page=fin)
                nuevo.save(destino)
            resultado.archivos.append(destino)
    return resultado


# ─── logo on photos ─────────────────────────────────────────────────────────────
ESQUINAS = {"arriba-izquierda": (0, 0), "arriba-derecha": (1, 0), "abajo-izquierda": (0, 1), "abajo-derecha": (1, 1)}


def poner_logo(foto: bytes, logo: Image.Image, esquina: str = "arriba-izquierda", proporcion: float = 0.26) -> bytes:
    """Returns the photo as JPEG with the logo pasted in a corner. Respects the camera's
    rotation (EXIF), so phone photos do not come out sideways."""
    imagen = ImageOps.exif_transpose(Image.open(io.BytesIO(foto))).convert("RGB")
    ancho = int(imagen.width * (proporcion * 1.25 if imagen.height > imagen.width else proporcion))
    marca = logo.convert("RGBA")
    marca = marca.resize((ancho, int(ancho * marca.height / marca.width)), Image.LANCZOS)
    margen = int(imagen.width * 0.02)
    cx, cy = ESQUINAS[esquina]
    x = margen if cx == 0 else imagen.width - marca.width - margen
    y = margen if cy == 0 else imagen.height - marca.height - margen
    imagen.paste(marca, (x, y), marca)
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", quality=92, optimize=True)
    return salida.getvalue()


def poner_logo_en_carpeta(fotos: list[Path], logo: Path, carpeta: Path, **opciones) -> tuple[list[Path], list[str]]:
    """Writes stamped copies to `carpeta`; originals are never touched."""
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = Image.open(logo)
    hechas, fallidas = [], []
    for foto in fotos:
        try:
            destino = carpeta / (foto.stem + ".jpg")
            destino.write_bytes(poner_logo(foto.read_bytes(), marca, **opciones))
            hechas.append(destino)
        except Exception as e:  # noqa: BLE001 - report and keep going
            fallidas.append(f"{foto.name}: {e}")
    return hechas, fallidas
