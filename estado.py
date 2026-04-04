# estado.py — Manejo de estado conversacional por usuario (WhatsApp)
# Cada usuario tiene: sección activa, sub-paso, contador de errores y datos temporales.

MAX_ERRORES = 3

_estados: dict = {}


def get(uid: str) -> dict:
    return _estados.get(uid, _default())

def _default() -> dict:
    return {"seccion": None, "esperando": None, "errores": 0, "datos": {}}

def entrar(uid: str, seccion: str, esperando: str = None, datos: dict = None):
    """Entra en una sección nueva, resetea errores."""
    _estados[uid] = {
        "seccion":   seccion,
        "esperando": esperando,
        "errores":   0,
        "datos":     datos or {},
    }

def avanzar(uid: str, esperando: str = None, datos: dict = None):
    """Avanza dentro de la sección actual, resetea errores."""
    e = get(uid)
    e["esperando"] = esperando
    e["errores"]   = 0
    if datos:
        e["datos"].update(datos)
    _estados[uid] = e

def salir(uid: str):
    """Vuelve al estado inicial (menú principal)."""
    _estados.pop(uid, None)

def sumar_error(uid: str) -> bool:
    """Incrementa errores. Devuelve True si se alcanzó el límite."""
    e = get(uid)
    e["errores"] = e.get("errores", 0) + 1
    _estados[uid] = e
    return e["errores"] >= MAX_ERRORES
