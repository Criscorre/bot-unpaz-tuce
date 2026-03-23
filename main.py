import os
from dotenv import load_dotenv
import telebot
from telebot import types
import time
import requests
from openai import OpenAI
from info_unpaz import DATOS_TECNICATURA
from materias_db import LISTA_HORARIOS
from talentos import (
    menu_talentos,
    iniciar_registro,
    mostrar_menu_explorar,
    mostrar_talentos_por_categoria,
    mostrar_perfil_individual,
    mostrar_destacados,
    registrar_voto,
    iniciar_edicion,
    confirmar_eliminacion,
    ejecutar_eliminacion,
    paso_categoria,
    paso_foto,
    paso_nombre,
    paso_username,
    paso_bio,
    paso_anio,
    paso_web,
    estados_talentos,
)

import http.server
import socketserver
import threading

def run_health_server():
    PORT = 8000
    Handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🌍 Servidor de salud activo en puerto {PORT}")
        httpd.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

base_dir   = os.path.dirname(__file__)
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
    print("✅ Bot TUCE iniciando — Talentos + Rating + IA mejorada")

bot    = telebot.TeleBot(TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

DATA_CALENDARIO = {
    "Ingresantes":      "📝 *INFO INGRESANTES:*\n🔹 Inscripción CIU: 06/11 al 28/11/2025\n🔹 Desarrollo CIU: 02/02 al 28/02/2026",
    "Primer Semestre":  "1️⃣ *1er SEMESTRE 2026:*\n🔹 Inscripción: 18/02 y 19/02\n🔹 Inicio clases: 09/03",
    "Segundo Semestre": "2️⃣ *2do SEMESTRE 2026:*\n🔹 Inscripción: 22/07 y 23/07\n🔹 Inicio clases: 10/08",
    "Verano 2027":      "☀️ *VERANO 2027:*\n🔹 Cursada: Febrero 2027"
}
DATA_PLAN = {
    "Primer Año":  ["Tecnología y Sociedad (4hs)", "Inglés I (4hs)", "Principios de Economía (4hs)", "Comunicación Institucional (4hs)", "Internet: Infraestructura y redes (4hs)", "Semántica de las interfaces (4hs)", "Introducción al comercio electrónico (4hs)", "Usabilidad, seguridad y Estándares Web (4hs)", "Inglés II (4hs)"],
    "Segundo Año": ["Investigación de mercado (4hs)", "Marco legal (4hs)", "Gestión del conocimiento (4hs)", "Desarrollo Web (4hs)", "Proyectos (4hs)", "Métricas (4hs)", "Productos y Servicios (4hs)", "Taller de Comunicación (4hs)", "Dispositivos móviles (4hs)"],
    "Tercer Año":  ["Calidad y Servicio al Cliente (4hs)", "Marketing digital (4hs)", "Taller de Práctica Integradora (4hs)", "Competencias emprendedoras (4hs)", "Gestión de Proyectos (4hs)"]
}
DATA_BOT_INFO = {
    "bot_equivalencias": "⚖️ *Equivalencias:* Trámite formal del 01/04 al 10/04/2026.",
    "bot_boleto":         "🚌 *Boleto Estudiantil:* Gestión vía SIU Guaraní para alumnos regulares.",
    "bot_certificados":  "📄 *Certificaciones:* Emisión digital de certificados vía SIU Guaraní.",
    "bot_inscripcion":    "✍️ *Inscripción:* Únicamente por SIU Guaraní en fechas publicadas."
}
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
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return ""
        t = r.text
        t = re.sub(r'<style[^>]*>.*?</style>', '', t, flags=re.DOTALL)
        t = re.sub(r'<script[^>]*>.*?</script>', '', t, flags=re.DOTALL)
        t = re.sub(r'<[^>]+>', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()[:3000]
    except:
        return ""

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
            requests.post(FORM_USUARIOS_URL, timeout=5, headers={"User-Agent": "Mozilla/5.0"}, data={
                FORM_USUARIOS_ID:       str(user.id),
                FORM_USUARIOS_NOMBRE:   user.first_name or "",
                FORM_USUARIOS_USERNAME: f"@{user.username}" if user.username else "Sin usuario",
                FORM_USUARIOS_FECHA:    time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except:
            pass

def responder_ia(pregunta):
    ctx = f"{DATOS_TECNICATURA}\nCALENDARIO: {DATA_CALENDARIO}\nPLAN: {DATA_PLAN}\n"
    ctx_web = ""
    url = detectar_url_relevante(pregunta)
    if url:
        try:
            info = obtener_info_web(url)
            if info:
                ctx_web = f"\n\nINFO WEB {url}:\n{info}"
        except:
            pass
    sistema = (
        "Sos el Asistente Virtual de la Comunidad TUCE - UNPAZ. "
        "Respondés preguntas de estudiantes de la Tecnicatura en Comercio Electrónico. "
        "Si te preguntan quién te creó, decís que fuiste desarrollado por Bytes Creativos. "
        "No decís que sos bot oficial. Respondés en español, claro y amigable. "
        "Si no sabés, recomendás unpaz.edu.ar o la mesa de ayuda. "
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
        return "Servicio no disponible temporalmente. Por favor, consultá en unpaz.edu.ar"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    registrar_usuario(message.from_user)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Materias horarios","🗓️ Calendario","📍 Sedes","🖥️ Gestión Alumnos","🤖 Bot TUCE","🌟 Talentos TUCE")
    bot.send_message(message.chat.id,
                     "Bienvenido al *Bot de la Comunidad TUCE - UNPAZ*.\n\nSeleccione una opción del menú.",
                     reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(content_types=['text', 'photo'])
def manejar_mensajes(message):
    user_id = message.from_user.id

    # Flujo Talentos
    if user_id in estados_talentos:
        paso = estados_talentos[user_id].get("paso")
        if paso == "foto"     and paso_foto(bot, message):     return
        if paso == "nombre"   and message.content_type=="text" and paso_nombre(bot, message):   return
        if paso == "username" and message.content_type=="text" and paso_username(bot, message): return
        if paso == "bio"      and message.content_type=="text" and paso_bio(bot, message):      return
        if paso == "web"      and message.content_type=="text" and paso_web(bot, message):      return

    if message.content_type == "photo":
        return

    txt = message.text

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
            types.InlineKeyboardButton("🖥️ SIU Guaraní",               url="https://estudiantes.unpaz.edu.ar/autogestion/"),
            types.InlineKeyboardButton("📄 Plan de Estudios",          callback_data="plan_info"),
            types.InlineKeyboardButton("📩 Contactos y Mesa de Ayuda", callback_data="ver_contactos"),
        )
        bot.send_message(message.chat.id, "🚀 *Gestión Alumnos:*", reply_markup=markup, parse_mode="Markdown")

    elif txt == "🌟 Talentos TUCE":
        menu_talentos(bot, message)

    else:
        FIJAS = {
            "hola":"👋 ¡Hola! Usá el menú para navegar.","buenas":"👋 ¡Buenas! Usá el menú.",
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

    # ── Talentos registro ──
    if d == "tal_registrar":
        bot.answer_callback_query(call.id)
        class FakeMsg:
            def __init__(self,c): self.chat=c.message.chat; self.from_user=c.from_user
        iniciar_registro(bot, FakeMsg(call))
        return

    if d.startswith("tal_cat_"):
        paso_categoria(bot, call, d.replace("tal_cat_",""))
        return

    if d.startswith("tal_anio_"):
        paso_anio(bot, call, d.replace("tal_anio_",""))
        return

    # ── Talentos explorar ──
    if d == "tal_explorar":
        mostrar_menu_explorar(bot, call, edit=True)
        return

    if d.startswith("tal_ver_"):
        mostrar_talentos_por_categoria(bot, call, d.replace("tal_ver_",""))
        return

    if d.startswith("tal_perfil_"):
        mostrar_perfil_individual(bot, call, int(d.replace("tal_perfil_","")))
        return

    if d == "tal_destacados":
        mostrar_destacados(bot, call)
        return

    # ── Votar ──
    if d.startswith("tal_votar_"):
        partes = d.split("_")
        idx      = int(partes[2])
        estrellas = int(partes[3])
        registrar_voto(bot, call, idx, estrellas)
        return

    if d == "tal_noop":
        bot.answer_callback_query(call.id)
        return

    # ── Editar / Eliminar ──
    if d.startswith("tal_editar_"):
        iniciar_edicion(bot, call, int(d.replace("tal_editar_","")))
        return

    if d.startswith("tal_eliminar_"):
        confirmar_eliminacion(bot, call, int(d.replace("tal_eliminar_","")))
        return

    if d.startswith("tal_confirm_del_"):
        ejecutar_eliminacion(bot, call, int(d.replace("tal_confirm_del_","")))
        return

    # ── Calendario ──
    if d.startswith("cal_"):
        bot.edit_message_text(DATA_CALENDARIO[d.replace("cal_","")],
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif d.startswith("bot_"):
        bot.edit_message_text(DATA_BOT_INFO[d],
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")

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
        bot.edit_message_text(f"📚 *Asignaturas {anio}:*\n" + "\n".join(DATA_PLAN[anio]),
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif d.startswith("hor_"):
        mat_sel = d.replace("hor_","")
        res = f"📍 *Horarios: {mat_sel}*\n\n"
        for f in LISTA_HORARIOS:
            if f[0] == mat_sel:
                res += f"👥 *Com {f[1]}* | 🗓️ {f[2]} | ⏰ {f[3][:-3]} a {f[4][:-3]} hs.\n"
                res += f"🏢 *Aula:* {f[8]}\n💻 *Mod:* {f[5]}\n📅 *Inicio Presencial:* {f[6]}\n"
                if f[7] != "//": res += f"🌐 *Inicio Virtual:* {f[7]}\n"
                res += "----------------------------\n"
        bot.edit_message_text(res, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif d == "sede_alem":
        bot.send_location(call.message.chat.id, -34.5164, -58.7615)
    elif d == "sede_arregui":
        bot.send_location(call.message.chat.id, -34.5208, -58.7758)


if __name__ == "__main__":
    while True:
        try:
            print("🚀 Bot TUCE — Talentos + Rating + IA")
            bot.infinity_polling(timeout=40)
        except Exception as e:
            print(f"Error crítico en polling: {e}")
            time.sleep(10)