import os
import time
import datetime
import threading
import requests
import re

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from openai import OpenAI
import telebot
import http.server, socketserver

from info_unpaz import DATOS_TECNICATURA
from materias_db import LISTA_HORARIOS
from scraper import scrape_todo, obtener_contexto_ia, obtener_novedades_texto, leer_cache
from datos_carrera import (
    DATA_CALENDARIO, DATA_PLAN, CORRELATIVAS, correlativas_de,
    DATA_CARRERA_INFO, DATA_DIRECTOR,
)
import wa_menu

# ─── Config ───────────────────────────────────────────────────────────────────
base_dir = os.path.dirname(__file__)
load_dotenv(os.path.join(base_dir, ".env"))

TOKEN          = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TOKEN or not OPENAI_API_KEY:
    print("❌ Faltan credenciales TELEGRAM_TOKEN / OPENAI_API_KEY")
    exit(1)

# ─── Clientes ─────────────────────────────────────────────────────────────────
bot    = telebot.TeleBot(TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

import firebase_admin
from firebase_admin import db as firebase_db

# ─── Health server (Koyeb) ────────────────────────────────────────────────────
def _run_health():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", 8000), http.server.SimpleHTTPRequestHandler) as h:
        print("🌍 Health server activo en :8000")
        h.serve_forever()

threading.Thread(target=_run_health, daemon=True).start()

# ─── Scraping automático cada 6 horas ─────────────────────────────────────────
from apscheduler.schedulers.background import BackgroundScheduler

def _scrape():
    try:
        scrape_todo(firebase_db)
    except Exception as e:
        print(f"⚠️ Error scraping: {e}")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(_scrape, "interval", hours=6, id="scraper")
scheduler.start()
threading.Thread(target=_scrape, daemon=True).start()

# ─── Historial de conversación ────────────────────────────────────────────────
MAX_HISTORIAL = 10  # Máximo de intercambios guardados por usuario

def _esc_uid(uid: str) -> str:
    return uid.replace(".", "___DOT___").replace("@", "___AT___").replace("+", "___PLUS___")

def _leer_historial(uid: str) -> list:
    """Lee el historial de conversación de un usuario desde Firebase."""
    if not uid:
        return []
    try:
        data = firebase_db.reference(f"wa_historial/{_esc_uid(uid)}").get()
        if not data:
            return []
        if isinstance(data, list):
            return [x for x in data if x]
        if isinstance(data, dict):
            keys = sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else 0)
            return [data[k] for k in keys if data[k]]
        return []
    except:
        return []

