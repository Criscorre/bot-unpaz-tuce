import os
from dotenv import load_dotenv
import telebot
from telebot import types
import time
from openai import OpenAI
from info_unpaz import DATOS_TECNICATURA 
from materias_db import LISTA_HORARIOS # <--- Importamos la data separada

# 1. Cargar variables de entorno y Configuración de APIs
base_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(base_dir, '.env')
load_dotenv(dotenv_path)

TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not TOKEN or not OPENAI_API_KEY:
    print("❌ Error: No se encontraron las credenciales en el archivo .env")
    exit()
else:
    print(f"✅ Credenciales detectadas. Iniciando bot de la UNPAZ...")

bot = telebot.TeleBot(TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# 2. DATA INSTITUCIONAL
DATA_CALENDARIO = {
    "Ingresantes": "📝 **INFO INGRESANTES:**\n🔹 Inscripción CIU: 06/11 al 28/11/2025\n🔹 Desarrollo CIU: 02/02 al 28/02/2026",
    "Primer Semestre": "1️⃣ **1er SEMESTRE 2026:**\n🔹 Inscripción: 18/02 y 19/02\n🔹 Inicio clases: 09/03",
    "Segundo Semestre": "2️⃣ **2do SEMESTRE 2026:**\n🔹 Inscripción: 22/07 y 23/07\n🔹 Inicio clases: 10/08",
    "Verano 2027": "☀️ **VERANO 2027:**\n🔹 Cursada: Febrero 2027"
}

DATA_PLAN = {
    "Primer Año": ["Tecnología y Sociedad (4hs)", "Inglés I (4hs)", "Principios de Economía (4hs)", "Comunicación Institucional (4hs)", "Internet: Infraestructura y redes (4hs)", "Semántica de las interfaces (4hs)", "Introducción al comercio electrónico (4hs)", "Usabilidad, seguridad y Estándares Web (4hs)", "Inglés II (4hs)"],
    "Segundo Año": ["Investigación de mercado (4hs)", "Marco legal (4hs)", "Gestión del conocimiento (4hs)", "Desarrollo Web (4hs)", "Proyectos (4hs)", "Métricas (4hs)", "Productos y Servicios (4hs)", "Taller de Comunicación (4hs)", "Dispositivos móviles (4hs)"],
    "Tercer Año": ["Calidad y Servicio al Cliente (4hs)", "Marketing digital (4hs)", "Taller de Práctica Integradora (4hs)", "Competencias emprendedoras (4hs)", "Gestión de Proyectos (4hs)"]
}

DATA_BOT_INFO = {
    "bot_equivalencias": "⚖️ **Equivalencias:** Trámite formal del 01/04 al 10/04/2026.",
    "bot_boleto": "🚌 **Boleto Estudiantil:** Gestión vía SIU Guaraní para alumnos regulares.",
    "bot_certificados": "📄 **Certificaciones:** Emisión digital de certificados vía SIU Guaraní.",
    "bot_inscripcion": "✍️ **Inscripción:** Únicamente por SIU Guaraní en fechas publicadas."
}

# 3. Funciones de Soporte
def registrar_usuario(user):
    try:
        with open("usuarios.txt", "a", encoding="utf-8") as f:
            fecha = time.strftime("%Y-%m-%d %H:%M:%S")
            linea = f"{fecha} | ID: {user.id} | Nombre: {user.first_name} | @{user.username}\n"
            f.write(linea)
            f.flush()
        print(f"📈 REGISTRO GUARDADO: {user.first_name}")
    except Exception as e:
        print(f"Error grabando usuario: {e}")

def responder_ia(pregunta):
    contexto_machete = f"{DATOS_TECNICATURA}\nCALENDARIO: {DATA_CALENDARIO}\nPLAN: {DATA_PLAN}"
    instruccion_sistema = (
        "Usted es el Asistente Virtual de la Comunidad TUCE - UNPAZ. "
        "Si le preguntan quién lo creó o quién es su autor, responda que fue desarrollado por la agencia Bytes Creativos. "
        "Bajo ninguna circunstancia diga que es un bot oficial. "
        "Responda de forma directa usando esta info: " + contexto_machete
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": instruccion_sistema}, {"role": "user", "content": pregunta}],
            max_tokens=300, temperature=0.1
        )
        return response.choices[0].message.content
    except:
        return "Servicio no disponible actualmente."

# 4. Manejadores de Interfaz
@bot.message_handler(commands=['start'])
def send_welcome(message):
    registrar_usuario(message.from_user)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📚 Materias horarios", "🗓️ Calendario", "📍 Sedes", "🖥️ Gestión Alumnos", "🤖 Bot TUCE")
    saludo = "Bienvenido al **Bot de la Comunidad TUCE - UNPAZ**.\n\nSeleccione una opción del menú."
    bot.send_message(message.chat.id, saludo, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def manejar_mensajes(message):
    if message.text == "📚 Materias horarios":
        materias = sorted(list(set([f[0] for f in LISTA_HORARIOS])))
        markup = types.InlineKeyboardMarkup(row_width=1)
        for mat in materias:
            markup.add(types.InlineKeyboardButton(text=mat, callback_data=f"hor_{mat}"))
        bot.send_message(message.chat.id, "📚 **Seleccione asignatura:**", reply_markup=markup)

    elif message.text == "🗓️ Calendario":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 Ingresantes", callback_data="cal_Ingresantes"), 
            types.InlineKeyboardButton("1️⃣ 1er Semestre", callback_data="cal_Primer Semestre"), 
            types.InlineKeyboardButton("2️⃣ 2do Semestre", callback_data="cal_Segundo Semestre"), 
            types.InlineKeyboardButton("☀️ Verano 2027", callback_data="cal_Verano 2027")
        )
        bot.send_message(message.chat.id, "🗓️ **Calendario Académico:**", reply_markup=markup)

    elif message.text == "🤖 Bot TUCE":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⚖️ Equivalencias", callback_data="bot_equivalencias"),
            types.InlineKeyboardButton("🚌 Boleto Estudiantil", callback_data="bot_boleto"),
            types.InlineKeyboardButton("📄 Certificados", callback_data="bot_certificados"),
            types.InlineKeyboardButton("✍️ Inscripción", callback_data="bot_inscripcion"),
            types.InlineKeyboardButton("💬 Consultar a la IA", callback_data="ia_modo")
        )
        bot.send_message(message.chat.id, "🤖 **Centro de Asistencia Bot TUCE**", reply_markup=markup)

    elif message.text == "📍 Sedes":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📍 Sede Alem", callback_data="sede_alem"), types.InlineKeyboardButton("📍 Sede Arregui", callback_data="sede_arregui"))
        bot.send_message(message.chat.id, "🏢 **Sedes:**", reply_markup=markup)

    elif message.text == "🖥️ Gestión Alumnos":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎓 Campus Virtual", url="https://campusvirtual.unpaz.edu.ar/"),
            types.InlineKeyboardButton("🖥️ SIU Guaraní", url="https://estudiantes.unpaz.edu.ar/autogestion/"),
            types.InlineKeyboardButton("📄 Plan de Estudios", callback_data="plan_info"),
            types.InlineKeyboardButton("📩 Contactos y Mesa de Ayuda", callback_data="ver_contactos")
        )
        bot.send_message(message.chat.id, "🚀 **Gestión Alumnos:**", reply_markup=markup)
    else:
        bot.send_chat_action(message.chat.id, 'typing')
        bot.reply_to(message, responder_ia(message.text))

