"""backend/transcripcion.py · Dictado de voz LOCAL con Whisper (faster-whisper).

Funciona con cualquier navegador: el navegador solo graba el audio y lo manda acá.
La transcripción se hace en esta máquina; el audio no sale a internet.
(La primera vez se descarga el modelo de Whisper; después funciona sin conexión.)

En app.py:
    from ia.transcripcion import bp as voz_bp
    app.register_blueprint(voz_bp)
"""
import os
import tempfile

from flask import Blueprint, jsonify, request

MODELO_WHISPER = os.environ.get("WHISPER_MODELO", "small")   # tiny | base | small | medium
MAX_BYTES = 25 * 1024 * 1024
PROMPT = ("Relato de ingreso a guardia: dolor abdominal, dolor de pecho, náuseas, vómitos, "
          "fiebre, presión arterial, frecuencia cardíaca, saturación, diabetes.")

bp = Blueprint("voz", __name__, url_prefix="/api")
_modelo = None


def _cargar():
    """Carga Whisper una sola vez (la primera transcripción tarda más)."""
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        _modelo = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")
    return _modelo


@bp.post("/transcribir")
def transcribir():
    audio = request.files.get("audio")
    if audio is None:
        return jsonify(error="Falta el audio."), 400
    datos = audio.read()
    if not datos:
        return jsonify(error="El audio está vacío."), 400
    if len(datos) > MAX_BYTES:
        return jsonify(error="El audio es demasiado largo."), 413

    sufijo = os.path.splitext(audio.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as f:
        f.write(datos)
        ruta = f.name
    try:
        segmentos, info = _cargar().transcribe(
            ruta, language="es", beam_size=1, vad_filter=True, initial_prompt=PROMPT)
        texto = " ".join(s.text.strip() for s in segmentos).strip()
        return jsonify(texto=texto, segundos=round(info.duration, 1), modelo=MODELO_WHISPER)
    except Exception as e:
        return jsonify(error=f"No se pudo transcribir: {e}"), 503
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
