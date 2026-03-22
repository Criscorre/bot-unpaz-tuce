# talentos.py
# Módulo completo de Talentos TUCE
# Usa Google Forms como intermediario para guardar en Google Sheets

import requests
import time
from telebot import types

# --- IDs DE LOS CAMPOS DEL GOOGLE FORM ---
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfpVGoa51jkmsp8OZ2tOAuZAJ8Z1f9HUXp60ZjvBLI8MVum_w/formResponse"
FIELD_TELEGRAM_ID = "entry.80058858"
FIELD_NOMBRE      = "entry.1297120149"
FIELD_USERNAME    = "entry.1956463938"
FIELD_CATEGORIA   = "entry.984886"
FIELD_ANIO        = "entry.1578470295"
FIELD_BIO         = "entry.852614958"
FIELD_WEB         = "entry.1049166554"
FIELD_FOTO_ID     = "entry.452793589"

# --- URL PÚBLICA DE LA SHEET (modo lectura) ---
# Reemplazá SHEET_ID por el ID real de tu Google Sheet una vez que el form esté conectado
# Lo encontrás en la URL: docs.google.com/spreadsheets/d/SHEET_ID/edit
SHEET_ID = "TU_SHEET_ID_AQUI"
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

# --- ESTADO CONVERSACIONAL POR USUARIO ---
# Guarda el paso actual y los datos temporales de cada usuario
# { user_id: { "paso": "categoria"|"bio"|"anio"|"web"|"foto", "datos": {...} } }
estados_talentos = {}

def enviar_a_form(datos: dict) -> bool:
    """Envía los datos del talento al Google Form."""
    payload = {
        FIELD_TELEGRAM_ID: str(datos.get("telegram_id", "")),
        FIELD_NOMBRE:       datos.get("nombre", ""),
        FIELD_USERNAME:     datos.get("username", "Sin usuario"),
        FIELD_CATEGORIA:    datos.get("categoria", ""),
        FIELD_ANIO:         datos.get("anio", ""),
        FIELD_BIO:          datos.get("bio", ""),
        FIELD_WEB:          datos.get("web", "Sin web"),
        FIELD_FOTO_ID:      datos.get("foto_id", "sin_foto"),
    }
    try:
        r = requests.post(FORM_URL, data=payload, timeout=10)
        return r.status_code in [200, 302]
    except Exception as e:
        print(f"❌ Error enviando a Form: {e}")
        return False

def leer_talentos_desde_sheet() -> list:
    """Lee los talentos publicados desde la Google Sheet pública (CSV)."""
    try:
        r = requests.get(SHEET_CSV_URL, timeout=10)
        if r.status_code != 200:
            return []
        lineas = r.text.strip().split("\n")
        talentos = []
        for linea in lineas[1:]:  # saltar encabezado
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

# ─────────────────────────────────────────────
#  FLUJO DE REGISTRO — paso a paso
# ─────────────────────────────────────────────

