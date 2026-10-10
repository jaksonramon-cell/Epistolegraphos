"""Builds the fictional demo project in demo/.

Everything here is invented: the foundation, the donors, the children, the stories and the
pictures. The spreadsheets keep the column layout of the real CRM exports (odd headers included)
so the app is exercised the way it was used in production.

    python scripts/crear_demo.py
"""

from __future__ import annotations

import json
import math
import random
import shutil
import sys
from pathlib import Path

import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
DEMO = RAIZ / "demo"
rnd = random.Random(1832)

PRIMARIO = (11, 122, 117)
ACENTO = (228, 87, 46)


def fuente(tamano: int, peso: str = "Bold"):
    for ruta in (f"/usr/share/fonts/opentype/inter/Inter-{peso}.otf", f"C:/Windows/Fonts/segoeui{'b' if peso == 'Bold' else ''}.ttf"):
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default(tamano)


# ─── names ─────────────────────────────────────────────────────────────────────
NOMBRES_F = ["Ana", "Laura", "Diana", "Paola", "Carolina", "Natalia", "Juliana", "Marcela", "Sandra", "Adriana",
             "Lucía", "Gloria", "Patricia", "Liliana", "Mónica", "Isabel", "Catalina", "Andrea", "Claudia", "Viviana"]
NOMBRES_M = ["Carlos", "Andrés", "Felipe", "Jorge", "Mauricio", "Sergio", "Hernán", "Julián", "Óscar", "Ricardo",
             "Fabio", "Germán", "Iván", "Camilo", "Santiago", "Diego", "Álvaro", "Mario", "Esteban", "Hugo"]
SEGUNDOS = ["", "", "María", "Andrea", "Alejandro", "José", "Eduardo", "Lucía", "Fernanda", "Antonio"]
APELLIDOS = ["Gómez", "Rodríguez", "Martínez", "López", "Vargas", "Rojas", "Moreno", "Castro", "Ortiz", "Rincón",
             "Salazar", "Cárdenas", "Pineda", "Osorio", "Quintero", "Mejía", "Restrepo", "Henao", "Duarte", "Beltrán",
             "Arango", "Zapata", "Cifuentes", "Valencia", "Ospina", "Barrera", "Londoño", "Suárez", "Acosta", "Lozano"]
CIUDADES = [("Bogotá", "Distrito Capital"), ("Medellín", "Antioquia"), ("Cali", "Valle del Cauca"),
            ("Bucaramanga", "Santander"), ("Pereira", "Risaralda"), ("Barranquilla", "Atlántico"),
            ("Chía", "Cundinamarca"), ("Manizales", "Caldas"), ("Villavicencio", "Meta"), ("Tunja", "Boyacá")]


def persona():
    f = rnd.random() < 0.62
    nombre = rnd.choice(NOMBRES_F if f else NOMBRES_M)
    segundo = rnd.choice(SEGUNDOS)
    if segundo in {"María", "Andrea", "Lucía", "Fernanda"} and not f or segundo in {"Alejandro", "José", "Eduardo", "Antonio"} and f:
        segundo = ""
    if segundo == nombre:
        segundo = ""
    completo = " ".join(x for x in [nombre, segundo, *rnd.sample(APELLIDOS, 2)] if x)
    return completo, ("Estimada" if f else "Estimado")


def direccion():
    via = rnd.choice(["Cl", "Cra", "Av", "Tv", "Dg"])
    texto = f"{via} {rnd.randint(1, 180)} # {rnd.randint(1, 99)}-{rnd.randint(1, 99):02d}"
    if rnd.random() < 0.4:
        texto += f" Apto {rnd.randint(1, 20)}{rnd.randint(0, 9)}{rnd.randint(1, 4)}"
    return texto


_contador = 0


def ids():
    global _contador
    _contador += 1
    contacto = f"DEMO{_contador:05d}"
    return contacto, f"PSN{900000 + _contador}"


