import os
from dotenv import load_dotenv
import telebot
from telebot import types
import time
import requests
from openai import OpenAI
from info_unpaz import DATOS_TECNICATURA
from materias_db import LISTA_HORARIOS
from scraper import scrape_todo, obtener_contexto_ia, obtener_novedades_texto
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

# ─── Estados conversacionales WhatsApp ───────────────────────────────────────
# Estructura: { "549XXXXXXXX@s.whatsapp.net": {"modo": "normal"|"horarios"|"ia"} }
estados_wa = {}

# Menú principal en texto plano (WhatsApp no tiene botones inline)
MENU_WA = (
    "👋 *Hola! Soy el Bot TUCE* 🎓\n"
    "Tu asistente de la Tecnicatura en Comercio Electrónico - UNPAZ\n\n"
    "Escribí el número de lo que necesitás:\n\n"
    "1️⃣ 📚 Horarios de materias\n"
    "2️⃣ 🗓️ Calendario académico\n"
    "3️⃣ 📍 Sedes UNPAZ\n"
    "4️⃣ 📄 Plan de estudios\n"
    "5️⃣ 🔗 Correlativas de una materia\n"
    "6️⃣ 💬 Consultar a la IA\n"
    "7️⃣ 📰 Novedades UNPAZ\n"
    "8️⃣ 🖥️ Gestión Alumnos\n"
    "9️⃣ 📩 Contactos y Mesa de Ayuda\n\n"
    "_Escribí *menu* en cualquier momento para volver acá._"
)

