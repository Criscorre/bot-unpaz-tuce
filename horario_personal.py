# horario_personal.py — Bot TUCE
# Permite a cada alumno armar su horario personal eligiendo comisiones por materia.
# Persiste la selección en Firebase bajo /horarios_personales/{user_id}.

from telebot import types
from materias_db import LISTA_HORARIOS

# ─── Estado conversacional ─────────────────────────────────────────────────────
# { user_id: {"paso": "materias"|"comisiones", "mat_idx": int, "seleccion": {mat: {...}}} }
estados_horario = {}

# ─── Constantes ───────────────────────────────────────────────────────────────
DIAS_ORDEN = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]

# Lista ordenada de materias únicas (índice estable para callbacks)
MATERIAS_HP = sorted(list(set(f[0] for f in LISTA_HORARIOS)))

def _comisiones_de(materia: str) -> list:
    """Devuelve lista de [comision, dia, inicio, fin, aula] para una materia."""
    return [f for f in LISTA_HORARIOS if f[0] == materia]


# ─── Firebase helpers ─────────────────────────────────────────────────────────

def guardar_horario_db(firebase_db, user_id: int, seleccion: dict):
    """Guarda el horario personal del alumno en Firebase."""
    try:
        firebase_db.reference(f"horarios_personales/{user_id}").set(seleccion)
    except Exception as e:
        print(f"❌ Error guardando horario: {e}")

def cargar_horario_db(firebase_db, user_id: int) -> dict:
    """Carga el horario personal desde Firebase. Devuelve dict o {}."""
    try:
        data = firebase_db.reference(f"horarios_personales/{user_id}").get()
        return data or {}
    except Exception as e:
        print(f"❌ Error cargando horario: {e}")
        return {}

def borrar_horario_db(firebase_db, user_id: int):
    """Elimina el horario personal de Firebase."""
    try:
        firebase_db.reference(f"horarios_personales/{user_id}").delete()
    except Exception as e:
        print(f"❌ Error borrando horario: {e}")


# ─── Formateo del horario ─────────────────────────────────────────────────────

def formatear_horario(seleccion: dict) -> str:
    """Convierte el dict de selección en texto legible agrupado por día."""
    if not seleccion:
        return "📅 *Tu Horario Personal*\n\n_Todavía no configuraste tu horario._"

    # Agrupar materias por día
    por_dia: dict = {d: [] for d in DIAS_ORDEN}
    for mat, info in seleccion.items():
        dia = info.get("dia", "")
        if dia in por_dia:
            por_dia[dia].append(info)
        else:
            por_dia[dia] = [info]

    lineas = ["📅 *Tu Horario Personal*\n"]
    for dia in DIAS_ORDEN:
        clases = por_dia.get(dia, [])
        if not clases:
            continue
        lineas.append(f"*{dia}:*")
        clases_ord = sorted(clases, key=lambda x: x.get("hora_inicio", ""))
        for c in clases_ord:
            h_ini = c.get("hora_inicio", "")[:5]
            h_fin = c.get("hora_fin",   "")[:5]
            lineas.append(
                f"  📚 {c['materia']}\n"
                f"  👥 Com {c['comision']} | ⏰ {h_ini}–{h_fin} hs\n"
                f"  🏢 {c['aula']}"
            )
        lineas.append("")

    return "\n".join(lineas).strip()


# ─── Menú principal del horario ───────────────────────────────────────────────

def menu_horario(bot, call_or_msg, firebase_db, editar=False):
    """
    Muestra el menú principal de Mi Horario.
    Si editar=True usa edit_message_text; si no, send_message.
    """
    uid   = call_or_msg.from_user.id
    chat  = call_or_msg.message.chat.id if hasattr(call_or_msg, "message") else call_or_msg.chat.id
    mid   = call_or_msg.message.message_id if hasattr(call_or_msg, "message") else None

    sel = cargar_horario_db(firebase_db, uid)
    texto = formatear_horario(sel)

    markup = types.InlineKeyboardMarkup(row_width=2)
    if sel:
        markup.add(
            types.InlineKeyboardButton("⚙️ Reconfigurar", callback_data="hp_cfg"),
            types.InlineKeyboardButton("🗑️ Borrar",       callback_data="hp_del_confirm"),
        )
    else:
        markup.add(types.InlineKeyboardButton("⚙️ Configurar mi horario", callback_data="hp_cfg"))

    if editar and mid:
        try:
            bot.edit_message_text(texto, chat, mid, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat, texto, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat, texto, reply_markup=markup, parse_mode="Markdown")


# ─── Inicio de configuración ──────────────────────────────────────────────────

def iniciar_config(bot, call, firebase_db):
    """Arranca el flujo de selección de materias."""
    uid = call.from_user.id
    # Cargar selección previa como base (el usuario puede sobrescribir)
    sel_previa = cargar_horario_db(firebase_db, uid)
    estados_horario[uid] = {
        "paso":      "materias",
        "mat_idx":   0,
        "seleccion": dict(sel_previa),  # copia mutable
    }
    _mostrar_materia_actual(bot, call)


