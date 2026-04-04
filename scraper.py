# scraper.py v2 — Bot TUCE
# Crawlea páginas clave de unpaz.edu.ar y guarda el contenido en Firebase.
# Usa selectores CSS de Drupal para extracción precisa de contenido.
# El scheduler lo corre cada 6 horas automáticamente.
# La IA usa este contenido como contexto actualizado.

import re
import time
import requests
from bs4 import BeautifulSoup

# ─── Páginas a scrapear ───────────────────────────────────────────────────────
PAGINAS_UNPAZ = {
    "inicio":           "https://www.unpaz.edu.ar/",
    "tuce":             "https://unpaz.edu.ar/comercioelectronico",
    "calendario":       "https://unpaz.edu.ar/calendario-academico",
    "calendario_ciu":   "https://unpaz.edu.ar/ciu-calendario",
    "becas":            "https://unpaz.edu.ar/bienestar/becas",
    "becas_unpaz":      "https://unpaz.edu.ar/becas-unpaz",
    "becas_externas":   "https://unpaz.edu.ar/becas-externas",
    "pasantias":        "https://unpaz.edu.ar/pasantias",
    "ingreso":          "https://unpaz.edu.ar/estudiaenunpaz",
    "faq_ingresantes":  "https://unpaz.edu.ar/preguntas-frecuentes-ingresantes",
    "equivalencias":    "https://unpaz.edu.ar/formularioequivalencias",
    "cursada":          "https://unpaz.edu.ar/cursada",
    "guia_estudiantes": "https://unpaz.edu.ar/guia-del-estudiante",
    "ayudantias":       "https://unpaz.edu.ar/ayudantias",
    "noticias":         "https://unpaz.edu.ar/noticias",
}

# Selectores CSS Drupal para contenido principal
CONTENT_SELECTORS = [
    "main .field--name-body",
    "main .field--type-text-with-summary",
    "article .node__content",
    ".view-content",
    "main .block-system-main-block",
    "#main-content",
    "main",
    ".layout-container main",
]

# Mapeo de palabras clave a páginas relevantes para la IA
KEYWORDS_PAGINAS = {
    "beca":            ["becas", "becas_unpaz", "becas_externas"],
    "becas":           ["becas", "becas_unpaz", "becas_externas"],
    "pasantía":        ["pasantias"],
    "pasantia":        ["pasantias"],
    "equivalencia":    ["equivalencias"],
    "calendario":      ["calendario", "inicio"],
    "fecha":           ["calendario", "inicio"],
    "ingresante":      ["ingreso", "faq_ingresantes", "inicio"],
    "ciu":             ["ingreso", "calendario_ciu", "faq_ingresantes"],
    "ciclo de inicio": ["ingreso", "calendario_ciu"],
    "tuce":            ["tuce", "inicio"],
    "comercio":        ["tuce"],
    "cursada":         ["cursada", "calendario"],
    "materia":         ["cursada", "tuce"],
    "ayudantia":       ["ayudantias"],
    "ayudantía":       ["ayudantias"],
    "novedad":         ["inicio", "noticias"],
    "noticia":         ["inicio", "noticias"],
    "inscripción":     ["calendario", "inicio"],
    "inscripcion":     ["calendario", "inicio"],
    "guia":            ["guia_estudiantes"],
    "guía":            ["guia_estudiantes"],
}

# ─── Extracción con selectores Drupal ────────────────────────────────────────

def extraer_contenido_principal(soup: BeautifulSoup) -> str:
    """Extrae el contenido principal usando selectores CSS de Drupal."""
    for selector in CONTENT_SELECTORS:
        try:
            elemento = soup.select_one(selector)
            if elemento:
                # Limpiar elementos no deseados dentro del contenido
                for tag in elemento(["script", "style", "nav", "footer",
                                      "header", "aside", "iframe", "form",
                                      ".menu", ".breadcrumb", ".pager"]):
                    tag.decompose()
                texto = elemento.get_text(separator=" ", strip=True)
                texto = re.sub(r"\s+", " ", texto).strip()
                if len(texto) > 100:  # Solo si hay contenido real
                    return texto[:4000]
        except Exception:
            continue

    # Fallback: extracción genérica
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "iframe", "form"]):
        tag.decompose()
    texto = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", texto).strip()[:4000]

