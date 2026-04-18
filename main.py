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

# ─── Telegram — Bot funcional ─────────────────────────────────────────────────

# Estado de menú por usuario: {chat_id: "principal" | "carrera" | "horarios" | "faq" | "sedes"}
_tg_estado = {}

_TG_FOOTER = "\n\n_I - Inicio  |  V - Volver  |  S - Salir_"

_TG_MENU = (
    "📋 *Menú principal:*\n\n"
    "1️⃣  📚 Información de la carrera\n"
    "2️⃣  🕒 Horarios del trimestre\n"
    "3️⃣  👥 Comunidad TUCE\n"
    "4️⃣  ❓ Preguntas frecuentes\n"
    "5️⃣  📍 Sedes UNPAZ\n"
    "6️⃣  🙋 Hablar con un humano\n\n"
    "_Escribí el número o preguntame directamente._"
    + _TG_FOOTER
)

_TG_SUBMENU_CARRERA = (
    "📚 *Información de la carrera:*\n\n"
    "1️⃣  Sobre la TUCE\n"
    "2️⃣  Plan de estudios\n"
    "3️⃣  Calendario académico\n"
    "4️⃣  Correlativas\n"
    "5️⃣  Director de la carrera\n"
    + _TG_FOOTER
)

_TG_MSG_HUMANO = (
    "Te conectamos con la comunidad TUCE directamente por WhatsApp. "
    "¡Allí vas a encontrar personas que te pueden ayudar! 👥\n"
    "https://chat.whatsapp.com/FSwCNJd2GirBVIVCZDGU0B"
    + _TG_FOOTER
)