# ─── children and their stories ─────────────────────────────────────────────────
PROGRAMAS = {
    "Programa Chocó": [("María José Mosquera", "f", 11), ("Yeison Andrés Palacios", "m", 9), ("Dayana Córdoba Rivas", "f", 14),
                       ("Tomás Elías Murillo", "m", 7), ("Luz Ángela Perea", "f", 16), ("Brayan Stiven Asprilla", "m", 12),
                       ("Isabela Mena Lloreda", "f", 8), ("Jhon Fredy Valencia", "m", 15), ("Sharith Yulieth Hinestroza", "f", 10),
                       ("Eider Smith Rentería", "m", 13)],
    "Programa Guajira": [("María José Mosquera", "f", 6), ("Yuliana Epiayú", "f", 12), ("Ronaldo Pushaina", "m", 10),
                         ("Kelly Johana Uriana", "f", 15), ("Deivis Ipuana", "m", 8), ("Ana Lucía Gouriyú", "f", 13),
                         ("Wilmer Jusayú", "m", 16), ("Nayeli Sapuana", "f", 9), ("Iván Darío Pana", "m", 11),
                         ("Rosa Elena Epinayú", "f", 7)],
    "Programa Nariño": [("Valentina Cortés Angulo", "f", 10), ("Samuel Quiñones", "m", 14), ("Hilary Sofía Castillo", "f", 8),
                        ("Jefferson Caicedo", "m", 12), ("Mariana Bolaños", "f", 15), ("Óscar Iván Riascos", "m", 9),
                        ("Daniela Estupiñán", "f", 13), ("Esteban Montaño", "m", 6), ("Laura Camila Preciado", "f", 11),
                        ("Andrés Felipe Obando", "m", 16)],
}

SUENOS = [
    ("bailar", "Pasos hacia un escenario", "graduarse como {bailarín}", "ensaya cada tarde nuevas coreografías",
     "Cuando bailo se me olvida el cansancio"),
    ("cocinar", "Una cocina llena de sueños", "convertirse en {chef}", "ayuda a preparar el almuerzo de los domingos en la casa",
     "Cuando cocino siento que cuido a los demás"),
    ("el fútbol", "Un gol para recordar", "jugar en un equipo profesional", "entrena tres veces por semana en la cancha del barrio",
     "En el equipo aprendí que nadie gana solo"),
    ("leer", "Las páginas que abren puertas", "ser {escritor} de cuentos", "lleva un libro nuevo de la biblioteca cada viernes",
     "Cuando leo, viajo a lugares que todavía no conozco"),
    ("la ciencia", "Pequeños experimentos, grandes preguntas", "estudiar medicina", "participa en el semillero de ciencias del colegio",
     "Quiero entender cómo funciona el cuerpo para ayudar a la gente"),
    ("la música", "Ritmo de río", "tocar en una orquesta", "aprende marimba con un profesor de la comunidad",
     "La música me pone feliz incluso en los días difíciles"),
    ("dibujar", "Colores que cuentan historias", "estudiar diseño gráfico", "llena cuadernos enteros con dibujos de su territorio",
     "Dibujo lo que veo y también lo que me imagino"),
]
GENERO = {"bailarín": ("bailarín", "bailarina"), "chef": ("chef", "chef"), "escritor": ("escritor", "escritora")}


def historia_nino(nombre: str, genero: str, edad: int, programa: str, i: int) -> tuple[str, str]:
    corto = " ".join(nombre.split(" ")[:2]) if len(nombre.split(" ")) > 3 else nombre.split(" ")[0]
    pasion, titulo, sueno, rutina, cita = SUENOS[i % len(SUENOS)]
    sueno = sueno.format(**{k: v[1 if genero == "f" else 0] for k, v in GENERO.items()})
    o = "a" if genero == "f" else "o"
    lugar = programa.replace("Programa ", "")
    texto = f"""# {titulo}

{corto} tiene {edad} años y una pasión que no esconde: {pasion}. Su gran meta es {sueno}, y para acercarse a ella {rutina}. "{cita}", dice con una sonrisa.

Este semestre {corto} ha mostrado avances en el colegio y en casa. Su cuidadora cuenta que está más segur{o} de sí mism{o} y que ahora ayuda a los más pequeños con las tareas. Desde el programa en {lugar} la seguimos acompañando para que cada paso sea firme.
"""
    if genero == "m":
        texto = texto.replace("la seguimos", "lo seguimos")
    pie = f"{corto} dedica sus tardes a {pasion}"
    return texto, pie


