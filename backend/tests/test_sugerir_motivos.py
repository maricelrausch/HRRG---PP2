"""
[Dario 30/10] MedGemma a veces lista como motivo un signo vital NORMAL («TA sistólica 120 mmHg»).
No explica el color, así que sugerir() lo saca de los motivos (queda en «normales_omitidos»).
No llama a Ollama: se reemplaza la respuesta del modelo.
Ejecutar desde backend:  python -m pytest -q tests/test_sugerir_motivos.py
"""
import ia.medgemma as ia

DATOS = {"motivo_categoria": "Trauma", "br_trauma": True, "ta_sistolica": 120, "ta_diastolica": 80,
         "frecuencia_cardiaca": 125, "frecuencia_respiratoria": 16, "saturacion_o2": 98, "temperatura": 36.5}


def _sugerir(monkeypatch, motivos):
    monkeypatch.setattr(ia, "_chat_json", lambda *a, **k: {"color": "NARANJA", "motivos": motivos})
    return ia.sugerir(DATOS, "me caí y me golpeé la cabeza")


def test_saca_los_signos_normales(monkeypatch):
    r = _sugerir(monkeypatch, ["Mecanismo de trauma", "Golpe en la cabeza", "TA sistólica 120 mmHg",
                               "TA diastólica 80 mmHg", "Temperatura 36,5 °C"])
    assert r["motivos"] == ["Mecanismo de trauma", "Golpe en la cabeza"]
    assert r["normales_omitidos"] == ["TA sistólica 120 mmHg", "TA diastólica 80 mmHg", "Temperatura 36,5 °C"]
    assert len(r["fuentes"]) == 2          # una fuente por motivo que queda
    assert r["color"] == "NARANJA"


def test_deja_los_signos_alterados_y_las_aclaraciones(monkeypatch):
    r = _sugerir(monkeypatch, ["Frecuencia cardíaca 125 lpm", "Taquicardia", "Sin fiebre"])
    assert r["motivos"] == ["Frecuencia cardíaca 125 lpm", "Taquicardia", "Sin fiebre"]
    assert r["normales_omitidos"] == []