def iniciar_registro(bot, message):
    """Paso 0: El alumno quiere publicar su perfil."""
    user_id = message.from_user.id
    estados_talentos[user_id] = {
        "paso": "categoria",
        "datos": {
            "telegram_id": user_id,
            "nombre":   message.from_user.first_name or "",
            "username": f"@{message.from_user.username}" if message.from_user.username else "Sin usuario",
        }
    }
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIAS:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"tal_cat_{cat}"))
    bot.send_message(
        message.chat.id,
        "🏷️ *¿Cuál es tu área principal?*\nElegí tu rol:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

def paso_categoria(bot, call, categoria):
    """Paso 1: Guardó categoría, pide foto."""
    user_id = call.from_user.id
    if user_id not in estados_talentos:
        bot.answer_callback_query(call.id, "Sesión expirada, empezá de nuevo.")
        return
    estados_talentos[user_id]["datos"]["categoria"] = categoria
    estados_talentos[user_id]["paso"] = "foto"
    bot.edit_message_text(
        f"✅ Categoría: *{categoria}*\n\n📸 Ahora mandame una *foto de perfil*.\n"
        "_(Si no querés foto, escribí_ `omitir`_)_",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

def paso_foto(bot, message):
    """Paso 2: Recibe foto o 'omitir', pide bio."""
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "foto":
        return False

    if message.photo:
        foto_id = message.photo[-1].file_id
        estados_talentos[user_id]["datos"]["foto_id"] = foto_id
    else:
        estados_talentos[user_id]["datos"]["foto_id"] = "sin_foto"

    estados_talentos[user_id]["paso"] = "bio"
    bot.send_message(
        message.chat.id,
        "✍️ Escribí tu *presentación breve*:\n\n"
        "_Ejemplo: \"Soy Lara, 2° año TUCE. Especializada en Meta Ads e Instagram. "
        "Trabajo con marcas locales.\"_\n\n"
        "_(Máx. 200 caracteres)_",
        parse_mode="Markdown"
    )
    return True

def paso_bio(bot, message):
    """Paso 3: Recibe bio, pide año."""
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "bio":
        return False

    bio = message.text[:200]
    estados_talentos[user_id]["datos"]["bio"] = bio
    estados_talentos[user_id]["paso"] = "anio"

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("1° año",    callback_data="tal_anio_1° año"),
        types.InlineKeyboardButton("2° año",    callback_data="tal_anio_2° año"),
        types.InlineKeyboardButton("3° año",    callback_data="tal_anio_3° año"),
        types.InlineKeyboardButton("Recibida/o", callback_data="tal_anio_Recibida/o"),
    )
    bot.send_message(
        message.chat.id,
        "📅 *¿Qué año de la carrera cursás?*",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    return True

def paso_anio(bot, call, anio):
    """Paso 4: Guardó año, pide web."""
    user_id = call.from_user.id
    if user_id not in estados_talentos:
        bot.answer_callback_query(call.id, "Sesión expirada, empezá de nuevo.")
        return
    estados_talentos[user_id]["datos"]["anio"] = anio
    estados_talentos[user_id]["paso"] = "web"
    bot.edit_message_text(
        f"✅ Año: *{anio}*\n\n🌐 *¿Tenés web, portfolio o Instagram profesional?*\n"
        "_(Pegá el link o escribí_ `no tengo`_)_",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

def paso_web(bot, message):
    """Paso 5: Recibe web, guarda todo y confirma."""
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "web":
        return False

    web = message.text.strip()
    estados_talentos[user_id]["datos"]["web"] = web
    datos = estados_talentos[user_id]["datos"]

    bot.send_chat_action(message.chat.id, "typing")

    exito = enviar_a_form(datos)

    del estados_talentos[user_id]  # limpiar estado

    if exito:
        cat = datos.get("categoria", "")
        nombre = datos.get("nombre", "")
        bot.send_message(
            message.chat.id,
            f"🎉 *¡Perfil publicado exitosamente!*\n\n"
            f"Ya aparecés en *Talentos TUCE* como *{cat}*.\n\n"
            f"Tus compañeros van a poder encontrarte y contactarte directamente.\n\n"
            f"_¿Querés ver otros talentos? Volvé al menú y tocá 🌟 Talentos TUCE._",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            message.chat.id,
            "⚠️ Hubo un problema al guardar tu perfil. Por favor intentá de nuevo en unos minutos."
        )
    return True

# ─────────────────────────────────────────────
#  FLUJO DE EXPLORACIÓN — ver talentos
# ─────────────────────────────────────────────

def mostrar_menu_explorar(bot, message_or_call, edit=False):
    """Muestra las categorías para explorar."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIAS:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"tal_ver_{cat}"))

    texto = "🔍 *¿Qué perfil buscás?*\nElegí una categoría:"

    if edit:
        bot.edit_message_text(
            texto,
            message_or_call.message.chat.id,
            message_or_call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            message_or_call.chat.id,
            texto,
            reply_markup=markup,
            parse_mode="Markdown"
        )

def mostrar_talentos_por_categoria(bot, call, categoria):
    """Muestra los talentos de una categoría leídos desde la Sheet."""
    bot.answer_callback_query(call.id, "Buscando talentos...")

    talentos = leer_talentos_desde_sheet()
    filtrados = [t for t in talentos if t["categoria"] == categoria]

    if not filtrados:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Ver otras categorías", callback_data="tal_explorar"))
        bot.edit_message_text(
            f"😕 Todavía no hay talentos registrados en *{categoria}*.\n\n"
            "¡Podés ser el primero en publicar tu perfil!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    texto = f"*{categoria}* — {len(filtrados)} talento(s)\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for t in filtrados[:10]:  # máximo 10 por categoría
        nombre   = t.get("nombre", "Sin nombre")
        anio     = t.get("anio", "")
        bio      = t.get("bio", "")[:80]
        web      = t.get("web", "")
        username = t.get("username", "")

        texto += f"👤 *{nombre}* · {anio}\n"
        texto += f"_{bio}..._\n"
        if web and web.lower() != "no tengo" and web.lower() != "sin web":
            texto += f"🌐 {web}\n"
        texto += "\n"

        if username and username != "Sin usuario":
            tg = username.replace("@", "")
            markup.add(types.InlineKeyboardButton(
                f"💬 Contactar a {nombre}",
                url=f"https://t.me/{tg}"
            ))

    markup.add(types.InlineKeyboardButton("⬅️ Ver otras categorías", callback_data="tal_explorar"))

    bot.edit_message_text(
        texto,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# ─────────────────────────────────────────────
#  MENÚ PRINCIPAL DE TALENTOS
# ─────────────────────────────────────────────

def menu_talentos(bot, message):
    """Menú de entrada a la sección Talentos TUCE."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Publicar mi perfil",    callback_data="tal_registrar"),
        types.InlineKeyboardButton("🔍 Explorar talentos",     callback_data="tal_explorar"),
    )
    bot.send_message(
        message.chat.id,
        "🌟 *Talentos TUCE*\n\n"
        "Conectá con compañeros de la carrera según su especialidad.\n"
        "¿Qué querés hacer?",
        reply_markup=markup,
        parse_mode="Markdown"
    )