HISTORIAS_PROGRAMA = {
    "Programa Chocó": [
        ("01 Feria de talentos", """# Feria de talentos

En el programa de {{ programa }} los sábados de agosto tuvieron un invitado especial: la primera feria de talentos organizada por los propios jóvenes. Hubo canto, teatro, chirimía y hasta una exposición de fotografía hecha con celulares prestados.

"Al principio me daba miedo subir al escenario; ahora quiero repetir el próximo año", cuenta Tobías, de 13 años. Las familias llevaron comida típica y la jornada terminó con un baile en el que participó todo el barrio.
""", "La feria reunió a más de cien personas del barrio"),
        ("02 Rumbo a la vida adulta", """# Rumbo a la vida adulta

Varios jóvenes del programa están a punto de cumplir la mayoría de edad. Para que ese paso no los tome por sorpresa, este semestre arrancó un ciclo de encuentros sobre cómo abrir una cuenta de ahorros, preparar una hoja de vida y presentarse a una entrevista.

"Hicimos simulacros de entrevista y me di cuenta de que sé más cosas de las que creía", dice Irene, de 17 años. El ciclo continuará con visitas a institutos técnicos de la región.
""", None),
    ],
    "Programa Guajira": [
        ("01 Agua para la ranchería", """# Agua para la ranchería

En las comunidades wayuu que acompañamos en {{ programa }}, el agua es el centro de la vida diaria. Este año, con el apoyo de padrinos y madrinas, se instaló un nuevo sistema de recolección de agua lluvia que beneficia a 40 familias.

"Antes caminábamos casi una hora para traer agua; ahora los niños llegan a tiempo al colegio", cuenta Rosa, una de las madres líderes de la comunidad.
""", "El nuevo tanque abastece a cuarenta familias"),
        ("02 Tejiendo la memoria", """# Tejiendo la memoria

Las abuelas de la comunidad enseñan a niñas y niños a tejer mochilas, y con cada puntada cuentan las historias de su pueblo. El taller se volvió el lugar favorito de los sábados.

"Mi abuela dice que cada figura tiene un significado; yo estoy aprendiendo la del caparazón de tortuga", dice Nayeli, de 9 años.
""", None),
    ],
    "Programa Nariño": [
        ("01 Escuela de padres", """# Escuela de padres

En {{ programa }} las familias también aprenden. Cada mes se reúnen madres, padres y cuidadores para conversar sobre crianza amorosa, manejo de las emociones y prevención de la violencia en casa.

"Aprendí a escuchar más a mis hijos y a gritar menos", dice Martha, mamá de tres niños del programa.
""", "Las familias se reúnen una vez al mes"),
        ("02 Un huerto en el patio", """# Un huerto en el patio

Con semillas, palas y mucha paciencia, las familias del programa sembraron huertas caseras. Hoy cosechan cilantro, tomate y cebolla, y los niños aprenden de dónde viene lo que comen.

"Lo que más me gusta es regar las plantas y ver cómo crecen", cuenta Esteban, de 6 años.
""", "Los niños riegan la huerta cada mañana"),
    ],
}

