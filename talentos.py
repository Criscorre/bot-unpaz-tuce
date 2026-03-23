import time
import re
import unicodedata
import json
import os
from telebot import types
import firebase_admin
from firebase_admin import credentials, db

# --- CONEXIÓN FIREBASE ---
firebase_json = os.getenv("FIREBASE_JSON")
database_url = os.getenv("FIREBASE_DB_URL")

if firebase_json and database_url:
    try:
        if not firebase_admin._apps:
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {'databaseURL': database_url})
        print("✅ Conectado a Firebase Realtime DB")
    except Exception as e:
        print(f"❌ Error Firebase: {e}")

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
    "username": "💬 *Paso 3/7 — Usuario de Telegram*\n¿Cuál es tu @usuario?",
    "bio":      "📝 *Paso 5/7 — Presentación*\nEscribí una bio breve (máx 200 car.):",
    "web":      "🌐 *Paso 6/7 — Web o Portfolio*\nPegá el link o escribí `no tengo`:",
    "foto":     "📸 *Paso 7/7 — Foto de perfil*\nMandame una foto o escribí `omitir`:",
}

estados_talentos = {}

# ─────────────────────────────────────────────
#  HELPERS & DB
# ─────────────────────────────────────────────

def normalizar_categoria(texto: str) -> str:
    if not texto: return ""
    return re.sub(r'[^\w\s]', '', texto).strip().lower()

def leer_talentos_desde_db():
    try:
        ref = db.reference('talentos')
        data = ref.get()
        return list(data.values()) if data else []
    except: return []

def leer_votos_db():
    try:
        ref = db.reference('votos')
        data = ref.get()
        return list(data.values()) if data else []
    except: return []

def calcular_rating(tid, votos):
    mis_votos = [v for v in votos if str(v.get("talento_id")) == str(tid)]
    if not mis_votos: return (0.0, 0)
    estrellas = [int(v["estrellas"]) for v in mis_votos]
    return (round(sum(estrellas)/len(estrellas), 1), len(estrellas))

def estrellas_emoji(p):
    return "⭐" * int(round(p)) + "☆" * (5 - int(round(p)))

# ─────────────────────────────────────────────
#  MENÚS Y FLUJO
# ─────────────────────────────────────────────

def menu_talentos(bot, message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Publicar mi perfil", callback_data="tal_registrar"),
        types.InlineKeyboardButton("🔍 Explorar talentos", callback_data="tal_explorar"),
        types.InlineKeyboardButton("⭐ Destacados", callback_data="tal_destacados")
    )
    bot.send_message(message.chat.id, "🌟 *Talentos TUCE*", reply_markup=markup, parse_mode="Markdown")

def iniciar_registro(bot, message):
    uid = message.from_user.id
    estados_talentos[uid] = {"paso": "categoria", "datos": {"telegram_id": uid}}
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIAS:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"tal_cat_{cat}"))
    bot.send_message(message.chat.id, "🏷️ *Paso 1/7 — Categoría*", reply_markup=markup, parse_mode="Markdown")

def paso_categoria(bot, call, cat):
    uid = call.from_user.id
    if uid not in estados_talentos: return
    estados_talentos[uid]["datos"]["categoria"] = cat
    estados_talentos[uid]["paso"] = "nombre"
    bot.edit_message_text(f"✅ Cat: {cat}", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, PASOS_PREGUNTAS["nombre"], parse_mode="Markdown")

def paso_nombre(bot, message):
    uid = message.from_user.id
    if uid not in estados_talentos: return False
    estados_talentos[uid]["datos"]["nombre"] = message.text.strip()
    estados_talentos[uid]["paso"] = "username"
    bot.send_message(message.chat.id, PASOS_PREGUNTAS["username"], parse_mode="Markdown")
    return True

def paso_username(bot, message):
    uid = message.from_user.id
    if uid not in estados_talentos: return False
    user = message.text.strip()
    estados_talentos[uid]["datos"]["username"] = user if user.startswith("@") else f"@{user}"
    estados_talentos[uid]["paso"] = "anio"
    markup = types.InlineKeyboardMarkup()
    markup.add(*(types.InlineKeyboardButton(a, callback_data=f"tal_anio_{a}") for a in ["1°","2°","3°","Recibido"]))
    bot.send_message(message.chat.id, "📅 *Paso 4/7 — Año*", reply_markup=markup, parse_mode="Markdown")
    return True

def paso_anio(bot, call, anio):
    uid = call.from_user.id
    if uid not in estados_talentos: return
    estados_talentos[uid]["datos"]["anio"] = anio
    estados_talentos[uid]["paso"] = "bio"
    bot.edit_message_text(f"✅ Año: {anio}", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, PASOS_PREGUNTAS["bio"], parse_mode="Markdown")

def paso_bio(bot, message):
    uid = message.from_user.id
    if uid not in estados_talentos: return False
    estados_talentos[uid]["datos"]["bio"] = message.text.strip()
    estados_talentos[uid]["paso"] = "web"
    bot.send_message(message.chat.id, PASOS_PREGUNTAS["web"], parse_mode="Markdown")
    return True