def _mostrar_materia_actual(bot, call):
    """Muestra la materia actual en el flujo de configuración."""
    uid   = call.from_user.id
    estado = estados_horario.get(uid)
    if not estado:
        return

    idx     = estado["mat_idx"]
    sel     = estado["seleccion"]

    if idx >= len(MATERIAS_HP):
        # Terminamos todas las materias → guardar y mostrar resumen
        _finalizar_config(bot, call)
        return

    materia  = MATERIAS_HP[idx]
    coms     = _comisiones_de(materia)
    ya_sel   = sel.get(materia)

    titulo = f"⚙️ *Configurar Horario* ({idx+1}/{len(MATERIAS_HP)})\n\n"
    titulo += f"📚 *{materia}*\n"
    if ya_sel:
        titulo += f"_Selección actual: Com {ya_sel['comision']} — {ya_sel['dia']} {ya_sel['hora_inicio'][:5]}-{ya_sel['hora_fin'][:5]}_\n"
    titulo += "\nElegí tu comisión (o Saltear si no cursás esta materia):"

    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, f in enumerate(coms):
        # f = [materia, comision, dia, inicio, fin, modalidad, //, //, aula]
        lbl = f"Com {f[1]} | {f[2]} {f[3][:5]}-{f[4][:5]} | {f[8]}"
        markup.add(types.InlineKeyboardButton(lbl, callback_data=f"hp_com_{idx}_{i}"))
    markup.add(types.InlineKeyboardButton("⏭️ Saltear esta materia", callback_data=f"hp_skip_{idx}"))
    markup.add(types.InlineKeyboardButton("✅ Guardar y terminar ahora", callback_data="hp_fin"))
    markup.add(types.InlineKeyboardButton("❌ Cancelar", callback_data="hp_cancel"))

    try:
        bot.edit_message_text(
            titulo,
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(
            call.message.chat.id, titulo,
            reply_markup=markup, parse_mode="Markdown"
        )


def seleccionar_comision(bot, call, mat_idx: int, com_idx: int, firebase_db):
    """Registra la comisión elegida y avanza a la siguiente materia."""
    uid    = call.from_user.id
    estado = estados_horario.get(uid)
    if not estado:
        bot.answer_callback_query(call.id, "Sesión expirada. Volvé a 📅 Mi Horario.")
        return

    materia = MATERIAS_HP[mat_idx]
    coms    = _comisiones_de(materia)
    if com_idx >= len(coms):
        bot.answer_callback_query(call.id, "Opción inválida.")
        return

    f = coms[com_idx]
    estado["seleccion"][materia] = {
        "materia":     f[0],
        "comision":    f[1],
        "dia":         f[2],
        "hora_inicio": f[3],
        "hora_fin":    f[4],
        "aula":        f[8],
    }
    estado["mat_idx"] = mat_idx + 1
    bot.answer_callback_query(call.id, f"✅ Com {f[1]} guardada")
    _mostrar_materia_actual(bot, call)


def saltear_materia(bot, call, mat_idx: int):
    """Salta la materia actual sin guardar comisión."""
    uid    = call.from_user.id
    estado = estados_horario.get(uid)
    if not estado:
        bot.answer_callback_query(call.id, "Sesión expirada.")
        return
    bot.answer_callback_query(call.id, "⏭️ Salteada")
    estado["mat_idx"] = mat_idx + 1
    _mostrar_materia_actual(bot, call)


def _finalizar_config(bot, call, firebase_db=None):
    """Guarda el horario en Firebase y muestra el resumen final."""
    uid    = call.from_user.id
    estado = estados_horario.pop(uid, {})
    sel    = estado.get("seleccion", {})

    # Necesitamos firebase_db; se lo pasamos desde el callback
    # (si no viene en el cierre automático, buscamos en el módulo importado)
    if firebase_db is None:
        # Se importa dinámicamente para evitar circular import
        from firebase_admin import db as firebase_db

    guardar_horario_db(firebase_db, uid, sel)

    texto = formatear_horario(sel)
    texto += "\n\n✅ *¡Horario guardado!*"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚙️ Reconfigurar", callback_data="hp_cfg"))
    try:
        bot.edit_message_text(
            texto,
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(
            call.message.chat.id, texto,
            reply_markup=markup, parse_mode="Markdown"
        )


def finalizar_config(bot, call, firebase_db):
    """Punto de entrada externo para finalizar desde callback hp_fin."""
    uid    = call.from_user.id
    estado = estados_horario.get(uid, {})
    sel    = estado.get("seleccion", {})
    estados_horario.pop(uid, None)

    guardar_horario_db(firebase_db, uid, sel)

    texto = formatear_horario(sel)
    texto += "\n\n✅ *¡Horario guardado!*"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚙️ Reconfigurar", callback_data="hp_cfg"))
    try:
        bot.edit_message_text(
            texto,
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(
            call.message.chat.id, texto,
            reply_markup=markup, parse_mode="Markdown"
        )


def confirmar_borrar(bot, call):
    """Muestra pantalla de confirmación antes de borrar el horario."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Sí, borrar", callback_data="hp_del_ok"),
        types.InlineKeyboardButton("❌ Cancelar",   callback_data="hp_ver"),
    )
    try:
        bot.edit_message_text(
            "🗑️ ¿Seguro que querés borrar tu horario personal?\n\n"
            "_Esta acción no se puede deshacer._",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(
            call.message.chat.id,
            "🗑️ ¿Seguro que querés borrar tu horario personal?",
            reply_markup=markup
        )


def ejecutar_borrar(bot, call, firebase_db):
    """Borra el horario del usuario de Firebase."""
    uid = call.from_user.id
    borrar_horario_db(firebase_db, uid)
    estados_horario.pop(uid, None)
    bot.answer_callback_query(call.id, "🗑️ Horario borrado")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚙️ Configurar mi horario", callback_data="hp_cfg"))
    try:
        bot.edit_message_text(
            "📅 *Tu Horario Personal*\n\n_Horario eliminado. Podés configurar uno nuevo cuando quieras._",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(call.message.chat.id, "🗑️ Horario eliminado.")


def cancelar_config(bot, call, firebase_db):
    """Cancela el flujo de configuración sin guardar cambios."""
    uid = call.from_user.id
    estados_horario.pop(uid, None)
    bot.answer_callback_query(call.id, "❌ Configuración cancelada")
    menu_horario(bot, call, firebase_db, editar=True)
