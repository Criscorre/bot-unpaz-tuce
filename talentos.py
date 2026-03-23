# talentos.py
import requests
import time
import re
from telebot import types

# --- GOOGLE FORM TALENTOS ---
FORM_URL          = "https://docs.google.com/forms/d/e/1FAIpQLSfpVGoa51jkmsp8OZ2tOAuZAJ8Z1f9HUXp60ZjvBLI8MVum_w/formResponse"
FIELD_TELEGRAM_ID = "entry.80058858"
FIELD_NOMBRE      = "entry.1297120149"
FIELD_USERNAME    = "entry.1956463938"
FIELD_CATEGORIA   = "entry.984886"
FIELD_ANIO        = "entry.1578470295"
FIELD_BIO         = "entry.852614958"
FIELD_WEB         = "entry.1049166554"
FIELD_FOTO_ID     = "entry.452793589"

# --- GOOGLE FORM VOTOS ---
FORM_VOTOS_URL       = "https://docs.google.com/forms/d/e/1FAIpQLSdlSuIG5gTDvcp71jFLKUo8BfZlcu_uZ5bBX62yEn1_B7f-ww/formResponse"
FIELD_VOTER_ID       = "entry.1171672904"
FIELD_TALENTO_ID     = "entry.1795842410"
FIELD_ESTRELLAS      = "entry.399597954"
FIELD_FECHA_VOTO     = "entry.1646839553"

# --- SHEETS ---
SHEET_TALENTOS_ID  = "1EDHX8juohDWDP0NaISaKUhmurL4ZqfwbAItVSD4Mn3E"
SHEET_VOTOS_ID     = "1HGCPojrHSygQPt9wL67rWwNSkU3OLlFHWpmIygZ2I98"
SHEET_CSV_URL      = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT8DocuqEQ1B64cPxj7QdvRhwGm33xTSiQ5jbvV573ZMw65knP6zR_fWcIUYjjFbpEooFxhh1KDdAIA/pub?gid=223881563&single=true&output=csv"
SHEET_VOTOS_URL    = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQmRdcceKVNXJTZYfPsKKU4S7tje_6E52PjZY6pxAaov0LMC2AukxKBvmVW2b_q0lLuaW9D_X3Gqt9i/pub?gid=912500209&single=true&output=csv"

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

PASOS_PREGUNTAS = {
    "nombre":   "👤 *Paso 2/7 — Nombre completo*\n¿Cómo te llamás?",
    "username": "💬 *Paso 3/7 — Usuario de Telegram*\n¿Cuál es tu @usuario?\n_(Si no tenés, escribí_ `no tengo`_)_",
    "bio":      "📝 *Paso 5/7 — Presentación*\nEscribí una bio breve:\n_(Máx. 200 caracteres)_",
    "web":      "🌐 *Paso 6/7 — Web o Portfolio*\n¿Tenés web, Instagram profesional o portfolio?\n_(Pegá el link/@usuario o escribí_ `no tengo`_)_",
    "foto":     "📸 *Paso 7/7 — Foto de perfil*\nMandame una foto o escribí `omitir`",
}

estados_talentos = {}
# Cache en memoria para evitar doble voto en la misma sesión
votos_cache = {}


# ─────────────────────────────────────────────
#  HELPERS — LINKS
# ─────────────────────────────────────────────

def normalizar_link(texto: str) -> str:
    if not texto or texto.lower() in ["no tengo", "sin web", ""]:
        return None
    t = texto.strip()
    if t.startswith("http://") or t.startswith("https://"):
        return t
    ig = re.search(r'(?:instagram\.com/|ig:|instagram\s*[@:]?\s*)@?([\w.]+)', t, re.IGNORECASE)
    if ig:
        return f"https://instagram.com/{ig.group(1)}"
    if t.startswith("@"):
        return f"https://instagram.com/{t[1:]}"
    li = re.search(r'linkedin\.com/in/([\w-]+)', t, re.IGNORECASE)
    if li:
        return f"https://linkedin.com/in/{li.group(1)}"
    be = re.search(r'behance\.net/([\w]+)', t, re.IGNORECASE)
    if be:
        return f"https://behance.net/{be.group(1)}"
    if re.match(r'^[\w-]+\.[\w.-]+', t):
        return f"https://{t}"
    return None

