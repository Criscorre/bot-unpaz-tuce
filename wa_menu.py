# wa_menu.py — Handler WhatsApp v5
#
# Filosofía:
#   - Si el usuario pregunta algo y tenemos la respuesta, la damos directo.
#   - El menú guía pero no bloquea.
#   - La IA trabaja en segundo plano como fallback — no es visible en el menú.
#   - Tono: registro "vos", informal pero respetuoso, consistente.
#   - Todas las respuestas terminan con MENÚ · ATRÁS · CERRAR.
#   - El bot siempre pide el nombre al primer contacto y lo recuerda.

from normalizer import normalizar, es_menu, extraer_numero, contiene_alguna
import estado as est
from materias_db import LISTA_HORARIOS
from faq_data import FAQ
from datos_carrera import (
    DATA_PLAN, DATA_CALENDARIO, CORRELATIVAS, correlativas_de,
    DATA_CARRERA_INFO, DATA_DIRECTOR, DATA_COMO_LLEGAR,
)

# ─── Sedes ────────────────────────────────────────────────────────────────────
SEDES = {
    "cem": {
        "nombre":    "CEM — Sede Pueyrredón",
        "direccion": "Leandro N. Alem 4593, José C. Paz, Buenos Aires",
        "maps":      "https://maps.google.com/?q=Leandro+N.+Alem+4593,+Jose+C.+Paz,+Buenos+Aires",
        "extra":     None,
    },
    "alem": {
        "nombre":    "Sede Alem",
        "direccion": "Leandro N. Alem 4731, José C. Paz, Buenos Aires",
        "maps":      "https://maps.google.com/?q=Leandro+N.+Alem+4731,+Jose+C.+Paz,+Buenos+Aires",
        "extra":     None,
    },
    "biblioteca": {
        "nombre":    "Biblioteca 'José C. Mondoví'",
        "direccion": "Leandro N. Alem 4673, José C. Paz, Buenos Aires",
        "maps":      "https://maps.google.com/?q=Leandro+N.+Alem+4673,+Jose+C.+Paz,+Buenos+Aires",
        "extra":     "🎬 Sala Multimedial en el 1er piso",
    },
    "comedor": {
        "nombre":    "Comedor Universitario",
        "direccion": "Leandro N. Alem 4751, José C. Paz, Buenos Aires",
        "maps":      "https://maps.google.com/?q=Leandro+N.+Alem+4751,+Jose+C.+Paz,+Buenos+Aires",
        "extra":     None,
    },
    "arregui": {
        "nombre":    "Campus Arregui",
        "direccion": "Av. Héctor Arregui 501, José C. Paz, Buenos Aires",
        "maps":      "https://maps.google.com/?q=Av.+Hector+Arregui+501,+Jose+C.+Paz,+Buenos+Aires",
        "extra":     None,
    },
}

# ─── Materias del plan (para correlativas — incluye todas, no solo las activas) ─
_MATERIAS_PLAN = sorted([info["nombre"] for info in CORRELATIVAS.values()])

# ─── Materias activas este trimestre ─────────────────────────────────────────
_MATERIAS = sorted(list(set(f[0] for f in LISTA_HORARIOS)))

# ─── Footer estándar ─────────────────────────────────────────────────────────
_FOOTER = "\n\n*MENÚ* · *ATRÁS* · *CERRAR*"

def _pie(extra: str = "") -> str:
    if extra:
        return f"\n\n_{extra}_" + _FOOTER
    return _FOOTER

# ─── Textos fijos ─────────────────────────────────────────────────────────────
BIENVENIDA_BASE = (
    "👋 ¡Hola{nombre}! Soy *Alma TUCE*, tu asistente de la\n"
    "*Tecnicatura Universitaria en Comercio Electrónico - UNPAZ*\n\n"
    "Podés preguntarme lo que necesitás directamente, o escribí *MENÚ* para ver todas las opciones."
)

PREGUNTA_NOMBRE = (
    "👋 ¡Hola! Soy *Alma TUCE*, tu asistente de la\n"
    "*Tecnicatura Universitaria en Comercio Electrónico - UNPAZ*\n\n"
    "¿Cómo te llamás?"
)