def procesar_mensaje_wa(from_id: str, text: str) -> str:
    """
    Procesa un mensaje de WhatsApp y devuelve la respuesta en texto plano.
    Maneja el estado conversacional del usuario.
    """
    texto = text.strip().lower()
    estado = estados_wa.get(from_id, {})

    # Comandos globales que siempre funcionan
    if texto in ("menu", "inicio", "start", "hola", "buenas", "hey", "0"):
        estados_wa.pop(from_id, None)
        return MENU_WA

    # ── Flujo: esperando nombre de materia para horarios ──────────────────────
    if estado.get("modo") == "horarios":
        estados_wa.pop(from_id, None)
        # Buscar coincidencia parcial en LISTA_HORARIOS
        resultados = [f for f in LISTA_HORARIOS if texto in f[0].lower()]
        if not resultados:
            # Intentar con cualquier palabra
            for palabra in texto.split():
                resultados = [f for f in LISTA_HORARIOS if palabra in f[0].lower()]
                if resultados:
                    break
        if not resultados:
            return (
                f"❌ No encontré horarios para *{text}*.\n\n"
                "Escribí *horarios* para ver la lista completa, o *menu* para volver."
            )
        materia_encontrada = resultados[0][0]
        cor = correlativas_de(materia_encontrada)
        resp = f"📍 *{materia_encontrada}*\n"
        if cor:
            resp += f"_{cor}_\n"
        resp += "\n"
        for f in LISTA_HORARIOS:
            if f[0] == materia_encontrada:
                resp += f"👥 Com {f[1]} | 🗓 {f[2]} | ⏰ {f[3][:-3]} a {f[4][:-3]} hs\n"
                resp += f"🏢 Aula: {f[8]} | 💻 {f[5]}\n"
                resp += "──────────────\n"
        resp += "\n_Escribí *menu* para volver._"
        return resp

    # ── Flujo: esperando nombre de materia para correlativas ──────────────────
    if estado.get("modo") == "correlativas":
        estados_wa.pop(from_id, None)
        # Buscar por nombre parcial en CORRELATIVAS
        encontrada = None
        for info in CORRELATIVAS.values():
            if texto in info["nombre"].lower():
                encontrada = info
                break
        if not encontrada:
            return (
                f"❌ No encontré *{text}* en el plan.\n"
                "Revisá el nombre y probá de nuevo, o escribí *menu*."
            )
        nombre = encontrada["nombre"]
        if not encontrada["necesita"]:
            return f"✅ *{nombre}*\n\nNo tiene correlativas. ¡Podés cursarla cuando quieras!"
        previas = "\n".join(
            f"  • {CORRELATIVAS[c]['nombre']}" for c in encontrada["necesita"]
        )
        return (
            f"🔗 *{nombre}*\n\n"
            f"Para cursarla necesitás tener aprobada/s:\n{previas}\n\n"
            "_Escribí *menu* para volver._"
        )

    # ── Flujo: modo IA activo ─────────────────────────────────────────────────
    if estado.get("modo") == "ia":
        return responder_ia(text) + "\n\n_Escribí *menu* para volver al menú._"

    # ── Opciones del menú principal ───────────────────────────────────────────
    if texto in ("1", "horarios"):
        materias = sorted(list(set(f[0] for f in LISTA_HORARIOS)))
        lista = "\n".join(f"  • {m}" for m in materias)
        estados_wa[from_id] = {"modo": "horarios"}
        return (
            f"📚 *Horarios de materias*\n\n"
            f"Materias disponibles:\n{lista}\n\n"
            "✏️ *Escribí el nombre (o parte) de la materia que querés ver:*"
        )

    if texto in ("2", "calendario"):
        resp = "🗓 *Calendario Académico 2026*\n\n"
        for k, v in DATA_CALENDARIO.items():
            resp += v.replace("*", "") + "\n\n"
        resp += "_Escribí *menu* para volver._"
        return resp

    if texto in ("3", "sedes"):
        return (
            "📍 *Sedes UNPAZ*\n\n"
            "🏢 *Sede Alem*\n"
            "Av. Alem 4731, José C. Paz\n"
            "📌 google.com/maps?q=-34.5164,-58.7615\n\n"
            "🏢 *Sede Arregui*\n"
            "Arregui 2080, José C. Paz\n"
            "📌 google.com/maps?q=-34.5208,-58.7758\n\n"
            "_Escribí *menu* para volver._"
        )

    if texto in ("4", "plan"):
        resp = "📄 *Plan de Estudios TUCE*\n\n"
        for anio, materias in DATA_PLAN.items():
            resp += f"*{anio}:*\n"
            for m in materias:
                resp += f"  • {m}\n"
            resp += "\n"
        resp += "_Escribí *menu* para volver._"
        return resp

    if texto in ("5", "correlativas"):
        estados_wa[from_id] = {"modo": "correlativas"}
        return (
            "🔗 *Correlativas*\n\n"
            "Escribí el nombre (o parte) de la materia para ver qué necesitás:\n\n"
            "_Ejemplo: 'desarrollo web', 'marketing', 'inglés'_"
        )

    if texto in ("6", "ia", "consultar"):
        estados_wa[from_id] = {"modo": "ia"}
        return (
            "💬 *Modo IA activado*\n\n"
            "Preguntame lo que necesites sobre la carrera, trámites, becas o UNPAZ.\n"
            "_Escribí *menu* cuando quieras volver al menú._"
        )

    if texto in ("7", "novedades"):
        try:
            return obtener_novedades_texto(firebase_db) + "\n\n_Escribí *menu* para volver._"
        except Exception:
            return "⚠️ No se pudo cargar las novedades. Intentá más tarde.\n\nVisitá: unpaz.edu.ar"

    if texto in ("8", "gestion", "gestión"):
        return (
            "🖥️ *Gestión Alumnos*\n\n"
            "🎓 *Campus Virtual:*\n"
            "https://campusvirtual.unpaz.edu.ar/\n\n"
            "🖥️ *SIU Guaraní (inscripciones, certificados, boleto):*\n"
            "https://estudiantes.unpaz.edu.ar/autogestion/\n\n"
            "📄 *Equivalencias:*\n"
            "https://unpaz.edu.ar/formularioequivalencias\n\n"
            "🌐 *Sitio oficial UNPAZ:*\n"
            "https://unpaz.edu.ar\n\n"
            "_Escribí *menu* para volver._"
        )

    if texto in ("9", "contactos", "ayuda", "mesa"):
        return (
            "📩 *Contactos y Mesa de Ayuda*\n\n"
            "🤝 Acceso y Apoyo:\n  accesoapoyo@unpaz.edu.ar\n\n"
            "📝 Consultas CIU:\n  ciu@unpaz.edu.ar\n\n"
            "👤 Consultas Estudiantes:\n  consultasestudiantes@unpaz.edu.ar\n\n"
            "💻 Soporte SIU Guaraní:\n  soporteinscripciones@unpaz.edu.ar\n\n"
            "🌐 UNPAZ Virtual:\n  formacionvirtual@unpaz.edu.ar\n\n"
            "💜 ORVIG (Género):\n  orvig@unpaz.edu.ar\n\n"
            "_Escribí *menu* para volver._"
        )

    # ── Respuesta IA por defecto ──────────────────────────────────────────────
    return responder_ia(text) + "\n\n_Escribí *menu* para ver las opciones._"