def formatear_web(texto: str) -> str:
    url = normalizar_link(texto)
    if not url:
        return None
    if "instagram.com" in url:  return f"[📸 Instagram]({url})"
    if "linkedin.com"  in url:  return f"[💼 LinkedIn]({url})"
    if "behance.net"   in url:  return f"[🎨 Behance]({url})"
    if "github.com"    in url:  return f"[💻 GitHub]({url})"
    return f"[🌐 Web/Portfolio]({url})"


# ─────────────────────────────────────────────
#  HELPERS — SHEET
# ─────────────────────────────────────────────

def leer_talentos_desde_sheet() -> list:
    try:
        r = requests.get(SHEET_CSV_URL, timeout=5)
        if r.status_code != 200:
            return []
        lineas = r.text.strip().split("\n")
        talentos = []
        for i, linea in enumerate(lineas[1:]):
            cols = [c.strip().strip('"') for c in linea.split(",")]
            if len(cols) >= 8:
                talentos.append({
                    "idx":         i,
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
        print(f"❌ Error leyendo talentos: {e}")
        return []

def leer_votos() -> list:
    try:
        r = requests.get(SHEET_VOTOS_URL, timeout=5)
        if r.status_code != 200:
            return []
        lineas = r.text.strip().split("\n")
        votos = []
        for linea in lineas[1:]:
            cols = [c.strip().strip('"') for c in linea.split(",")]
            if len(cols) >= 4:
                votos.append({
                    "voter_id":   cols[1],
                    "talento_id": cols[2],
                    "estrellas":  cols[3],
                    "fecha":      cols[4] if len(cols) > 4 else "",
                })
        return votos
    except Exception as e:
        print(f"❌ Error leyendo votos: {e}")
        return []

def calcular_rating(talento_id: str, votos: list) -> tuple:
    mis_votos = [v for v in votos if v["talento_id"] == str(talento_id)]
    if not mis_votos:
        return (0.0, 0)
    try:
        estrellas = [float(v["estrellas"]) for v in mis_votos]
        return (round(sum(estrellas) / len(estrellas), 1), len(estrellas))
    except:
        return (0.0, 0)

def estrellas_emoji(promedio: float) -> str:
    llenas = int(round(promedio))
    return "⭐" * llenas + "☆" * (5 - llenas)

def ya_voto(voter_id: str, talento_id: str, votos_sheet: list) -> bool:
    key = f"{voter_id}:{talento_id}"
    if key in votos_cache:
        return True
    return any(
        v["voter_id"] == str(voter_id) and v["talento_id"] == str(talento_id)
        for v in votos_sheet
    )

def enviar_voto_a_form(voter_id: str, talento_id: str, estrellas: int) -> bool:
    payload = {
        FIELD_VOTER_ID:   str(voter_id),
        FIELD_TALENTO_ID: str(talento_id),
        FIELD_ESTRELLAS:  str(estrellas),
        FIELD_FECHA_VOTO: time.strftime("%Y-%m-%d"),
    }
    try:
        r = requests.post(FORM_VOTOS_URL, data=payload, timeout=10)
        return r.status_code in [200, 302]
    except Exception as e:
        print(f"❌ Error enviando voto: {e}")
        return False

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
        print(f"❌ Error enviando talento: {e}")
        return False

def pedir_anio(bot, chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("1° año",     callback_data="tal_anio_1° año"),
        types.InlineKeyboardButton("2° año",     callback_data="tal_anio_2° año"),
        types.InlineKeyboardButton("3° año",     callback_data="tal_anio_3° año"),
        types.InlineKeyboardButton("Recibida/o", callback_data="tal_anio_Recibida/o"),
    )
    bot.send_message(chat_id, "📅 *Paso 4/7 — Año de carrera*\n¿Qué año cursás?",
                     reply_markup=markup, parse_mode="Markdown")


# ─────────────────────────────────────────────
#  MENÚ PRINCIPAL
# ─────────────────────────────────────────────

def menu_talentos(bot, message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Publicar mi perfil",  callback_data="tal_registrar"),
        types.InlineKeyboardButton("🔍 Explorar talentos",   callback_data="tal_explorar"),
        types.InlineKeyboardButton("⭐ Talentos destacados", callback_data="tal_destacados"),
    )
    bot.send_message(
        message.chat.id,
        "🌟 *Talentos TUCE*\n\nConectá con compañeros según su especialidad.\n¿Qué querés hacer?",
        reply_markup=markup, parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
#  FLUJO REGISTRO
#  categoria → nombre → username → anio → bio → web → foto
# ─────────────────────────────────────────────

def iniciar_registro(bot, message):
    user_id = message.from_user.id
    estados_talentos[user_id] = {"paso": "categoria", "datos": {"telegram_id": user_id}}
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIAS:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"tal_cat_{cat}"))
    bot.send_message(message.chat.id, "🏷️ *Paso 1/7 — Categoría*\n¿Cuál es tu área principal?",
                     reply_markup=markup, parse_mode="Markdown")

def paso_categoria(bot, call, categoria):
    user_id = call.from_user.id
    if user_id not in estados_talentos:
        bot.answer_callback_query(call.id)
        iniciar_registro(bot, call.message)
        return
    estados_talentos[user_id]["datos"]["categoria"] = categoria
    estados_talentos[user_id]["paso"] = "nombre"
    bot.edit_message_text(f"✅ Categoría: *{categoria}*",
                          call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.send_message(call.message.chat.id, PASOS_PREGUNTAS["nombre"], parse_mode="Markdown")

def paso_anio(bot, call, anio):
    user_id = call.from_user.id
    if user_id not in estados_talentos:
        return
    estados_talentos[user_id]["datos"]["anio"] = anio
    estados_talentos[user_id]["paso"] = "bio"
    bot.edit_message_text(f"✅ Año: *{anio}*",
                          call.message.chat.id, call.message.message_id, parse_mode="Markdown")
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
    user_id = message.from_user.id
    if user_id not in estados_talentos or estados_talentos[user_id]["paso"] != "foto":
        return False
    if message.content_type == "photo" and message.photo:
        estados_talentos[user_id]["datos"]["foto_id"] = message.photo[-1].file_id
    else:
        estados_talentos[user_id]["datos"]["foto_id"] = "sin_foto"

    datos = estados_talentos[user_id]["datos"]
    bot.send_chat_action(message.chat.id, "typing")
    exito = enviar_a_form(datos)
    del estados_talentos[user_id]

    if exito:
        cat = datos.get("categoria", "")
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔍 Ver talentos de mi categoría", callback_data=f"tal_ver_{cat}"),
            types.InlineKeyboardButton("⭐ Ver destacados",               callback_data="tal_destacados"),
        )
        bot.send_message(
            message.chat.id,
            f"🎉 *¡Perfil publicado!*\n\n"
            f"*Categoría:* {cat}\n"
            f"*Nombre:* {datos.get('nombre','')}\n"
            f"*Usuario:* {datos.get('username','')}\n"
            f"*Año:* {datos.get('anio','')}\n"
            f"*Bio:* {datos.get('bio','')}\n\n"
            f"Tus compañeros ya pueden encontrarte en 🌟 Talentos TUCE.",
            reply_markup=markup, parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id,
                         "⚠️ Hubo un problema al guardar tu perfil. Intentá de nuevo en unos minutos.")
    return True


# ─────────────────────────────────────────────
#  TARJETA DE TALENTO
# ─────────────────────────────────────────────

def enviar_tarjeta_talento(bot, chat_id, talento: dict, viewer_id: int, votos: list):
    nombre   = talento.get("nombre", "Sin nombre")
    username = talento.get("username", "")
    anio     = talento.get("anio", "")
    bio      = talento.get("bio", "")
    web      = talento.get("web", "")
    cat      = talento.get("categoria", "")
    foto_id  = talento.get("foto_id", "")
    tid      = talento.get("telegram_id", "")
    idx      = talento.get("idx", 0)

    promedio, nvotes = calcular_rating(str(idx), votos)
    rating_txt = (f"{estrellas_emoji(promedio)} {promedio}/5 ({nvotes} voto{'s' if nvotes!=1 else ''})"
                  if nvotes > 0 else "Sin votos aún — ¡sé el primero!")

    web_fmt = formatear_web(web)

    texto = (
        f"👤 *{nombre}*\n"
        f"{cat} · {anio}\n\n"
        f"_{bio}_\n\n"
    )
    if web_fmt:
        texto += f"{web_fmt}\n"
    texto += f"\n⭐ *Rating:* {rating_txt}"

    markup = types.InlineKeyboardMarkup(row_width=5)

    # Botones de votación
    ya = ya_voto(str(viewer_id), str(idx), votos)
    if not ya:
        markup.add(
            types.InlineKeyboardButton("1⭐", callback_data=f"tal_votar_{idx}_1"),
            types.InlineKeyboardButton("2⭐", callback_data=f"tal_votar_{idx}_2"),
            types.InlineKeyboardButton("3⭐", callback_data=f"tal_votar_{idx}_3"),
            types.InlineKeyboardButton("4⭐", callback_data=f"tal_votar_{idx}_4"),
            types.InlineKeyboardButton("5⭐", callback_data=f"tal_votar_{idx}_5"),
        )
    else:
        markup.add(types.InlineKeyboardButton("✅ Ya votaste este perfil", callback_data="tal_noop"))

    # Contactar
    if username and username not in ["Sin usuario", "no tengo"]:
        tg = username.replace("@", "")
        markup.add(types.InlineKeyboardButton(f"💬 Contactar a {nombre}", url=f"https://t.me/{tg}"))

    # Editar / Eliminar solo para el dueño
    if str(viewer_id) == str(tid):
        markup.add(
            types.InlineKeyboardButton("✏️ Editar perfil",   callback_data=f"tal_editar_{idx}"),
            types.InlineKeyboardButton("🗑️ Eliminar perfil", callback_data=f"tal_eliminar_{idx}"),
        )

    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data=f"tal_ver_{cat}"))

    # Enviar foto si tiene
    if foto_id and foto_id not in ["sin_foto", ""]:
        try:
            bot.send_photo(chat_id, foto_id, caption=texto,
                           reply_markup=markup, parse_mode="Markdown")
            return
        except:
            pass

    bot.send_message(chat_id, texto, reply_markup=markup,
                     parse_mode="Markdown", disable_web_page_preview=False)


