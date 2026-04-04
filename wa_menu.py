# wa_menu.py — Handler WhatsApp v4
#
# Filosofía:
#   - Si el usuario pregunta algo y tenemos la respuesta, la damos directo.
#   - El menú guía pero no bloquea.
#   - Tono: registro "vos", informal pero respetuoso, consistente.
#   - Todas las respuestas terminan con MENÚ · ATRÁS · CERRAR.
#   - El bot recuerda el nombre del usuario (Firebase).

from normalizer import normalizar, es_menu, extraer_numero, contiene_alguna
import estado as est
from materias_db import LISTA_HORARIOS
from faq_data import FAQ
from datos_carrera import DATA_PLAN, DATA_CALENDARIO, CORRELATIVAS, correlativas_de

# ─── Sedes ────────────────────────────────────────────────────────────────────
SEDES = {
    "alem": {
        "nombre":    "Sede Alem",
        "direccion": "Leandro N. Alem 4731, José C. Paz, Buenos Aires",
        "maps":      "https://maps.google.com/?q=Leandro+N.+Alem+4731,+Jose+C.+Paz,+Buenos+Aires",
    },
    "arregui": {
        "nombre":    "Sede Arregui",
        "direccion": "Av. Héctor Arregui 501, José C. Paz, Buenos Aires",
        "maps":      "https://maps.google.com/?q=Av.+Hector+Arregui+501,+Jose+C.+Paz,+Buenos+Aires",
    },
}

# ─── Materias del plan (para correlativas — incluye todas, no solo las activas) ─
_MATERIAS_PLAN = sorted([info["nombre"] for info in CORRELATIVAS.values()])

# ─── Materias activas este trimestre ─────────────────────────────────────────
_MATERIAS = sorted(list(set(f[0] for f in LISTA_HORARIOS)))

# ─── Footer estándar ─────────────────────────────────────────────────────────
_FOOTER = "\n\n*MENÚ* · *ATRÁS* · *CERRAR*"

def _pie(extra: str = "") -> str:
    """Devuelve el pie estándar con navegación."""
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
    "5️⃣  📍 Sedes UNPAZ\n"
    "6️⃣  🤖 Consultar a la IA\n\n"
    "_Escribí el número, el nombre de la opción, o preguntame directamente._"
    + _FOOTER
)

MSG_NO_ENTENDI = (
    "No tengo información sobre tu solicitud.\n"
    "Podés escribir *MENÚ* para ver las opciones disponibles."
    + _FOOTER
)

MSG_CERRAR = (
    "👋 ¡Hasta luego{nombre}! Cuando necesites algo, acá estoy. 😊"
)

# ─── Firebase: memoria de nombre ─────────────────────────────────────────────

def _esc_uid(uid: str) -> str:
    """Escapa caracteres inválidos para claves de Firebase (. @ +)."""
    return uid.replace(".", "___DOT___").replace("@", "___AT___").replace("+", "___PLUS___")

def _get_nombre(firebase_db, uid: str) -> str | None:
    try:
        return firebase_db.reference(f"wa_usuarios/{_esc_uid(uid)}/nombre").get()
    except:
        return None

def _set_nombre(firebase_db, uid: str, nombre: str):
    try:
        firebase_db.reference(f"wa_usuarios/{_esc_uid(uid)}").set({"nombre": nombre.strip().capitalize()})
    except:
        pass

# ─── Búsqueda de materias ─────────────────────────────────────────────────────

def _buscar_materia_activa(texto_norm: str) -> str | None:
    """Busca en las materias activas del trimestre (LISTA_HORARIOS)."""
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
    """Busca en TODAS las materias del plan (incluye las que no están activas)."""
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

def _txt_calendario() -> str:
    resp = "🗓️ *Calendario Académico 2026*\n\n"
    for v in DATA_CALENDARIO.values():
        resp += v + "\n\n"
    resp += "🔗 https://unpaz.edu.ar/calendario-academico"
    return resp + _pie()

def _txt_gestion() -> str:
    return (
        "🖥️ *Gestión Alumnos:*\n\n"
        "🎓 Campus Virtual:\nhttps://campusvirtual.unpaz.edu.ar/\n\n"
        "🖥️ SIU Guaraní (inscripciones, certificados, boleto):\nhttps://estudiantes.unpaz.edu.ar/autogestion/\n\n"
        "📄 Equivalencias:\nhttps://unpaz.edu.ar/formularioequivalencias\n\n"
        "🌐 Sitio oficial:\nhttps://unpaz.edu.ar"
    ) + _pie()

def _txt_sedes() -> str:
    resp = "📍 *Sedes UNPAZ:*\n\n"
    for s in SEDES.values():
        resp += f"🏢 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}\n\n"
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
    "1. 📄 Plan de estudios\n"
    "2. 🔗 Correlativas\n"
    "3. 🗓️ Calendario académico\n"
    "4. 🖥️ Gestión (Campus / SIU Guaraní)\n"
    "5. 📍 Sedes\n"
    "6. 📩 Contactos y Mesa de Ayuda"
) + _pie("Escribí el número de la opción")

_KEYWORDS_CARRERA = {
    1: ["plan", "estudio", "materias de la carrera", "que se estudia"],
    2: ["correlativa", "previa", "requiere", "para cursar", "necesito tener"],
    3: ["calendario", "fecha", "cuando empiezan", "inicio", "semestre", "trimestre"],
    4: ["gestion", "campus", "guarani", "siu", "certificado", "boleto", "equivalencia"],
    5: ["sede", "donde", "direccion", "como llego"],
    6: ["contacto", "ayuda", "mail", "email", "beca", "pasantia", "orvig"],
}