# ─── Webhook Flask para el bridge de WhatsApp ────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/wa", methods=["POST"])
def webhook_wa():
    data     = request.get_json(silent=True) or {}
    from_id  = data.get("from", "")
    message  = data.get("message", "").strip()
    if not from_id or not message:
        return jsonify({"response": ""}), 400
    respuesta = procesar_mensaje_wa(from_id, message)
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
scheduler.start()
# Primer scraping en background al iniciar (no bloquea el arranque del bot)
threading.Thread(target=_iniciar_scraper, daemon=True).start()

DATA_CALENDARIO = {
    "Ingresantes":      "📝 *INFO INGRESANTES:*\n🔹 Inscripción CIU: 06/11 al 28/11/2025\n🔹 Desarrollo CIU: 02/02 al 28/02/2026",
    "Primer Semestre":  "1️⃣ *1er SEMESTRE 2026:*\n🔹 Inscripción: 18/02 y 19/02\n🔹 Inicio clases: 09/03",
    "Segundo Semestre": "2️⃣ *2do SEMESTRE 2026:*\n🔹 Inscripción: 22/07 y 23/07\n🔹 Inicio clases: 10/08",
    "Verano 2027":      "☀️ *VERANO 2027:*\n🔹 Cursada: Febrero 2027"
}
DATA_PLAN = {
    "Primer Año": [
        "Tecnología y Sociedad (4hs)",
        "Inglés I (4hs)",
        "Principios de Economía (4hs)",
        "Comunicación Institucional (4hs)",
        "Internet: Infraestructura y redes (4hs)",
        "Semántica de las interfaces (4hs)",
        "Introducción al comercio electrónico (4hs)",
        "Usabilidad, seguridad y Estándares Web (4hs)",
        "Inglés II (4hs)",
    ],
    "Segundo Año": [
        "Investigación de mercado (4hs)",
        "Marco legal de negocios electrónicos (4hs)",
        "Gestión del conocimiento (4hs)",
        "Desarrollo Web (4hs)",
        "Formulación, incubación y evaluación de proyectos (4hs)",
        "Métricas del mundo digital (4hs)",
        "Desarrollo de Productos y Servicios (4hs)",
        "Taller de Comunicación (4hs)",
        "Desarrollos para Dispositivos móviles (4hs)",
    ],
    "Tercer Año": [
        "Calidad y Servicio al Cliente (4hs)",
        "Marketing digital (4hs)",
        "Taller de Práctica Integradora (4hs)",
        "Competencias emprendedoras (4hs)",
        "Gestión de Proyectos (4hs)",
    ],
}

