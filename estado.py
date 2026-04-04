# estado.py — Estado conversacional por usuario (WhatsApp)
# Cada usuario tiene: sección activa, sub-paso, contador de errores,
# última sección (para ATRÁS) y datos temporales.

MAX_ERRORES = 3

_estados: dict = {}


def get(uid: str) -> dict:
    return _estados.get(uid, _default())

def _default() -> dict:
    return {"seccion": None, "esperando": None, "errores": 0, "ultima": None, "datos": {}}

def entrar(uid: str, seccion: str, esperando: str = None, datos: dict = None):
    """Entra en una sección nueva. Guarda la anterior como 'ultima' para ATRÁS."""
    anterior = _estados.get(uid, {}).get("seccion")
    _estados[uid] = {
        "seccion":   seccion,
        "esperando": esperando,
        "errores":   0,
        "ultima":    anterior,
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
    _estados.pop(uid, None)

def volver_atras(uid: str) -> str | None:
    """Restaura la última sección. Devuelve el nombre de esa sección o None."""
    e = get(uid)
    ultima = e.get("ultima")
    if ultima:
        entrar(uid, ultima)
    else:
        salir(uid)
    return ultima

def sumar_error(uid: str) -> bool:
    """Incrementa errores. Devuelve True si se alcanzó el límite."""
    e = get(uid)
    e["errores"] = e.get("errores", 0) + 1
    _estados[uid] = e
    return e["errores"] >= MAX_ERRORES