TEXTOS = {
    "historias_intro": """Hola, {{ primer_nombre }}. Llegó el momento de ponerte al día. En esta carta encontrarás noticias de **{{ ninos }}**{% if n_ninos > 1 %} ({{ ninos_por_programa }}){% endif %}: lo que han aprendido, lo que les emociona y lo que viene para este semestre.

Para proteger su privacidad, los nombres de otras personas que aparecen en estas historias fueron cambiados. ¡Esperamos que las disfrutes tanto como nosotros!
""",
    "historias_cierre": """Gracias por leer hasta aquí y por seguir de cerca a {{ ahijado }}. Tener {{ gp('un padrino', 'una madrina') }} tan {{ gp('comprometido', 'comprometida') }} como tú hace posible que {{ ninos }} {% if plural %}sigan{% else %}siga{% endif %} {{ gn('creciendo rodeado', 'creciendo rodeada', 'creciendo rodeados', 'creciendo rodeadas') }} de cuidado.

¡Hasta la próxima!
""",
    "programa_intro": """Hola, {{ primer_nombre }}. Gracias a tu aporte, en {{ lugares }} seguimos acompañando a niñas, niños, jóvenes y sus familias. En esta carta te contamos lo que hicimos juntos durante este semestre.
""",
    "programa_cierre": """Cada una de estas historias es posible porque {{ gp('un padrino', 'una madrina') }} como tú decidió creer en el Programa {{ programas }}. ¡Gracias por estar ahí!

Un abrazo de toda la familia de {{ organizacion }}.
""",
    "egreso_cierre": """Tu apoyo fue parte fundamental de {% if plural %}estos logros{% else %}este logro{% endif %}. Gracias por haber caminado a su lado.

En {{ organizacion }} nos sentimos muy orgullosos de crear esperanza y nuevas oportunidades para más niñas, niños y jóvenes. **De ahora en adelante, apoyarás** {{ nuevos }}.

{% if solo_programas %}En la siguiente carta conocerás más acerca de este territorio y de cómo, a través de tu apoyo, generamos impacto positivo en la vida de las familias y la comunidad.{% else %}En la siguiente carta conocerás sus sueños, intereses y pasatiempos, y en los próximos meses recibirás noticias sobre su progreso.{% endif %}

Un fuerte y caluroso abrazo,
""",
}

EGRESANDO = [("Matías Ernesto Lozada", "m"), ("Celeste Amaranta Ruiz", "f"), ("Gabriel Antonio Pardo", "m"),
             ("Renata Isolda Garcés", "f"), ("Joaquín Lisandro Peña", "m"), ("Aurora Milena Toro", "f"),
             ("Emiliano José Bernal", "m"), ("Violeta Inés Salcedo", "f")]
NUEVOS = [("Lucía Fernanda Ortega", "Tumaco - Fortalecimiento Familiar"), ("Simón Andrés Quintana", "Quibdó-Chocó - Fortalecimiento Familiar"),
          ("Antonella Paz Ricaurte", "Guajira - Fortalecimiento Familiar"), ("Programa Chocó", "Programa Chocó"),
          ("Programa Guajira", "Programa Guajira"), ("Martina Sol Arboleda", "Tumaco - Fortalecimiento Familiar")]


def texto_egreso(nombre: str, genero: str, i: int) -> str:
    corto = " ".join(nombre.split(" ")[:2])
    o = "a" if genero == "f" else "o"
    variantes = [
        f"Queremos contarte que {corto} y su familia cumplieron su proceso en el programa. Durante estos años fortalecieron sus vínculos, mejoraron sus ingresos y hoy cuentan con una red de apoyo en su comunidad. {corto} está list{o} para seguir adelante con su familia.",
        f"Tenemos una noticia muy especial: {corto} terminó su ciclo en el programa. Gracias a tu acompañamiento, hoy estudia, tiene metas claras y su familia puede cuidarl{o} con autonomía. Nos llena de orgullo ver cuánto ha crecido.",
        f"Después de varios años de trabajo conjunto, la familia de {corto} alcanzó los objetivos de su plan de desarrollo. {corto} se despide del programa con nuevas habilidades y muchos sueños por cumplir.",
    ]
    return variantes[i % len(variantes)] + "\n"