def _tg_send(cid, texto):
    try:
        bot.send_message(cid, texto, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        print(f"⚠️ Error Telegram send: {e}")

def _tg_menu_carrera(num):
    if num == 1:
        info = DATA_CARRERA_INFO
        return (
            f"🎓 *{info['titulo']}*\n\n"
            f"📅 Duración: {info['duracion']}\n"
            f"🏫 Modalidad: {info['modalidad']}\n\n"
            f"{info['descripcion']}"
        ) + _TG_FOOTER
    if num == 2:
        lines = []
        for anio, mats in DATA_PLAN.items():
            lines.append(f"*{anio}:*")
            lines += [f"  • {m}" for m in mats]
        return "📋 *Plan de estudios TUCE:*\n\n" + "\n".join(lines) + _TG_FOOTER
    if num == 3:
        lines = [f"*{k}:*\n{v}" for k, v in DATA_CALENDARIO.items()]
        return "\n\n".join(lines) + _TG_FOOTER
    if num == 4:
        return (
            "🔗 *Correlativas*\n\nEscribí el nombre de la materia "
            "y te digo qué necesitás tener aprobado."
        ) + _TG_FOOTER
    if num == 5:
        d = DATA_DIRECTOR
        return (
            f"👤 *Director de la TUCE:*\n\n"
            f"*{d['nombre']}*\n"
            f"📧 {d.get('email', 'Sin datos')}"
        ) + _TG_FOOTER
    return None

def _tg_sedes():
    from wa_menu import SEDES
    lineas = []
    for s in SEDES.values():
        lineas.append(f"📍 *{s['nombre']}*\n{s['direccion']}\n{s['maps']}")
        if s.get("extra"):
            lineas[-1] += f"\n_{s['extra']}_"
    return "\n\n".join(lineas) + _TG_FOOTER

def _tg_faq_lista():
    from faq_data import FAQ
    items = "\n".join(f"{i+1}. {f['q']}" for i, f in enumerate(FAQ))
    return f"❓ *Preguntas frecuentes:*\n\n{items}\n\nEscribí el número para ver la respuesta." + _TG_FOOTER

def _tg_faq_respuesta(num):
    from faq_data import FAQ
    if 1 <= num <= len(FAQ):
        return FAQ[num - 1]["a"] + _TG_FOOTER
    return None

def _tg_comunidad():
    return (
        "👥 *Comunidad TUCE*\n\n"
        "📱 *Grupo de WhatsApp:* https://chat.whatsapp.com/FSwCNJd2GirBVIVCZDGU0B\n"
        "📸 *Instagram:* @tuce.unpaz\n"
        "📘 *Facebook:* TUCE UNPAZ"
    ) + _TG_FOOTER

@bot.message_handler(commands=["start"])
def tg_start(message):
    cid = message.chat.id
    _tg_estado[cid] = "principal"
    nombre = message.from_user.first_name or "estudiante"
    _tg_send(cid, f"¡Hola {nombre}! Soy *Alma TUCE* 🎓\n\n" + _TG_MENU)

@bot.message_handler(func=lambda m: True, content_types=["text"])
def tg_handle(message):
    cid   = message.chat.id
    texto = message.text.strip().lower() if message.text else ""
    menu  = _tg_estado.get(cid, "principal")

    # Comandos globales
    if texto in ("i", "inicio", "/menu"):
        _tg_estado[cid] = "principal"
        _tg_send(cid, _TG_MENU)
        return
    if texto in ("s", "salir"):
        _tg_estado.pop(cid, None)
        _tg_send(cid, "👋 ¡Hasta luego! Cuando necesites algo, acá estoy. 😊")
        return
    if texto in ("v", "volver"):
        _tg_estado[cid] = "principal"
        _tg_send(cid, _TG_MENU)
        return

    num = None
    try:
        num = int(texto)
    except ValueError:
        pass

    # ── Menú principal ────────────────────────────────────────────────────────
    if menu == "principal":
        if num == 1:
            _tg_estado[cid] = "carrera"
            _tg_send(cid, _TG_SUBMENU_CARRERA)
        elif num == 2:
            _tg_estado[cid] = "principal"
            from materias_db import LISTA_HORARIOS
            materias = sorted(set(f[0] for f in LISTA_HORARIOS))
            lista = "\n".join(f"• {m}" for m in materias)
            _tg_send(cid, f"🕒 *Materias del trimestre:*\n\n{lista}\n\nEscribí el nombre de la materia para ver el horario." + _TG_FOOTER)
            _tg_estado[cid] = "horarios"
        elif num == 3:
            _tg_send(cid, _tg_comunidad())
        elif num == 4:
            _tg_estado[cid] = "faq"
            _tg_send(cid, _tg_faq_lista())
        elif num == 5:
            _tg_send(cid, _tg_sedes())
        elif num == 6:
            _tg_send(cid, _TG_MSG_HUMANO)
        else:
            # Texto libre → IA como fallback
            respuesta = responder_ia(message.text.strip(), uid=f"tg_{cid}")
            _tg_send(cid, respuesta + _TG_FOOTER)

    # ── Submenú carrera ───────────────────────────────────────────────────────
    elif menu == "carrera":
        if num and 1 <= num <= 5:
            resp = _tg_menu_carrera(num)
            if num == 4:
                _tg_estado[cid] = "correlativa"
            _tg_send(cid, resp)
        else:
            _tg_send(cid, _TG_SUBMENU_CARRERA)

    # ── Correlativas ──────────────────────────────────────────────────────────
    elif menu == "correlativa":
        from wa_menu import CORRELATIVAS
        from normalizer import normalizar
        texto_norm = normalizar(message.text.strip())
        encontrada = None
        for info in CORRELATIVAS.values():
            if normalizar(info["nombre"]) in texto_norm or texto_norm in normalizar(info["nombre"]):
                encontrada = info
                break
        if encontrada:
            if not encontrada["necesita"]:
                _tg_send(cid, f"✅ *{encontrada['nombre']}*\n\nNo tiene correlativas." + _TG_FOOTER)
            else:
                previas = "\n".join(f"  • {CORRELATIVAS[c]['nombre']}" for c in encontrada["necesita"])
                _tg_send(cid, f"🔗 *{encontrada['nombre']}*\n\nPara cursarla necesitás:\n{previas}" + _TG_FOOTER)
        else:
            _tg_send(cid, "❌ No encontré esa materia. Escribí el nombre completo o parte de él." + _TG_FOOTER)

    # ── Horarios ──────────────────────────────────────────────────────────────
    elif menu == "horarios":
        from materias_db import LISTA_HORARIOS
        from normalizer import normalizar
        texto_norm = normalizar(message.text.strip())
        filas = [f for f in LISTA_HORARIOS if normalizar(f[0]) in texto_norm or texto_norm in normalizar(f[0])]
        if filas:
            materia = filas[0][0]
            resp = f"🕒 *{materia}*\n"
            for f in filas:
                aula = f[8] if f[8] and f[8] not in ("//", "A confirmar") else "A confirmar"
                resp += f"\n👥 *Com {f[1]}* — {f[2]} {f[3][:5]}–{f[4][:5]} hs\n🏢 Aula: {aula} | {f[5]}"
            _tg_send(cid, resp + _TG_FOOTER)
        else:
            _tg_send(cid, "❌ No encontré esa materia. Escribí el nombre completo o parte de él." + _TG_FOOTER)

    # ── FAQ ───────────────────────────────────────────────────────────────────
    elif menu == "faq":
        if num:
            resp = _tg_faq_respuesta(num)
            _tg_send(cid, resp if resp else "❌ Número inválido.\n\n" + _tg_faq_lista())
        else:
            _tg_send(cid, _tg_faq_lista())

@bot.callback_query_handler(func=lambda call: True)
def tg_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

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
