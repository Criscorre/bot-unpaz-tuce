import telebot
from telebot import types
import requests

# 1. Configuración de Google Sheets (Para Horarios, Calendario y Mensajes)
API_KEY_GOOGLE = 'AIzaSyAAY-9zAeUAE4-cePHtWEZ9MJrNUkZwZ64'
SPREADSHEET_ID = '1DNRXgRYrytRVMqddNlQlFJKuNYUVCUHVzXOsHjrG2xc'

URL_MENSAJES = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/bot_mensajes!A1:C20?key={API_KEY_GOOGLE}"
URL_HORARIOS = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Horarios!A2:E50?key={API_KEY_GOOGLE}"
URL_CALENDARIO = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Calendario!A2:D100?key={API_KEY_GOOGLE}"

# 2. DATA DEL PLAN DE ESTUDIOS (Cargada directamente para que no falle)
DATA_PLAN = {
    "Primer Año": [
        "Tecnología y Sociedad (4hs)", "Inglés I (4hs)", "Principios de Economía (4hs)",
        "Comunicación Institucional (4hs)", "Internet: Infraestructura y redes (4hs)",
        "Semántica de las interfaces (4hs)", "Introducción al comercio electrónico (4hs)",
        "Usabilidad, seguridad y Estándares Web (4hs)", "Inglés II (4hs)"
    ],
    "Segundo Año": [
        "Investigación de mercado (4hs)", "Marco legal de negocios electrónicos (4hs)",
        "Gestión del conocimiento (4hs)", "Desarrollo Web (4hs)",
        "Formulación, incubación y evaluación de proyectos (4hs)", "Métricas del mundo digital (4hs)",
        "Desarrollo de Productos y Servicios (4hs)", "Taller de Comunicación (4hs)",
        "Desarrollos para Dispositivos móviles (4hs)"
    ],
    "Tercer Año": [
        "Calidad y Servicio al Cliente (4hs)", "Marketing digital (4hs)",
        "Taller de Práctica Integradora (4hs)", "Competencias emprendedoras (4hs)",
        "Gestión de Proyectos (4hs)"
    ]
}

# 3. Configuración del Bot
TOKEN = '8515265096:AAHTqfGgxGxlBOAQLoNEbokYpW68PDri4IY'
bot = telebot.TeleBot(TOKEN)