# ─── pictures (abstract landscapes: no real people) ─────────────────────────────
def paisaje(ruta: Path, semilla: int, ancho=780, alto=540):
    r = random.Random(semilla)
    img = Image.new("RGB", (ancho, alto))
    d = ImageDraw.Draw(img)
    cielo1 = (r.randint(120, 190), r.randint(180, 220), r.randint(220, 250))
    cielo2 = (r.randint(240, 255), r.randint(200, 235), r.randint(170, 210))
    for y in range(alto):
        t = y / alto
        d.line([(0, y), (ancho, y)], fill=tuple(int(cielo1[k] * (1 - t) + cielo2[k] * t) for k in range(3)))
    sx, sy = r.randint(80, ancho - 80), r.randint(60, 180)
    d.ellipse([sx - 45, sy - 45, sx + 45, sy + 45], fill=(255, 214, 120))
    verdes = [(46, 125, 90), (34, 102, 80), (70, 150, 95), (24, 84, 70)]
    for capa in range(4):
        base = int(alto * (0.45 + capa * 0.13))
        amp, fase, freq = r.randint(18, 50), r.random() * 6, r.uniform(0.004, 0.012)
        puntos = [(x, base + amp * math.sin(x * freq + fase)) for x in range(0, ancho + 10, 10)]
        d.polygon(puntos + [(ancho, alto), (0, alto)], fill=verdes[capa])
        if capa == 2:
            for _ in range(r.randint(2, 5)):  # houses
                hx = r.randint(40, ancho - 100)
                hy = int(base + amp * math.sin(hx * freq + fase)) - 10
                color = r.choice([(240, 200, 120), (230, 120, 90), (120, 170, 210), (245, 245, 235)])
                d.rectangle([hx, hy - 40, hx + 56, hy + 10], fill=color)
                d.polygon([(hx - 8, hy - 40), (hx + 28, hy - 70), (hx + 64, hy - 40)], fill=(150, 60, 50))
                d.rectangle([hx + 22, hy - 12, hx + 34, hy + 10], fill=(90, 60, 40))
        if capa == 1:
            for _ in range(r.randint(3, 7)):  # trees
                tx = r.randint(10, ancho - 10)
                ty = int(base + amp * math.sin(tx * freq + fase))
                d.rectangle([tx - 4, ty - 30, tx + 4, ty + 5], fill=(90, 70, 50))
                d.ellipse([tx - 28, ty - 75, tx + 28, ty - 22], fill=r.choice(verdes[:2]))
    img = img.filter(ImageFilter.SMOOTH_MORE)
    img.save(ruta, "JPEG", quality=82, optimize=True)


def logo(ruta: Path):
    img = Image.new("RGBA", (900, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 10, 200, 200], radius=40, fill=PRIMARIO)
    d.rectangle([97, 100, 113, 175], fill="white")
    for cx, cy, rr in [(105, 75, 40), (68, 95, 28), (142, 95, 28)]:
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill="white")
    d.line([(60, 175), (150, 175)], fill="white", width=8)
    d.text((235, 30), "FUNDACIÓN", font=fuente(70), fill=PRIMARIO)
    d.text((235, 108), "CEIBA VIVA", font=fuente(70), fill=ACENTO)
    img.save(ruta)


