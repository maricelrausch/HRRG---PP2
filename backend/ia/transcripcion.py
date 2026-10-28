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
import wave

from flask import Blueprint, jsonify, request

MODELO_WHISPER = os.environ.get("WHISPER_MODELO", "small")   # tiny | base | small | medium
# cpu (por defecto, siempre funciona) | cuda (placa NVIDIA: requiere instalar las librerías CUDA/cuDNN) | auto
DISPOSITIVO = os.environ.get("WHISPER_DISPOSITIVO", "cpu")
# Hilos de CPU para Whisper: la mitad de los núcleos lógicos, con un máximo de 4.
# Medido con scripts/probar_whisper.py (26/10): con 4 hilos es más rápido que con 6, 8 u 11;
# más hilos caen en los núcleos de eficiencia y frenan al resto. Se cambia con WHISPER_HILOS.
HILOS = int(os.environ.get("WHISPER_HILOS") or min(4, max(2, (os.cpu_count() or 4) // 2)))
MAX_BYTES = 25 * 1024 * 1024
# Whisper imita el estilo y el vocabulario de este texto: conviene que sean frases
# como las que se dictan en guardia, no una lista de palabras sueltas.
PROMPT = ("Relato de ingreso a guardia. Paciente de 45 años, llega con dolor abdominal, "
          "náuseas y vómitos desde ayer. Refiere fiebre, dolor de pecho, dolor de cabeza "
          "y falta de aire. Antecedentes de diabetes e hipertensión.")
# Cuántas opciones compara antes de elegir cada palabra: 1 = más rápido, 5 = más preciso.
BEAM = int(os.environ.get("WHISPER_BEAM") or 5)

bp = Blueprint("voz", __name__, url_prefix="/api")
_modelo = None
_dispositivo = None
_bloqueo = threading.Lock()
_turno = threading.Lock()        # un audio a la vez: dos transcripciones juntas se frenan entre sí


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
                _modelo = WhisperModel(MODELO_WHISPER, device=dev, compute_type=tipo,
                                       cpu_threads=HILOS)
                _dispositivo = dev
                print(f"[Whisper] modelo '{MODELO_WHISPER}' cargado en {dev.upper()}"
                      + (f" con {HILOS} hilos" if dev == "cpu" else ""))
                return _modelo
            except Exception as e:
                ultimo = e
                print(f"[Whisper] no se pudo usar {dev}: {e}")
        raise RuntimeError(f"No se pudo cargar Whisper: {ultimo}")


def _precalentar():
    """Carga Whisper y hace una transcripción de prueba: la primera siempre es mucho más
    lenta (prepara memoria y cálculos internos). Así no la paga el primer paciente."""
    try:
        modelo = _cargar()
        import numpy as np
        t0 = time.time()
        with _turno:
            segs, _ = modelo.transcribe(np.zeros(2 * 16000, dtype=np.float32), language="es",
                                        beam_size=BEAM, vad_filter=False,
                                        without_timestamps=True, initial_prompt=PROMPT)
            list(segs)
        print(f"[Whisper] listo para dictar (calentamiento: {time.time() - t0:.1f} s)")
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


def _leer_wav(ruta):
    """El dictado por trozos manda WAV 16 kHz mono 16 bits: se lee directo, sin ffmpeg."""
    try:
        import numpy as np
        with wave.open(ruta, "rb") as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (16000, 1, 2):
                return None
            pcm = w.readframes(w.getnframes())
        return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return None


def _transcribir(ruta, previo=""):
    """previo: lo último ya transcripto del mismo dictado, para que Whisper siga el hilo
    entre un trozo y el siguiente (puntuación, nombres, términos médicos)."""
    audio = _leer_wav(ruta) if ruta.endswith(".wav") else None
    prompt = (PROMPT + " " + previo[-200:]).strip() if previo else PROMPT
    with _turno:
        segmentos, info = _cargar().transcribe(
            ruta if audio is None else audio, language="es", beam_size=BEAM, vad_filter=True,
            condition_on_previous_text=False, without_timestamps=True, initial_prompt=prompt)
        texto = " ".join(s.text.strip() for s in segmentos).strip()   # se decodifica acá adentro
    return texto, info


@bp.post("/transcribir")
def transcribir():
    audio = request.files.get("audio")
    if audio is None:
        return jsonify(error="Falta el audio."), 400
    previo = (request.form.get("previo") or "")[-400:]
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
            texto, info = _transcribir(ruta, previo)
        except Exception as e:
            if _dispositivo != "cuda":
                raise
            print(f"[Whisper] falló en CUDA ({e}); paso a CPU")   # p. ej. faltan librerías de NVIDIA
            _cargar(forzar_cpu=True)
            texto, info = _transcribir(ruta, previo)
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