MENU_TEXTO = (
    "📋 *Menú principal:*\n\n"
    "1️⃣  📚 Información de la carrera\n"
    "2️⃣  🕒 Horarios del trimestre\n"
    "3️⃣  👥 Comunidad TUCE\n"
    "4️⃣  ❓ Preguntas frecuentes\n"
    "5️⃣  📍 Sedes UNPAZ\n\n"
    "_Escribí el número, el nombre de la opción, o preguntame directamente._"
    + _FOOTER
)

MSG_NO_ENTENDI = (
    "No tengo información sobre tu solicitud.\n"
    "Podés escribir *MENÚ* para ver las opciones disponibles."
    + _FOOTER
)

MSG_CERRAR = "👋 ¡Hasta luego{nombre}! Cuando necesités algo, acá estoy. 😊"

# ─── Firebase: memoria de nombre ─────────────────────────────────────────────

def _esc_uid(uid: str) -> str:
    return uid.replace(".", "___DOT___").replace("@", "___AT___").replace("+", "___PLUS___")

def _get_usuario(firebase_db, uid: str) -> dict:
    """Lee el nodo completo del usuario (nombre, visto)."""
    try:
        data = firebase_db.reference(f"wa_usuarios/{_esc_uid(uid)}").get()
        return data if isinstance(data, dict) else {}
    except:
        return {}

def _get_nombre(firebase_db, uid: str) -> str | None:
    return _get_usuario(firebase_db, uid).get("nombre")

def _get_visto(firebase_db, uid: str) -> bool:
    """True si el usuario ya tuvo al menos un intercambio con el bot."""
    return bool(_get_usuario(firebase_db, uid).get("visto"))

def _marcar_visto(firebase_db, uid: str):
    """Registra que el usuario ya fue contactado (aunque no haya dado nombre)."""
    try:
        firebase_db.reference(f"wa_usuarios/{_esc_uid(uid)}").update({"visto": True})
    except:
        pass

def _set_nombre(firebase_db, uid: str, nombre: str):
    try:
        firebase_db.reference(f"wa_usuarios/{_esc_uid(uid)}").update({
            "nombre": nombre.strip().capitalize(),
            "visto":  True,
        })
    except:
        pass

# ─── Búsqueda de materias ─────────────────────────────────────────────────────

def _buscar_materia_activa(texto_norm: str) -> str | None:
    num = extraer_numero(texto_norm)
    if num is not None and 1 <= num <= len(_MATERIAS):
        return _MATERIAS[num - 1]
    for m in _MATERIAS:
        if texto_norm == normalizar(m):
            return m
    palabras = [p for p in texto_norm.split() if len(p) >= 3]
    if palabras:
        for m in _MATERIAS:
            m_norm = normalizar(m)
            if all(p in m_norm for p in palabras):
                return m
    for p in sorted(palabras, key=len, reverse=True):
        if len(p) >= 4:
            for m in _MATERIAS:
                if p in normalizar(m):
                    return m
    return None

def _buscar_en_correlativas(texto_norm: str) -> dict | None:
    for info in CORRELATIVAS.values():
        if texto_norm == normalizar(info["nombre"]):
            return info
    palabras = [p for p in texto_norm.split() if len(p) >= 3]
    if palabras:
        for info in CORRELATIVAS.values():
            n = normalizar(info["nombre"])
            if all(p in n for p in palabras):
                return info
    for p in sorted(palabras, key=len, reverse=True):
        if len(p) >= 4:
            for info in CORRELATIVAS.values():
                if p in normalizar(info["nombre"]):
                    return info
    return None

# ─── Formateo de respuestas ───────────────────────────────────────────────────

def _txt_lista_materias() -> str:
    lineas = [
        "🕒 *Horarios — trimestre en curso*\n",
        "Seleccioná una materia por número o escribí su nombre:\n",
    ]
    for i, m in enumerate(_MATERIAS, 1):
        lineas.append(f"  {i}. {m}")
    return "\n".join(lineas) + _pie("Escribí el número o el nombre de la materia")

