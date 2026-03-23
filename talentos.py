# talentos.py
import requests
from telebot import types

# --- IDs GOOGLE FORM ---
FORM_URL          = "https://docs.google.com/forms/d/e/1FAIpQLSfpVGoa51jkmsp8OZ2tOAuZAJ8Z1f9HUXp60ZjvBLI8MVum_w/formResponse"
FIELD_TELEGRAM_ID = "entry.80058858"
FIELD_NOMBRE      = "entry.1297120149"
FIELD_USERNAME    = "entry.1956463938"
FIELD_CATEGORIA   = "entry.984886"
FIELD_ANIO        = "entry.1578470295"
FIELD_BIO         = "entry.852614958"
FIELD_WEB         = "entry.1049166554"
FIELD_FOTO_ID     = "entry.452793589"

# --- SHEET ---
SHEET_ID      = "1EDHX8juohDWDP0NaISaKUhmurL4ZqfwbAItVSD4Mn3E"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1"

# --- CATEGORÍAS ---
CATEGORIAS = [
    "👥 Community Manager",
    "🗂️ Project Manager",
    "🎨 Diseño Gráfico",
    "📢 Experto en Ads",
    "💻 Desarrollo Web",
    "📊 Analista Digital",
    "🛒 E-commerce Manager",
    "🏢 Agencias TUCE",
]

# Orden de pasos: categoria → nombre → username → anio → bio → web → foto → guardar
PASOS_PREGUNTAS = {
    "nombre":   "👤 *Paso 2/7 — Nombre completo*\n¿Cómo te llamás?",
    "username": "💬 *Paso 3/7 — Usuario de Telegram*\n¿Cuál es tu @usuario?\n_(Si no tenés, escribí_ `no tengo`_)_",
    "bio":      "📝 *Paso 5/7 — Presentación*\nEscribí una bio breve:\n\n_Ejemplo: \"Especializado en Meta Ads, trabajo con marcas locales.\"_\n_(Máx. 200 caracteres)_",
    "web":      "🌐 *Paso 6/7 — Web o Portfolio*\n¿Tenés web, portfolio o Instagram profesional?\n_(Pegá el link o escribí_ `no tengo`_)_",
    "foto":     "📸 *Paso 7/7 — Foto de perfil*\nMandame una foto o escribí `omitir`",
}

# Estado por usuario
estados_talentos = {}


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def enviar_a_form(datos: dict) -> bool:
    payload = {
        FIELD_TELEGRAM_ID: str(datos.get("telegram_id", "")),
        FIELD_NOMBRE:      datos.get("nombre", ""),
        FIELD_USERNAME:    datos.get("username", "Sin usuario"),
        FIELD_CATEGORIA:   datos.get("categoria", ""),
        FIELD_ANIO:        datos.get("anio", ""),
        FIELD_BIO:         datos.get("bio", ""),
        FIELD_WEB:         datos.get("web", "Sin web"),
        FIELD_FOTO_ID:     datos.get("foto_id", "sin_foto"),
    }
    try:
        r = requests.post(FORM_URL, data=payload, timeout=10)
        return r.status_code in [200, 302]
    except Exception as e:
        print(f"❌ Error enviando a Form: {e}")
        return False

def leer_talentos_desde_sheet() -> list:
    try:
        r = requests.get(SHEET_CSV_URL, timeout=5)
        if r.status_code != 200:
            return []
        lineas = r.text.strip().split("\n")
        talentos = []
        for linea in lineas[1:]:
            cols = [c.strip().strip('"') for c in linea.split(",")]
            if len(cols) >= 8:
                talentos.append({
                    "timestamp":   cols[0],
                    "telegram_id": cols[1],
                    "nombre":      cols[2],
                    "username":    cols[3],
                    "categoria":   cols[4],
                    "anio":        cols[5],
                    "bio":         cols[6],
                    "web":         cols[7],
                    "foto_id":     cols[8] if len(cols) > 8 else "",
                })
        return talentos
    except Exception as e:
        print(f"❌ Error leyendo Sheet: {e}")
        return []

