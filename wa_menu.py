# wa_menu.py — Handler de WhatsApp con menú guiado (v2)
#
# Arquitectura:
#   procesar(from_id, texto, firebase_db, responder_ia_fn) → str
#
# Flujo:
#   1. Normalizar input
#   2. Comandos globales (menu/volver) → siempre funcionan
#   3. Si hay estado activo → delegar al handler de la sección
#   4. Sin estado → interpretar como selección del menú principal
#   5. Input desconocido → mensaje de error + menú (nunca IA por defecto)
#
# La IA solo se usa cuando el usuario elige explícitamente la opción 5.

from normalizer import normalizar, es_menu, extraer_numero, contiene_alguna
import estado as est
from materias_db import LISTA_HORARIOS
from faq_data import FAQ
from datos_carrera import DATA_PLAN, DATA_CALENDARIO, CORRELATIVAS, correlativas_de

# ─── Textos fijos ─────────────────────────────────────────────────────────────

BIENVENIDA = (
    "¡Hola! 😃\n"
    "Soy el asistente de la *TUCE - UNPAZ*.\n\n"
    "Escribí *MENÚ* para ver todas las opciones disponibles."
)

MENU_TEXTO = (
    "📋 *Menú principal:*\n\n"
    "1️⃣  📚 Información de la carrera\n"
    "2️⃣  🕒 Horarios de materias\n"
    "3️⃣  👥 Comunidad TUCE\n"
    "4️⃣  ❓ Preguntas frecuentes\n"
    "5️⃣  🤖 Consultar a la IA\n\n"
    "_Escribí el número o el nombre de la opción._\n"
    "_Escribí MENÚ en cualquier momento para volver acá._"
)

MSG_NO_ENTENDI = (
    "❓ No entendí tu consulta.\n"
    "Escribí *MENÚ* para ver las opciones disponibles."
)

MSG_DEMASIADOS_ERRORES = "⚠️ Demasiados intentos. Volviendo al menú...\n\n"

# ─── Materias ─────────────────────────────────────────────────────────────────

_MATERIAS = sorted(list(set(f[0] for f in LISTA_HORARIOS)))

def _txt_lista_materias() -> str:
    lineas = [
        "🕒 *Horarios del cuatrimestre en curso*\n",
        "Seleccioná una materia por número o nombre:\n",
    ]
    for i, m in enumerate(_MATERIAS, 1):
        lineas.append(f"{i}. {m}")
    lineas.append("\n_Escribí MENÚ para volver al menú principal._")
    return "\n".join(lineas)

def _txt_horarios_materia(materia: str) -> str:
    filas = [f for f in LISTA_HORARIOS if f[0] == materia]
    resp  = f"📍 *{materia}*\n\n"
    for f in filas:
        resp += f"👥 *Com {f[1]}* — {f[2]} {f[3][:5]}–{f[4][:5]} hs\n"
        resp += f"🏢 {f[8]} | {f[5]}\n"
        resp += "──────────\n"
    resp += "\n_Escribí otro número para ver otra materia, o MENÚ para volver._"
    return resp

def _buscar_materia(texto_norm: str) -> str | None:
    """Busca por número o nombre parcial. Devuelve nombre exacto o None."""
    num = extraer_numero(texto_norm)
    if num is not None and 1 <= num <= len(_MATERIAS):
        return _MATERIAS[num - 1]
    for m in _MATERIAS:
        if texto_norm in normalizar(m):
            return m
    for palabra in texto_norm.split():
        if len(palabra) >= 4:
            for m in _MATERIAS:
                if palabra in normalizar(m):
                    return m
    return None

# ─── Sección: Carrera ─────────────────────────────────────────────────────────

SUBMENU_CARRERA = (
    "📚 *Información de la carrera:*\n\n"
    "1. 📄 Plan de estudios\n"
    "2. 🔗 Correlativas de una materia\n"
    "3. 🗓️ Calendario académico\n"
    "4. 🖥️ Gestión (Campus, SIU Guaraní)\n"
    "5. 📍 Sedes\n"
    "6. 📩 Contactos y Mesa de Ayuda\n\n"
    "_Escribí el número o MENÚ para volver._"
)

def _txt_plan() -> str:
    resp = "📄 *Plan de Estudios TUCE*\n\n"
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
    return (
        "📍 *Sedes UNPAZ:*\n\n"
        "🏢 *Sede Alem*\nAv. Alem 4731, José C. Paz\n"
        "https://maps.google.com/?q=-34.5164,-58.7615\n\n"
        "🏢 *Sede Arregui*\nArregui 2080, José C. Paz\n"
        "https://maps.google.com/?q=-34.5208,-58.7758\n\n"
        "_Escribí MENÚ para volver._"
    )