def extraer_links_adjuntos(soup: BeautifulSoup) -> list:
    """Extrae links a PDFs y documentos adjuntos."""
    adjuntos = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        texto = a.get_text(strip=True)
        if any(href.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]):
            if href.startswith("/"):
                href = "https://unpaz.edu.ar" + href
            adjuntos.append({"texto": texto, "url": href})
    return adjuntos[:10]  # Máximo 10 adjuntos

def extraer_novedades(html: str) -> list:
    """
    Extrae titulares / noticias usando selectores específicos de Drupal UNPAZ.
    Devuelve lista de strings con los items encontrados.
    """
    soup = BeautifulSoup(html, "html.parser")
    novedades = []

    # Selectores Drupal para noticias/novedades
    selectores_noticias = [
        ".views-row .node__title",
        ".views-row h2",
        ".views-row h3",
        "article.node--type-news .node__title",
        "article.node--type-noticia .node__title",
        ".field--name-title",
        "h2.node__title",
        "h3.node__title",
    ]

    for selector in selectores_noticias:
        try:
            elementos = soup.select(selector)
            for el in elementos:
                texto = el.get_text(strip=True)
                if 30 < len(texto) < 300:
                    novedades.append(texto)
        except Exception:
            continue

    # Fallback: h2/h3 genéricos si no se encontró nada
    if not novedades:
        for tag in soup.find_all(["h2", "h3"], limit=30):
            texto = tag.get_text(strip=True)
            if 30 < len(texto) < 300:
                novedades.append(texto)

    # Deduplicar manteniendo orden
    vistos = set()
    resultado = []
    for item in novedades:
        if item not in vistos:
            vistos.add(item)
            resultado.append(item)

    return resultado[:10]

def extraer_titulo(soup: BeautifulSoup) -> str:
    """Extrae el título principal de la página."""
    # Selectores Drupal para título
    for selector in ["h1.page-header", "h1.node__title", ".page-title", "h1"]:
        try:
            el = soup.select_one(selector)
            if el:
                titulo = el.get_text(strip=True)
                if titulo:
                    return titulo
        except Exception:
            continue
    return ""

# ─── Scraping de una página ───────────────────────────────────────────────────

def scrape_pagina(url: str) -> dict:
    """Scrappea una URL. Devuelve dict con contenido, novedades y adjuntos."""
    try:
        time.sleep(1)  # Pausa cortés entre requests
        r = requests.get(url, timeout=12, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BotTUCE/2.0; +https://unpaz.edu.ar)"
        })
        if r.status_code != 200:
            print(f"  ⚠️  HTTP {r.status_code} — {url}")
            return {}

        soup    = BeautifulSoup(r.text, "html.parser")
        titulo  = extraer_titulo(soup)
        contenido = extraer_contenido_principal(soup)
        adjuntos  = extraer_links_adjuntos(soup)

        es_inicio   = url.rstrip("/") in ("https://www.unpaz.edu.ar", "https://unpaz.edu.ar")
        es_noticias = "noticias" in url

        return {
            "url":       url,
            "titulo":    titulo,
            "contenido": contenido,
            "adjuntos":  adjuntos,
            "novedades": extraer_novedades(r.text) if (es_inicio or es_noticias) else [],
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
    print("🔍 Iniciando scraping v2 de unpaz.edu.ar...")
    resultados = {}

    for nombre, url in PAGINAS_UNPAZ.items():
        data = scrape_pagina(url)
        if data:
            resultados[nombre] = data
            adj_count = len(data.get("adjuntos", []))
            print(f"  ✅ {nombre} — {len(data.get('contenido',''))} chars"
                  + (f", {adj_count} adjuntos" if adj_count else ""))
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
    Incluye adjuntos (PDFs/docs) si los hay.
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
            entrada   = cache[nombre]
            titulo    = entrada.get("titulo", "")
            contenido = entrada.get("contenido", "")[:1500]
            adjuntos  = entrada.get("adjuntos", [])
            ts        = entrada.get("timestamp", "")

            header = titulo if titulo else nombre.upper()
            contexto += f"\n[{header} — actualizado {ts}]:\n{contenido}\n"

            if adjuntos:
                contexto += "Documentos adjuntos:\n"
                for adj in adjuntos[:5]:
                    contexto += f"  • {adj.get('texto','')} → {adj.get('url','')}\n"

    return contexto[:4000]

def obtener_novedades_texto(firebase_db) -> str:
    """
    Devuelve las novedades de la página principal como texto formateado.
    Usado por la sección Novedades del bot.
    """
    cache = leer_cache(firebase_db)

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