def obtener_datos(url):
    try:
        response = requests.get(url).json()
        return response.get('values', [])
    except:
        return []

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("📅 Horarios")
    btn2 = types.KeyboardButton("🗓️ Calendario")
    btn3 = types.KeyboardButton("📍 Sedes")
    btn4 = types.KeyboardButton("🖥️ Gestión Alumnos")
    markup.add(btn1, btn2, btn3, btn4)
    
    datos = obtener_datos(URL_MENSAJES)
    saludo = datos[1][2].replace("\\n", "\n") if len(datos) > 1 else "¡Hola! Bienvenido al Bot TUCE de la UNPAZ."
    bot.send_message(message.chat.id, saludo, reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def manejar_mensajes_principales(message):
    if message.text == "📅 Horarios":
        filas = obtener_datos(URL_HORARIOS)
        if not filas:
            bot.send_message(message.chat.id, "❌ No hay horarios cargados.")
            return
        materias_unicas = sorted(list(set([f[0] for f in filas if f])))
        markup = types.InlineKeyboardMarkup(row_width=1)
        for mat in materias_unicas:
            markup.add(types.InlineKeyboardButton(text=mat, callback_data=f"hor_{mat}"))
        bot.send_message(message.chat.id, "📚 **¿De qué materia querés ver el horario?**", reply_markup=markup, parse_mode="Markdown")

    elif message.text == "🗓️ Calendario":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 Ingresantes", callback_data="cal_Ingresantes"),
            types.InlineKeyboardButton("1️⃣ Primer Semestre", callback_data="cal_Primer Semestre"),
            types.InlineKeyboardButton("2️⃣ Segundo Semestre", callback_data="cal_Segundo Semestre"),
            types.InlineKeyboardButton("☀️ Verano 2027", callback_data="cal_Verano 2027")
        )
        bot.send_message(message.chat.id, "🗓️ **Calendario Académico**", reply_markup=markup, parse_mode="Markdown")

    elif message.text == "📍 Sedes":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📍 Sede Alem / Pueyrredón", callback_data="sede_alem"),
            types.InlineKeyboardButton("📍 Sede Arregui", callback_data="sede_arregui")
        )
        bot.send_message(message.chat.id, "🏢 **Seleccioná la sede:**", reply_markup=markup, parse_mode="Markdown")

    elif message.text == "🖥️ Gestión Alumnos":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎓 Campus Virtual", callback_data="gest_campus"),
            types.InlineKeyboardButton("🖥️ SIU Guaraní", callback_data="gest_siu"),
            types.InlineKeyboardButton("📄 Plan de Estudios", callback_data="plan_info")
        )
        bot.send_message(message.chat.id, "🚀 **Gestión de Alumnos:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_global(call):
    # SECCIÓN PLAN DE ESTUDIOS (DATA FIJA)
    if call.data == "plan_info":
        texto = (
            "📄 **Plan de Estudios - TUCE**\n\n"
            "🎓 **Título Intermedio:** Técnica/o Universitaria/o en Comercio Electrónico.\n\n"
            "⏳ **Duración total:** 3 años (1600 horas totales).\n\n"
            "👤 **Perfil del egresado:** Capacitado para gestionar tiendas online, "
            "interactuar con equipos de diseño/desarrollo y administrar proyectos propios.\n\n"
            "¿Deseás ver las materias de un año específico?"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("Primer Año", callback_data="anio_Primer Año"),
            types.InlineKeyboardButton("Segundo Año", callback_data="anio_Segundo Año"),
            types.InlineKeyboardButton("Tercer Año", callback_data="anio_Tercer Año")
        )
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=texto, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("anio_"):
        anio = call.data.replace("anio_", "")
        materias = DATA_PLAN.get(anio, [])
        
        res = f"📚 **Materias de {anio}:**\n\n"
        for m in materias:
            res += f"🔹 {m}\n"
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Volver", callback_data="plan_info"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=res, reply_markup=markup, parse_mode="Markdown")

    # RESTO DE CALLBACKS
    elif call.data.startswith("hor_"):
        mat_sel = call.data.replace("hor_", "")
        filas = obtener_datos(URL_HORARIOS)
        res = f"📍 **Horarios: {mat_sel}**\n\n"
        for f in filas:
            if len(f) >= 5 and f[0] == mat_sel:
                res += f"👥 *Com {f[1]}* | 🗓️ {f[2]} | ⏰ {f[3]} a {f[4]} hs.\n"
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=res, parse_mode="Markdown")
    elif call.data.startswith("cal_"):
        per = call.data.replace("cal_", "")
        filas_cal = obtener_datos(URL_CALENDARIO)
        info = ""
        for f in filas_cal:
            if len(f) >= 4 and f[0].strip() == per:
                info += f"📌 *{f[2]}*\n🗓️ {f[3]}\n\n"
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"🗓️ **{per}**\n\n{info or 'S/D'}", parse_mode="Markdown")
    elif call.data == "gest_campus":
        bot.send_message(call.message.chat.id, "🎓 **Campus:** https://campusvirtual.unpaz.edu.ar/login/index.php")
    elif call.data == "gest_siu":
        bot.send_message(call.message.chat.id, "🖥️ **SIU:** https://estudiantes.unpaz.edu.ar/autogestion/")
    elif call.data == "sede_alem":
        bot.send_location(call.message.chat.id, -34.5164, -58.7615)
    elif call.data == "sede_arregui":
        bot.send_location(call.message.chat.id, -34.5208, -58.7758)

bot.remove_webhook()
print("¡Bot UNPAZ con Plan Blindado Activo!")
bot.infinity_polling()