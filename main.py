import os
from dotenv import load_dotenv
import telebot
from telebot import types
import time
import requests
from openai import OpenAI
from info_unpaz import DATOS_TECNICATURA
from materias_db import LISTA_HORARIOS
from scraper import scrape_todo, obtener_contexto_ia, obtener_novedades_texto, leer_cache
from datos_carrera import DATA_CALENDARIO, DATA_PLAN, CORRELATIVAS, correlativas_de, DATA_BOT_INFO
import wa_menu
from talentos import (
    menu_talentos, iniciar_registro, mostrar_menu_explorar,
    mostrar_talentos_por_categoria, mostrar_perfil_individual,
    mostrar_destacados, registrar_voto, iniciar_edicion,
    confirmar_eliminacion, ejecutar_eliminacion,
    paso_categoria, paso_foto, paso_nombre, paso_username,
    paso_bio, paso_anio, paso_web, estados_talentos,
)
from herramientas import (
    menu_herramientas, menu_banco, menu_ocr,
    iniciar_subida, paso_materia_subir, paso_tipo_subir,
    paso_archivo_subir, mostrar_buscar_materia,
    mostrar_material_materia, descargar_archivo,
    procesar_foto_ocr, generar_documento,
    estados_herramientas,
)
from horario_personal import (
    menu_horario, iniciar_config, seleccionar_comision,
    saltear_materia, finalizar_config, confirmar_borrar,
    ejecutar_borrar, cancelar_config,
    estados_horario,
)

import http.server, socketserver, threading
from flask import Flask, request, jsonify

# ─── Health server (Koyeb) ────────────────────────────────────────────────────
def run_health_server():
    PORT = 8000
    Handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🌍 Servidor de salud activo en puerto {PORT}")
        httpd.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# WhatsApp: procesamiento delegado a wa_menu.py
# El estado conversacional y el menú guiado viven en ese módulo.


# ─── Webhook Flask para el bridge de WhatsApp ────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/wa", methods=["POST"])
def webhook_wa():
    data     = request.get_json(silent=True) or {}
    from_id  = data.get("from", "")
    message  = data.get("message", "").strip()
    if not from_id or not message:
        return jsonify({"response": ""}), 400
    respuesta = wa_menu.procesar(from_id, message, firebase_db, responder_ia)
    return jsonify({"response": respuesta})

@flask_app.route("/health", methods=["GET"])
def health():
    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

threading.Thread(target=run_flask, daemon=True).start()

base_dir = os.path.dirname(__file__)
load_dotenv(os.path.join(base_dir, '.env'))

TOKEN          = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
FORM_USUARIOS_URL      = os.getenv('FORM_USUARIOS_URL', '')
FORM_USUARIOS_ID       = os.getenv('FORM_USUARIOS_FIELD_ID', '')
FORM_USUARIOS_NOMBRE   = os.getenv('FORM_USUARIOS_FIELD_NOMBRE', '')
FORM_USUARIOS_USERNAME = os.getenv('FORM_USUARIOS_FIELD_USERNAME', '')
FORM_USUARIOS_FECHA    = os.getenv('FORM_USUARIOS_FIELD_FECHA', '')

if not TOKEN or not OPENAI_API_KEY:
    print("❌ Error: credenciales no encontradas")
    exit()
else:
    print("✅ Bot TUCE iniciando — Talentos + Herramientas + IA")

