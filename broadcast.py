"""
broadcast.py — Enviá un mensaje a todos los usuarios del bot TUCE.

Uso:
    python broadcast.py
    python broadcast.py "Tu mensaje personalizado con {nombre}"

El placeholder {nombre} se reemplaza con el nombre de cada usuario.
"""

import sys
import requests

BRIDGE_URL = "http://localhost:3000/broadcast"

MENSAJE_DEFAULT = (
    "👋 ¡Hola {nombre}! Soy *Alma TUCE* 🎓\n\n"
    "¿Necesitás info sobre horarios, materias o trámites de la UNPAZ? "
    "Escribime cuando quieras o mandá *MENÚ* para ver todo lo que puedo hacer."
)

def main():
    mensaje = sys.argv[1] if len(sys.argv) > 1 else MENSAJE_DEFAULT

    print("📤 Iniciando broadcast...")
    print(f"📝 Mensaje:\n{mensaje}\n")
    confirmacion = input("¿Confirmar envío? (s/n): ").strip().lower()
    if confirmacion != "s":
        print("❌ Cancelado.")
        return

    try:
        resp = requests.post(BRIDGE_URL, json={"mensaje": mensaje}, timeout=3600)
        resp.raise_for_status()
        data = resp.json()
        print(f"\n✅ Broadcast finalizado — Enviados: {data['enviados']} | Errores: {data['errores']}")
    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar al bridge. ¿Está corriendo whatsapp_bridge.js?")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
