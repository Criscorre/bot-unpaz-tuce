# datos_carrera.py — Datos estáticos de la carrera TUCE
# Fuente única de verdad para plan, correlativas y calendario.
# Actualizar acá cuando cambien los datos; el resto del código los importa.

DATA_CALENDARIO = {
    "Ingresantes":      "📝 INFO INGRESANTES:\n🔹 Inscripción CIU: 06/11 al 28/11/2025\n🔹 Desarrollo CIU: 02/02 al 28/02/2026",
    "Primer Semestre":  "1️⃣ 1er SEMESTRE 2026:\n🔹 Inscripción: 18/02 y 19/02\n🔹 Inicio clases: 09/03",
    "Segundo Semestre": "2️⃣ 2do SEMESTRE 2026:\n🔹 Inscripción: 22/07 y 23/07\n🔹 Inicio clases: 10/08",
    "Verano 2027":      "☀️ VERANO 2027:\n🔹 Cursada: Febrero 2027",
}

DATA_PLAN = {
    "Primer Año": [
        "Tecnología y Sociedad (4hs)",
        "Inglés I (4hs)",
        "Principios de Economía (4hs)",
        "Comunicación Institucional (4hs)",
        "Internet: Infraestructura y redes (4hs)",
        "Semántica de las interfaces (4hs)",
        "Introducción al comercio electrónico (4hs)",
        "Usabilidad, seguridad y Estándares Web (4hs)",
        "Inglés II (4hs)",
    ],
    "Segundo Año": [
        "Investigación de mercado (4hs)",
        "Marco legal de negocios electrónicos (4hs)",
        "Gestión del conocimiento (4hs)",
        "Desarrollo Web (4hs)",
        "Formulación, incubación y evaluación de proyectos (4hs)",
        "Métricas del mundo digital (4hs)",
        "Desarrollo de Productos y Servicios (4hs)",
        "Taller de Comunicación (4hs)",
        "Desarrollos para Dispositivos móviles (4hs)",
    ],
    "Tercer Año": [
        "Calidad y Servicio al Cliente (4hs)",
        "Marketing digital (4hs)",
        "Taller de Práctica Integradora (4hs)",
        "Competencias emprendedoras (4hs)",
        "Gestión de Proyectos (4hs)",
    ],
}

CORRELATIVAS = {
    "01": {"nombre": "Tecnología y Sociedad",                             "necesita": []},
    "02": {"nombre": "Inglés I",                                          "necesita": []},
    "03": {"nombre": "Principios de Economía",                            "necesita": []},
    "04": {"nombre": "Comunicación Institucional",                        "necesita": []},
    "05": {"nombre": "Internet: Infraestructura y redes",                 "necesita": []},
    "06": {"nombre": "Semántica de las interfaces",                       "necesita": []},
    "07": {"nombre": "Introducción al comercio electrónico",              "necesita": []},
    "08": {"nombre": "Usabilidad, seguridad y Estándares Web",            "necesita": ["05"]},
    "09": {"nombre": "Inglés II",                                         "necesita": ["02"]},
    "10": {"nombre": "Investigación de mercado",                          "necesita": ["03", "07"]},
    "11": {"nombre": "Marco legal de negocios electrónicos",              "necesita": ["07"]},
    "12": {"nombre": "Gestión del conocimiento",                          "necesita": ["01"]},
    "13": {"nombre": "Desarrollo Web",                                    "necesita": ["06", "08"]},
    "14": {"nombre": "Formulación, incubación y evaluación de proyectos", "necesita": ["03"]},
    "15": {"nombre": "Métricas del mundo digital",                        "necesita": []},
    "16": {"nombre": "Desarrollo de Productos y Servicios",               "necesita": ["10"]},
    "17": {"nombre": "Taller de Comunicación",                            "necesita": ["04"]},
    "18": {"nombre": "Desarrollos para Dispositivos móviles",             "necesita": ["13"]},
    "19": {"nombre": "Calidad y Servicio al Cliente",                     "necesita": ["16"]},
    "20": {"nombre": "Marketing digital",                                 "necesita": ["17"]},
    "21": {"nombre": "Taller de Práctica Integradora",                    "necesita": ["16", "17"]},
    "22": {"nombre": "Competencias emprendedoras",                        "necesita": ["14"]},
    "23": {"nombre": "Gestión de Proyectos",                              "necesita": ["07", "14"]},
}

def correlativas_de(nombre_materia: str) -> str:
    """Devuelve texto con las correlativas de una materia."""
    nombre_lower = nombre_materia.lower()
    for info in CORRELATIVAS.values():
        if info["nombre"].lower() == nombre_lower:
            if not info["necesita"]:
                return "✅ Sin correlativas"
            previas = " + ".join(CORRELATIVAS[c]["nombre"] for c in info["necesita"])
            return f"🔗 Requiere: {previas}"
    return ""

# Usado en los callbacks de Telegram para el Bot TUCE (equivalencias, boleto, etc.)
DATA_BOT_INFO = {
    "bot_equivalencias": "⚖️ *Equivalencias:* Trámite formal del 01/04 al 10/04/2026.",
    "bot_boleto":        "🚌 *Boleto Estudiantil:* Gestión vía SIU Guaraní para alumnos regulares.",
    "bot_certificados":  "📄 *Certificaciones:* Emisión digital de certificados vía SIU Guaraní.",
    "bot_inscripcion":   "✍️ *Inscripción:* Únicamente por SIU Guaraní en fechas publicadas.",
}