bot    = telebot.TeleBot(TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# Firebase
import firebase_admin
from firebase_admin import db as firebase_db

# ─── Scheduler: scraping automático cada 6 horas ─────────────────────────────
from apscheduler.schedulers.background import BackgroundScheduler

def _iniciar_scraper():
    """Lanza el primer scraping y programa los siguientes cada 6 horas."""
    try:
        scrape_todo(firebase_db)
    except Exception as e:
        print(f"⚠️ Error en scraping inicial: {e}")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(_iniciar_scraper, "interval", hours=6, id="scraper_unpaz")

# ─── Recordatorios automáticos ────────────────────────────────────────────────
# Fechas clave del calendario académico 2026 que se notifican 48hs antes
FECHAS_RECORDATORIOS = {
    "2026-02-16": "📝 Pasado mañana arranca la inscripción al 1er semestre (18/02).",
    "2026-02-17": "📝 Mañana arranca la inscripción al 1er semestre (18/02). ¡Preparate!",
    "2026-03-07": "📚 Pasado mañana empiezan las clases del 1er semestre (09/03).",
    "2026-03-08": "📚 ¡Mañana empiezan las clases! 1er semestre 2026. ¡Buena cursada!",
    "2026-07-20": "📝 Pasado mañana arranca la inscripción al 2do semestre (22/07).",
    "2026-07-21": "📝 Mañana arranca la inscripción al 2do semestre (22/07). ¡Preparate!",
    "2026-08-08": "📚 Pasado mañana empiezan las clases del 2do semestre (10/08).",
    "2026-08-09": "📚 ¡Mañana empiezan las clases! 2do semestre 2026. ¡Buena cursada!",
    "2026-04-08": "⚖️ Pasado mañana vence el período de equivalencias (10/04/2026).",
    "2026-04-09": "⚖️ ¡Mañana es el último día para tramitar equivalencias (10/04)! Ingresá al SIU.",
}

import datetime

def _enviar_recordatorios():
    """Se ejecuta todos los días a las 11:00 UTC (08:00 Argentina).
       Busca si hoy hay recordatorio y lo envía a todos los usuarios registrados."""
    try:
        hoy = datetime.date.today().strftime("%Y-%m-%d")
        mensaje = FECHAS_RECORDATORIOS.get(hoy)
        if not mensaje:
            return
        # Verificar si ya se envió hoy para evitar duplicados
        key_enviado = f"recordatorios_enviados/{hoy}"
        ya_enviado = firebase_db.reference(key_enviado).get()
        if ya_enviado:
            return
        # Obtener todos los usuarios registrados
        usuarios = firebase_db.reference("usuarios_telegram").get() or {}
        enviados = 0
        for uid, info in usuarios.items():
            try:
                chat_id = info.get("chat_id") if isinstance(info, dict) else None
                if not chat_id:
                    continue
                bot.send_message(
                    chat_id,
                    f"🔔 *Recordatorio TUCE*\n\n{mensaje}\n\n"
                    "_Podés ver más info con /start → 🗓️ Calendario_",
                    parse_mode="Markdown"
                )
                enviados += 1
            except Exception as ex:
                print(f"⚠️ No se pudo notificar a {uid}: {ex}")
        # Marcar como enviado
        firebase_db.reference(key_enviado).set(True)
        print(f"🔔 Recordatorios enviados a {enviados} usuarios para {hoy}")
    except Exception as e:
        print(f"❌ Error en recordatorios: {e}")

scheduler.add_job(_enviar_recordatorios, "cron", hour=11, minute=0, id="recordatorios")
scheduler.start()
# Primer scraping en background al iniciar (no bloquea el arranque del bot)
threading.Thread(target=_iniciar_scraper, daemon=True).start()

# DATA_CALENDARIO, DATA_PLAN, CORRELATIVAS, correlativas_de, DATA_BOT_INFO
# → importados desde datos_carrera.py (al inicio del archivo)
URLS_UNPAZ = {
    "tuce":         "https://unpaz.edu.ar/comercioelectronico",
    "becas":        "https://unpaz.edu.ar/bienestar/becas",
    "calendario":   "https://unpaz.edu.ar/calendario-academico",
    "ingreso":      "https://unpaz.edu.ar/estudiaenunpaz",
    "equivalencias":"https://unpaz.edu.ar/formularioequivalencias",
    "pasantias":    "https://unpaz.edu.ar/pasantias",
    "reglamento":   "https://unpaz.edu.ar/regimen-general-de-estudios",
}

def obtener_info_web(url):
    try:
        import re
        r = requests.get(url, timeout=3, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200: return ""
        t = r.text
        t = re.sub(r'<style[^>]*>.*?</style>', '', t, flags=re.DOTALL)
        t = re.sub(r'<script[^>]*>.*?</script>', '', t, flags=re.DOTALL)
        t = re.sub(r'<[^>]+>', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()[:3000]
    except: return ""

def detectar_url_relevante(p):
    p = p.lower()
    if any(w in p for w in ["beca","becas"]):                return URLS_UNPAZ["becas"]
    if any(w in p for w in ["pasantía","pasantias"]):        return URLS_UNPAZ["pasantias"]
    if any(w in p for w in ["equivalencia","equivalencias"]): return URLS_UNPAZ["equivalencias"]
    if any(w in p for w in ["calendario","fechas","cuándo"]): return URLS_UNPAZ["calendario"]
    if any(w in p for w in ["ingreso","ingresante","ciu"]):   return URLS_UNPAZ["ingreso"]
    if any(w in p for w in ["reglamento","régimen"]):         return URLS_UNPAZ["reglamento"]
    if any(w in p for w in ["tuce","comercio electrónico"]):  return URLS_UNPAZ["tuce"]
    return ""

def registrar_usuario(user):
    try:
        with open("usuarios.txt", "a", encoding="utf-8") as f:
            fecha = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{fecha} | ID: {user.id} | Nombre: {user.first_name} | @{user.username}\n")
            f.flush()
        print(f"📈 {user.first_name}")
    except Exception as e:
        print(f"Error registro local: {e}")
    if FORM_USUARIOS_URL and FORM_USUARIOS_ID:
        try:
            requests.post(FORM_USUARIOS_URL, timeout=3, data={
                FORM_USUARIOS_ID:       str(user.id),
                FORM_USUARIOS_NOMBRE:   user.first_name or "",
                FORM_USUARIOS_USERNAME: f"@{user.username}" if user.username else "Sin usuario",
                FORM_USUARIOS_FECHA:    time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except: pass

def _cache_fresco() -> bool:
    """Devuelve True si el cache de scraping tiene menos de 12 horas."""
    try:
        cache = leer_cache(firebase_db)
        if not cache:
            return False
        ts_str = cache.get("inicio", {}).get("timestamp", "")
        if not ts_str:
            return False
        ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        diferencia = datetime.datetime.now() - ts
        return diferencia.total_seconds() < 12 * 3600
    except Exception:
        return False

def responder_ia(pregunta):
    ctx = f"{DATOS_TECNICATURA}\nCALENDARIO: {DATA_CALENDARIO}\nPLAN: {DATA_PLAN}\n"

    # Scraping on-demand: si el cache tiene más de 12 horas, actualizar en background
    if not _cache_fresco():
        threading.Thread(target=_iniciar_scraper, daemon=True).start()

    # Contexto scrapeado desde Firebase (se actualiza cada 6 horas)
    try:
        ctx_scraper = obtener_contexto_ia(firebase_db, pregunta)
        if ctx_scraper:
            ctx += f"\n\nINFO ACTUALIZADA DE UNPAZ.EDU.AR:\n{ctx_scraper}"
    except Exception as e:
        print(f"⚠️ Error leyendo cache scraper: {e}")

    ctx_web = ""
    url = detectar_url_relevante(pregunta)
    if url:
        try:
            info = obtener_info_web(url)
            if info: ctx_web = f"\n\nINFO WEB {url}:\n{info}"
        except: pass
    sistema = (
        "Sos el Asistente Virtual de la Comunidad TUCE - UNPAZ. "
        "REGLA PRINCIPAL: NO inventes información. Si no tenés certeza de algo, decí 'No tengo esa información. "
        "Te recomiendo consultar en unpaz.edu.ar o escribir a la mesa de ayuda.' "
        "Respondés SOLO sobre UNPAZ, la carrera TUCE, materias, trámites, becas, fechas y vida universitaria. "
        "Si te preguntan algo que no tiene que ver con la UNPAZ, decís amablemente que solo podés ayudar con temas de la carrera. "
        "Si te preguntan quién te creó, decís que fuiste desarrollado por Bytes Creativos. "
        "Respondés en español, claro y breve (máximo 3 líneas). Sin preamble ni relleno. "
        "Cuando tenés info actualizada de la web de la UNPAZ, la usás. "
        "Si no sabés, derivás a unpaz.edu.ar o la mesa de ayuda. "
        "NUNCA respondas sobre política, entretenimiento, tecnología general ni nada ajeno a UNPAZ/TUCE. "
        "Contexto: " + ctx + ctx_web
    )
    try:
        r = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":sistema},{"role":"user","content":pregunta}],
            max_tokens=400, temperature=0.1
        )
        return r.choices[0].message.content
    except Exception as e:
        print(f"Error IA: {e}")
        return "Servicio no disponible. Consultá en unpaz.edu.ar"

# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def send_welcome(message):
    registrar_usuario(message.from_user)
    # Guardar usuario en Firebase para recordatorios automáticos
    try:
        firebase_db.reference(f"usuarios_telegram/{message.from_user.id}").set({
            "nombre":   message.from_user.first_name or "",
            "username": message.from_user.username or "",
            "chat_id":  message.chat.id,
        })
    except Exception as e:
        print(f"⚠️ Error registrando usuario en Firebase: {e}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        "📚 Materias horarios", "🗓️ Calendario",
        "📍 Sedes",             "🖥️ Gestión Alumnos",
        "🤖 Bot TUCE",          "🌟 Talentos TUCE",
        "🛠️ Herramientas",      "📰 Novedades UNPAZ",
        "📅 Mi Horario",
    )
    bot.send_message(
        message.chat.id,
        "Bienvenido al *Bot de la Comunidad TUCE - UNPAZ*.\n\nSeleccione una opción del menú.",
        reply_markup=markup, parse_mode="Markdown"
    )

@bot.message_handler(content_types=['text', 'photo', 'document'])
def manejar_mensajes(message):
    user_id = message.from_user.id

    # ── Flujo Herramientas ──
    if user_id in estados_herramientas:
        paso = estados_herramientas[user_id].get("paso")
        if paso == "esperando_foto_ocr":
            if message.content_type == "photo":
                if procesar_foto_ocr(bot, message, client): return
        if paso == "archivo_subir":
            if paso_archivo_subir(bot, message, firebase_db): return

    # ── Flujo Talentos ──
    if user_id in estados_talentos:
        paso = estados_talentos[user_id].get("paso")
        if paso == "foto"     and paso_foto(bot, message):     return
        if paso == "nombre"   and message.content_type=="text" and paso_nombre(bot, message):   return
        if paso == "username" and message.content_type=="text" and paso_username(bot, message): return
        if paso == "bio"      and message.content_type=="text" and paso_bio(bot, message):      return
        if paso == "web"      and message.content_type=="text" and paso_web(bot, message):      return

    if message.content_type in ["photo", "document"]:
        return

    txt = message.text

    # Limpiar estados activos si el usuario navega al menú principal
    BOTONES_MENU = {
        "📚 Materias horarios", "🗓️ Calendario", "📍 Sedes",
        "🖥️ Gestión Alumnos", "🤖 Bot TUCE", "🌟 Talentos TUCE", "🛠️ Herramientas",
        "📰 Novedades UNPAZ", "📅 Mi Horario",
    }
    if txt in BOTONES_MENU:
        estados_herramientas.pop(user_id, None)
        estados_talentos.pop(user_id, None)

    if txt == "📚 Materias horarios":
        materias = sorted(list(set([f[0] for f in LISTA_HORARIOS])))
        markup = types.InlineKeyboardMarkup(row_width=1)
        for mat in materias:
            markup.add(types.InlineKeyboardButton(mat, callback_data=f"hor_{mat}"))
        bot.send_message(message.chat.id, "📚 *Seleccione asignatura:*", reply_markup=markup, parse_mode="Markdown")

    elif txt == "🗓️ Calendario":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 Ingresantes",   callback_data="cal_Ingresantes"),
            types.InlineKeyboardButton("1️⃣ 1er Semestre", callback_data="cal_Primer Semestre"),
            types.InlineKeyboardButton("2️⃣ 2do Semestre", callback_data="cal_Segundo Semestre"),
            types.InlineKeyboardButton("☀️ Verano 2027",  callback_data="cal_Verano 2027"),
        )
        bot.send_message(message.chat.id, "🗓️ *Calendario Académico:*", reply_markup=markup, parse_mode="Markdown")

    elif txt == "🤖 Bot TUCE":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⚖️ Equivalencias",      callback_data="bot_equivalencias"),
            types.InlineKeyboardButton("🚌 Boleto Estudiantil", callback_data="bot_boleto"),
            types.InlineKeyboardButton("📄 Certificados",       callback_data="bot_certificados"),
            types.InlineKeyboardButton("✍️ Inscripción",        callback_data="bot_inscripcion"),
            types.InlineKeyboardButton("💬 Consultar a la IA",  callback_data="ia_modo"),
        )
        bot.send_message(message.chat.id, "🤖 *Centro de Asistencia Bot TUCE*", reply_markup=markup, parse_mode="Markdown")

    elif txt == "📍 Sedes":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📍 Sede Alem",    callback_data="sede_alem"),
            types.InlineKeyboardButton("📍 Sede Arregui", callback_data="sede_arregui"),
        )
        bot.send_message(message.chat.id, "🏢 *Sedes:*", reply_markup=markup, parse_mode="Markdown")

    elif txt == "🖥️ Gestión Alumnos":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎓 Campus Virtual",            url="https://campusvirtual.unpaz.edu.ar/"),
            types.InlineKeyboardButton("🖥️ SIU Guaraní",              url="https://estudiantes.unpaz.edu.ar/autogestion/"),
            types.InlineKeyboardButton("📄 Plan de Estudios",          callback_data="plan_info"),
            types.InlineKeyboardButton("📅 Mi Horario Personal",       callback_data="hp_ver"),
            types.InlineKeyboardButton("📩 Contactos y Mesa de Ayuda", callback_data="ver_contactos"),
        )
        bot.send_message(message.chat.id, "🚀 *Gestión Alumnos:*", reply_markup=markup, parse_mode="Markdown")

    elif txt == "🌟 Talentos TUCE":
        menu_talentos(bot, message)

    elif txt == "🛠️ Herramientas":
        menu_herramientas(bot, message)

    elif txt == "📰 Novedades UNPAZ":
        bot.send_chat_action(message.chat.id, "typing")
        try:
            texto = obtener_novedades_texto(firebase_db)
        except Exception:
            texto = "⚠️ No se pudo cargar las novedades. Intentá más tarde."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Ver en unpaz.edu.ar", url="https://www.unpaz.edu.ar/noticias"))
        bot.send_message(message.chat.id, texto, reply_markup=markup, parse_mode="Markdown")

    elif txt == "📅 Mi Horario":
        menu_horario(bot, message, firebase_db, editar=False)

    else:
        FIJAS = {
            "hola":"👋 ¡Hola! Usá el menú para navegar.",
            "buenas":"👋 ¡Buenas! Usá el menú.",
            "gracias":"🙌 ¡De nada!","ok":"👍 ¡Perfecto!",
            "campus":"🎓 https://campusvirtual.unpaz.edu.ar/",
            "siu":"🖥️ https://estudiantes.unpaz.edu.ar/autogestion/",
            "guarani":"🖥️ https://estudiantes.unpaz.edu.ar/autogestion/",
            "instagram":"📸 Instagram TUCE: @tuce_unpaz","youtube":"▶️ @TUCEUNPAZ",
            "discord":"🎮 https://discord.com/invite/Sa28wwk8b3",
            "whatsapp":"💬 https://chat.whatsapp.com/JElcFd4U08QBKsL1J1YM8u",
            "becas":"🎓 https://unpaz.edu.ar/bienestar/becas",
            "pasantias":"💼 https://unpaz.edu.ar/pasantias",
            "equivalencias":"⚖️ Trámite 01/04 al 10/04/2026: https://unpaz.edu.ar/formularioequivalencias",
            "boleto":"🚌 Gestionalo vía SIU Guaraní si sos alumno regular.",
            "certificados":"📄 Emisión digital vía SIU Guaraní.",
        }
        t = txt.lower().strip()
        if t in FIJAS:
            bot.reply_to(message, FIJAS[t])
        else:
            bot.send_chat_action(message.chat.id, 'typing')
            bot.reply_to(message, responder_ia(txt))


