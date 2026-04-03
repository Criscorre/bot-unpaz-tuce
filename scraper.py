# scraper.py — Bot TUCE
# Crawlea páginas clave de unpaz.edu.ar y guarda el contenido en Firebase.
# El scheduler lo corre cada 6 horas automáticamente.
# La IA usa este contenido como contexto actualizado.

import re
import time
import requests
from bs4 import BeautifulSoup

# ─── Páginas a scrapear ───────────────────────────────────────────────────────
PAGINAS_UNPAZ = {
    "inicio":        "https://www.unpaz.edu.ar/",
    "tuce":          "https://unpaz.edu.ar/comercioelectronico",
    "calendario":    "https://unpaz.edu.ar/calendario-academico",
    "becas":         "https://unpaz.edu.ar/bienestar/becas",
    "pasantias":     "https://unpaz.edu.ar/pasantias",
    "ingreso":       "https://unpaz.edu.ar/estudiaenunpaz",
    "equivalencias": "https://unpaz.edu.ar/formularioequivalencias",
    "noticias":      "https://unpaz.edu.ar/noticias",
}

# Mapeo de palabras clave a páginas relevantes para la IA
KEYWORDS_PAGINAS = {
    "beca":          ["becas"],
    "pasantía":      ["pasantias"],
    "pasantia":      ["pasantias"],
    "equivalencia":  ["equivalencias"],
    "calendario":    ["calendario", "inicio"],
    "fecha":         ["calendario", "inicio"],
    "ingresante":    ["ingreso", "inicio"],
    "ciu":           ["ingreso"],
    "tuce":          ["tuce", "inicio"],
    "comercio":      ["tuce"],
    "novedad":       ["inicio", "noticias"],
    "noticia":       ["inicio", "noticias"],
    "inscripción":   ["calendario", "inicio"],
    "inscripcion":   ["calendario", "inicio"],
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def extraer_texto_limpio(html: str, max_chars: int = 3000) -> str:
    """Extrae texto limpio de HTML eliminando nav, footer, scripts."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]

def extraer_novedades(html: str) -> list:
    """
    Intenta extraer titulares / noticias de la página principal de UNPAZ.
    Devuelve lista de strings con los items encontrados.
    """
    soup = BeautifulSoup(html, "html.parser")
    novedades = []

    # Buscar elementos típicos de noticias: h2, h3, artículos, etc.
    for tag in soup.find_all(["h2", "h3", "article", "li"], limit=30):
        texto = tag.get_text(strip=True)
        # Filtrar textos muy cortos o de navegación
        if len(texto) > 30 and len(texto) < 300:
            novedades.append(texto)

    # Deduplicar manteniendo orden
    vistos = set()
    resultado = []
    for item in novedades:
        if item not in vistos:
            vistos.add(item)
            resultado.append(item)

    return resultado[:10]

def scrape_pagina(url: str) -> dict:
    """Scrappea una URL. Devuelve dict con contenido y novedades."""
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return {}
        html = r.text
        return {
            "url":       url,
            "contenido": extraer_texto_limpio(html),
            "novedades": extraer_novedades(html) if "unpaz.edu.ar/" == url[8:24] or "noticias" in url else [],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        print(f"❌ Error scrapeando {url}: {e}")
        return {}

# ─── Scraping completo ────────────────────────────────────────────────────────

def scrape_todo(firebase_db) -> dict:
    """
    Scrappea todas las páginas configuradas y guarda en Firebase.
    Se llama al iniciar y cada 6 horas via APScheduler.
    """
    print("🔍 Iniciando scraping de unpaz.edu.ar...")
    resultados = {}

    for nombre, url in PAGINAS_UNPAZ.items():
        data = scrape_pagina(url)
        if data:
            resultados[nombre] = data
            print(f"  ✅ {nombre} — {len(data.get('contenido',''))} chars")
        else:
            print(f"  ⚠️  {nombre} — sin contenido")

    if resultados:
        try:
            firebase_db.reference("scraper_cache").set(resultados)
            print(f"✅ Scraping completo — {len(resultados)} páginas en Firebase")
        except Exception as e:
            print(f"❌ Error guardando en Firebase: {e}")

    return resultados

# ─── Lectura de cache ─────────────────────────────────────────────────────────

def leer_cache(firebase_db) -> dict:
    """Lee el cache de scraping desde Firebase."""
    try:
        data = firebase_db.reference("scraper_cache").get()
        return data or {}
    except:
        return {}

def obtener_contexto_ia(firebase_db, query: str = "") -> str:
    """
    Devuelve el contenido scrapeado más relevante para una consulta.
    Usado por responder_ia() para enriquecer el contexto del GPT.
    """
    cache = leer_cache(firebase_db)
    if not cache:
        return ""

    query_lower = query.lower()

    # Detectar páginas relevantes según palabras clave
    paginas_relevantes = set()
    for keyword, paginas in KEYWORDS_PAGINAS.items():
        if keyword in query_lower:
            paginas_relevantes.update(paginas)

    # Si no hay match, usar inicio y tuce por defecto
    if not paginas_relevantes:
        paginas_relevantes = {"inicio", "tuce"}

    contexto = ""
    for nombre in paginas_relevantes:
        if nombre in cache:
            contenido = cache[nombre].get("contenido", "")[:1500]
            ts        = cache[nombre].get("timestamp", "")
            contexto += f"\n[{nombre.upper()} actualizado {ts}]:\n{contenido}\n"

    return contexto[:4000]

def obtener_novedades_texto(firebase_db) -> str:
    """
    Devuelve las novedades de la página principal como texto formateado.
    Usado por el botón 📰 Novedades.
    """
    cache = leer_cache(firebase_db)

    # Buscar en inicio y noticias
    items = []
    for seccion in ["inicio", "noticias"]:
        if seccion in cache:
            novedades = cache[seccion].get("novedades", [])
            items.extend(novedades)

    # Deduplicar
    vistos = set()
    unicos = []
    for item in items:
        if item not in vistos:
            vistos.add(item)
            unicos.append(item)

    ts = ""
    if "inicio" in cache:
        ts = cache["inicio"].get("timestamp", "")

    if not unicos:
        return (
            "📰 *Novedades UNPAZ*\n\n"
            "No hay novedades disponibles en este momento.\n"
            "Visitá unpaz.edu.ar para ver las últimas noticias."
        )

    texto = f"📰 *Novedades UNPAZ*\n_Actualizado: {ts}_\n\n"
    for i, item in enumerate(unicos[:8], 1):
        texto += f"{i}. {item}\n\n"
    texto += "🔗 Más info: unpaz.edu.ar"
    return texto