def _txt_horario_materia(materia: str) -> str:
    filas = [f for f in LISTA_HORARIOS if f[0] == materia]
    cor   = correlativas_de(materia)
    resp  = f"🕒 *{materia}*\n"
    if cor and "Sin correlativas" not in cor:
        resp += f"_{cor}_\n"
    resp += "\n"
    for f in filas:
        aula = f[8] if f[8] and f[8] not in ("//", "A confirmar") else "A confirmar"
        resp += f"👥 *Com {f[1]}* — {f[2]} {f[3][:5]}–{f[4][:5]} hs\n"
        resp += f"🏢 Aula: {aula} | {f[5]}\n"
        resp += "──────────\n"
    return resp + _pie("Escribí otra materia o su número para seguir consultando")

def _txt_plan() -> str:
    resp = "📄 *Plan de Estudios*\n*Tecnicatura Universitaria en Comercio Electrónico*\n\n"
    for anio, materias in DATA_PLAN.items():
        resp += f"*{anio}:*\n"
        for m in materias:
            resp += f"  • {m}\n"
        resp += "\n"
    resp += "🔗 https://unpaz.edu.ar/comercioelectronico"
    return resp + _pie()

def _txt_carrera_desc() -> str:
    info = DATA_CARRERA_INFO
    resp = (
        f"🎓 *{info['titulo']}*\n\n"
        f"⏱️ Duración: {info['duracion']}\n"
        f"📍 Modalidad: {info['modalidad']}\n\n"
        f"📖 *Descripción:*\n{info['descripcion']}\n\n"
        "✅ *Lo que vas a poder hacer:*\n"
    )
    for item in info["perfil_egresado"]:
        resp += f"  • {item}\n"
    resp += "\n💼 *Salidas laborales:*\n"
    for item in info["alcance"]:
        resp += f"  • {item}\n"
    resp += "\n🔗 https://unpaz.edu.ar/comercioelectronico"
    return resp + _pie()

def _txt_calendario() -> str:
    resp = "🗓️ *Calendario Académico 2026*\n\n"
    for v in DATA_CALENDARIO.values():
        resp += v + "\n\n"
    resp += "🔗 https://unpaz.edu.ar/calendario-academico"
    return resp + _pie()

def _txt_gestion() -> str:
    return (
        "🖥️ *Gestión Alumnos — SIU Guaraní:*\n\n"
        "🔗 https://estudiantes.unpaz.edu.ar/autogestion/\n\n"
        "Desde ahí podés:\n"
        "  • Inscribirte a exámenes y materias\n"
        "  • Ver tu historia académica e inasistencias\n"
        "  • Consultar tu plan y avance\n"
        "  • Tramitar constancias y certificados\n"
        "  • Solicitar el boleto estudiantil\n"
        "  • Actualizar datos personales\n\n"
        "🎓 Campus Virtual:\nhttps://campusvirtual.unpaz.edu.ar/\n\n"
        "📄 Equivalencias:\nhttps://unpaz.edu.ar/formularioequivalencias\n\n"
        "🌐 Sitio oficial:\nhttps://unpaz.edu.ar"
    ) + _pie()

def _txt_sedes() -> str:
    resp = "📍 *Sedes UNPAZ — Campus Alem:*\n\n"
    for key in ["cem", "biblioteca", "comedor", "alem"]:
        s = SEDES[key]
        resp += f"🏢 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}"
        if s.get("extra"):
            resp += f"\n_{s['extra']}_"
        resp += "\n\n"
    resp += "──────────\n"
    resp += "📍 *Campus Arregui:*\n\n"
    s = SEDES["arregui"]
    resp += f"🏢 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}\n\n"
    resp += "_Escribí *cómo llego* para obtener indicaciones personalizadas._"
    return resp + _pie()

