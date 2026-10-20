"""backend/ia/chat.py · Chat "Consultar a la IA" con MedGemma (Ollama, local).

Rutas (requieren sesión; las protege verificar_acceso de app.py):
    GET  /api/ia/estado    -> {"ia": bool, "modelo": str}   (además precarga Whisper)
    POST /api/ia/consulta  -> {"respuesta": str, "tipo": str}

Usa ia.medgemma.consultar_detalle, que:
    1. bloquea preguntas de diagnóstico, tratamiento o medicación sin consultar al modelo;
    2. responde exacto (sin modelo) "qué falta", "qué lo haría subir" y "por qué este color";
    3. para el resto consulta a MedGemma con el caso, el color y el historial del chat;
    4. revisa la respuesta del modelo y la bloquea si diagnostica o indica tratamiento.
Si Ollama no responde, devuelve una respuesta armada (no un error).

En app.py:
    from ia.chat import bp as chat_ia_bp
    app.register_blueprint(chat_ia_bp)
"""
from flask import Blueprint, current_app, jsonify, request

from . import medgemma as ia
from . import transcripcion

bp = Blueprint("iachat", __name__, url_prefix="/api/ia")

MAX_PREGUNTA = 1000


def _json():
    j = request.get_json(silent=True)
    return j if isinstance(j, dict) else {}


@bp.get("/estado")
def estado():
    transcripcion.precargar_en_segundo_plano()   # deja Whisper listo para el primer dictado
    return jsonify(ia=ia.disponible(), modelo=ia.MODELO)


@bp.post("/consulta")
def consulta():
    j = _json()
    pregunta = str(j.get("pregunta", "")).strip()
    if not pregunta:
        return jsonify(error="Pregunta vacía."), 400
    if len(pregunta) > MAX_PREGUNTA:
        return jsonify(error="La pregunta es demasiado larga."), 400
    historial = j.get("historial") if isinstance(j.get("historial"), list) else []
    contexto = j.get("contexto") if isinstance(j.get("contexto"), dict) else {}
    datos = j.get("datos") if isinstance(j.get("datos"), dict) else {}
    try:
        resp, tipo = ia.consultar_detalle(
            pregunta, datos, str(j.get("sugerencia", "")), contexto,
            historial, str(j.get("relato", "")), bool(j.get("sin_ia")))
        return jsonify(respuesta=resp, tipo=tipo)
        # Registra el fallo sin incluir el relato ni detalles internos
    # en la respuesta que recibe el navegador.
    except Exception:
        current_app.logger.error("ERROR_CONSULTA_IA")
        return jsonify({
            "ok": False,
            "codigo": "IA_NO_DISPONIBLE",
            "mensaje": "No se pudo completar la consulta a la IA. Intentá nuevamente."
        }), 503
