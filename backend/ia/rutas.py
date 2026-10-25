"""backend/ia/rutas.py · Rutas de IA (Blueprint de Flask).

En app.py:
    from ia.rutas import bp as ia_bp
    app.register_blueprint(ia_bp)
"""
import hashlib
import threading
import time

from flask import Blueprint, jsonify, request

from . import medgemma as ia
from . import transcripcion
from . import trazabilidad as traza

bp = Blueprint("ia", __name__, url_prefix="/api")
bp.register_blueprint(traza.bp)          # /api/traza/... (registro, constancia, CSV)

# Precarga MedGemma en segundo plano al arrancar Flask (no demora el arranque)
threading.Thread(target=ia.precalentar, daemon=True).start()


def _json():
    return request.get_json(silent=True) or {}


@bp.get("/estado")
def estado():
    # la pantalla consulta el estado al abrirse: aprovechamos para dejar cargado Whisper
    transcripcion.precargar_en_segundo_plano()
    return jsonify(ia=ia.disponible(), modelo=ia.MODELO)


@bp.post("/analizar")
def analizar():
    texto = str(_json().get("texto", "")).strip()
    if not texto:
        return jsonify(error="El relato está vacío."), 400
    if len(texto) > 4000:
        return jsonify(error="El relato es demasiado largo (máx. 4000 caracteres)."), 400
    j = _json()
    t0 = time.time()
    try:
        d = ia.extraer(texto)
    except Exception as e:
        traza.registrar_desde_pedido(j, "ia_no_disponible", {"etapa": "extracción", "error": str(e)[:300]})
        return jsonify(error=f"MedGemma no respondió: {e}"), 503
    traza.registrar_desde_pedido(j, "extraccion_ia", {
        "modo": "con IA", "relato": texto, "relato_sha256": hashlib.sha256(texto.encode()).hexdigest(),
        "modelo": ia.MODELO, "segundos": round(time.time() - t0, 1),
        "resultado": {k: v for k, v in d.items() if not k.startswith("_") and v not in (None, False, "")}})
    return jsonify(d)


@bp.post("/sugerir")
def sugerir():
    j = _json()
    t0 = time.time()
    try:
        r = ia.sugerir(j.get("datos", {}), str(j.get("relato", "")))
    except Exception as e:
        traza.registrar_desde_pedido(j, "ia_no_disponible", {"etapa": "sugerencia", "error": str(e)[:300]})
        return jsonify(error=f"MedGemma no respondió: {e}"), 503
    if r.get("insuficiente"):
        traza.registrar_desde_pedido(j, "sugerencia_insuficiente", {})
    else:
        traza.registrar_desde_pedido(j, "sugerencia_ia", {
            "color": r.get("color"), "motivos": r.get("motivos"), "fuentes": r.get("fuentes"),
            "descartados": r.get("descartados"), "modelo": ia.MODELO, "segundos": round(time.time() - t0, 1)})
    return jsonify(r)


@bp.post("/consulta")
def consulta():
    j = _json()
    pregunta = str(j.get("pregunta", "")).strip()
    if not pregunta:
        return jsonify(error="Pregunta vacía."), 400
    try:
        historial = j.get("historial") if isinstance(j.get("historial"), list) else []
        contexto = j.get("contexto") if isinstance(j.get("contexto"), dict) else {}
        resp, tipo = ia.consultar_detalle(pregunta, j.get("datos", {}), j.get("sugerencia", ""),
                                          contexto, historial, str(j.get("relato", "")), bool(j.get("sin_ia")))
        traza.registrar_desde_pedido(j, "chat", {"pregunta": pregunta, "respuesta": resp,
                                                 "tipo_respuesta": tipo, "color_en_pantalla": j.get("sugerencia", "")})
        return jsonify(respuesta=resp, tipo=tipo)
    except Exception as e:
        return jsonify(error=f"MedGemma no respondió: {e}"), 503