def _txt_contactos() -> str:
    return (
        "📩 *Contactos y Mesa de Ayuda:*\n\n"
        "🤝 Dirección de Acceso y Apoyo al Estudiante (becas, tutorías, CIU):\n"
        "  accesoapoyo@unpaz.edu.ar\n\n"
        "👤 Consultas Estudiantes (trámites generales):\n"
        "  consultasestudiantes@unpaz.edu.ar\n\n"
        "💻 Soporte SIU Guaraní:\n"
        "  soporteinscripciones@unpaz.edu.ar\n\n"
        "🌐 UNPAZ Virtual (campus):\n"
        "  formacionvirtual@unpaz.edu.ar\n\n"
        "💜 ORVIG (perspectiva de género):\n"
        "  orvig@unpaz.edu.ar"
    ) + _pie()

def _txt_comunidad() -> str:
    return (
        "👥 *Comunidad TUCE*\n\nSumate 👇\n\n"
        "💬 *WhatsApp TUCE:*\nhttps://chat.whatsapp.com/FSwCNJd2GirBVIVCZDGU0B\n\n"
        "💬 *Grupo adicional:*\nhttps://chat.whatsapp.com/JElcFd4U08QBKsL1J1YM8u\n\n"
        "📸 *Instagram:*\nhttps://www.instagram.com/tuce_unpaz/\n\n"
        "📘 *Facebook:*\nhttps://m.facebook.com/tuceunpaz/\n\n"
        "▶️ *YouTube:*\nhttps://www.youtube.com/@TUCEUNPAZ"
    ) + _pie()

# ─── Cómo llegar ─────────────────────────────────────────────────────────────

def _txt_como_llegar(sede: str, origen: str) -> str:
    data = DATA_COMO_LLEGAR.get(sede)
    if not data:
        return _txt_como_llegar_todo()
    return (
        f"🗺️ *Cómo llegar a {data['nombre']}*\n\n"
        + data.get(origen, data["a_pie"])
    ) + _pie("Escribí MENÚ para más opciones")

def _txt_como_llegar_todo() -> str:
    resp = "🗺️ *Cómo llegar a UNPAZ — Campus Alem:*\n\n"
    d = DATA_COMO_LLEGAR["alem"]
    resp += d["desde_acceso_oeste"] + "\n\n"
    resp += d["desde_panamericana"] + "\n\n"
    resp += d["a_pie"] + "\n\n"
    resp += "──────────\n"
    resp += "🗺️ *Campus Arregui:*\n\n"
    d2 = DATA_COMO_LLEGAR["arregui"]
    resp += d2["desde_acceso_oeste"] + "\n\n"
    resp += d2["desde_panamericana"] + "\n\n"
    resp += d2["a_pie"]
    return resp + _pie()

# ─── FAQ ──────────────────────────────────────────────────────────────────────

def _txt_lista_faq() -> str:
    lineas = ["❓ *Preguntas frecuentes:*\n"]
    for i, item in enumerate(FAQ, 1):
        lineas.append(f"  {i}. {item['q']}")
    return "\n".join(lineas) + _pie("Escribí el número de tu pregunta")

def _buscar_faq(texto_norm: str) -> dict | None:
    num = extraer_numero(texto_norm)
    if num is not None and 1 <= num <= len(FAQ):
        return FAQ[num - 1]
    # Solo palabras de 5+ caracteres para evitar falsos positivos
    palabras = [p for p in texto_norm.split() if len(p) >= 5]
    if not palabras:
        return None
    for item in FAQ:
        q_norm = normalizar(item["q"])
        if any(p in q_norm for p in palabras):
            return item
    return None

# ─── Sección: Información de la carrera ──────────────────────────────────────

SUBMENU_CARRERA = (
    "📚 *Información de la carrera:*\n\n"
    "1. 📖 Descripción y perfil egresado\n"
    "2. 📄 Plan de estudios\n"
    "3. 🔗 Correlativas\n"
    "4. 🗓️ Calendario académico\n"
    "5. 🖥️ Gestión (Campus / SIU Guaraní)\n"
    "6. 📩 Contactos y Mesa de Ayuda"
) + _pie("Escribí el número de la opción")

