from pathlib import Path

import pandas as pd
import pymupdf
import pytest

from epistolegraphos import cartas, datos, render, utilidades
from epistolegraphos.proyecto import Proyecto

DEMO = Path(__file__).resolve().parent.parent / "demo"


@pytest.fixture(scope="module")
def proyecto():
    return Proyecto(DEMO)


def leer(nombre, *hojas):
    ruta = DEMO / "datos" / nombre
    return [f for h in (hojas or datos.hojas_de(ruta)) for f in datos.leer_hoja(ruta, h).filas]


def test_encabezados_del_crm_se_reconocen():
    mapa = datos.mapear_columnas(["ID De Contacto ", "Nombre_Padrino", "Saludo ", "Dirección", "Nombre Completo NNJA",
                                  "AldeaPrograma", "ID Nombre niño NUEVO Completo ", "PSN Nombre niño NUEVO Completo "])
    assert {"id_padrino", "padrino", "saludo", "direccion", "nino", "programa", "nuevo_nino", "nuevo_programa"} <= set(mapa)
    assert datos.mapear_columnas(["nombre_completo_padrino", "Direccion "])["padrino"] == "nombre_completo_padrino"


def test_digital_por_hoja_o_direccion():
    filas = leer("padrinos_ninos.xlsx", "UNI DIGITAL")
    assert filas and all(f.digital for f in filas)
    multi = leer("padrinos_ninos.xlsx", "MULTI")
    assert any(f.digital for f in multi) and not all(f.digital for f in multi)


def test_un_padrino_con_varios_ninos_recibe_una_carta(proyecto):
    filas = leer("padrinos_ninos.xlsx", "MULTI")
    lista = cartas.construir(proyecto, cartas.HISTORIAS, filas)
    assert len(lista) == len({f.id_padrino for f in filas})
    varios = next(c for c in lista if len(c.ninos) > 1)
    assert varios.titulo.startswith("Padrinazgo de ")
    assert " y " in varios.titulo or " e " in varios.titulo


def test_la_revision_encuentra_los_problemas(proyecto):
    lista = cartas.construir(proyecto, cartas.HISTORIAS, leer("padrinos_ninos.xlsx", "UNI FISICO"))
    errores = " | ".join(e for c in lista for e in c.errores)
    assert "Samuel Antonio Rentería" in errores
    assert "sin dirección" in errores
    assert any("sin saludo" in a for c in lista for a in c.avisos)


def test_ninos_con_el_mismo_nombre_no_se_mezclan(proyecto):
    choco, _ = proyecto.buscar_nino("Programa Chocó", "María José Mosquera")
    guajira, _ = proyecto.buscar_nino("Programa Guajira", "María José Mosquera")
    assert choco != guajira
    assert "Chocó" in choco.parent.name and "Guajira" in guajira.parent.name


def test_variable_desconocida_es_un_error(proyecto, tmp_path, monkeypatch):
    monkeypatch.setattr(proyecto, "texto", lambda nombre: "Hola, {{ nombre_que_no_existe }}")
    carta = cartas.construir(proyecto, cartas.PROGRAMA, leer("padrinos_programa.xlsx")[:1])[0]
    assert any("variable desconocida" in e for e in carta.errores)


def test_egreso_a_programa_y_a_nino(proyecto):
    lista = cartas.construir(proyecto, cartas.EGRESO, leer("egresos.xlsx"))
    textos = [c.bloques[-1].html for c in lista]
    assert any("Programa Chocó" in t for t in textos)
    assert any('class="nino"' in t for t in textos)
    assert all(c.saludo_inicial.startswith("Hola, ") for c in lista)


def test_generar_pdfs_impresion_y_division(proyecto, tmp_path):
    lista = cartas.construir(proyecto, cartas.PROGRAMA, leer("padrinos_programa.xlsx", "PROGRAMA FISICO")[:3])
    r = render.generar(proyecto, lista, tmp_path, procesos=1)
    assert r.generadas == 3 and r.fallidas == 0
    assert len(pd.read_excel(r.registro)) == 3
    [impresion] = r.impresion
    with pymupdf.open(impresion) as doc:
        assert len(doc.get_toc()) == 3
    division = utilidades.dividir_pdf(impresion, tmp_path / "division")
    assert division.metodo == "marcadores" and len(division.archivos) == 3
