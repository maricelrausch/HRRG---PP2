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
