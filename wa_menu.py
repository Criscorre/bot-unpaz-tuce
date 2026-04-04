# wa_menu.py — Handler WhatsApp v3
#
# Filosofía: si el usuario pregunta algo y tenemos la respuesta, la damos
# directamente sin obligar a navegar por el menú. El menú existe para guiar,
# no para bloquear.
#
# Prioridad de procesamiento:
#   1. Comando global (menu/hola/start) → siempre muestra el menú
#   2. Respuesta directa por intención → si detectamos qué quiere, respondemos
#   3. Estado activo → seguimos el flujo en curso
#   4. Selección numerada del menú
#   5. Fallback → menú + "no entendí"

from normalizer import normalizar, es_menu, extraer_numero, contiene_alguna
import estado as est
from materias_db import LISTA_HORARIOS
from faq_data import FAQ
from datos_carrera import DATA_PLAN, DATA_CALENDARIO, CORRELATIVAS, correlativas_de

# ─── Datos de sedes ───────────────────────────────────────────────────────────
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

# ─── Materias indexadas ───────────────────────────────────────────────────────
_MATERIAS = sorted(list(set(f[0] for f in LISTA_HORARIOS)))

# ─── Textos fijos ─────────────────────────────────────────────────────────────
BIENVENIDA = (
    "👋 ¡Hola! Soy el asistente de la\n"
    "*Tecnicatura Universitaria en Comercio Electrónico - UNPAZ*\n\n"
    "Podés preguntarme directamente lo que necesitás, o escribir *MENÚ* para ver todas las opciones."
)

MENU_TEXTO = (
    "📋 *Menú principal:*\n\n"
    "1️⃣  📚 Información de la carrera\n"
    "2️⃣  🕒 Horarios del cuatrimestre\n"
    "3️⃣  👥 Comunidad TUCE\n"
    "4️⃣  ❓ Preguntas frecuentes\n"
    "5️⃣  📍 Sedes UNPAZ\n"
    "6️⃣  🤖 Consultar a la IA\n\n"
    "_Escribí el número, el nombre, o preguntame directamente._\n"
    "_Escribí MENÚ en cualquier momento para volver acá._"
)

MSG_NO_ENTENDI = (
    "❓ No entendí tu consulta.\n\n"
    + MENU_TEXTO
)

# ─── Formateo de horarios ─────────────────────────────────────────────────────

def _txt_lista_materias() -> str:
    lineas = [
        "🕒 *Horarios — 1er cuatrimestre 2026*\n",
        "Seleccioná una materia por número o escribí su nombre:\n",
    ]
    for i, m in enumerate(_MATERIAS, 1):
        lineas.append(f"  {i}. {m}")
    lineas.append("\n_Escribí MENÚ para volver._")
    return "\n".join(lineas)

def _txt_horario_materia(materia: str) -> str:
    filas = [f for f in LISTA_HORARIOS if f[0] == materia]
    cor   = correlativas_de(materia)
    resp  = f"🕒 *{materia}*\n"
    if cor and "Sin correlativas" not in cor:
        resp += f"_{cor}_\n"
    resp += "\n"
    for f in filas:
        aula = f[8] if f[8] and f[8] != "//" else "A confirmar"
        resp += f"👥 *Com {f[1]}* — {f[2]} {f[3][:5]}–{f[4][:5]} hs\n"
        resp += f"🏢 Aula: {aula} | {f[5]}\n"
        resp += "──────────\n"
    resp += "\n_Escribí otra materia, un número, o MENÚ para volver._"
    return resp

def _buscar_materia(texto_norm: str) -> str | None:
    """Busca por número o nombre parcial. Devuelve nombre exacto o None."""
    num = extraer_numero(texto_norm)
    if num is not None and 1 <= num <= len(_MATERIAS):
        return _MATERIAS[num - 1]
    # Búsqueda exacta normalizada
    for m in _MATERIAS:
        if texto_norm == normalizar(m):
            return m
    # Búsqueda parcial: todas las palabras del input en el nombre
    palabras = [p for p in texto_norm.split() if len(p) >= 3]
    if palabras:
        for m in _MATERIAS:
            m_norm = normalizar(m)
            if all(p in m_norm for p in palabras):
                return m
    # Búsqueda con una sola palabra clave larga
    for p in sorted(palabras, key=len, reverse=True):
        if len(p) >= 4:
            for m in _MATERIAS:
                if p in normalizar(m):
                    return m
    return None

# ─── Sección: Carrera ─────────────────────────────────────────────────────────

