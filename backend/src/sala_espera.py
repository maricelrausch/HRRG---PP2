# Lista de espera para la sala y cualquier celular (Darío).
# GET /api/sala/espera → pública y de solo lectura. No pide sesión, por eso NO devuelve
# DNI, motivo, código de paciente ni profesional: solo los últimos 4 caracteres del
# episodio, el color y cuánto lleva esperando. Lee los mismos datos que /api/demo/espera.
# Se puede apagar con la variable de entorno HRRG_SALA_PUBLICA=0.
import os
import sqlite3
import logging
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

from src.registro import listar_espera_demo
from src.reglas_hospital import leer_tiempos

bp = Blueprint("sala", __name__)
logger = logging.getLogger(__name__)

# Orden por color, igual que la pantalla En espera.
# Sin AZUL: el equipo lo sacó. Sin color = todavía no pasó por el triage: no entra en la lista.
# [Dario 29/10 · Etapa C] El tiempo objetivo de cada color se lee de la configuración de reglas.
PRIORIDAD = {"ROJO": 0, "NARANJA": 1, "AMARILLO": 2, "VERDE": 3}


def codigo_corto(codigo_episodio):
    # Mismo criterio que el DNI enmascarado: se muestra solo el final.
    return (codigo_episodio or "")[-4:].upper()


def leer_espera_completa(ruta_base):
    # listar_espera_demo pagina de a 100 como máximo: se recorren todas las páginas.
    episodios, desplazamiento = [], 0
    while True:
        pagina = listar_espera_demo(ruta_base=ruta_base, limite=100, desplazamiento=desplazamiento)
        episodios += pagina["episodios"]
        desplazamiento += len(pagina["episodios"])
        if not pagina["episodios"] or desplazamiento >= pagina["total"]:
            return episodios


@bp.route("/api/sala/espera", methods=["GET"])
def sala_espera():
    if os.environ.get("HRRG_SALA_PUBLICA", "1") == "0":
        return jsonify({"ok": False, "mensaje": "La lista pública está deshabilitada."}), 404

    try:
        episodios = leer_espera_completa(current_app.config["BASE_REGISTRO_DEMO"])
    except (sqlite3.Error, ValueError):
        logger.error("ERROR_SALA_ESPERA")
        return jsonify({"ok": False, "mensaje": "No se pudo consultar la lista de espera."}), 500

    ahora = datetime.now(timezone.utc)
    objetivo = leer_tiempos(current_app.config.get("BASE_REGLAS"))
    lista = []
    for ep in episodios:
        color = ep.get("color_final")
        if color not in PRIORIDAD:
            continue
        desde = datetime.fromisoformat(ep["en_espera_desde"])
        if desde.tzinfo is None:
            desde = desde.replace(tzinfo=timezone.utc)
        lista.append({
            "codigo": codigo_corto(ep["codigo_episodio"]),
            "color": color,
            "espera_seg": max(0, int((ahora - desde).total_seconds())),
"objetivo_min": objetivo[color],
            # [Barby 30/10] Para pantallas externas de la sala: hora del triage y si superó el tiempo.
            "en_espera_desde": desde.isoformat(),
            "vencido": color != "ROJO" and (ahora - desde).total_seconds() / 60 > objetivo[color],
        })

    # Primero por color (ROJO arriba) y después por quien espera más.
    lista.sort(key=lambda x: (PRIORIDAD[x["color"]], -x["espera_seg"]))

    respuesta = jsonify({"ok": True, "episodios": lista, "tiempos": objetivo})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200


# ------------------------------------------------
# [Propuesta Barby 30/10] Código QR para abrir la lista de espera desde un celular.
#   GET /api/sala/qr                    → las direcciones (JSON)
#   GET /api/sala/qr.svg?destino=sala   → QR de la pantalla de sala (sala.html)
#   [31/10] Se sacó el QR al JSON (destino=datos): el equipo acordó que no hacía falta.
# Es público como la lista (no tiene datos personales). Si la PC se abrió como 127.0.0.1
# (localhost), el celular no podría entrar: se usa la IP de la PC en la red local.
# ------------------------------------------------
import io
import socket

from flask import request

DESTINOS_QR = {"sala": "/sala.html"}


def _ip_local():
    """IP de la PC en la red local. No envía nada: solo pregunta qué interfaz usaría."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def direccion_base():
    """Dirección con la que un celular de la misma red llega al sistema (http://IP:puerto)."""
    host = request.headers.get("X-Forwarded-Host") or request.host
    esquema = request.headers.get("X-Forwarded-Proto") or request.scheme
    nombre, _, puerto = host.rpartition(":") if host.count(":") == 1 else (host, "", "")
    if nombre in ("127.0.0.1", "localhost"):
        ip = _ip_local()
        if ip and not ip.startswith("127."):
            host = ip + (":" + puerto if puerto else "")
    return f"{esquema}://{host}"


@bp.route("/api/sala/qr", methods=["GET"])
def sala_qr_datos():
    if os.environ.get("HRRG_SALA_PUBLICA", "1") == "0":
        return jsonify({"ok": False, "mensaje": "La lista pública está deshabilitada."}), 404
    base = direccion_base()
    local = any(x in base for x in ("://127.", "://localhost"))
    respuesta = jsonify({
        "ok": True,
        "direcciones": {k: base + v for k, v in DESTINOS_QR.items()},
        "aviso": ("No se encontró la IP de la PC en la red: el celular no va a poder entrar. "
                  "Conectá la PC al Wi-Fi.") if local else None,
    })
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200


@bp.route("/api/sala/qr.svg", methods=["GET"])
def sala_qr_svg():
    if os.environ.get("HRRG_SALA_PUBLICA", "1") == "0":
        return jsonify({"ok": False, "mensaje": "La lista pública está deshabilitada."}), 404
    destino = request.args.get("destino", "sala")
    if destino not in DESTINOS_QR or set(request.args) - {"destino", "t"}:   # t = evita caché del navegador
        return jsonify({"ok": False, "mensaje": "Usá ?destino=sala."}), 400
    try:
        import segno
    except ImportError:
        return jsonify({"ok": False, "mensaje": "Falta instalar segno: python -m pip install -r requirements.txt"}), 503
    salida = io.BytesIO()
    segno.make(direccion_base() + DESTINOS_QR[destino], error="m").save(
        salida, kind="svg", scale=10, border=2, dark="#1B2030", light="#FFFFFF")
    respuesta = current_app.response_class(salida.getvalue(), mimetype="image/svg+xml")
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200