def paso_web(bot, message):
    uid = message.from_user.id
    if uid not in estados_talentos: return False
    estados_talentos[uid]["datos"]["web"] = message.text.strip()
    estados_talentos[uid]["paso"] = "foto"
    bot.send_message(message.chat.id, PASOS_PREGUNTAS["foto"], parse_mode="Markdown")
    return True

def paso_foto(bot, message):
    uid = message.from_user.id
    if uid not in estados_talentos: return False
    
    # Si manda foto la guardamos, si manda texto (como "Listo" u "Omitir") va sin foto
    if message.content_type == "photo":
        fid = message.photo[-1].file_id
    else:
        fid = "sin_foto"
        
    estados_talentos[uid]["datos"]["foto_id"] = fid
    
    try:
        # Guardamos en Firebase usando el ID de telegram como llave
        db.reference('talentos').child(str(uid)).set(estados_talentos[uid]["datos"])
        
        # Guardamos copia local de los datos para el mensaje final antes de borrar el estado
        datos_finales = estados_talentos[uid]["datos"]
        del estados_talentos[uid]
        
        bot.send_message(
            message.chat.id, 
            f"🎉 *¡Perfil guardado!*\n\n"
            f"👤 *Nombre:* {datos_finales.get('nombre')}\n"
            f"🏷️ *Categoría:* {datos_finales.get('categoria')}\n\n"
            "Ya podés consultarlo en el explorador de talentos.",
            parse_mode="Markdown"
        )
        return True
    except Exception as e:
        print(f"❌ Error al guardar en Firebase: {e}")
        bot.send_message(message.chat.id, "⚠️ Hubo un error al guardar tu perfil. Reintentá en unos momentos.")
        return False

# ─────────────────────────────────────────────
#  VISTAS
# ─────────────────────────────────────────────

def mostrar_menu_explorar(bot, call, edit=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIAS: markup.add(types.InlineKeyboardButton(cat, callback_data=f"tal_ver_{cat}"))
    if edit: bot.edit_message_text("🔍 *Elegí categoría:*", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    else: bot.send_message(call.message.chat.id, "🔍 *Elegí categoría:*", reply_markup=markup, parse_mode="Markdown")

def mostrar_talentos_por_categoria(bot, call, cat):
    talentos = leer_talentos_desde_db()
    cat_n = normalizar_categoria(cat)
    filtrados = [t for t in talentos if normalizar_categoria(t.get("categoria")) == cat_n]
    if not filtrados:
        bot.answer_callback_query(call.id, "No hay nadie aún.")
        return
    markup = types.InlineKeyboardMarkup()
    for t in filtrados:
        markup.add(types.InlineKeyboardButton(t.get("nombre"), callback_data=f"tal_perfil_{t.get('telegram_id')}"))
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="tal_explorar"))
    bot.edit_message_text(f"👥 *{cat}*", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

def mostrar_perfil_individual(bot, call, tid):
    talentos = leer_talentos_desde_db()
    votos = leer_votos_db()
    t = next((x for x in talentos if str(x.get("telegram_id")) == str(tid)), None)
    if not t: return
    
    prom, nv = calcular_rating(tid, votos)
    txt = (f"👤 *{t.get('nombre')}*\n{t.get('categoria')} · {t.get('anio')}\n\n"
           f"_{t.get('bio')}_\n\n"
           f"🌐 {t.get('web')}\n"
           f"⭐ {estrellas_emoji(prom)} {prom}/5 ({nv} votos)")

    markup = types.InlineKeyboardMarkup(row_width=5)
    # Si no es su propio perfil, puede votar
    if str(call.from_user.id) != str(tid):
        markup.add(*(types.InlineKeyboardButton(f"{i}⭐", callback_data=f"tal_votar_{tid}_{i}") for i in range(1,6)))
    
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data=f"tal_ver_{t.get('categoria')}"))
    
    if t.get("foto_id") != "sin_foto":
        bot.send_photo(call.message.chat.id, t.get("foto_id"), caption=txt, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(call.message.chat.id, txt, reply_markup=markup, parse_mode="Markdown")

def registrar_voto(bot, call, tid, estrellas):
    vid = call.from_user.id
    db.reference('votos').child(f"{vid}_{tid}").set({
        "voter_id": str(vid), "talento_id": str(tid), "estrellas": int(estrellas)
    })
    bot.answer_callback_query(call.id, f"¡Diste {estrellas} estrellas!")
    mostrar_perfil_individual(bot, call, tid)

def mostrar_destacados(bot, call):
    talentos = leer_talentos_desde_db()
    votos = leer_votos_db()
    ranked = []
    for t in talentos:
        p, n = calcular_rating(t.get("telegram_id"), votos)
        if n > 0: ranked.append((t, p, n))
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    res = "🏆 *Top 5 Talentos*\n\n"
    for t, p, n in ranked[:5]:
        res += f"• {t.get('nombre')} - {p}⭐ ({n} v.)\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="tal_explorar"))
    bot.edit_message_text(res, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

def iniciar_edicion(bot, call, tid): pass
def confirmar_eliminacion(bot, call, tid): pass
def ejecutar_eliminacion(bot, call, tid): pass