SUBMENU_CARRERA = (
    "📚 *Información de la carrera:*\n\n"
    "1. 📄 Plan de estudios\n"
    "2. 🔗 Correlativas\n"
    "3. 🗓️ Calendario académico\n"
    "4. 🖥️ Gestión (Campus / SIU Guaraní)\n"
    "5. 📍 Sedes\n"
    "6. 📩 Contactos y Mesa de Ayuda\n\n"
    "_Escribí el número o MENÚ para volver._"
)

def _txt_plan() -> str:
    resp = "📄 *Plan de Estudios*\n*Tecnicatura Universitaria en Comercio Electrónico*\n\n"
    for anio, materias in DATA_PLAN.items():
        resp += f"*{anio}:*\n"
        for m in materias:
            resp += f"  • {m}\n"
        resp += "\n"
    resp += "_Escribí MENÚ para volver._"
    return resp

def _txt_calendario() -> str:
    resp = "🗓️ *Calendario Académico 2026*\n\n"
    for v in DATA_CALENDARIO.values():
        resp += v + "\n\n"
    resp += "_Escribí MENÚ para volver._"
    return resp

def _txt_gestion() -> str:
    return (
        "🖥️ *Gestión Alumnos:*\n\n"
        "🎓 Campus Virtual:\nhttps://campusvirtual.unpaz.edu.ar/\n\n"
        "🖥️ SIU Guaraní (inscripciones, certificados, boleto):\nhttps://estudiantes.unpaz.edu.ar/autogestion/\n\n"
        "📄 Equivalencias:\nhttps://unpaz.edu.ar/formularioequivalencias\n\n"
        "_Escribí MENÚ para volver._"
    )

def _txt_sedes() -> str:
    resp = "📍 *Sedes UNPAZ:*\n\n"
    for s in SEDES.values():
        resp += f"🏢 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}\n\n"
    resp += "_Escribí MENÚ para volver._"
    return resp

def _txt_contactos() -> str:
    return (
        "📩 *Contactos y Mesa de Ayuda:*\n\n"
        "🤝 Acceso y Apoyo (Becas/Tutorías):\n  accesoapoyo@unpaz.edu.ar\n\n"
        "📝 CIU (Ingreso):\n  ciu@unpaz.edu.ar\n\n"
        "👤 Consultas Estudiantes:\n  consultasestudiantes@unpaz.edu.ar\n\n"
        "💻 Soporte SIU Guaraní:\n  soporteinscripciones@unpaz.edu.ar\n\n"
        "🌐 UNPAZ Virtual:\n  formacionvirtual@unpaz.edu.ar\n\n"
        "💜 ORVIG (Género):\n  orvig@unpaz.edu.ar\n\n"
        "_Escribí MENÚ para volver._"
    )

def _txt_comunidad() -> str:
    return (
        "👥 *Comunidad TUCE*\n\nSumate 👇\n\n"
        "💬 *WhatsApp TUCE:*\nhttps://chat.whatsapp.com/FSwCNJd2GirBVIVCZDGU0B\n\n"
        "💬 *Grupo adicional:*\nhttps://chat.whatsapp.com/JElcFd4U08QBKsL1J1YM8u\n\n"
        "📸 *Instagram:*\nhttps://www.instagram.com/tuce_unpaz/\n\n"
        "📘 *Facebook:*\nhttps://m.facebook.com/tuceunpaz/\n\n"
        "_Escribí MENÚ para volver._"
    )

# ─── FAQ ──────────────────────────────────────────────────────────────────────

def _txt_lista_faq() -> str:
    lineas = ["❓ *Preguntas frecuentes:*\n"]
    for i, item in enumerate(FAQ, 1):
        lineas.append(f"  {i}. {item['q']}")
    lineas.append("\n_Escribí el número de tu pregunta, o MENÚ para volver._")
    return "\n".join(lineas)

def _buscar_faq(texto_norm: str) -> dict | None:
    num = extraer_numero(texto_norm)
    if num is not None and 1 <= num <= len(FAQ):
        return FAQ[num - 1]
    palabras = [p for p in texto_norm.split() if len(p) >= 4]
    for item in FAQ:
        q_norm = normalizar(item["q"])
        if any(p in q_norm for p in palabras):
            return item
    return None

# ─── Detección de intención directa ──────────────────────────────────────────
# Si el usuario escribe algo que claramente tiene respuesta en nuestros datos,
# respondemos directamente sin exigir que navegue por el menú.