@bot.callback_query_handler(func=lambda call: True)
def callback_global(call):
    d = call.data

    # ── Herramientas ──
    if d == "her_menu":
        estados_herramientas.pop(call.from_user.id, None)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📂 Banco de material", callback_data="her_banco"),
            types.InlineKeyboardButton("📸 Foto → Word / PDF", callback_data="her_ocr"),
        )
        bot.edit_message_text(
            "🛠️ *Herramientas Estudiantes*\n\n¿Qué querés usar?",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )
        return

    if d == "her_menu_msg":
        estados_herramientas.pop(call.from_user.id, None)
        bot.answer_callback_query(call.id)
        menu_herramientas(bot, call.message)
        return

    if d == "her_banco":
        estados_herramientas.pop(call.from_user.id, None)
        menu_banco(bot, call)
        return

    if d == "her_ocr":
        menu_ocr(bot, call)
        return

    if d == "her_subir":
        iniciar_subida(bot, call)
        return

    if d == "her_buscar":
        mostrar_buscar_materia(bot, call)
        return

    if d.startswith("her_mat_"):
        paso_materia_subir(bot, call, d.replace("her_mat_", ""))
        return

    if d.startswith("her_tipo_"):
        paso_tipo_subir(bot, call, d.replace("her_tipo_", ""))
        return

    if d.startswith("her_ver_"):
        mostrar_material_materia(bot, call, d.replace("her_ver_", ""), firebase_db)
        return

    if d.startswith("her_dl_"):
        descargar_archivo(bot, call, d.replace("her_dl_", ""), firebase_db)
        return

    if d == "her_fmt_word":
        generar_documento(bot, call, "word", client)
        return

    if d == "her_fmt_pdf":
        generar_documento(bot, call, "pdf", client)
        return

    if d == "her_fmt_ambos":
        generar_documento(bot, call, "ambos", client)
        return

    # ── Talentos ──
    if d == "tal_registrar":
        bot.answer_callback_query(call.id)
        class FakeMsg:
            def __init__(self,c): self.chat=c.message.chat; self.from_user=c.from_user
        iniciar_registro(bot, FakeMsg(call))
        return

    if d == "tal_menu_principal":
        bot.answer_callback_query(call.id)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        menu_talentos(bot, call.message)
        return

    if d.startswith("tal_cat_"):
        paso_categoria(bot, call, d.replace("tal_cat_",""))
        return

    if d.startswith("tal_anio_"):
        paso_anio(bot, call, d.replace("tal_anio_",""))
        return

    if d == "tal_explorar":
        mostrar_menu_explorar(bot, call, edit=True)
        return

    if d.startswith("tal_ver_"):
        mostrar_talentos_por_categoria(bot, call, d.replace("tal_ver_",""))
        return

    if d.startswith("tal_perfil_"):
        mostrar_perfil_individual(bot, call, d.replace("tal_perfil_",""))
        return

    if d == "tal_destacados":
        mostrar_destacados(bot, call)
        return

    if d.startswith("tal_votar_"):
        partes = d.split("_")
        registrar_voto(bot, call, partes[2], int(partes[3]))
        return

    if d == "tal_noop":
        bot.answer_callback_query(call.id)
        return

    if d.startswith("tal_editar_"):
        iniciar_edicion(bot, call, d.replace("tal_editar_",""))
        return

    if d.startswith("tal_eliminar_"):
        confirmar_eliminacion(bot, call, d.replace("tal_eliminar_",""))
        return

    if d.startswith("tal_confirm_del_"):
        ejecutar_eliminacion(bot, call, d.replace("tal_confirm_del_",""))
        return

    # ── Horario Personal ──
    if d == "hp_ver":
        menu_horario(bot, call, firebase_db, editar=True)
        return

    if d == "hp_cfg":
        iniciar_config(bot, call, firebase_db)
        return

    if d == "hp_del_confirm":
        confirmar_borrar(bot, call)
        return

    if d == "hp_del_ok":
        ejecutar_borrar(bot, call, firebase_db)
        return

    if d == "hp_fin":
        finalizar_config(bot, call, firebase_db)
        return

    if d == "hp_cancel":
        cancelar_config(bot, call, firebase_db)
        return

    if d.startswith("hp_com_"):
        partes = d.split("_")  # ["hp", "com", mat_idx, com_idx]
        seleccionar_comision(bot, call, int(partes[2]), int(partes[3]), firebase_db)
        return

    if d.startswith("hp_skip_"):
        saltear_materia(bot, call, int(d.replace("hp_skip_", "")))
        return

    # ── Calendario ──
    if d == "cal_volver":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 Ingresantes",   callback_data="cal_Ingresantes"),
            types.InlineKeyboardButton("1️⃣ 1er Semestre", callback_data="cal_Primer Semestre"),
            types.InlineKeyboardButton("2️⃣ 2do Semestre", callback_data="cal_Segundo Semestre"),
            types.InlineKeyboardButton("☀️ Verano 2027",  callback_data="cal_Verano 2027"),
        )
        bot.edit_message_text(
            "🗓️ *Calendario Académico:*",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )

    elif d.startswith("cal_"):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver al Calendario", callback_data="cal_volver"))
        bot.edit_message_text(
            DATA_CALENDARIO[d.replace("cal_","")],
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )

    elif d == "bot_volver":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⚖️ Equivalencias",      callback_data="bot_equivalencias"),
            types.InlineKeyboardButton("🚌 Boleto Estudiantil", callback_data="bot_boleto"),
            types.InlineKeyboardButton("📄 Certificados",       callback_data="bot_certificados"),
            types.InlineKeyboardButton("✍️ Inscripción",        callback_data="bot_inscripcion"),
            types.InlineKeyboardButton("💬 Consultar a la IA",  callback_data="ia_modo"),
        )
        bot.edit_message_text(
            "🤖 *Centro de Asistencia Bot TUCE*",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )

    elif d.startswith("bot_"):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="bot_volver"))
        bot.edit_message_text(
            DATA_BOT_INFO[d],
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )


    elif d == "ver_contactos":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🤝 Acceso y Apoyo",        callback_data="con_acceso"),
            types.InlineKeyboardButton("📝 Consultas CIU",         callback_data="con_ciu"),
            types.InlineKeyboardButton("👤 Consultas Estudiantes", callback_data="con_est"),
            types.InlineKeyboardButton("💻 Soporte SIU Guaraní",   callback_data="con_siu"),
            types.InlineKeyboardButton("🌐 UNPAZ Virtual",         callback_data="con_virt"),
            types.InlineKeyboardButton("💜 ORVIG (Género)",        callback_data="con_orvig"),
        )
        bot.edit_message_text("📩 *Seleccione el área de consulta:*",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="Markdown")

    elif d.startswith("con_"):
        contactos = {
            "acceso":"🤝 *Acceso y Apoyo:* 📩 accesoapoyo@unpaz.edu.ar",
            "ciu":"📝 *Consultas CIU:* 📩 ciu@unpaz.edu.ar",
            "est":"👤 *Consultas Estudiantes:* 📩 consultasestudiantes@unpaz.edu.ar",
            "siu":"💻 *Soporte SIU Guaraní:* 📩 soporteinscripciones@unpaz.edu.ar",
            "virt":"🌐 *UNPAZ Virtual:* 📩 formacionvirtual@unpaz.edu.ar",
            "orvig":"💜 *ORVIG:* 📩 orvig@unpaz.edu.ar",
        }
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="ver_contactos"))
        bot.edit_message_text(contactos[d.replace("con_","")],
                              call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="Markdown")

    elif d == "ia_modo":
        bot.send_message(call.message.chat.id, "💬 *Modo IA activado.* Preguntá lo que necesites:", parse_mode="Markdown")

    elif d == "plan_info":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("1º Año", callback_data="anio_Primer Año"),
            types.InlineKeyboardButton("2º Año", callback_data="anio_Segundo Año"),
            types.InlineKeyboardButton("3º Año", callback_data="anio_Tercer Año"),
        )
        bot.edit_message_text("📄 *Plan de Estudios*",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="Markdown")

    elif d.startswith("anio_"):
        anio = d.replace("anio_","")
        lineas = []
        for materia in DATA_PLAN[anio]:
            nombre = materia.replace(" (4hs)", "")
            cor = correlativas_de(nombre)
            if cor and "Sin correlativas" not in cor:
                lineas.append(f"• {materia}\n  _{cor}_")
            else:
                lineas.append(f"• {materia}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver al Plan", callback_data="plan_info"))
        bot.edit_message_text(
            f"📚 *Asignaturas {anio}:*\n\n" + "\n".join(lineas),
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )

    elif d == "ver_lista_materias":
        materias = sorted(list(set([f[0] for f in LISTA_HORARIOS])))
        markup = types.InlineKeyboardMarkup(row_width=1)
        for mat in materias:
            markup.add(types.InlineKeyboardButton(mat, callback_data=f"hor_{mat}"))
        bot.edit_message_text(
            "📚 *Seleccione asignatura:*",
            call.message.chat.id, call.message.message_id,
            reply_markup=markup, parse_mode="Markdown"
        )

    elif d.startswith("hor_"):
        mat_sel = d.replace("hor_","")
        cor = correlativas_de(mat_sel)
        res = f"📍 *{mat_sel}*\n"
        if cor:
            res += f"_{cor}_\n"
        res += "\n"
        for f in LISTA_HORARIOS:
            if f[0] == mat_sel:
                res += f"👥 *Com {f[1]}* | 🗓️ {f[2]} | ⏰ {f[3][:-3]} a {f[4][:-3]} hs.\n"
                res += f"🏢 *Aula:* {f[8]}\n💻 *Mod:* {f[5]}\n"
                res += "----------------------------\n"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver a Materias", callback_data="ver_lista_materias"))
        bot.edit_message_text(res, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif d == "sede_alem":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📍 *Sede Alem*\nLeandro N. Alem 4731, José C. Paz, Buenos Aires\n"
            "https://maps.google.com/?q=Leandro+N.+Alem+4731,+Jose+C.+Paz,+Buenos+Aires",
            parse_mode="Markdown"
        )
    elif d == "sede_arregui":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📍 *Sede Arregui*\nAv. Héctor Arregui 501, José C. Paz, Buenos Aires\n"
            "https://maps.google.com/?q=Av.+Hector+Arregui+501,+Jose+C.+Paz,+Buenos+Aires",
            parse_mode="Markdown"
        )


if __name__ == "__main__":
    # Esperar que el deploy anterior termine antes de empezar polling
    print("⏳ Esperando 20s para que el deploy anterior termine...")
    time.sleep(20)
    try:
        bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook limpiado")
    except Exception as e:
        print(f"⚠️ No se pudo limpiar webhook: {e}")
    while True:
        try:
            print("🚀 Bot TUCE — Talentos + Herramientas + IA")
            bot.infinity_polling(timeout=40, allowed_updates=[])
        except Exception as e:
            err = str(e)
            if "409" in err:
                print(f"⚠️ 409 Conflicto — esperando 30s antes de reintentar...")
                time.sleep(30)
            else:
                print(f"Error: {e}")
                time.sleep(15)