# ─────────────────────────────────────────────
#  EXPLORAR
# ─────────────────────────────────────────────

def mostrar_menu_explorar(bot, call, edit=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIAS:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"tal_ver_{cat}"))
    markup.add(types.InlineKeyboardButton("⭐ Ver destacados", callback_data="tal_destacados"))
    texto = "🔍 *¿Qué perfil buscás?*\nElegí una categoría:"
    if edit:
        bot.edit_message_text(texto, call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(call.message.chat.id, texto, reply_markup=markup, parse_mode="Markdown")

def mostrar_talentos_por_categoria(bot, call, categoria):
    bot.answer_callback_query(call.id, "Buscando talentos...")
    talentos  = leer_talentos_desde_sheet()
    votos     = leer_votos()
    filtrados = [t for t in talentos if t["categoria"] == categoria]

    if not filtrados:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Ver otras categorías", callback_data="tal_explorar"))
        bot.edit_message_text(
            f"😕 Todavía no hay talentos en *{categoria}*.\n¡Podés ser el primero!",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    texto = f"*{categoria}* — {len(filtrados)} talento(s)\n\n"

    for t in filtrados[:10]:
        nombre   = t.get("nombre", "Sin nombre")
        anio     = t.get("anio", "")
        bio      = t.get("bio", "")[:60]
        idx      = t.get("idx", 0)
        promedio, nvotes = calcular_rating(str(idx), votos)
        stars = estrellas_emoji(promedio) if nvotes > 0 else ""
        texto += f"👤 *{nombre}* · {anio} {stars}\n_{bio}..._\n\n"
        markup.add(types.InlineKeyboardButton(
            f"Ver perfil de {nombre}", callback_data=f"tal_perfil_{idx}"
        ))

    markup.add(types.InlineKeyboardButton("⬅️ Ver otras categorías", callback_data="tal_explorar"))
    bot.edit_message_text(texto, call.message.chat.id, call.message.message_id,
                          reply_markup=markup, parse_mode="Markdown")

def mostrar_perfil_individual(bot, call, idx: int):
    bot.answer_callback_query(call.id)
    talentos = leer_talentos_desde_sheet()
    votos    = leer_votos()
    talento  = next((t for t in talentos if t["idx"] == idx), None)
    if not talento:
        bot.send_message(call.message.chat.id, "❌ Perfil no encontrado.")
        return
    enviar_tarjeta_talento(bot, call.message.chat.id, talento,
                            viewer_id=call.from_user.id, votos=votos)

def mostrar_destacados(bot, call):
    bot.answer_callback_query(call.id, "Cargando destacados...")
    talentos = leer_talentos_desde_sheet()
    votos    = leer_votos()

    ranked = []
    for t in talentos:
        promedio, nvotes = calcular_rating(str(t["idx"]), votos)
        if nvotes >= 1:
            ranked.append((t, promedio, nvotes))
    ranked.sort(key=lambda x: x[1], reverse=True)
    top = ranked[:5]

    if not top:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="tal_explorar"))
        bot.edit_message_text(
            "⭐ *Talentos Destacados*\n\nTodavía nadie recibió votos.\n¡Explorá los perfiles y empezá a votar!",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
        return

    medallas = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    texto = "⭐ *Top Talentos TUCE*\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)

    for i, (t, prom, nv) in enumerate(top):
        nombre = t.get("nombre", "")
        cat    = t.get("categoria", "")
        texto += f"{medallas[i]} *{nombre}* — {cat}\n{estrellas_emoji(prom)} {prom}/5 ({nv} votos)\n\n"
        markup.add(types.InlineKeyboardButton(
            f"Ver perfil de {nombre}", callback_data=f"tal_perfil_{t['idx']}"
        ))

    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="tal_explorar"))
    bot.edit_message_text(texto, call.message.chat.id, call.message.message_id,
                          reply_markup=markup, parse_mode="Markdown")