def pedir_anio(bot, chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("1° año",     callback_data="tal_anio_1° año"),
        types.InlineKeyboardButton("2° año",     callback_data="tal_anio_2° año"),
        types.InlineKeyboardButton("3° año",     callback_data="tal_anio_3° año"),
        types.InlineKeyboardButton("Recibida/o", callback_data="tal_anio_Recibida/o"),
    )
    bot.send_message(
        chat_id,
        "📅 *Paso 4/7 — Año de carrera*\n¿Qué año cursás?",
        reply_markup=markup,
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
#  MENÚ PRINCIPAL
# ─────────────────────────────────────────────

def menu_talentos(bot, message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Publicar mi perfil", callback_data="tal_registrar"),
        types.InlineKeyboardButton("🔍 Explorar talentos",  callback_data="tal_explorar"),
    )
    bot.send_message(
        message.chat.id,
        "🌟 *Talentos TUCE*\n\nConectá con compañeros según su especialidad.\n¿Qué querés hacer?",
        reply_markup=markup,
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
#  FLUJO DE REGISTRO — orden fijo
#  categoria → nombre → username → anio → bio → web → foto → guardar
# ─────────────────────────────────────────────

def iniciar_registro(bot, message):
    user_id = message.from_user.id
    estados_talentos[user_id] = {
        "paso": "categoria",
        "datos": {"telegram_id": user_id}
    }
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIAS:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"tal_cat_{cat}"))
    bot.send_message(
        message.chat.id,
        "🏷️ *Paso 1/7 — Categoría*\n¿Cuál es tu área principal?",
        reply_markup=markup,
        parse_mode="Markdown"
    )

def paso_categoria(bot, call, categoria):
    user_id = call.from_user.id
    if user_id not in estados_talentos:
        bot.answer_callback_query(call.id)
        iniciar_registro(bot, call.message)
        return
    estados_talentos[user_id]["datos"]["categoria"] = categoria
    estados_talentos[user_id]["paso"] = "nombre"
    bot.edit_message_text(
        f"✅ Categoría: *{categoria}*",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown"
    )
    bot.send_message(call.message.chat.id, PASOS_PREGUNTAS["nombre"], parse_mode="Markdown")

def paso_anio(bot, call, anio):
    user_id = call.from_user.id
    if user_id not in estados_talentos:
        return
    estados_talentos[user_id]["datos"]["anio"] = anio
    estados_talentos[user_id]["paso"] = "bio"
    bot.edit_message_text(
        f"✅ Año: *{anio}*",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown"
    )
    bot.send_message(call.message.chat.id, PASOS_PREGUNTAS["bio"], parse_mode="Markdown")

def paso_nombre(bot, message) -> bool:
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "nombre":
        return False
    estados_talentos[user_id]["datos"]["nombre"] = message.text.strip()[:80]
    estados_talentos[user_id]["paso"] = "username"
    bot.send_message(message.chat.id, PASOS_PREGUNTAS["username"], parse_mode="Markdown")
    return True

def paso_username(bot, message) -> bool:
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "username":
        return False
    username = message.text.strip()
    if username.lower() == "no tengo":
        username = f"@{message.from_user.username}" if message.from_user.username else "Sin usuario"
    elif not username.startswith("@"):
        username = f"@{username}"
    estados_talentos[user_id]["datos"]["username"] = username
    estados_talentos[user_id]["paso"] = "anio"
    pedir_anio(bot, message.chat.id)
    return True

def paso_bio(bot, message) -> bool:
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "bio":
        return False
    estados_talentos[user_id]["datos"]["bio"] = message.text.strip()[:200]
    estados_talentos[user_id]["paso"] = "web"
    bot.send_message(message.chat.id, PASOS_PREGUNTAS["web"], parse_mode="Markdown")
    return True

def paso_web(bot, message) -> bool:
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "web":
        return False
    estados_talentos[user_id]["datos"]["web"] = message.text.strip()
    estados_talentos[user_id]["paso"] = "foto"
    bot.send_message(message.chat.id, PASOS_PREGUNTAS["foto"], parse_mode="Markdown")
    return True