_KEYWORDS_HORARIO    = ["horario", "hora", "cuando cursa", "dia de", "aula", "comision", "cuando es"]
_KEYWORDS_CORRELATIVA = ["correlativa", "requiere", "necesito tener", "previa", "para cursar"]
_KEYWORDS_SEDE       = ["sede", "donde queda", "donde esta", "direccion", "como llego"]
_KEYWORDS_CALENDARIO = ["calendario", "cuando empiezan", "inicio de clases", "inscripcion", "cuatrimestre"]
_KEYWORDS_PLAN       = ["plan de estudio", "materias de la carrera", "que materias hay", "cuantos anos"]
_KEYWORDS_COMUNIDAD  = ["grupo de whatsapp", "instagram", "facebook", "comunidad", "redes sociales"]
_KEYWORDS_GESTION    = ["campus", "guarani", "siu", "certificado", "boleto estudiantil", "equivalencia"]
_KEYWORDS_CONTACTO   = ["contacto", "mail", "email", "correo", "mesa de ayuda", "beca", "pasantia"]

def _respuesta_directa(texto_norm: str, texto_original: str) -> str | None:
    """
    Intenta dar una respuesta directa si detecta la intención claramente.
    Devuelve la respuesta como string, o None si no puede determinar la intención.
    """
    # ¿Pregunta por una materia específica?
    materia = _buscar_materia(texto_norm)
    if materia:
        return _txt_horario_materia(materia)

    # ¿Pregunta por correlativas de una materia específica?
    if contiene_alguna(texto_norm, _KEYWORDS_CORRELATIVA):
        # Intentar extraer nombre de materia del mismo mensaje
        materia = _buscar_materia(texto_norm)
        if materia:
            cor = correlativas_de(materia)
            return f"🔗 *{materia}*\n\n{cor}\n\n_Escribí MENÚ para volver._"
        # No encontró materia → pedir que especifique
        return None

    # ¿Pregunta por horarios en general?
    if contiene_alguna(texto_norm, _KEYWORDS_HORARIO):
        materia = _buscar_materia(texto_norm)
        if materia:
            return _txt_horario_materia(materia)
        return _txt_lista_materias()

    # ¿Pregunta por una sede?
    if contiene_alguna(texto_norm, _KEYWORDS_SEDE):
        if contiene_alguna(texto_norm, ["alem"]):
            s = SEDES["alem"]
            return f"📍 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}\n\n_Escribí MENÚ para volver._"
        if contiene_alguna(texto_norm, ["arregui"]):
            s = SEDES["arregui"]
            return f"📍 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}\n\n_Escribí MENÚ para volver._"
        return _txt_sedes()

    # ¿Pregunta por el calendario?
    if contiene_alguna(texto_norm, _KEYWORDS_CALENDARIO):
        return _txt_calendario()

    # ¿Pregunta por el plan de estudios?
    if contiene_alguna(texto_norm, _KEYWORDS_PLAN):
        return _txt_plan()

    # ¿Pregunta por la comunidad / redes?
    if contiene_alguna(texto_norm, _KEYWORDS_COMUNIDAD):
        return _txt_comunidad()

    # ¿Pregunta por gestión / campus / SIU?
    if contiene_alguna(texto_norm, _KEYWORDS_GESTION):
        return _txt_gestion()

    # ¿Pregunta por contactos / mesa de ayuda?
    if contiene_alguna(texto_norm, _KEYWORDS_CONTACTO):
        return _txt_contactos()

    # ¿Hay una pregunta frecuente que coincida?
    faq = _buscar_faq(texto_norm)
    if faq:
        return faq["a"] + "\n\n_Escribí MENÚ para ver más opciones._"

    return None

# ─── Handlers de sección ─────────────────────────────────────────────────────

def _handle_carrera(uid: str, texto_norm: str) -> str:
    estado    = est.get(uid)
    esperando = estado.get("esperando")

    if esperando == "correlativa":
        materia = _buscar_materia(texto_norm)
        if materia:
            cor = correlativas_de(materia)
            est.avanzar(uid, esperando=None)
            return (
                f"🔗 *{materia}*\n\n{cor}\n\n"
                "_Escribí otra materia, un número del submenú o MENÚ para volver._"
            )
        if est.sumar_error(uid):
            est.salir(uid)
            return "⚠️ No pude encontrar esa materia.\n\n" + MENU_TEXTO
        return (
            "❌ No encontré esa materia. Intentá con otra parte del nombre.\n"
            "_Ejemplo: 'desarrollo', 'ingles', 'marketing'_"
        )

    # Sub-menú de carrera: acepta número o palabra clave
    _MAP = {
        1: (None,          _txt_plan),
        2: ("correlativa", lambda: "🔗 Escribí el nombre (o parte) de la materia:\n_Ejemplo: 'marketing', 'ingles'_"),
        3: (None,          _txt_calendario),
        4: (None,          _txt_gestion),
        5: (None,          _txt_sedes),
        6: (None,          _txt_contactos),
    }
    _KEYWORDS_SUB = {
        1: ["plan", "estudio", "materias de la carrera"],
        2: ["correlativa", "previa", "requiere"],
        3: ["calendario", "fecha", "cuando"],
        4: ["gestion", "campus", "guarani", "siu", "certificado"],
        5: ["sede", "donde"],
        6: ["contacto", "ayuda", "mail", "beca"],
    }

    num = extraer_numero(texto_norm)
    if num is None:
        for n, kws in _KEYWORDS_SUB.items():
            if contiene_alguna(texto_norm, kws):
                num = n
                break

    if num in _MAP:
        next_esp, fn = _MAP[num]
        est.entrar(uid, "carrera", esperando=next_esp)
        return fn()

    if est.sumar_error(uid):
        est.salir(uid)
        return "⚠️ Demasiados intentos. Volviendo al menú.\n\n" + MENU_TEXTO
    return SUBMENU_CARRERA

