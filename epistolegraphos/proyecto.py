"""A project is a folder with the spreadsheets, the stories, the photos and the brand assets.

    proyecto.json                     organisation, signer, colours
    datos/*.xlsx                      donor spreadsheets
    textos/*.md                       intro and closing paragraphs (Jinja + Markdown)
    historias/ninos/<programa>/<Nombre Completo>.md   (+ .jpg/.png photo, + .txt caption)
    historias/programas/<programa>/<01 título>.md     (+ photo, + caption)
    historias/egresos/<Nombre Completo>.md
    marca/logo.png, firma.png, qr.png
    plantillas/                       optional, overrides the bundled letter templates
    salida/                           generated letters
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .gramatica import clave, nombre_programa

IMAGENES = (".jpg", ".jpeg", ".png")

CONFIG_INICIAL = {
    "organizacion": "Mi organización",
    "firmante": {"nombre": "", "cargo": "", "direccion": "", "correo": ""},
    "color_primario": "#0b7a75",
    "color_acento": "#e4572e",
}


@dataclass
class Seccion:
    titulo: str
    markdown: str
    foto: Path | None = None
    pie: str = ""


@dataclass
class Historia:
    ruta: Path
    secciones: list[Seccion] = field(default_factory=list)


def leer_historia(ruta: Path) -> Historia:
    """A story file holds one or more sections, each starting with '# Título'.
    A photo with the same file name is attached to the first section; a .txt with that name is its caption."""
    texto = ruta.read_text(encoding="utf-8").replace("\r\n", "\n")
    secciones: list[Seccion] = []
    actual = Seccion("", "")
    for linea in texto.split("\n"):
        if linea.startswith("# "):
            if actual.titulo or actual.markdown.strip():
                secciones.append(actual)
            actual = Seccion(linea[2:].strip(), "")
        else:
            actual.markdown += linea + "\n"
    if actual.titulo or actual.markdown.strip():
        secciones.append(actual)

    foto = next((ruta.with_suffix(ext) for ext in IMAGENES if ruta.with_suffix(ext).exists()), None)
    if foto and secciones:
        secciones[0].foto = foto
        pie = ruta.with_suffix(".txt")
        secciones[0].pie = pie.read_text(encoding="utf-8").strip() if pie.exists() else ""
    return Historia(ruta, secciones)


def _clave_programa(nombre: str) -> str:
    return clave(nombre_programa(nombre))


class Proyecto:
    def __init__(self, carpeta: Path | str):
        self.carpeta = Path(carpeta).expanduser().resolve()
        self.config = dict(CONFIG_INICIAL)
        archivo = self.carpeta / "proyecto.json"
        if archivo.exists():
            self.config.update(json.loads(archivo.read_text(encoding="utf-8")))
        self._indexar()

    # --- paths -------------------------------------------------------------
    def ruta(self, *partes) -> Path:
        return self.carpeta.joinpath(*partes)

    @property
    def salida(self) -> Path:
        return self.ruta("salida")

    def excels(self) -> list[Path]:
        carpeta = self.ruta("datos")
        if not carpeta.exists():
            return []
        return sorted(p for p in carpeta.glob("*.xlsx") if not p.name.startswith("~$"))

    def texto(self, nombre: str) -> str | None:
        ruta = self.ruta("textos", f"{nombre}.md")
        return ruta.read_text(encoding="utf-8") if ruta.exists() else None

    def marca(self, nombre: str) -> Path | None:
        for ext in IMAGENES:
            ruta = self.ruta("marca", nombre + ext)
            if ruta.exists():
                return ruta
        return None

    def faltantes(self) -> list[str]:
        """Folders a project needs; used by the home screen."""
        necesarias = ["datos", "textos", "historias/ninos", "historias/programas", "historias/egresos", "marca"]
        return [n for n in necesarias if not self.ruta(n).is_dir()]

    # --- story index (built once; the old app searched the disk for every letter) ---
    def _indexar(self):
        self.ninos: dict[tuple[str, str], Path] = {}
        self.ninos_por_nombre: dict[str, list[Path]] = {}
        self.programas: dict[str, list[Path]] = {}
        self.nombres_programa: dict[str, str] = {}
        self.egresos: dict[str, Path] = {}

        base = self.ruta("historias", "ninos")
        if base.is_dir():
            for md in sorted(base.rglob("*.md")):
                programa = _clave_programa(md.parent.name) if md.parent != base else ""
                self.ninos[(programa, clave(md.stem))] = md
                self.ninos_por_nombre.setdefault(clave(md.stem), []).append(md)

        base = self.ruta("historias", "programas")
        if base.is_dir():
            for carpeta in sorted(p for p in base.iterdir() if p.is_dir()):
                self.programas[_clave_programa(carpeta.name)] = sorted(carpeta.glob("*.md"))
                self.nombres_programa[_clave_programa(carpeta.name)] = carpeta.name

        base = self.ruta("historias", "egresos")
        if base.is_dir():
            for md in sorted(base.rglob("*.md")):
                self.egresos[clave(md.stem)] = md

    def buscar_nino(self, programa: str, *nombres: str) -> tuple[Path | None, str]:
        """Story file for a child. Looks inside the program folder first, so two children with
        the same name in different programs never get each other's story.
        Returns (path, problem)."""
        prog = _clave_programa(programa)
        for nombre in nombres:
            if nombre and (prog, clave(nombre)) in self.ninos:
                return self.ninos[(prog, clave(nombre))], ""
        for nombre in nombres:
            candidatos = self.ninos_por_nombre.get(clave(nombre), []) if nombre else []
            if len(candidatos) == 1:
                return candidatos[0], ""
            if len(candidatos) > 1:
                return None, f"hay {len(candidatos)} historias llamadas '{nombre}' y ninguna en la carpeta de {programa}"
        return None, f"no hay historia para {nombres[0]} ({programa})"

    def historias_programa(self, programa: str) -> list[Path]:
        return self.programas.get(_clave_programa(programa), [])

    def buscar_egreso(self, *nombres: str) -> Path | None:
        for nombre in nombres:
            if nombre and clave(nombre) in self.egresos:
                return self.egresos[clave(nombre)]
        return None