def paso_foto(bot, message) -> bool:
    """Último paso — acepta foto O texto ('omitir'). Luego guarda todo."""
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "foto":
        return False

    # Acepta foto o texto
    if message.content_type == "photo" and message.photo:
        estados_talentos[user_id]["datos"]["foto_id"] = message.photo[-1].file_id
    else:
        estados_talentos[user_id]["datos"]["foto_id"] = "sin_foto"

    datos = estados_talentos[user_id]["datos"]
    bot.send_chat_action(message.chat.id, "typing")
    exito = enviar_a_form(datos)
    del estados_talentos[user_id]

    if exito:
        cat  = datos.get("categoria", "")
        nom  = datos.get("nombre", "")
        usr  = datos.get("username", "")
        anio = datos.get("anio", "")
        bio  = datos.get("bio", "")
        web  = datos.get("web", "")

        # Mostrar resumen + botón para explorar
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔍 Ver talentos de mi categoría", callback_data=f"tal_ver_{cat}"),
            types.InlineKeyboardButton("🌟 Ir a Talentos TUCE", callback_data="tal_explorar"),
        )
        bot.send_message(
            message.chat.id,
            f"🎉 *¡Perfil publicado!*\n\n"
            f"*Categoría:* {cat}\n"
            f"*Nombre:* {nom}\n"
            f"*Usuario:* {usr}\n"
            f"*Año:* {anio}\n"
            f"*Bio:* {bio}\n"
            f"*Web:* {web}\n\n"
            f"Tus compañeros ya pueden encontrarte en 🌟 Talentos TUCE.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            message.chat.id,
            "⚠️ Hubo un problema al guardar tu perfil. Intentá de nuevo en unos minutos."
        )
    return True


# ─────────────────────────────────────────────
#  FLUJO DE EXPLORACIÓN
# ─────────────────────────────────────────────

def mostrar_menu_explorar(bot, call, edit=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIAS:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"tal_ver_{cat}"))
    texto = "🔍 *¿Qué perfil buscás?*\nElegí una categoría:"
    if edit:
        bot.edit_message_text(
            texto, call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
    else:
        bot.send_message(call.message.chat.id, texto, reply_markup=markup, parse_mode="Markdown")

def mostrar_talentos_por_categoria(bot, call, categoria):
    bot.answer_callback_query(call.id, "Buscando talentos...")
    talentos  = leer_talentos_desde_sheet()
    filtrados = [t for t in talentos if t["categoria"] == categoria]

    markup = types.InlineKeyboardMarkup(row_width=1)

    if not filtrados:
        markup.add(types.InlineKeyboardButton("⬅️ Ver otras categorías", callback_data="tal_explorar"))
        bot.edit_message_text(
            f"😕 Todavía no hay talentos en *{categoria}*.\n¡Podés ser el primero!",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
        return

    texto = f"*{categoria}* — {len(filtrados)} talento(s)\n\n"
    for t in filtrados[:10]:
        nombre   = t.get("nombre", "Sin nombre")
        anio     = t.get("anio", "")
        bio      = t.get("bio", "")[:80]
        web      = t.get("web", "")
        username = t.get("username", "")

        texto += f"👤 *{nombre}* · {anio}\n_{bio}_\n"
        if web and web.lower() not in ["no tengo", "sin web"]:
            texto += f"🌐 {web}\n"
        texto += "\n"

        if username and username not in ["Sin usuario", "no tengo"]:
            tg = username.replace("@", "")
            markup.add(types.InlineKeyboardButton(
                f"💬 Contactar a {nombre}",
                url=f"https://t.me/{tg}"
            ))

    markup.add(types.InlineKeyboardButton("⬅️ Ver otras categorías", callback_data="tal_explorar"))
    bot.edit_message_text(
        texto, call.message.chat.id, call.message.message_id,
        reply_markup=markup, parse_mode="Markdown",
        disable_web_page_preview=True
    )