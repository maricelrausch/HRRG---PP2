"""backend/ia/transcripcion.py · Dictado de voz LOCAL con Whisper (faster-whisper).

Funciona con cualquier navegador: el navegador solo graba el audio y lo manda acá.
La transcripción se hace en esta máquina; el audio no sale a internet.
(La primera vez se descarga el modelo de Whisper; después funciona sin conexión.)

En app.py:
    from ia.transcripcion import bp as voz_bp
    app.register_blueprint(voz_bp)
"""
import os
import tempfile
import threading
import time

from flask import Blueprint, jsonify, request

MODELO_WHISPER = os.environ.get("WHISPER_MODELO", "small")   # tiny | base | small | medium
# cpu (por defecto, siempre funciona) | cuda (placa NVIDIA: requiere instalar las librerías CUDA/cuDNN) | auto
DISPOSITIVO = os.environ.get("WHISPER_DISPOSITIVO", "cpu")
MAX_BYTES = 25 * 1024 * 1024
PROMPT = ("Relato de ingreso a guardia: dolor abdominal, dolor de pecho, náuseas, vómitos, "
          "fiebre, presión arterial, frecuencia cardíaca, saturación, diabetes.")

bp = Blueprint("voz", __name__, url_prefix="/api")
_modelo = None
_dispositivo = None
_bloqueo = threading.Lock()


def _cargar(forzar_cpu=False):
    """Carga Whisper una sola vez. Prueba la placa de video (CUDA) y si no está disponible usa la CPU."""
    global _modelo, _dispositivo
    with _bloqueo:
        if _modelo is not None and not (forzar_cpu and _dispositivo != "cpu"):
            return _modelo
        from faster_whisper import WhisperModel
        intentos = [("cpu", "int8")] if (forzar_cpu or DISPOSITIVO == "cpu") else [("cuda", "float16"), ("cpu", "int8")]
        if DISPOSITIVO == "cuda" and not forzar_cpu:
            intentos = [("cuda", "float16")]
        ultimo = None
        for dev, tipo in intentos:
            try:
                _modelo = WhisperModel(MODELO_WHISPER, device=dev, compute_type=tipo)
                _dispositivo = dev
                print(f"[Whisper] modelo '{MODELO_WHISPER}' cargado en {dev.upper()}")
                return _modelo
            except Exception as e:
                ultimo = e
                print(f"[Whisper] no se pudo usar {dev}: {e}")
        raise RuntimeError(f"No se pudo cargar Whisper: {ultimo}")


def _precalentar():
    try:
        _cargar()
    except Exception as e:
        print(f"[Whisper] precarga fallida: {e}")


_precargando = False


def precargar_en_segundo_plano():
    """Se llama cuando se abre la app (/api/estado): Whisper queda cargado antes del primer dictado.
    Funciona igual con debug=True o debug=False."""
    global _precargando
    if _modelo is None and not _precargando:
        _precargando = True
        threading.Thread(target=_precalentar, daemon=True).start()


def _transcribir(ruta):
    segmentos, info = _cargar().transcribe(
        ruta, language="es", beam_size=1, vad_filter=True,
        condition_on_previous_text=False, initial_prompt=PROMPT)
    return " ".join(s.text.strip() for s in segmentos).strip(), info


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
    t0 = time.time()
    try:
        try:
            texto, info = _transcribir(ruta)
        except Exception as e:
            if _dispositivo != "cuda":
                raise
            print(f"[Whisper] falló en CUDA ({e}); paso a CPU")   # p. ej. faltan librerías de NVIDIA
            _cargar(forzar_cpu=True)
            texto, info = _transcribir(ruta)
        demora = round(time.time() - t0, 1)
        print(f"[Whisper] {info.duration:.1f} s de audio transcriptos en {demora} s ({_dispositivo})")
        return jsonify(texto=texto, segundos=round(info.duration, 1), demora=demora,
                       modelo=MODELO_WHISPER, dispositivo=_dispositivo)
    except Exception as e:
        return jsonify(error=f"No se pudo transcribir: {e}"), 503
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
