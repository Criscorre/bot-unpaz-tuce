# datos_carrera.py — Datos estáticos de la carrera TUCE
# Fuente única de verdad para plan, correlativas, calendario, director y cómo llegar.
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

# ─── Descripción de la carrera ────────────────────────────────────────────────
DATA_CARRERA_INFO = {
    "titulo":    "TÉCNICA/O UNIVERSITARIA/O EN COMERCIO ELECTRÓNICO",
    "duracion":  "3 años (6 trimestres)",
    "modalidad": "Presencial con contenido virtual",
    "descripcion": (
        "La/el Técnica/o Universitaria/o en Comercio Electrónico podrá participar "
        "de toda la actividad relacionada con la presencia y la venta en línea en "
        "cualquier tipo de organización. Su formación le permitirá interactuar con "
        "los equipos de desarrollo, diseño y producción, así como gestionar sus propios "
        "proyectos. Podrá montar y administrar una tienda en línea y construir productos "
        "y servicios para diversos canales de venta."
    ),
    "alcance": [
        "Desarrollo de canales de venta digital",
        "Estrategias de comercialización",
        "Trabajo en empresas, PyMES y organizaciones sociales",
        "Desarrollo de negocio propio",
    ],
    "titulo_alcance": [
        "Colaborar o desarrollar sectores de venta online",
        "Estrategia web",
        "Campañas de marketing",
        "Planes de negocio",
    ],
    "perfil_egresado": [
        "Crear tiendas online",
        "Definir métricas y KPIs",
        "Elaborar planes comerciales",
        "Gestionar contenido web y SEO",
        "Administrar productos y promociones",
        "Ejecutar campañas de marketing y comunicación",
        "Desarrollar planes de inversión",
        "Impulsar proyectos emprendedores propios",
    ],
}

# ─── Director de la carrera ───────────────────────────────────────────────────
DATA_DIRECTOR = {
    "nombre":   "Fernando Fiorenzo",
    "cargo":    "Director de la carrera TUCE",
    "linkedin": "https://www.linkedin.com/in/fernando-fiorenzo-0a47841a/",
}

# ─── Cómo llegar ─────────────────────────────────────────────────────────────
DATA_COMO_LLEGAR = {
    "alem": {
        "nombre":             "Campus Alem (sede principal)",
        "desde_acceso_oeste": (
            "🚗 *Desde Acceso Oeste:*\n"
            "Tomá Ruta 24 (ex 197) → Girá en Sarmiento → José C. Paz → Av. Alem"
        ),
        "desde_panamericana": (
            "🚗 *Desde Panamericana:*\n"
            "Tomá Ruta 24 → Av. Perón → José C. Paz → Av. Alem"
        ),
        "a_pie": (
            "🚶 *A pie / tren:*\n"
            "Bajá en estación José C. Paz → Tomá Ruta 24 → Dirección Av. Alem"
        ),
    },
    "arregui": {
        "nombre":             "Campus Arregui",
        "desde_acceso_oeste": (
            "🚗 *Desde Acceso Oeste:*\n"
            "Ruta 197 → Chacabuco → Piñero → Av. Arregui"
        ),
        "desde_panamericana": (
            "🚗 *Desde Panamericana:*\n"
            "Ruta 197 → Félix Iglesias → Oribe → Av. Arregui"
        ),
        "a_pie": (
            "🚶 *A pie:*\n"
            "Bajá en estación José C. Paz → Ruta 197 → Rivadavia → Girondo → Arregui"
        ),
    },
}

# ─── Info de gestión / SIU ────────────────────────────────────────────────────
DATA_BOT_INFO = {
    "bot_equivalencias": "⚖️ *Equivalencias:* Trámite formal del 01/04 al 10/04/2026.",
    "bot_boleto":        "🚌 *Boleto Estudiantil:* Gestión vía SIU Guaraní para alumnos regulares.",
    "bot_certificados":  "📄 *Certificaciones:* Emisión digital de certificados vía SIU Guaraní.",
    "bot_inscripcion":   "✍️ *Inscripción:* Únicamente por SIU Guaraní en fechas publicadas.",
}