_KEYWORDS_CARRERA = {
    1: ["descripcion", "perfil", "egresado", "que es la tuce", "para que sirve", "salida laboral"],
    2: ["plan", "estudio", "materias de la carrera", "que se estudia"],
    3: ["correlativa", "previa", "requiere", "para cursar", "necesito tener"],
    4: ["calendario", "fecha", "cuando empiezan", "inicio", "trimestre"],
    5: ["gestion", "campus", "guarani", "siu", "certificado", "boleto", "equivalencia"],
    6: ["contacto", "ayuda", "mail", "email", "beca", "pasantia", "orvig"],
}

def _handle_carrera(uid: str, texto_norm: str) -> str:
    estado    = est.get(uid)
    esperando = estado.get("esperando")

    if esperando == "correlativa":
        info = _buscar_en_correlativas(texto_norm)
        if info:
            est.avanzar(uid, esperando="correlativa")
            nombre = info["nombre"]
            if not info["necesita"]:
                return (
                    f"✅ *{nombre}*\n\n"
                    "No tiene correlativas. ¡Podés cursarla cuando quieras!"
                ) + _pie("Escribí otra materia para consultar más correlativas")
            previas = "\n".join(f"  • {CORRELATIVAS[c]['nombre']}" for c in info["necesita"])
            return (
                f"🔗 *{nombre}*\n\n"
                f"Para cursarla necesitás tener aprobada/s:\n{previas}"
            ) + _pie("Escribí otra materia para seguir consultando")
        if est.sumar_error(uid):
            est.salir(uid)
            return "⚠️ No pude encontrar esa materia.\n\n" + MENU_TEXTO
        return (
            "❌ No encontré esa materia. Probá con parte del nombre.\n"
            "_Ejemplo: 'desarrollo', 'ingles', 'marketing'_"
        ) + _FOOTER

    _MAP = {
        1: (None,          _txt_carrera_desc),
        2: (None,          _txt_plan),
        3: ("correlativa", lambda: "🔗 *Correlativas*\n\nEscribí el nombre (o parte) de la materia:" + _pie("Ejemplo: 'marketing', 'ingles', 'desarrollo web'")),
        4: (None,          _txt_calendario),
        5: (None,          _txt_gestion),
        6: (None,          _txt_contactos),
    }

    num = extraer_numero(texto_norm)
    if num is None:
        for n, kws in _KEYWORDS_CARRERA.items():
            if contiene_alguna(texto_norm, kws):
                num = n
                break

    if num in _MAP:
        next_esp, fn = _MAP[num]
        est.entrar(uid, "carrera", esperando=next_esp)
        return fn()

    if est.sumar_error(uid):
        est.salir(uid)
        return "⚠️ Demasiados intentos.\n\n" + MENU_TEXTO
    return SUBMENU_CARRERA

def _handle_horarios(uid: str, texto_norm: str) -> str:
    materia = _buscar_materia_activa(texto_norm)
    if materia:
        est.avanzar(uid, esperando="materia")
        return _txt_horario_materia(materia)
    if est.sumar_error(uid):
        est.salir(uid)
        return "⚠️ No encontré esa materia.\n\n" + MENU_TEXTO
    return (
        "❌ No encontré esa materia. Probá con el número de la lista o parte del nombre.\n\n"
        + _txt_lista_materias()
    )

def _handle_faq(uid: str, texto_norm: str) -> str:
    item = _buscar_faq(texto_norm)
    if item:
        est.avanzar(uid, esperando="faq")
        return item["a"] + _pie("Escribí otro número para seguir consultando")
    if est.sumar_error(uid):
        est.salir(uid)
        return "⚠️ Demasiados intentos.\n\n" + MENU_TEXTO
    return "❌ No encontré esa pregunta.\n\n" + _txt_lista_faq()

# ─── Cómo llegar: estado inteligente ─────────────────────────────────────────

