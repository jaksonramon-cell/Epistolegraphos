import pytest

from epistolegraphos import gramatica as gr


@pytest.mark.parametrize("items, esperado", [
    ([], ""),
    (["Ana"], "Ana"),
    (["Ana", "Luis"], "Ana y Luis"),
    (["Ana", "Luis", "Sofía"], "Ana, Luis y Sofía"),
    (["Juan", "Isabel"], "Juan e Isabel"),
    (["Juan", "Hilda"], "Juan e Hilda"),
    (["agua", "hielo"], "agua y hielo"),  # diphthong: stays "y"
])
def test_unir(items, esperado):
    assert gr.unir(items) == esperado


def test_unir_o_u():
    assert gr.unir(["siete", "ocho"], "o") == "siete u ocho"


@pytest.mark.parametrize("entrada, esperado", [
    ("MARTHA LUCÍA  GÓMEZ RINCÓN", "Martha Lucía Gómez Rincón"),
    ("maría de los ángeles", "María de los Ángeles"),
    ("ana-maría PÉREZ", "Ana-María Pérez"),
])
def test_nombre_propio(entrada, esperado):
    assert gr.nombre_propio(entrada) == esperado


def test_limpiar_valores_vacios_del_crm():
    assert gr.limpiar(float("nan")) == ""
    assert gr.limpiar("0") == ""
    assert gr.limpiar("  Cl 5  # 3 ") == "Cl 5 # 3"
    assert gr.limpiar("1045143382.0") == "1045143382"


def test_concordancia():
    assert gr.concordar("f", False, "ahijado", "ahijada") == "ahijada"
    assert gr.concordar("m", True, "ahijado", "ahijada") == "ahijados"
    assert gr.concordar(None, False, "ahijado", "ahijada") == "ahijado(a)"
    assert gr.genero_grupo(["f", "f"]) == "f"
    assert gr.genero_grupo(["f", "m"]) == "m"
    assert gr.genero_grupo(["f", None]) is None
    assert gr.genero_desde_saludo("Estimada") == "f"
    assert gr.genero_desde_saludo("Estimado ") == "m"


def test_programas():
    assert gr.nombre_programa("Programa Chocó") == "Chocó"
    assert gr.programa_legible("Programa Chocó") == "Programa Chocó"
    assert gr.programa_legible("Tumaco- Fortalecimiento Familiar") == "programa de Fortalecimiento Familiar en Tumaco"
    assert gr.lugar_programa("Quibdó-Chocó - Fortalecimiento Familiar") == "Quibdó-Chocó"