# ─────────────────────────────────────────────
#  VOTAR
# ─────────────────────────────────────────────

def registrar_voto(bot, call, idx: int, estrellas: int):
    voter_id = call.from_user.id
    votos    = leer_votos()

    if ya_voto(str(voter_id), str(idx), votos):
        bot.answer_callback_query(call.id, "Ya votaste este perfil.", show_alert=True)
        return

    # Guardar en cache local y en Google Form (persistente)
    key = f"{voter_id}:{idx}"
    votos_cache[key] = estrellas
    exito = enviar_voto_a_form(str(voter_id), str(idx), estrellas)

    if exito:
        bot.answer_callback_query(call.id, f"¡Gracias! Diste {estrellas}⭐", show_alert=True)
    else:
        bot.answer_callback_query(call.id, f"Voto registrado: {estrellas}⭐", show_alert=True)

    # Refrescar tarjeta
    talentos = leer_talentos_desde_sheet()
    votos    = leer_votos()
    talento  = next((t for t in talentos if t["idx"] == idx), None)
    if talento:
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        enviar_tarjeta_talento(bot, call.message.chat.id, talento,
                                viewer_id=voter_id, votos=votos)


# ─────────────────────────────────────────────
#  EDITAR / ELIMINAR
# ─────────────────────────────────────────────