_TRANSPORTE_PUBLICO = (
    "🚌 *Transporte público a UNPAZ:*\n\n"
    "🚆 *Tren:*\n"
    "Ramal José C. Paz (Ferrocarril Mitre) → bajá en *Estación José C. Paz*\n"
    "Desde la estación: caminás por Ruta 24 hacia Av. Alem (~10 min a pie)\n\n"
    "🚌 *Colectivos:*\n"
    "• Línea 440 — pasa por Av. Alem\n"
    "• Consultá en moovit.com o Google Maps con destino 'UNPAZ José C. Paz'\n\n"
    "🔗 Planificá tu viaje: https://maps.google.com/?q=UNPAZ+Jose+C+Paz"
)

def _handle_viaje(uid: str, texto_norm: str) -> str:
    estado    = est.get(uid)
    esperando = estado.get("esperando")

    # Follow-up sobre transporte público (puede venir con o sin estado activo)
    if contiene_alguna(texto_norm, ["transporte", "colectivo", "micro", "tren", "que tomo",
                                     "que linea", "que colectivo", "que tren", "publico"]):
        est.salir(uid)
        return _TRANSPORTE_PUBLICO + _pie("Escribí MENÚ para más opciones")

    if esperando == "origen_viaje":
        # Detectar sede destino
        sede = "arregui" if "arregui" in texto_norm else "alem"

        # Detectar origen
        if contiene_alguna(texto_norm, ["acceso", "oeste", "moron", "merlo", "moreno", "ituzaingo", "haedo"]):
            origen = "desde_acceso_oeste"
        elif contiene_alguna(texto_norm, ["panamericana", "norte", "tigre", "pilar", "zona norte", "palermo", "capital", "caba"]):
            origen = "desde_panamericana"
        elif contiene_alguna(texto_norm, ["pie", "tren", "estacion", "caminando", "colectivo", "publico"]):
            origen = "a_pie"
        else:
            # No detectamos origen → mostrar las tres opciones
            est.salir(uid)
            return _txt_como_llegar_todo()

        # Quedarse en estado viaje para que el usuario pueda hacer follow-up
        est.avanzar(uid, esperando="viaje_followup")
        return _txt_como_llegar(sede, origen)

    if esperando == "viaje_followup":
        # Otra pregunta relacionada al viaje
        if contiene_alguna(texto_norm, ["arregui"]):
            est.avanzar(uid, esperando="viaje_followup")
            return _txt_como_llegar_todo()
        # Si no es de viaje, salimos del estado
        est.salir(uid)
        return None  # Dejar que el flujo principal lo maneje

    # Primera vez: preguntar desde dónde
    est.entrar(uid, "viaje", esperando="origen_viaje")
    return (
        "🗺️ *¿Cómo llego a UNPAZ?*\n\n"
        "Para darte las indicaciones más precisas, ¿desde dónde venís?\n\n"
        "_Ejemplo: 'Acceso Oeste', 'Panamericana', 'José C. Paz a pie'_"
    ) + _FOOTER

# ─── Respuesta directa por intención ─────────────────────────────────────────

_KW_HORARIO     = ["horario", "cuando cursa", "que dia", "aula de", "comision de"]
_KW_CORRELATIVA = ["correlativa", "requiere", "necesito tener", "previa", "para cursar"]
_KW_SEDE        = ["sede", "donde queda", "donde esta", "direccion", "edificio"]
_KW_LLEGAR      = ["como llego", "como llegar", "como ir a", "como voy", "indicaciones",
                   "transporte", "colectivo", "micro", "tren", "colectivos", "como me muevo",
                   "que tomo", "que linea", "que colectivo", "que tren"]
_KW_CALENDARIO  = ["calendario", "cuando empiezan", "inicio de clases", "inscripcion al trimestre"]
_KW_PLAN        = ["plan de estudio", "materias de la carrera", "que materias hay", "cuantos anos dura"]
_KW_COMUNIDAD   = ["grupo de whatsapp", "instagram", "facebook", "comunidad tuce", "redes sociales"]
_KW_GESTION     = ["campus virtual", "guarani", "siu guarani", "certificado de alumno", "boleto estudiantil", "equivalencias"]
_KW_CONTACTO    = ["mesa de ayuda", "correo de", "email de", "contacto de", "beca", "pasantia"]
_KW_CARRERA_DESC = ["que es la tuce", "de que trata", "perfil del egresado", "para que sirve", "descripcion de la carrera"]