def _guardar_historial(uid: str, pregunta: str, respuesta: str):
    """Guarda un intercambio en el historial del usuario en Firebase."""
    if not uid:
        return
    try:
        historial = _leer_historial(uid)
        historial.append({
            "q":  pregunta[:300],
            "r":  respuesta[:600],
            "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        if len(historial) > MAX_HISTORIAL:
            historial = historial[-MAX_HISTORIAL:]
        data = {str(i): h for i, h in enumerate(historial)}
        firebase_db.reference(f"wa_historial/{_esc_uid(uid)}").set(data)
    except:
        pass

# ─── IA ───────────────────────────────────────────────────────────────────────
URLS_UNPAZ = {
    "becas":        "https://unpaz.edu.ar/bienestar/becas",
    "pasantias":    "https://unpaz.edu.ar/pasantias",
    "equivalencias":"https://unpaz.edu.ar/formularioequivalencias",
    "calendario":   "https://unpaz.edu.ar/calendario-academico",
    "ingreso":      "https://unpaz.edu.ar/estudiaenunpaz",
    "reglamento":   "https://unpaz.edu.ar/regimen-general-de-estudios",
    "tuce":         "https://unpaz.edu.ar/comercioelectronico",
}

def _info_web(url: str) -> str:
    try:
        r = requests.get(url, timeout=4, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return ""
        t = re.sub(r"<style[^>]*>.*?</style>", "", r.text, flags=re.DOTALL)
        t = re.sub(r"<script[^>]*>.*?</script>", "", t, flags=re.DOTALL)
        t = re.sub(r"<[^>]+>", " ", t)
        return re.sub(r"\s+", " ", t).strip()[:3000]
    except:
        return ""

def _url_relevante(p: str) -> str:
    p = p.lower()
    if any(w in p for w in ["beca"]):                          return URLS_UNPAZ["becas"]
    if any(w in p for w in ["pasantia", "pasantía"]):          return URLS_UNPAZ["pasantias"]
    if any(w in p for w in ["equivalencia"]):                  return URLS_UNPAZ["equivalencias"]
    if any(w in p for w in ["calendario", "fecha", "cuando"]): return URLS_UNPAZ["calendario"]
    if any(w in p for w in ["ingreso", "ingresante", "ciu"]):  return URLS_UNPAZ["ingreso"]
    if any(w in p for w in ["reglamento", "regimen"]):         return URLS_UNPAZ["reglamento"]
    if any(w in p for w in ["tuce", "comercio"]):              return URLS_UNPAZ["tuce"]
    return ""

def _cache_fresco() -> bool:
    try:
        cache  = leer_cache(firebase_db)
        ts_str = cache.get("inicio", {}).get("timestamp", "") if cache else ""
        if not ts_str:
            return False
        ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return (datetime.datetime.now() - ts).total_seconds() < 12 * 3600
    except:
        return False

def responder_ia(pregunta: str, uid: str = "") -> str:
    """
    Responde usando GPT-3.5 con contexto de la carrera e historial del usuario.
    Se usa internamente como fallback cuando el bot no tiene una respuesta directa.
    """
    # Refrescar cache si está viejo
    if not _cache_fresco():
        threading.Thread(target=_scrape, daemon=True).start()

    # Construir contexto base
    info_carrera = (
        f"TÍTULO: {DATA_CARRERA_INFO['titulo']}\n"
        f"DURACIÓN: {DATA_CARRERA_INFO['duracion']}\n"
        f"MODALIDAD: {DATA_CARRERA_INFO['modalidad']}\n"
        f"DESCRIPCIÓN: {DATA_CARRERA_INFO['descripcion']}\n"
        f"PERFIL EGRESADO: {', '.join(DATA_CARRERA_INFO['perfil_egresado'])}\n"
        f"DIRECTOR: {DATA_DIRECTOR['nombre']}\n"
        f"PLAN: {list(DATA_PLAN.keys())}\n"
        f"CALENDARIO: {DATA_CALENDARIO}\n"
    )
    ctx = f"{DATOS_TECNICATURA}\n{info_carrera}"

    try:
        scraper_ctx = obtener_contexto_ia(firebase_db, pregunta)
        if scraper_ctx:
            ctx += f"\nINFO ACTUALIZADA UNPAZ:\n{scraper_ctx}"
    except Exception as e:
        print(f"⚠️ Error cache scraper: {e}")

    url = _url_relevante(pregunta)
    if url:
        info = _info_web(url)
        if info:
            ctx += f"\nINFO WEB {url}:\n{info}"

    sistema = (
        "Sos Alma TUCE, la asistente virtual de la Tecnicatura Universitaria en Comercio Electrónico (TUCE) de la UNPAZ. "
        "Usás registro informal con 'vos' (no 'tú'). Sos directo, claro y amigable. Máximo 4 líneas por respuesta. "
        "\n\nTEMAS EN LOS QUE ERES EXPERTA: e-commerce, comercio electrónico, marketing digital, estrategias de venta online, "
        "tiendas online, CEO, emprendimiento digital, salida laboral en el mundo digital, SEO, redes sociales con fines comerciales, "
        "métricas digitales, campañas publicitarias online, gestión de proyectos digitales, y todo lo relacionado a la TUCE y UNPAZ. "
        "\n\nREGLAS IMPORTANTES:\n"
        "1. NUNCA inventes información sobre la carrera, fechas, o trámites. Si no sabés algo con certeza, respondé: "
        "'No tengo esa información. Te recomiendo consultar en unpaz.edu.ar o escribir a la mesa de ayuda.'\n"
        "2. NUNCA respondas sobre horarios, aulas ni comisiones específicas — para eso existe la sección Horarios del menú.\n"
        "3. Si te preguntan algo ajeno a e-commerce, marketing digital, TUCE o UNPAZ, podés responder brevemente si es un tema general de negocios digitales.\n"
        "4. Si te preguntan quién te creó: 'Fui desarrollada por Bytes Creativos, agencia de marketing y soluciones digitales nacida en la UNPAZ. "
        "Conocelos en https://bytescreativos.com.ar/ o en Instagram @bytescreativoss'\n"
        "5. El CIU es el Ciclo de Inicio Universitario. El área que lo gestiona es la Dirección de Acceso y Apoyo al Estudiante.\n"
        "6. No digas 'la carrera de TUCE' — decí 'la TUCE' o 'la carrera'.\n"
        "7. No digas 'cuatrimestre' — esta carrera se organiza por trimestres.\n"
        "\nContexto disponible: " + ctx
    )

    # Leer historial del usuario para contexto conversacional
    historial = _leer_historial(uid) if uid else []

    messages = [{"role": "system", "content": sistema}]
    # Incluir últimos 3 intercambios para continuidad
    for h in historial[-3:]:
        if h.get("q") and h.get("r"):
            messages.append({"role": "user",      "content": h["q"]})
            messages.append({"role": "assistant", "content": h["r"]})
    messages.append({"role": "user", "content": pregunta})

    try:
        r = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=400,
            temperature=0.15,
        )
        respuesta = r.choices[0].message.content
    except Exception as e:
        print(f"❌ Error IA: {e}")
        respuesta = "Servicio no disponible. Consultá en unpaz.edu.ar"

    # Guardar en historial
    _guardar_historial(uid, pregunta, respuesta)

    return respuesta

# ─── Flask — webhook WhatsApp ─────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/wa", methods=["POST"])
def webhook_wa():
    data    = request.get_json(silent=True) or {}
    from_id = data.get("from", "")
    mensaje = data.get("message", "").strip()
    if not from_id or not mensaje:
        return jsonify({"response": ""}), 400
    respuesta = wa_menu.procesar(from_id, mensaje, firebase_db, responder_ia)
    return jsonify({"response": respuesta})

@flask_app.route("/health", methods=["GET"])
def health():
    return "OK", 200

threading.Thread(
    target=lambda: flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False),
    daemon=True,
).start()

# ─── Telegram — solo mensaje de mantenimiento ─────────────────────────────────
MSG_MANTENIMIENTO = (
    "🔧 *Bot en actualización*\n\n"
    "Estamos trabajando en mejoras para vos. ¡Muy pronto volvemos!\n\n"
    "📱 Mientras tanto, escribinos por *WhatsApp* para consultas.\n\n"
    "_Att: Bytes Creativos_"
)

@bot.message_handler(func=lambda m: True, content_types=["text", "photo", "document", "sticker", "voice"])
def mantenimiento(message):
    try:
        bot.send_message(message.chat.id, MSG_MANTENIMIENTO, parse_mode="Markdown")
    except Exception as e:
        print(f"⚠️ Error enviando mantenimiento: {e}")

@bot.callback_query_handler(func=lambda call: True)
def mantenimiento_callback(call):
    try:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, MSG_MANTENIMIENTO, parse_mode="Markdown")
    except Exception as e:
        print(f"⚠️ Error callback mantenimiento: {e}")

# ─── Arranque ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Alma TUCE — WhatsApp activo | Telegram en mantenimiento")
    try:
        bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook Telegram limpiado")
    except Exception as e:
        print(f"⚠️ No se pudo limpiar webhook: {e}")
    while True:
        try:
            bot.infinity_polling(timeout=40, allowed_updates=[])
        except Exception as e:
            err = str(e)
            wait = 30 if "409" in err else 15
            print(f"⚠️ Error polling ({wait}s): {e}")
            time.sleep(wait)
