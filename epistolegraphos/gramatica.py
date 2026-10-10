"""Small Spanish grammar helpers used by the letter texts.

The spreadsheets come from a CRM, so names arrive in any case and with stray spaces,
and the texts must agree in gender and number with the donor and the children.
"""

from __future__ import annotations

import re
import unicodedata

_PARTICULAS = {"de", "del", "la", "las", "los", "y", "e", "da", "van", "von"}


def sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def clave(texto: str) -> str:
    """Comparison key: no accents, lower case, only letters and digits."""
    return re.sub(r"[^a-z0-9]+", "", sin_tildes(str(texto)).lower())


def limpiar(valor) -> str:
    """Cell value to clean text. Empty cells, NaN and the CRM's '0' placeholders become ''."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat", "0"}:
        return ""
    if re.fullmatch(r"\d+\.0", texto):  # numbers read as float by Excel
        texto = texto[:-2]
    return re.sub(r"\s+", " ", texto)


def nombre_propio(nombre: str) -> str:
    """'MARÍA  DE LOS ángeles' -> 'María de los Ángeles'."""
    palabras = limpiar(nombre).split(" ")
    salida = []
    for i, p in enumerate(palabras):
        if not p:
            continue
        if i > 0 and p.lower() in _PARTICULAS:
            salida.append(p.lower())
        else:
            salida.append("-".join(s[:1].upper() + s[1:].lower() for s in p.split("-")))
    return " ".join(salida)


def primer_nombre(nombre: str) -> str:
    partes = nombre_propio(nombre).split(" ")
    return partes[0] if partes and partes[0] else ""


def _suena_i(palabra: str) -> bool:
    p = sin_tildes(palabra).lower()
    # "y" becomes "e" before an /i/ sound: Isabel, Hilda; not before a diphthong: hielo, hiato.
    if p.startswith("hi"):
        return len(p) < 3 or p[2] not in "aeou"
    return p.startswith("i") and not (len(p) > 1 and p[1] in "aeou")


def _suena_o(palabra: str) -> bool:
    p = sin_tildes(palabra).lower()
    return p.startswith("o") or p.startswith("ho")


def unir(elementos, conjuncion: str = "y") -> str:
    """['Ana', 'Luis', 'Isabel'] -> 'Ana, Luis e Isabel'. Uses 'e'/'u' where Spanish requires it."""
    items = [str(x).strip() for x in elementos if str(x).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    ultimo = items[-1]
    conj = conjuncion
    if conjuncion == "y" and _suena_i(ultimo):
        conj = "e"
    elif conjuncion == "o" and _suena_o(ultimo):
        conj = "u"
    return f"{', '.join(items[:-1])} {conj} {ultimo}"


def genero_desde_saludo(saludo: str) -> str | None:
    """'Estimada' / 'Querida' -> 'f'; 'Estimado' -> 'm'; anything else -> None (neutral)."""
    s = clave(saludo)
    if not s:
        return None
    if s.endswith("a") or "senora" in s:
        return "f"
    if s.endswith("o") or "senor" in s:
        return "m"
    return None


def genero_desde_celda(valor: str) -> str | None:
    s = clave(valor)
    if s in {"f", "femenino", "mujer", "nina", "fem"}:
        return "f"
    if s in {"m", "masculino", "hombre", "nino", "masc"}:
        return "m"
    return None


def genero_grupo(generos) -> str | None:
    """Gender for agreement of a group: all 'f' -> 'f'; any 'm' -> 'm'; unknown -> None."""
    generos = list(generos)
    if not generos or any(g is None for g in generos):
        return None
    return "f" if all(g == "f" for g in generos) else "m"


def concordar(genero: str | None, plural: bool, m: str, f: str, pm: str | None = None, pf: str | None = None) -> str:
    """Pick the word form. Unknown gender gives a neutral 'o(a)' form."""
    pm = pm or m + "s"
    pf = pf or f + "s"
    if genero == "f":
        return pf if plural else f
    if genero == "m":
        return pm if plural else m
    return f"{pm}(as)" if plural else f"{m}(a)"


def nombre_programa(programa: str) -> str:
    """Program name without a leading 'Programa', so texts can write 'el Programa {{ ... }}' safely."""
    p = limpiar(programa)
    return re.sub(r"^programa\s+", "", p, flags=re.IGNORECASE)


_GUION = r"\s+-\s*|\s*-\s+"  # a dash with a space on one side; 'Quibdó-Chocó' stays whole


def lugar_programa(programa: str) -> str:
    """'Quibdó - Fortalecimiento Familiar' -> 'Quibdó'; 'Programa Chocó' -> 'Chocó'."""
    return re.split(_GUION, nombre_programa(programa))[0].strip()


def programa_legible(programa: str) -> str:
    """For running text: 'Programa Chocó' -> 'Programa Chocó';
    'Tumaco - Fortalecimiento Familiar' -> 'programa de Fortalecimiento Familiar en Tumaco'."""
    partes = re.split(_GUION, nombre_programa(programa), maxsplit=1)
    if len(partes) == 2 and partes[1].strip():
        return f"programa de {partes[1].strip()} en {partes[0].strip()}"
    return f"Programa {nombre_programa(programa)}"
