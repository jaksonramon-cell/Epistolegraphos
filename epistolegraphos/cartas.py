"""Turns spreadsheet rows into letter models (what goes in each letter), without rendering anything.

Building every model first is what makes the review step possible: missing stories, missing
addresses and template mistakes are all found before a single PDF is written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import markdown
from jinja2 import Environment, StrictUndefined, TemplateError, UndefinedError

from . import gramatica as gr
from .datos import Fila, agrupar_por_padrino
from .proyecto import Historia, Proyecto, leer_historia

HISTORIAS, PROGRAMA, EGRESO = "historias", "programa", "egreso"

_jinja = Environment(undefined=StrictUndefined, autoescape=False)


@dataclass
class Bloque:
    html: str
    titulo: str = ""
    foto: Path | None = None
    pie: str = ""

    def partes(self) -> tuple[str, str]:
        """First paragraph and the rest; the template keeps heading, photo and first paragraph together."""
        corte = self.html.find("</p>")
        return (self.html[:corte + 4], self.html[corte + 4:]) if corte >= 0 else (self.html, "")


@dataclass
class Carta:
    tipo: str
    hoja: str
    filas: list[Fila]
    titulo: str = ""
    saludo_inicial: str = ""
    bloques: list[Bloque] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)  # the letter is not generated
    avisos: list[str] = field(default_factory=list)  # generated, but worth a look

    @property
    def principal(self) -> Fila:
        return self.filas[0]

    @property
    def padrino(self) -> str:
        return self.principal.padrino

    @property
    def digital(self) -> bool:
        return self.principal.digital

    @property
    def ninos(self) -> list[str]:
        return list(dict.fromkeys(f.nino for f in self.filas if f.nino))

    @property
    def programas(self) -> list[str]:
        return list(dict.fromkeys(f.programa for f in self.filas if f.programa))

    @property
    def estado(self) -> str:
        return "error" if self.errores else ("aviso" if self.avisos else "ok")

    def archivo(self) -> Path:
        canal = "digitales" if self.digital else "fisicas"
        nombre = re.sub(r"[^\w\- ]+", "", gr.sin_tildes(self.padrino)).strip() or "sin_nombre"
        sufijo = re.sub(r"[^\w]+", "", self.principal.id_padrino)[-8:]
        return Path(self.tipo, _seguro(self.hoja), canal, f"{nombre} ({sufijo}).pdf")


def _seguro(texto: str) -> str:
    return re.sub(r"[^\w\- ]+", "", gr.sin_tildes(texto)).strip().replace(" ", "_") or "hoja"


def _md(texto: str) -> str:
    return markdown.markdown(texto, extensions=["extra", "sane_lists"]) if texto.strip() else ""


def _render(texto: str, contexto: dict, carta: Carta, origen: str) -> str:
    try:
        return _jinja.from_string(texto).render(**contexto)
    except UndefinedError as e:
        carta.errores.append(f"{origen}: variable desconocida ({e.message})")
    except TemplateError as e:
        carta.errores.append(f"{origen}: error en la plantilla ({e})")
    return ""


def _contexto_padrino(f: Fila) -> dict:
    g = f.genero_padrino
    return {
        "padrino": f.padrino,
        "primer_nombre": gr.primer_nombre(f.padrino),
        "saludo": f.saludo or gr.concordar(g, False, "Estimado", "Estimada"),
        "gp": lambda m, fem: gr.concordar(g, False, m, fem),
        "unir": gr.unir,
    }


def _remitente(carta: Carta):
    f = carta.principal
    if not f.saludo:
        carta.avisos.append("sin saludo: se usará 'Estimado(a)'")
    if not f.digital and not (f.direccion and f.ciudad):
        carta.errores.append("carta física sin dirección o ciudad completa")


def _secciones(historia: Historia, contexto: dict, carta: Carta) -> list[Bloque]:
    bloques = []
    for s in historia.secciones:
        html = _md(_render(s.markdown, contexto, carta, historia.ruta.name))
        bloques.append(Bloque(html, titulo=_render(s.titulo, contexto, carta, historia.ruta.name),
                              foto=s.foto, pie=s.pie))
    return bloques


def _texto(proyecto: Proyecto, nombre: str, contexto: dict, carta: Carta) -> str:
    plantilla = proyecto.texto(nombre)
    if plantilla is None:
        carta.errores.append(f"falta el texto textos/{nombre}.md")
        return ""
    contexto = contexto | {"organizacion": proyecto.config.get("organizacion", "")}
    return _md(_render(plantilla, contexto, carta, f"{nombre}.md"))


# ─── sponsorship letters (one child, several children, or a program) ─────────────
def _carta_padrinazgo(proyecto: Proyecto, filas: list[Fila]) -> Carta:
    con_nino = [f for f in filas if f.nino]
    tipo = HISTORIAS if con_nino else PROGRAMA
    carta = Carta(tipo, filas[0].hoja, filas)
    _remitente(carta)

    if tipo == PROGRAMA:
        return _carta_programa(proyecto, carta)

    # children grouped by program, in sheet order
    por_programa: dict[str, list[Fila]] = {}
    for f in con_nino:
        if f.nino not in [x.nino for x in por_programa.get(f.programa, [])]:
            por_programa.setdefault(f.programa, []).append(f)
    todos = [f for grupo in por_programa.values() for f in grupo]

    g_ninos = gr.genero_grupo(f.genero_nino for f in todos)
    plural = len(todos) > 1
    if g_ninos is None:
        carta.avisos.append("género del niño/niña sin dato: se usan formas neutras")

    contexto = _contexto_padrino(filas[0]) | {
        "ninos": gr.unir(f.nino_corto for f in todos),
        "n_ninos": len(todos),
        "plural": plural,
        "ahijado": ("tus " if plural else "tu ") + gr.concordar(g_ninos, plural, "ahijado", "ahijada"),
        "gn": lambda m, fem, pm=None, pf=None: gr.concordar(g_ninos, plural, m, fem, pm, pf),
        "programas": gr.unir(gr.nombre_programa(p) for p in por_programa),
        "lugares": gr.unir(gr.lugar_programa(p) for p in por_programa),
        "ninos_por_programa": gr.unir(
            f"{gr.unir(f.nino_corto for f in grupo)} en el {gr.programa_legible(p)}"
            for p, grupo in por_programa.items()
        ),
    }
    carta.titulo = f"Padrinazgo de {contexto['ninos']} en {contexto['lugares']}"
    carta.bloques.append(Bloque(_texto(proyecto, "historias_intro", contexto, carta)))

    for programa, grupo in por_programa.items():
        for f in grupo:
            ruta, problema = proyecto.buscar_nino(programa, f.nino, f.nino_corto)
            if not ruta:
                carta.errores.append(problema)
                continue
            ctx = contexto | {"nino": f.nino_corto, "g": lambda m, fem, _g=f.genero_nino: gr.concordar(_g, False, m, fem)}
            carta.bloques += _secciones(leer_historia(ruta), ctx, carta)
        historias = proyecto.historias_programa(programa)
        if not historias:
            carta.avisos.append(f"no hay historias del programa {programa}")
        for ruta in historias:
            carta.bloques += _secciones(leer_historia(ruta), contexto | {"programa": gr.nombre_programa(programa)}, carta)

    # rows of the same donor without a child: add that program's stories too
    for programa in dict.fromkeys(f.programa for f in filas if not f.nino and f.programa):
        if programa not in por_programa:
            for ruta in proyecto.historias_programa(programa):
                carta.bloques += _secciones(leer_historia(ruta), contexto | {"programa": gr.nombre_programa(programa)}, carta)

    carta.bloques.append(Bloque(_texto(proyecto, "historias_cierre", contexto, carta)))
    return carta


def _carta_programa(proyecto: Proyecto, carta: Carta) -> Carta:
    programas = carta.programas
    if not programas:
        carta.errores.append("la fila no tiene niño ni programa")
        return carta
    contexto = _contexto_padrino(carta.principal) | {
        "programas": gr.unir(gr.nombre_programa(p) for p in programas),
        "lugares": gr.unir(gr.lugar_programa(p) for p in programas),
        "plural": len(programas) > 1,
    }
    carta.titulo = f"Tu apoyo en {contexto['lugares']}"
    carta.bloques.append(Bloque(_texto(proyecto, "programa_intro", contexto, carta)))
    for programa in programas:
        historias = proyecto.historias_programa(programa)
        if not historias:
            carta.errores.append(f"no hay historias del programa {programa}")
        for ruta in historias:
            carta.bloques += _secciones(leer_historia(ruta), contexto | {"programa": gr.nombre_programa(programa)}, carta)
    carta.bloques.append(Bloque(_texto(proyecto, "programa_cierre", contexto, carta)))
    return carta


def cartas_de_padrinazgo(proyecto: Proyecto, filas: list[Fila]) -> list[Carta]:
    return [_carta_padrinazgo(proyecto, grupo) for grupo in agrupar_por_padrino(filas)]


# ─── departure letters (a child leaves; the donor is moved to a new child or program) ─
def _es_programa(f: Fila) -> bool:
    nuevo = gr.clave(f.nuevo_nino)
    return not nuevo or nuevo == gr.clave(f.nuevo_programa) or nuevo.startswith("programa")


def _destacar(html: str, nombre: str) -> str:
    if not nombre:
        return html
    patron = r"(?<![\w>])" + re.escape(nombre) + r"(?!\w)"
    return re.sub(patron, f'<span class="destacado">{nombre}</span>', html, count=1)


def _carta_egreso(proyecto: Proyecto, filas: list[Fila]) -> Carta:
    carta = Carta(EGRESO, filas[0].hoja, filas)
    _remitente(carta)
    contexto = _contexto_padrino(filas[0])
    carta.saludo_inicial = f"Hola, {contexto['primer_nombre']}:"

    nuevos = []
    for f in filas:
        ruta = proyecto.buscar_egreso(f.nino, f.nino_corto)
        if not ruta:
            carta.errores.append(f"no hay texto de egreso para {f.nino}")
            continue
        historia = leer_historia(ruta)
        ctx = contexto | {"nino": f.nino_corto, "g": lambda m, fem, _g=f.genero_nino: gr.concordar(_g, False, m, fem)}
        for b in _secciones(historia, ctx, carta):
            b.html = _destacar(b.html, f.nino_corto)
            carta.bloques.append(b)
        programa = gr.programa_legible(f.nuevo_programa or f.nuevo_nino)
        if _es_programa(f):
            nuevos.append(f'al <span class="programa">{programa}</span>')
        else:
            nuevos.append(f'a <span class="nino">{f.nuevo_corto}</span> del <span class="programa">{programa}</span>')

    solo_programas = all(_es_programa(f) for f in filas)
    contexto |= {
        "nuevos": gr.unir(nuevos),
        "solo_programas": solo_programas,
        "plural": len(filas) > 1,
    }
    carta.bloques.append(Bloque(_texto(proyecto, "egreso_cierre", contexto, carta)))
    return carta


def cartas_de_egreso(proyecto: Proyecto, filas: list[Fila]) -> list[Carta]:
    return [_carta_egreso(proyecto, grupo) for grupo in agrupar_por_padrino(filas)]


def construir(proyecto: Proyecto, tipo: str, filas: list[Fila]) -> list[Carta]:
    return cartas_de_egreso(proyecto, filas) if tipo == EGRESO else cartas_de_padrinazgo(proyecto, filas)