def firma(ruta: Path):
    escala = 3
    img = Image.new("RGBA", (520 * escala, 150 * escala), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = random.Random(7)
    puntos = []
    for i in range(240):
        t = i / 239
        x = 20 + t * 470
        y = 85 + 38 * math.sin(t * 14) * (1 - t * 0.5) + 14 * math.sin(t * 41) + r.uniform(-1, 1)
        puntos.append((x * escala, y * escala))
    d.line(puntos, fill=(25, 40, 95, 255), width=3 * escala, joint="curve")
    d.line([(60 * escala, 125 * escala), (400 * escala, 112 * escala)], fill=(25, 40, 95, 255), width=2 * escala)
    img.resize((520, 150), Image.LANCZOS).save(ruta)


def qr(ruta: Path):
    codigo = qrcode.QRCode(border=1, box_size=10)
    codigo.add_data("https://example.org/pasate-a-digital")
    imagen = codigo.make_image(fill_color=(11, 122, 117), back_color="white").convert("RGB")
    lienzo = Image.new("RGB", (imagen.width + 20, imagen.height + 80), "white")
    ImageDraw.Draw(lienzo).text((lienzo.width // 2, 38), "¡Pásate a digital!", font=fuente(30), fill=ACENTO, anchor="mm")
    lienzo.paste(imagen, (10, 70))
    lienzo.save(ruta)


# ─── spreadsheets ───────────────────────────────────────────────────────────────
COLUMNAS = ["ID De Contacto ", "PSN", "mult", "ID Compromiso", "Unico", "Estado de la relacion Padrino/Ahijado",
            "Nombre_Padrino", "Saludo ", "correo", "Dirección", "Ciudad", "Departamento", "Cedula "]


def fila_padrino(digital: bool, mult: int = 1, contacto=None):
    nombre, saludo = persona()
    cid, psn = contacto or ids()
    ciudad, depto = rnd.choice(CIUDADES)
    usuario = nombre.split(" ")[0].lower().translate(str.maketrans("áéíóúñ", "aeioun"))
    return {
        "ID De Contacto ": cid, "PSN": psn, "mult": mult, "ID Compromiso": f"CMP{rnd.randint(10**6, 10**7)}",
        "Unico": f"{psn}-{cid}", "Estado de la relacion Padrino/Ahijado": "Activo",
        "Nombre_Padrino": nombre, "Saludo ": saludo, "correo": f"{usuario}{rnd.randint(1, 99)}@example.com",
        "Dirección": "Envio Digital" if digital else direccion(), "Ciudad": ciudad, "Departamento": depto,
        "Cedula ": "",
    }


def con_nino(base: dict, programa: str, nino: tuple) -> dict:
    nombre, genero, _ = nino
    return base | {"Nombre Completo NNJA": nombre, "Nombre_NNAJ": nombre.split(" ")[0] if len(nombre.split()) <= 3 else " ".join(nombre.split()[:2]),
                   "Genero_NNAJ": genero.upper(), "AldeaPrograma": programa}


def hojas_historias():
    ninos = [(p, n) for p, lista in PROGRAMAS.items() for n in lista]
    uni_f, uni_d, multi = [], [], []
    for i in range(70):
        p, n = ninos[i % len(ninos)]
        uni_f.append(con_nino(fila_padrino(False), p, n))
    for i in range(24):
        p, n = ninos[(i * 7) % len(ninos)]
        uni_d.append(con_nino(fila_padrino(True), p, n))
    for i in range(10):
        cuantos = 2 if i < 7 else 3
        base = fila_padrino(i % 3 == 0, mult=cuantos)
        for k in range(cuantos):
            p, n = ninos[(i * 5 + k * 11) % len(ninos)]
            multi.append(con_nino(base, p, n))
    # cases that the review step should catch
    uni_f[3]["Nombre_Padrino"] = "MARTHA LUCÍA  GÓMEZ RINCÓN"  # shouting caps and double spaces
    uni_f[8]["Saludo "] = ""
    uni_f[12]["Dirección"] = ""
    uni_f[20] |= {"Nombre Completo NNJA": "Samuel Antonio Rentería", "Nombre_NNAJ": "Samuel"}  # no story file
    return {"UNI FISICO": uni_f, "UNI DIGITAL": uni_d, "MULTI": multi}


def hojas_programa():
    fis, dig = [], []
    for i in range(36):
        programa = list(PROGRAMAS)[i % 3]
        fila = fila_padrino(i % 4 == 0)
        fila["AldeaPrograma"] = programa
        (dig if i % 4 == 0 else fis).append(fila)
    return {"PROGRAMA FISICO": fis, "PROGRAMA DIGITAL": dig}


def hojas_egreso():
    uni, multi = [], []
    for i in range(40):
        nombre, _ = EGRESANDO[i % len(EGRESANDO)]
        nuevo, programa = NUEVOS[i % len(NUEVOS)]
        fila = fila_padrino(i % 5 == 0)
        uni.append(fila | {"Nombre Completo NNJA": nombre, "Nombre": " ".join(nombre.split()[:2]),
                           "AldeaPrograma": "Quibdó - Fortalecimiento Familiar",
                           "ID Nombre niño NUEVO Completo ": nuevo, "Nuevo_Nombre": " ".join(nuevo.split()[:2]),
                           "PSN Nombre niño NUEVO Completo ": programa})
    for i in range(6):
        base = fila_padrino(i == 0, mult=2)
        for k in range(2):
            nombre, _ = EGRESANDO[(i + k * 3) % len(EGRESANDO)]
            nuevo, programa = NUEVOS[(i + k) % len(NUEVOS)]
            multi.append(base | {"Nombre Completo NNJA": nombre, "Nombre": " ".join(nombre.split()[:2]),
                                 "AldeaPrograma": "Quibdó - Fortalecimiento Familiar",
                                 "ID Nombre niño NUEVO Completo ": nuevo, "Nuevo_Nombre": " ".join(nuevo.split()[:2]),
                                 "PSN Nombre niño NUEVO Completo ": programa})
    return {"EGRESOS": uni, "EGRESOS MULTI": multi}


def escribir_excel(ruta: Path, hojas: dict):
    with pd.ExcelWriter(ruta) as xls:
        for nombre, filas in hojas.items():
            pd.DataFrame(filas).to_excel(xls, sheet_name=nombre, index=False)


def main():
    if DEMO.exists():
        shutil.rmtree(DEMO)
    for carpeta in ["datos", "textos", "marca", "historias/ninos", "historias/programas", "historias/egresos"]:
        (DEMO / carpeta).mkdir(parents=True)

    (DEMO / "proyecto.json").write_text(json.dumps({
        "organizacion": "Fundación Ceiba Viva",
        "firmante": {"nombre": "Mariana Ceballos Ortiz", "cargo": "Coordinadora de Experiencia al Donante",
                     "direccion": "Calle Ficticia # 12-34, Bogotá D.C.", "correo": "padrinos@example.org"},
        "color_primario": "#0b7a75",
        "color_acento": "#e4572e",
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    for nombre, texto in TEXTOS.items():
        (DEMO / "textos" / f"{nombre}.md").write_text(texto, encoding="utf-8")

    logo(DEMO / "marca" / "logo.png")
    firma(DEMO / "marca" / "firma.png")
    qr(DEMO / "marca" / "qr.png")

    semilla = 0
    for programa, ninos in PROGRAMAS.items():
        carpeta = DEMO / "historias" / "ninos" / programa
        carpeta.mkdir()
        for i, (nombre, genero, edad) in enumerate(ninos):
            texto, pie = historia_nino(nombre, genero, edad, programa, i + len(programa))
            (carpeta / f"{nombre}.md").write_text(texto, encoding="utf-8")
            (carpeta / f"{nombre}.txt").write_text(pie, encoding="utf-8")
            semilla += 1
            paisaje(carpeta / f"{nombre}.jpg", semilla)
        carpeta = DEMO / "historias" / "programas" / programa
        carpeta.mkdir()
        for archivo, texto, pie in HISTORIAS_PROGRAMA[programa]:
            (carpeta / f"{archivo}.md").write_text(texto, encoding="utf-8")
            if pie:
                (carpeta / f"{archivo}.txt").write_text(pie, encoding="utf-8")
                semilla += 1
                paisaje(carpeta / f"{archivo}.jpg", semilla)

    for i, (nombre, genero) in enumerate(EGRESANDO):
        (DEMO / "historias" / "egresos" / f"{nombre}.md").write_text(texto_egreso(nombre, genero, i), encoding="utf-8")

    escribir_excel(DEMO / "datos" / "padrinos_ninos.xlsx", hojas_historias())
    escribir_excel(DEMO / "datos" / "padrinos_programa.xlsx", hojas_programa())
    escribir_excel(DEMO / "datos" / "egresos.xlsx", hojas_egreso())
    print(f"Demo creada en {DEMO}")


if __name__ == "__main__":
    sys.exit(main())