def _txt_contactos() -> str:
    return (
        "📩 *Contactos y Mesa de Ayuda:*\n\n"
        "🤝 Acceso y Apoyo (Becas/Tutorías):\n  accesoapoyo@unpaz.edu.ar\n\n"
        "📝 CIU (Ingreso):\n  ciu@unpaz.edu.ar\n\n"
        "👤 Consultas Estudiantes:\n  consultasestudiantes@unpaz.edu.ar\n\n"
        "💻 SIU Guaraní:\n  soporteinscripciones@unpaz.edu.ar\n\n"
        "🌐 UNPAZ Virtual:\n  formacionvirtual@unpaz.edu.ar\n\n"
        "💜 ORVIG (Género):\n  orvig@unpaz.edu.ar\n\n"
        "_Escribí MENÚ para volver._"
    )

def _txt_comunidad() -> str:
    return (
        "👥 *Comunidad TUCE*\n\n"
        "Sumate a la comunidad 👇\n\n"
        "💬 *WhatsApp TUCE:*\nhttps://chat.whatsapp.com/FSwCNJd2GirBVIVCZDGU0B\n\n"
        "💬 *Grupo adicional:*\nhttps://chat.whatsapp.com/JElcFd4U08QBKsL1J1YM8u\n\n"
        "📸 *Instagram:*\nhttps://www.instagram.com/tuce_unpaz/\n\n"
        "📘 *Facebook:*\nhttps://m.facebook.com/tuceunpaz/\n\n"
        "_Escribí MENÚ para volver al menú principal._"
    )

# Mapeo de palabras clave → número de sub-opción en carrera
_KEYWORDS_CARRERA = {
    1: ["plan", "estudio", "materia", "asignatura"],
    2: ["correlativa", "requiere", "necesita", "previa"],
    3: ["calendario", "fecha", "cuando", "inicio", "semestre"],
    4: ["gestion", "campus", "siu", "guarani", "inscripcion", "certificado", "boleto"],
    5: ["sede", "donde", "alem", "arregui", "direccion"],
    6: ["contacto", "ayuda", "email", "correo", "mesa", "beca", "pasantia"],
}

def _opcion_carrera_por_texto(texto_norm: str) -> int | None:
    for num, keywords in _KEYWORDS_CARRERA.items():
        if contiene_alguna(texto_norm, keywords):
            return num
    return None

def _handle_carrera(uid: str, texto_norm: str) -> str:
    estado    = est.get(uid)
    esperando = estado.get("esperando")

    # ── Esperando nombre de materia para correlativas ─────────────────────────
    if esperando == "correlativa":
        encontrada = None
        for info in CORRELATIVAS.values():
            if texto_norm in normalizar(info["nombre"]):
                encontrada = info
                break
        if not encontrada:
            if est.sumar_error(uid):
                est.salir(uid)
                return MSG_DEMASIADOS_ERRORES + MENU_TEXTO
            return (
                "❌ No encontré esa materia.\n"
                "Intentá con otro nombre o parte del nombre.\n"
                "_Ejemplo: 'desarrollo', 'ingles', 'marketing'_"
            )
        est.entrar(uid, "carrera")  # vuelve al sub-menú de carrera
        nombre = encontrada["nombre"]
        if not encontrada["necesita"]:
            return (
                f"✅ *{nombre}*\n\n"
                "No tiene correlativas. ¡Podés cursarla cuando quieras!\n\n"
                "_Escribí otro número o MENÚ para volver._"
            )
        previas = "\n".join(f"  • {CORRELATIVAS[c]['nombre']}" for c in encontrada["necesita"])
        return (
            f"🔗 *{nombre}*\n\n"
            f"Para cursarla necesitás tener aprobada/s:\n{previas}\n\n"
            "_Escribí otro nombre de materia o MENÚ para volver._"
        )

    # ── Sub-menú de carrera ───────────────────────────────────────────────────
    num = extraer_numero(texto_norm) or _opcion_carrera_por_texto(texto_norm)

    respuestas = {
        1: (None,          _txt_plan()),
        2: ("correlativa", "🔗 *Correlativas*\n\nEscribí el nombre (o parte) de la materia:\n_Ejemplo: 'marketing', 'ingles', 'desarrollo'_"),
        3: (None,          _txt_calendario()),
        4: (None,          _txt_gestion()),
        5: (None,          _txt_sedes()),
        6: (None,          _txt_contactos()),
    }

    if num in respuestas:
        next_esp, texto_resp = respuestas[num]
        est.entrar(uid, "carrera", esperando=next_esp)
        return texto_resp

    if est.sumar_error(uid):
        est.salir(uid)
        return MSG_DEMASIADOS_ERRORES + MENU_TEXTO
    return SUBMENU_CARRERA


# ─── Sección: Horarios ────────────────────────────────────────────────────────

def _handle_horarios(uid: str, texto_norm: str) -> str:
    materia = _buscar_materia(texto_norm)
    if materia:
        est.avanzar(uid, esperando="materia")  # reset errores, permanece en horarios
        return _txt_horarios_materia(materia)
    if est.sumar_error(uid):
        est.salir(uid)
        return MSG_DEMASIADOS_ERRORES + MENU_TEXTO
    return "❌ No encontré esa materia.\n\n" + _txt_lista_materias()


# ─── Sección: FAQ ─────────────────────────────────────────────────────────────