@bot.callback_query_handler(func=lambda call: True)
def callback_global(call):
    if call.data.startswith("cal_"):
        bot.edit_message_text(DATA_CALENDARIO[call.data.replace("cal_", "")], call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    elif call.data.startswith("bot_"):
        bot.edit_message_text(DATA_BOT_INFO[call.data], call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    elif call.data == "ver_contactos":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🤝 Acceso y Apoyo", callback_data="con_acceso"),
            types.InlineKeyboardButton("📝 Consultas CIU", callback_data="con_ciu"),
            types.InlineKeyboardButton("👤 Consultas Estudiantes", callback_data="con_est"),
            types.InlineKeyboardButton("💻 Soporte SIU Guaraní", callback_data="con_siu"),
            types.InlineKeyboardButton("🌐 UNPAZ Virtual", callback_data="con_virt"),
            types.InlineKeyboardButton("💜 ORVIG (Género)", callback_data="con_orvig")
        )
        bot.edit_message_text("📩 **Seleccione el área de consulta:**", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("con_"):
        contactos = {
            "acceso": "🤝 **Acceso y Apoyo:** 📩 accesoapoyo@unpaz.edu.ar",
            "ciu": "📝 **Consultas CIU:** 📩 ciu@unpaz.edu.ar",
            "est": "👤 **Consultas Estudiantes:** 📩 consultasestudiantes@unpaz.edu.ar",
            "siu": "💻 **Soporte SIU Guaraní:** 📩 soporteinscripciones@unpaz.edu.ar",
            "virt": "🌐 **UNPAZ Virtual:** 📩 formacionvirtual@unpaz.edu.ar",
            "orvig": "💜 **ORVIG:** 📩 orvig@unpaz.edu.ar"
        }
        ref = call.data.replace("con_", "")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="ver_contactos"))
        bot.edit_message_text(contactos[ref], call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "ia_modo":
        bot.send_message(call.message.chat.id, "💬 **Modo IA activado.** Pregunte lo que necesite:")

    elif call.data == "plan_info":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("1º Año", callback_data="anio_Primer Año"), 
            types.InlineKeyboardButton("2º Año", callback_data="anio_Segundo Año"), 
            types.InlineKeyboardButton("3º Año", callback_data="anio_Tercer Año")
        )
        bot.edit_message_text("📄 **Plan de Estudios**", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("anio_"):
        anio = call.data.replace("anio_", "")
        bot.edit_message_text(f"📚 **Asignaturas {anio}:**\n" + "\n".join(DATA_PLAN[anio]), call.message.chat.id, call.message.message_id)

    elif call.data.startswith("hor_"):
        mat_sel = call.data.replace("hor_", "")
        res = f"📍 **Horarios: {mat_sel}**\n\n"
        for f in LISTA_HORARIOS:
            if f[0] == mat_sel:
                res += f"👥 *Com {f[1]}* | 🗓️ {f[2]} | ⏰ {f[3][:-3]} a {f[4][:-3]} hs.\n"
                res += f"🏢 **Aula:** {f[8]}\n"
                res += f"💻 **Mod:** {f[5]}\n"
                res += f"📅 **Inicio Presencial:** {f[6]}\n"
                if f[7] != "//": res += f"🌐 **Inicio Virtual:** {f[7]}\n"
                res += "----------------------------\n"
        bot.edit_message_text(res, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    elif call.data == "sede_alem": bot.send_location(call.message.chat.id, -34.5164, -58.7615)
    elif call.data == "sede_arregui": bot.send_location(call.message.chat.id, -34.5208, -58.7758)

while True:
    try:
        print("🚀 Bot Comunidad TUCE Activo (Data Separada)")
        bot.infinity_polling(timeout=40)
    except Exception as e:
        print(f"Error en el bot: {e}")
        time.sleep(10)