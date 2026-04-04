# normalizer.py — Normalización de input de usuario
import unicodedata
import re

def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes, sin puntuación, sin espacios extra."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()

_PALABRAS_MENU = {
    "menu", "manu", "volver", "inicio", "start",
    "hola", "buenas", "hey", "0", "salir", "atras",
}

def es_menu(texto: str) -> bool:
    return normalizar(texto) in _PALABRAS_MENU

def extraer_numero(texto: str) -> int | None:
    t = texto.strip()
    return int(t) if t.isdigit() else None

def contiene_alguna(texto_norm: str, palabras: list[str]) -> bool:
    return any(p in texto_norm for p in palabras)
