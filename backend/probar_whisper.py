"""backend/probar_whisper.py · Mide qué configuración de Whisper es más rápida EN ESTA PC.

Uso (con la app cerrada, para que nada más use la CPU):
    cd C:\\Users\\LENOVO\\Documents\\HRRG---PP2\\backend
    python probar_whisper.py                 # genera una frase de prueba con la voz de Windows
    python probar_whisper.py mi_audio.wav    # o usa un audio tuyo (wav/mp3/webm)

Prueba modelos, hilos y beam; cada combinación se mide 3 veces (descartando el arranque)
y muestra el tiempo promedio y el texto que salió.
"""
import os
import subprocess
import sys
import tempfile
import time

from faster_whisper import WhisperModel

FRASE = "Paciente de 30 años, llega con dolor de cabeza leve desde esta mañana."
PROMPT = ("Relato de ingreso a guardia. Paciente de 45 años, llega con dolor abdominal, "
          "náuseas y vómitos desde ayer. Refiere fiebre, dolor de pecho, dolor de cabeza "
          "y falta de aire. Antecedentes de diabetes e hipertensión.")

MODELOS = ["base", "small"]
HILOS = sorted({4, 6, 8, max(2, (os.cpu_count() or 4) // 2)})
BEAMS = [1, 5]
REPETICIONES = 3


def audio_de_prueba():
    """Crea un WAV con la frase usando la voz en español de Windows."""
    ruta = os.path.join(tempfile.gettempdir(), "whisper_prueba.wav")
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like 'es*' }} | Select-Object -First 1
if ($v) {{ $s.SelectVoice($v.VoiceInfo.Name) }} else {{ Write-Host 'AVISO: no hay voz en español instalada' }}
$s.SetOutputToWaveFile('{ruta}')
$s.Speak('{FRASE}')
$s.Dispose()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    return ruta


def medir(modelo, audio, beam):
    tiempos, texto = [], ""
    for i in range(REPETICIONES + 1):
        t0 = time.time()
        segs, info = modelo.transcribe(audio, language="es", beam_size=beam, vad_filter=True,
                                       condition_on_previous_text=False,
                                       without_timestamps=True, initial_prompt=PROMPT)
        texto = " ".join(s.text.strip() for s in segs).strip()
        if i:                                  # la primera vuelta es el arranque en frío
            tiempos.append(time.time() - t0)
    return sum(tiempos) / len(tiempos), info.duration, texto


def main():
    audio = sys.argv[1] if len(sys.argv) > 1 else audio_de_prueba()
    print(f"Audio: {audio}")
    print(f"CPU: {os.cpu_count()} hilos lógicos\n")
    print(f"{'modelo':7} {'hilos':>5} {'beam':>4} {'seg':>6} {'x tiempo real':>13}  texto")
    print("-" * 100)
    for nombre in MODELOS:
        for h in HILOS:
            t0 = time.time()
            m = WhisperModel(nombre, device="cpu", compute_type="int8", cpu_threads=h)
            carga = time.time() - t0
            for beam in BEAMS:
                seg, dur, texto = medir(m, audio, beam)
                print(f"{nombre:7} {h:>5} {beam:>4} {seg:6.2f} {seg / dur:13.2f}  {texto}")
            print(f"{'':7} (carga del modelo: {carga:.1f} s)")
            del m
    print("\n'x tiempo real' menor a 0.5 = el dictado por trozos se siente fluido.")


if __name__ == "__main__":
    main()
