"""Reading the donor spreadsheets.

The CRM exports were never consistent ('Dirección', 'Direccion ', 'dirección'; 'Nombre_Padrino',
'nombre_completo_padrino'...), so every header is normalised and mapped to one canonical field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .gramatica import clave, genero_desde_celda, genero_desde_saludo, limpiar, nombre_propio

# canonical field -> accepted header keys (see gramatica.clave)
ALIAS = {
    "id_padrino": ["iddecontacto", "idcontacto", "idpadrino"],
    "padrino": ["nombrepadrino", "nombrecompletopadrino", "padrino", "nombredonante"],
    "saludo": ["saludo", "tratamiento"],
    "direccion": ["direccion"],
    "ciudad": ["ciudad"],
    "departamento": ["departamento"],
    "correo": ["correo", "email", "correoelectronico"],
    "nino": ["nombrecompletonnja", "nombrecompletonnaj", "nombrecompletonino"],
    "nino_corto": ["nombrennaj", "nombrennja", "nombre"],
    "genero_nino": ["generonnaj", "generonnja", "genero", "sexo"],
    "programa": ["aldeaprograma", "programa", "aldea"],
    "nuevo_nino": ["idnombreninonuevocompleto", "nuevoninocompleto", "nuevonnaj"],
    "nuevo_corto": ["nuevonombre", "nuevonombrepnuevo"],
    "nuevo_genero": ["nuevogenero"],
    "nuevo_programa": ["psnnombreninonuevocompleto", "nuevoprograma"],
}

DIGITAL = {"enviodigital", "digital", "correo", "email"}


@dataclass
class Fila:
    hoja: str
    numero: int  # Excel row number, for messages
    id_padrino: str
    padrino: str
    saludo: str
    direccion: str
    ciudad: str
    departamento: str
    correo: str
    digital: bool
    nino: str = ""
    nino_corto: str = ""
    genero_nino: str | None = None
    programa: str = ""
    nuevo_nino: str = ""
    nuevo_corto: str = ""
    nuevo_genero: str | None = None
    nuevo_programa: str = ""

    @property
    def genero_padrino(self) -> str | None:
        return genero_desde_saludo(self.saludo)


@dataclass
class Hoja:
    nombre: str
    filas: list[Fila] = field(default_factory=list)
    columnas_faltantes: list[str] = field(default_factory=list)

    @property
    def digitales(self) -> int:
        return sum(f.digital for f in self.filas)


def mapear_columnas(columnas) -> dict[str, str]:
    """canonical field -> real column name present in the sheet."""
    por_clave = {clave(c): c for c in columnas}
    mapa = {}
    for campo, alias in ALIAS.items():
        for a in alias:
            if a in por_clave:
                mapa[campo] = por_clave[a]
                break
    return mapa


def hojas_de(ruta: Path) -> list[str]:
    with pd.ExcelFile(ruta) as xls:
        return list(xls.sheet_names)


def leer_hoja(ruta: Path, nombre: str, requeridas=("padrino",)) -> Hoja:
    df = pd.read_excel(ruta, sheet_name=nombre, dtype=str)
    mapa = mapear_columnas(df.columns)
    hoja = Hoja(nombre, columnas_faltantes=[c for c in requeridas if c not in mapa])
    hoja_digital = "digital" in clave(nombre)

    def val(registro, campo):
        col = mapa.get(campo)
        return limpiar(registro.get(col)) if col else ""

    for i, registro in enumerate(df.to_dict("records")):
        padrino = nombre_propio(val(registro, "padrino"))
        if not padrino:
            continue
        direccion = val(registro, "direccion")
        nino = nombre_propio(val(registro, "nino"))
        nino_corto = nombre_propio(val(registro, "nino_corto")) or nino.split(" ")[0]
        nuevo = nombre_propio(val(registro, "nuevo_nino"))
        hoja.filas.append(Fila(
            hoja=nombre,
            numero=i + 2,
            id_padrino=val(registro, "id_padrino") or f"{clave(padrino)}",
            padrino=padrino,
            saludo=val(registro, "saludo").capitalize(),
            direccion=direccion,
            ciudad=nombre_propio(val(registro, "ciudad")),
            departamento=nombre_propio(val(registro, "departamento")),
            correo=val(registro, "correo").lower(),
            digital=hoja_digital or clave(direccion) in DIGITAL,
            nino=nino or nino_corto,
            nino_corto=nino_corto,
            genero_nino=genero_desde_celda(val(registro, "genero_nino")),
            programa=val(registro, "programa"),
            nuevo_nino=nuevo,
            nuevo_corto=nombre_propio(val(registro, "nuevo_corto")) or nuevo.split(" ")[0],
            nuevo_genero=genero_desde_celda(val(registro, "nuevo_genero")),
            nuevo_programa=val(registro, "nuevo_programa"),
        ))
    return hoja


def agrupar_por_padrino(filas: list[Fila]) -> list[list[Fila]]:
    """One group per donor, by CRM contact ID (names are not unique), keeping sheet order."""
    grupos: dict[str, list[Fila]] = {}
    for f in filas:
        grupos.setdefault(f.id_padrino, []).append(f)
    return list(grupos.values())
