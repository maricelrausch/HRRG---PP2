"""backend/rutas_ia.py · Rutas de IA (Blueprint de Flask).

En app.py:
    from ia.rutas import bp as ia_bp
    app.register_blueprint(ia_bp)
y BORRAR la ruta /api/analizar vieja (si quedan las dos, Flask usa la primera).
"""
from flask import Blueprint, jsonify, request

from . import medgemma as ia

bp = Blueprint("ia", __name__, url_prefix="/api")


def _json():
    return request.get_json(silent=True) or {}


@bp.get("/estado")
def estado():
    return jsonify(ia=ia.disponible(), modelo=ia.MODELO)


@bp.post("/analizar")
def analizar():
    texto = str(_json().get("texto", "")).strip()
    if not texto:
        return jsonify(error="El relato está vacío."), 400
    if len(texto) > 4000:
        return jsonify(error="El relato es demasiado largo (máx. 4000 caracteres)."), 400
    try:
        return jsonify(ia.extraer(texto))
    except Exception as e:
        return jsonify(error=f"MedGemma no respondió: {e}"), 503


@bp.post("/sugerir")
def sugerir():
    try:
        j = _json()
        return jsonify(ia.sugerir(j.get("datos", {}), str(j.get("relato", ""))))
    except Exception as e:
        return jsonify(error=f"MedGemma no respondió: {e}"), 503


@bp.post("/consulta")
def consulta():
    j = _json()
    pregunta = str(j.get("pregunta", "")).strip()
    if not pregunta:
        return jsonify(error="Pregunta vacía."), 400
    try:
        return jsonify(respuesta=ia.consultar(pregunta, j.get("datos", {}), j.get("sugerencia", "")))
    except Exception as e:
        return jsonify(error=f"MedGemma no respondió: {e}"), 503