def _respuesta_directa(uid: str, texto_norm: str, texto_original: str) -> str | None:
    # Materia específica mencionada por nombre
    materia = _buscar_materia_activa(texto_norm)
    if materia and not contiene_alguna(texto_norm, ["correlativa", "previa", "requiere"]):
        return _txt_horario_materia(materia)

    # Correlativa de materia específica
    if contiene_alguna(texto_norm, _KW_CORRELATIVA):
        info = _buscar_en_correlativas(texto_norm)
        if info:
            nombre = info["nombre"]
            if not info["necesita"]:
                return f"✅ *{nombre}*\n\nNo tiene correlativas." + _pie()
            previas = "\n".join(f"  • {CORRELATIVAS[c]['nombre']}" for c in info["necesita"])
            return f"🔗 *{nombre}*\n\nPara cursarla necesitás:\n{previas}" + _pie()

    if contiene_alguna(texto_norm, _KW_HORARIO):
        materia = _buscar_materia_activa(texto_norm)
        if materia:
            return _txt_horario_materia(materia)
        return _txt_lista_materias()

    if contiene_alguna(texto_norm, _KW_LLEGAR):
        return _handle_viaje(uid, texto_norm)

    if contiene_alguna(texto_norm, _KW_SEDE):
        if "arregui" in texto_norm:
            s = SEDES["arregui"]
            return f"📍 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}" + _pie()
        return _txt_sedes()

    if contiene_alguna(texto_norm, _KW_CALENDARIO):
        return _txt_calendario()

    if contiene_alguna(texto_norm, _KW_CARRERA_DESC):
        return _txt_carrera_desc()

    if contiene_alguna(texto_norm, _KW_PLAN):
        return _txt_plan()

    if contiene_alguna(texto_norm, _KW_COMUNIDAD):
        return _txt_comunidad()

    if contiene_alguna(texto_norm, _KW_GESTION):
        return _txt_gestion()

    if contiene_alguna(texto_norm, _KW_CONTACTO):
        return _txt_contactos()

    faq = _buscar_faq(texto_norm)
    if faq:
        return faq["a"] + _pie("Escribí MENÚ para más opciones")

    return None

# ─── Métricas ─────────────────────────────────────────────────────────────────

def _log(firebase_db, seccion: str):
    try:
        import datetime
        hoy = datetime.date.today().strftime("%Y-%m-%d")
        ref = firebase_db.reference(f"metricas/wa/{hoy}/{seccion}")
        ref.set((ref.get() or 0) + 1)
    except:
        pass

# ─── Función principal ────────────────────────────────────────────────────────

_KEYWORDS_OPCION = {
    1: ["informacion de la carrera", "info carrera", "plan de estudio", "sobre la carrera"],
    2: ["horarios del trimestre", "horario de materias", "ver horarios", "materias disponibles"],
    3: ["comunidad tuce", "grupo de whatsapp", "redes sociales"],
    4: ["preguntas frecuentes", "faq", "dudas frecuentes"],
    5: ["sedes unpaz", "ver sedes", "donde queda unpaz"],
}