# Correlativas según el plan de estudios oficial (PDF UNPAZ)
CORRELATIVAS = {
    "01": {"nombre": "Tecnología y Sociedad",                              "necesita": []},
    "02": {"nombre": "Inglés I",                                           "necesita": []},
    "03": {"nombre": "Principios de Economía",                             "necesita": []},
    "04": {"nombre": "Comunicación Institucional",                         "necesita": []},
    "05": {"nombre": "Internet: Infraestructura y redes",                  "necesita": []},
    "06": {"nombre": "Semántica de las interfaces",                        "necesita": []},
    "07": {"nombre": "Introducción al comercio electrónico",               "necesita": []},
    "08": {"nombre": "Usabilidad, seguridad y Estándares Web",             "necesita": ["05"]},
    "09": {"nombre": "Inglés II",                                          "necesita": ["02"]},
    "10": {"nombre": "Investigación de mercado",                           "necesita": ["03", "07"]},
    "11": {"nombre": "Marco legal de negocios electrónicos",               "necesita": ["07"]},
    "12": {"nombre": "Gestión del conocimiento",                           "necesita": ["01"]},
    "13": {"nombre": "Desarrollo Web",                                     "necesita": ["06", "08"]},
    "14": {"nombre": "Formulación, incubación y evaluación de proyectos",  "necesita": ["03"]},
    "15": {"nombre": "Métricas del mundo digital",                         "necesita": []},
    "16": {"nombre": "Desarrollo de Productos y Servicios",                "necesita": ["10"]},
    "17": {"nombre": "Taller de Comunicación",                             "necesita": ["04"]},
    "18": {"nombre": "Desarrollos para Dispositivos móviles",              "necesita": ["13"]},
    "19": {"nombre": "Calidad y Servicio al Cliente",                      "necesita": ["16"]},
    "20": {"nombre": "Marketing digital",                                  "necesita": ["17"]},
    "21": {"nombre": "Taller de Práctica Integradora",                     "necesita": ["16", "17"]},
    "22": {"nombre": "Competencias emprendedoras",                         "necesita": ["14"]},
    "23": {"nombre": "Gestión de Proyectos",                               "necesita": ["07", "14"]},
}

def correlativas_de(nombre_materia: str) -> str:
    """Devuelve texto con las correlativas de una materia, buscando por nombre."""
    nombre_lower = nombre_materia.lower()
    for info in CORRELATIVAS.values():
        if info["nombre"].lower() == nombre_lower:
            if not info["necesita"]:
                return "✅ Sin correlativas"
            previas = " + ".join(CORRELATIVAS[c]["nombre"] for c in info["necesita"])
            return f"🔗 Requiere: {previas}"
    return ""
DATA_BOT_INFO = {
    "bot_equivalencias": "⚖️ *Equivalencias:* Trámite formal del 01/04 al 10/04/2026.",
    "bot_boleto":        "🚌 *Boleto Estudiantil:* Gestión vía SIU Guaraní para alumnos regulares.",
    "bot_certificados":  "📄 *Certificaciones:* Emisión digital de certificados vía SIU Guaraní.",
    "bot_inscripcion":   "✍️ *Inscripción:* Únicamente por SIU Guaraní en fechas publicadas."
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

def responder_ia(pregunta):
    ctx = f"{DATOS_TECNICATURA}\nCALENDARIO: {DATA_CALENDARIO}\nPLAN: {DATA_PLAN}\n"

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
        "Respondés SOLO preguntas relacionadas con la UNPAZ, la carrera TUCE, materias, trámites, becas, fechas y vida universitaria. "
        "Si te preguntan algo que no tiene que ver con la UNPAZ o TUCE, decís amablemente que solo podés ayudar con temas de la carrera. "
        "Si te preguntan quién te creó, decís que fuiste desarrollado por Bytes Creativos. "
        "No decís que sos bot oficial. Respondés en español, claro y amigable. "
        "Cuando tenés info actualizada de la web de la UNPAZ, la usás para responder con precisión. "
        "Si no sabés algo con certeza, recomendás unpaz.edu.ar o la mesa de ayuda. "
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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        "📚 Materias horarios", "🗓️ Calendario",
        "📍 Sedes",             "🖥️ Gestión Alumnos",
        "🤖 Bot TUCE",          "🌟 Talentos TUCE",
        "🛠️ Herramientas",      "📰 Novedades UNPAZ",
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
        bot.send_location(call.message.chat.id, -34.5164, -58.7615)
    elif d == "sede_arregui":
        bot.send_location(call.message.chat.id, -34.5208, -58.7758)


if __name__ == "__main__":
    while True:
        try:
            print("🚀 Bot TUCE — Talentos + Herramientas + IA")
            bot.infinity_polling(timeout=40)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)