def _handle_horarios(uid: str, texto_norm: str) -> str:
    materia = _buscar_materia(texto_norm)
    if materia:
        est.avanzar(uid, esperando="materia")
        return _txt_horario_materia(materia)
    if est.sumar_error(uid):
        est.salir(uid)
        return "⚠️ No encontré esa materia. Volviendo al menú.\n\n" + MENU_TEXTO
    return (
        "❌ No encontré esa materia. Probá con el número de la lista o parte del nombre.\n\n"
        + _txt_lista_materias()
    )

def _handle_faq(uid: str, texto_norm: str) -> str:
    item = _buscar_faq(texto_norm)
    if item:
        est.avanzar(uid, esperando="faq")
        return item["a"] + "\n\n_Escribí otro número o MENÚ para volver._"
    if est.sumar_error(uid):
        est.salir(uid)
        return "⚠️ Demasiados intentos. Volviendo al menú.\n\n" + MENU_TEXTO
    return "❌ No encontré esa pregunta.\n\n" + _txt_lista_faq()

# ─── Métricas ─────────────────────────────────────────────────────────────────

def _log(firebase_db, seccion: str):
    try:
        import datetime
        hoy = datetime.date.today().strftime("%Y-%m-%d")
        ref = firebase_db.reference(f"metricas/wa/{hoy}/{seccion}")
        actual = ref.get() or 0
        ref.set(actual + 1)
    except Exception:
        pass

# ─── Función principal ────────────────────────────────────────────────────────

def procesar(from_id: str, texto: str, firebase_db, responder_ia_fn) -> str:
    texto_norm = normalizar(texto)

    # ── 1. Comandos globales ──────────────────────────────────────────────────
    if es_menu(texto) or texto_norm in ("menu", "manu"):
        est.salir(from_id)
        _log(firebase_db, "menu")
        return MENU_TEXTO

    estado  = est.get(from_id)
    seccion = estado.get("seccion")

    # ── 2. Estado activo → el flujo en curso tiene prioridad ─────────────────
    if seccion == "carrera":
        return _handle_carrera(from_id, texto_norm)

    if seccion == "horarios":
        return _handle_horarios(from_id, texto_norm)

    if seccion == "faq":
        return _handle_faq(from_id, texto_norm)

    if seccion == "ia":
        _log(firebase_db, "ia")
        return responder_ia_fn(texto) + "\n\n_Escribí MENÚ para volver al menú._"

    # ── 3. Sin estado activo: primero menú numerado, luego texto libre ────────
    # Números 1-5 siempre van al menú principal (nunca a materias)
    num = extraer_numero(texto_norm)

    _KEYWORDS_OPCION = {
        1: ["informacion", "info carrera", "plan de estudio"],
        2: ["horarios", "horario de", "que materias hay", "materias disponibles"],
        3: ["comunidad", "grupo de whatsapp", "instagram", "facebook", "redes sociales"],
        4: ["preguntas frecuentes", "faq", "dudas frecuentes"],
        5: ["sede", "donde queda", "donde esta", "direccion", "como llego"],
        6: ["consultar ia", "hablar con ia", "pregunta a la ia"],
    }
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
            "Preguntame sobre la carrera, trámites, becas o UNPAZ.\n"
            "_Escribí MENÚ para volver._"
        )

    # ── 4. Texto libre sin estado: respuesta directa por intención ───────────
    directa = _respuesta_directa(texto_norm, texto)
    if directa:
        _log(firebase_db, "directa")
        return directa

    # ── 5. Primer contacto → bienvenida ──────────────────────────────────────
    if estado.get("errores", 0) == 0:
        _log(firebase_db, "bienvenida")
        est.entrar(from_id, None)  # marcar que ya fue saludado
        est.salir(from_id)
        return BIENVENIDA + "\n\n" + MENU_TEXTO

    # ── 6. Fallback ───────────────────────────────────────────────────────────
    _log(firebase_db, "fallback")
    return MSG_NO_ENTENDI