def procesar(from_id: str, texto: str, firebase_db, responder_ia_fn) -> str:
    texto_norm = normalizar(texto)
    nombre_db  = _get_nombre(firebase_db, from_id)
    saludo     = f", {nombre_db}" if nombre_db else ""

    estado  = est.get(from_id)
    seccion = estado.get("seccion")

    # ── Comandos globales ─────────────────────────────────────────────────────
    if es_menu(texto) or texto_norm == "manu":
        est.salir(from_id)
        _log(firebase_db, "menu")
        return MENU_TEXTO

    if texto_norm in ("cerrar", "salir", "chau", "adios", "hasta luego"):
        est.salir(from_id)
        _log(firebase_db, "cerrar")
        return MSG_CERRAR.format(nombre=saludo)

    if texto_norm in ("atras", "volver", "anterior"):
        if seccion == "carrera" and estado.get("esperando") == "correlativa":
            est.entrar(from_id, "carrera")
            return SUBMENU_CARRERA
        ultima = est.volver_atras(from_id)
        if ultima == "carrera":
            return SUBMENU_CARRERA
        if ultima == "horarios":
            return _txt_lista_materias()
        if ultima == "faq":
            return _txt_lista_faq()
        return MENU_TEXTO

    # ── Flujo de registro de nombre ───────────────────────────────────────────
    if seccion == "esperando_nombre":
        nombre_ingresado = texto.strip().split()[0].capitalize()
        _set_nombre(firebase_db, from_id, nombre_ingresado)  # también setea visto=True
        est.salir(from_id)
        _log(firebase_db, "nombre_registrado")
        return (
            f"¡Buenísimo, {nombre_ingresado}! 😊 Ya te tengo registrado.\n\n"
            + MENU_TEXTO
        )

    # ── Estado activo ─────────────────────────────────────────────────────────
    if seccion == "carrera":
        return _handle_carrera(from_id, texto_norm)

    if seccion == "horarios":
        return _handle_horarios(from_id, texto_norm)

    if seccion == "faq":
        return _handle_faq(from_id, texto_norm)

    if seccion == "viaje":
        resp = _handle_viaje(from_id, texto_norm)
        if resp is not None:
            return resp
        # resp=None significa que no era una consulta de viaje; continuamos el flujo normal

    # ── Sin estado: opciones numeradas del menú (5 opciones) ─────────────────
    num = extraer_numero(texto_norm)
    if num is None:
        for n, kws in _KEYWORDS_OPCION.items():
            if contiene_alguna(texto_norm, kws):
                num = n
                break

    if num == 1:
        est.entrar(from_id, "carrera")
        _log(firebase_db, "carrera")
        return SUBMENU_CARRERA

    if num == 2:
        est.entrar(from_id, "horarios", esperando="materia")
        _log(firebase_db, "horarios")
        return _txt_lista_materias()

    if num == 3:
        _log(firebase_db, "comunidad")
        return _txt_comunidad()

    if num == 4:
        est.entrar(from_id, "faq")
        _log(firebase_db, "faq")
        return _txt_lista_faq()

    if num == 5:
        _log(firebase_db, "sedes")
        return _txt_sedes()

    # ── Identidad del bot ─────────────────────────────────────────────────────
    if contiene_alguna(texto_norm, ["quien te creo", "quien te hizo", "quien te desarrollo",
                                     "bytes creativos", "quien sos", "como te llamas",
                                     "cual es tu nombre", "quien es tu creador"]):
        return (
            "Soy *Alma TUCE* 🎓\n\n"
            "Fui desarrollada por *Bytes Creativos*, agencia de marketing y soluciones digitales nacida en la UNPAZ.\n"
            "📱 https://bytescreativos.com.ar/\n"
            "📸 @bytescreativoss"
        ) + _pie()

    # ── Director de la carrera ────────────────────────────────────────────────
    if contiene_alguna(texto_norm, ["director", "fiorenzo", "quien dirige", "coordinador"]):
        d = DATA_DIRECTOR
        return (
            f"👤 *{d['cargo']}:*\n\n"
            f"{d['nombre']}\n"
            f"🔗 {d['linkedin']}"
        ) + _pie()

    # ── Texto libre: respuesta directa por intención ──────────────────────────
    directa = _respuesta_directa(from_id, texto_norm, texto)
    if directa:
        _log(firebase_db, "directa")
        return directa

    # ── Primer contacto: pedir nombre (solo en el primer mensaje, nunca después) ─
    if not nombre_db and not _get_visto(firebase_db, from_id):
        _marcar_visto(firebase_db, from_id)
        est.entrar(from_id, "esperando_nombre")
        _log(firebase_db, "bienvenida")
        return PREGUNTA_NOMBRE

    # ── Fallback: IA interna (transparente para el usuario) ───────────────────
    _log(firebase_db, "ia_fallback")
    return responder_ia_fn(texto, from_id) + _pie("Seguí preguntando o escribí MENÚ para más opciones")
