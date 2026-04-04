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
from datos_carrera import DATA_CALENDARIO, DATA_PLAN, CORRELATIVAS, correlativas_de
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

def responder_ia(pregunta: str) -> str:
    # Si el cache es viejo, refrescarlo en background
    if not _cache_fresco():
        threading.Thread(target=_scrape, daemon=True).start()

    ctx = f"{DATOS_TECNICATURA}\nCALENDARIO: {DATA_CALENDARIO}\nPLAN: {DATA_PLAN}\n"

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
        "Sos Alma TUCE, la asistente virtual de la Tecnicatura Universitaria en Comercio Electrónico (TUCE) de UNPAZ. "
        "Usás registro informal con 'vos' (no 'tú'). Sos directo, claro y amigable. Máximo 3 líneas por respuesta. "
        "REGLA PRINCIPAL: NUNCA inventes información. Si no sabés algo con certeza, respondé: "
        "'No tengo esa información. Te recomiendo consultar en unpaz.edu.ar o escribir a la mesa de ayuda.' "
        "Respondés SOLO sobre UNPAZ, la TUCE, trámites, becas y vida universitaria. "
        "NUNCA respondas sobre horarios, aulas o comisiones específicas — para eso existe la sección Horarios. "
        "Si te preguntan algo ajeno a UNPAZ/TUCE, decí que solo podés ayudar con temas de la carrera. "
        "Si te preguntan quién te creó, decí: 'Fui desarrollado por Bytes Creativos, agencia de marketing y soluciones digitales nacida en la UNPAZ. "
        "Podés conocerlos en https://bytescreativos.com.ar/ o en Instagram @bytescreativoss' "
        "El CIU es el Ciclo de Inicio Universitario. El área que lo gestiona es la Dirección de Acceso y Apoyo al Estudiante. "
        "No digas 'la carrera de TUCE' — decí 'la TUCE' o 'la carrera'. "
        "No digas 'primer cuatrimestre' — esta carrera se organiza por trimestres. "
        "Contexto disponible: " + ctx
    )
    try:
        r = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",  "content": sistema},
                {"role": "user",    "content": pregunta},
            ],
            max_tokens=350,
            temperature=0.1,
        )
        return r.choices[0].message.content
    except Exception as e:
        print(f"❌ Error IA: {e}")
        return "Servicio no disponible. Consultá en unpaz.edu.ar"

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