def _handle_carrera(uid: str, texto_norm: str) -> str:
    estado    = est.get(uid)
    esperando = estado.get("esperando")

    if esperando == "correlativa":
        info = _buscar_en_correlativas(texto_norm)
        if info:
            est.avanzar(uid, esperando="correlativa")  # permanecer para más consultas
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
        1: (None,          _txt_plan),
        2: ("correlativa", lambda: "🔗 *Correlativas*\n\nEscribí el nombre (o parte) de la materia:" + _pie("Ejemplo: 'marketing', 'ingles', 'desarrollo web'")),
        3: (None,          _txt_calendario),
        4: (None,          _txt_gestion),
        5: (None,          _txt_sedes),
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
        est.avanzar(uid, esperando="materia")  # permanece en horarios para más consultas
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
        est.avanzar(uid, esperando="faq")  # permanece para más consultas
        return item["a"] + _pie("Escribí otro número para seguir consultando")
    if est.sumar_error(uid):
        est.salir(uid)
        return "⚠️ Demasiados intentos.\n\n" + MENU_TEXTO
    return "❌ No encontré esa pregunta.\n\n" + _txt_lista_faq()

# ─── Respuesta directa por intención ─────────────────────────────────────────

_KW_HORARIO     = ["horario", "cuando cursa", "que dia", "aula de", "comision de"]
_KW_CORRELATIVA = ["correlativa", "requiere", "necesito tener", "previa", "para cursar"]
_KW_SEDE        = ["sede", "donde queda", "donde esta", "direccion", "como llego"]
_KW_CALENDARIO  = ["calendario", "cuando empiezan", "inicio de clases", "inscripcion al trimestre"]
_KW_PLAN        = ["plan de estudio", "materias de la carrera", "que materias hay", "cuantos anos dura"]
_KW_COMUNIDAD   = ["grupo de whatsapp", "instagram", "facebook", "comunidad tuce", "redes sociales"]
_KW_GESTION     = ["campus virtual", "guarani", "siu guarani", "certificado de alumno", "boleto estudiantil", "equivalencias"]
_KW_CONTACTO    = ["mesa de ayuda", "correo de", "email de", "contacto de", "beca", "pasantia"]

def _respuesta_directa(texto_norm: str, texto_original: str) -> str | None:
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

    if contiene_alguna(texto_norm, _KW_SEDE):
        if "alem" in texto_norm:
            s = SEDES["alem"]
            return f"📍 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}" + _pie()
        if "arregui" in texto_norm:
            s = SEDES["arregui"]
            return f"📍 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}" + _pie()
        return _txt_sedes()

    if contiene_alguna(texto_norm, _KW_CALENDARIO):
        return _txt_calendario()

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
    1: ["informacion de la carrera", "info carrera", "plan de estudio"],
    2: ["horarios del trimestre", "horario de materias", "ver horarios", "materias disponibles"],
    3: ["comunidad tuce", "grupo de whatsapp", "redes sociales"],
    4: ["preguntas frecuentes", "faq", "dudas frecuentes"],
    5: ["sedes unpaz", "ver sedes", "donde queda unpaz"],
    6: ["consultar ia", "hablar con ia", "modo ia"],
}

def procesar(from_id: str, texto: str, firebase_db, responder_ia_fn) -> str:
    texto_norm = normalizar(texto)
    nombre_db  = _get_nombre(firebase_db, from_id)
    saludo     = f", {nombre_db}" if nombre_db else ""

    # ── Estado actual ─────────────────────────────────────────────────────────
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
        # Si estamos en correlativas, volvemos al submenú de carrera
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

    if seccion == "esperando_nombre":
        nombre_ingresado = texto.strip().split()[0].capitalize()
        _set_nombre(firebase_db, from_id, nombre_ingresado)
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

    if seccion == "ia":
        _log(firebase_db, "ia")
        return responder_ia_fn(texto) + _pie("Seguí preguntando o escribí MENÚ para más opciones")

    # ── Sin estado: primero opciones numeradas del menú ───────────────────────
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

    if num == 6:
        est.entrar(from_id, "ia")
        _log(firebase_db, "ia_activado")
        return (
            "🤖 *Modo IA activado*\n\n"
            "Preguntame sobre la TUCE, trámites, becas o UNPAZ.\n"
            "_No respondo sobre horarios ni aulas — para eso usá la opción 2._"
        ) + _pie()

    # ── Respuestas especiales antes del fallback ──────────────────────────────
    # Quién te creó / quién sos
    if contiene_alguna(texto_norm, ["quien te creo", "quien te hizo", "quien te desarrollo", "bytes creativos", "quien sos", "como te llamas", "cual es tu nombre"]):
        return (
            "Soy *Alma TUCE* 🎓\n\n"
            "Fui desarrollada por *Bytes Creativos*, agencia de marketing y soluciones digitales nacida en la UNPAZ.\n"
            "📱 https://bytescreativos.com.ar/\n"
            "📸 @bytescreativoss"
        ) + _pie()

    # ── Texto libre: respuesta directa por intención ──────────────────────────
    directa = _respuesta_directa(texto_norm, texto)
    if directa:
        _log(firebase_db, "directa")
        return directa

    # ── Primer contacto: pedir nombre ─────────────────────────────────────────
    if not nombre_db:
        est.entrar(from_id, "esperando_nombre")
        _log(firebase_db, "bienvenida")
        return PREGUNTA_NOMBRE

    # ── No entendí ────────────────────────────────────────────────────────────
    _log(firebase_db, "fallback")
    return MSG_NO_ENTENDI