def iniciar_edicion(bot, call, idx: int):
    user_id  = call.from_user.id
    talentos = leer_talentos_desde_sheet()
    talento  = next((t for t in talentos if t["idx"] == idx), None)

    if not talento or str(talento.get("telegram_id","")) != str(user_id):
        bot.answer_callback_query(call.id, "Solo podés editar tu propio perfil.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👤 Nombre",    callback_data=f"tal_edit_campo_nombre_{idx}"),
        types.InlineKeyboardButton("📝 Bio",       callback_data=f"tal_edit_campo_bio_{idx}"),
        types.InlineKeyboardButton("🌐 Web",       callback_data=f"tal_edit_campo_web_{idx}"),
        types.InlineKeyboardButton("📸 Foto",      callback_data=f"tal_edit_campo_foto_{idx}"),
        types.InlineKeyboardButton("🏷️ Categoría", callback_data=f"tal_edit_campo_categoria_{idx}"),
    )
    markup.add(types.InlineKeyboardButton("❌ Cancelar", callback_data=f"tal_perfil_{idx}"))
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "✏️ *¿Qué querés editar?*",
                     reply_markup=markup, parse_mode="Markdown")

def confirmar_eliminacion(bot, call, idx: int):
    user_id  = call.from_user.id
    talentos = leer_talentos_desde_sheet()
    talento  = next((t for t in talentos if t["idx"] == idx), None)

    if not talento or str(talento.get("telegram_id","")) != str(user_id):
        bot.answer_callback_query(call.id, "Solo podés eliminar tu propio perfil.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"tal_confirm_del_{idx}"),
        types.InlineKeyboardButton("❌ Cancelar",     callback_data=f"tal_perfil_{idx}"),
    )
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,
                     "⚠️ *¿Seguro que querés eliminar tu perfil?*",
                     reply_markup=markup, parse_mode="Markdown")

def ejecutar_eliminacion(bot, call, idx: int):
    user_id  = call.from_user.id
    talentos = leer_talentos_desde_sheet()
    talento  = next((t for t in talentos if t["idx"] == idx), None)

    if not talento or str(talento.get("telegram_id","")) != str(user_id):
        bot.answer_callback_query(call.id, "No autorizado.", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "🗑️ Solicitud registrada. Para confirmar la baja escribí a @Btescr o al grupo de la comunidad.\n\n"
        "_La eliminación directa desde el bot estará disponible próximamente._",
        parse_mode="Markdown"
    )