def _txt_lista_faq() -> str:
    lineas = ["❓ *Preguntas frecuentes:*\n"]
    for i, item in enumerate(FAQ, 1):
        lineas.append(f"{i}. {item['q']}")
    lineas.append("\n_Escribí el número de tu pregunta, o MENÚ para volver._")
    return "\n".join(lineas)

def _buscar_faq(texto_norm: str) -> dict | None:
    num = extraer_numero(texto_norm)
    if num is not None and 1 <= num <= len(FAQ):
        return FAQ[num - 1]
    for item in FAQ:
        if any(p in normalizar(item["q"]) for p in texto_norm.split() if len(p) >= 4):
            return item
    return None

def _handle_faq(uid: str, texto_norm: str) -> str:
    item = _buscar_faq(texto_norm)
    if item:
        est.avanzar(uid, esperando="faq")
        return item["a"] + "\n\n_Escribí otro número o MENÚ para volver._"
    if est.sumar_error(uid):
        est.salir(uid)
        return MSG_DEMASIADOS_ERRORES + MENU_TEXTO
    return "❌ No encontré esa pregunta.\n\n" + _txt_lista_faq()


# ─── Métricas básicas en Firebase ────────────────────────────────────────────

def _log_uso(firebase_db, seccion: str):
    """Incrementa contador de uso por sección en Firebase."""
    try:
        ref = firebase_db.reference(f"metricas/wa/{seccion}")
        actual = ref.get() or 0
        ref.set(actual + 1)
    except Exception:
        pass


# ─── Selección del menú principal ────────────────────────────────────────────

_KEYWORDS_MENU = {
    1: ["informacion", "carrera", "plan", "estudio"],
    2: ["horario", "horarios", "materia", "materias", "clase"],
    3: ["comunidad", "grupo", "instagram", "facebook", "redes"],
    4: ["faq", "pregunta", "frecuente", "duda", "consulta"],
    5: ["ia", "inteligencia", "gpt", "chat", "consultar"],
}

def _opcion_menu_por_texto(texto_norm: str) -> int | None:
    for num, keywords in _KEYWORDS_MENU.items():
        if contiene_alguna(texto_norm, keywords):
            return num
    return None


# ─── Función principal ────────────────────────────────────────────────────────

def procesar(from_id: str, texto: str, firebase_db, responder_ia_fn) -> str:
    """
    Procesa un mensaje de WhatsApp y devuelve la respuesta.

    Args:
        from_id:        ID del remitente (WA JID o número)
        texto:          Mensaje original sin modificar
        firebase_db:    Referencia a Firebase (para métricas y novedades)
        responder_ia_fn: Función responder_ia() de main.py (solo llamada en opción 5)
    """
    texto_norm = normalizar(texto)

    # ── Comandos globales: vuelven al menú desde cualquier lugar ──────────────
    if es_menu(texto) or texto_norm == "menu":
        est.salir(from_id)
        _log_uso(firebase_db, "menu")
        return MENU_TEXTO

    estado  = est.get(from_id)
    seccion = estado.get("seccion")

    # ── Dentro de una sección activa ──────────────────────────────────────────
    if seccion == "carrera":
        return _handle_carrera(from_id, texto_norm)

    if seccion == "horarios":
        return _handle_horarios(from_id, texto_norm)

    if seccion == "faq":
        return _handle_faq(from_id, texto_norm)

    if seccion == "ia":
        respuesta = responder_ia_fn(texto)
        return respuesta + "\n\n_Escribí MENÚ para volver al menú principal._"

    # ── Sin sección activa: interpretar como selección del menú principal ─────
    num = extraer_numero(texto_norm) or _opcion_menu_por_texto(texto_norm)

    if num == 1:
        est.entrar(from_id, "carrera")
        _log_uso(firebase_db, "carrera")
        return SUBMENU_CARRERA

    if num == 2:
        est.entrar(from_id, "horarios", esperando="materia")
        _log_uso(firebase_db, "horarios")
        return _txt_lista_materias()

    if num == 3:
        _log_uso(firebase_db, "comunidad")
        return _txt_comunidad()

    if num == 4:
        est.entrar(from_id, "faq")
        _log_uso(firebase_db, "faq")
        return _txt_lista_faq()

    if num == 5:
        est.entrar(from_id, "ia")
        _log_uso(firebase_db, "ia")
        return (
            "🤖 *Modo IA activado*\n\n"
            "Preguntame lo que necesites sobre la carrera, trámites o UNPAZ.\n"
            "_La IA responde solo sobre la TUCE y UNPAZ._\n\n"
            "_Escribí MENÚ para volver al menú principal._"
        )

    # ── Input desconocido: primer mensaje → bienvenida, resto → error ─────────
    if seccion is None and estado.get("errores", 0) == 0:
        _log_uso(firebase_db, "bienvenida")
        # Primer contacto: dar bienvenida + menú
        est.entrar(from_id, None)  # marcar que ya saludamos
        # En realidad no guardamos estado "saludado", simplemente mostramos menú
        est.salir(from_id)
        return BIENVENIDA + "\n\n" + MENU_TEXTO

    return MSG_NO_ENTENDI
