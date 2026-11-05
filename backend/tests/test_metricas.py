"""
Pruebas de evaluacion/metricas.py y evaluacion/reglas_seguridad.py (sin Ollama).

Ejecutar desde la carpeta backend:   python -m pytest -q tests/test_metricas.py
"""
import pytest

from evaluacion import metricas as M
from evaluacion import reglas_seguridad as RS
from evaluacion import evaluar as E


# ---------------------------------------------------------------- extracción
@pytest.mark.parametrize("esp,pred,tipo,res", [
    (40, 40, "numero", "VP"),
    (36.8, "36,8", "numero", "VP"),
    (36.8, 37.5, "numero", "ERR"),
    (None, 95, "numero", "FP"),          # alucinación
    (112, None, "numero", "FN"),         # omisión
    (None, None, "numero", "VN"),
    (0, 0, "numero", "VP"),              # cero es un valor, no un vacío
    (True, True, "booleano", "VP"),
    (False, True, "booleano", "FP"),
    ("Tórax", "pecho", "texto", "VP"),
    ("Abdomen", "panza, arriba", "texto", "VP"),
    ("Tórax", "Abdomen", "texto", "ERR"),
    ("Dolor torácico", "dolor torácico", "categoria", "VP"),
])
def test_comparar_campo(esp, pred, tipo, res):
    tol = 0.1 if isinstance(esp, float) else 0
    assert M.comparar_campo(esp, pred, tipo, tol) == res


def test_resumen_extraccion_cuenta_err_como_fp_y_fn():
    filas = [{"campo": "fc", "grupo": "e", "resultado": r} for r in ("VP", "VP", "ERR", "FP", "FN", "VN")]
    m = M.resumir_extraccion(filas)["micro"]
    assert (m["vp"], m["fp"], m["fn"], m["vn"]) == (2, 2, 2, 1)
    assert m["precision"] == pytest.approx(0.5) and m["recall"] == pytest.approx(0.5)
    assert m["tasa_alucinacion"] == pytest.approx(0.5)      # 1 FP de 2 campos que debían quedar vacíos


# ---------------------------------------------------------------- clasificación
def test_kappa_perfecto_y_azar():
    r = ["ROJO", "NARANJA", "AMARILLO", "VERDE"]
    assert M.kappa_cohen(r, r) == pytest.approx(1.0)
    assert M.kappa_cohen(r, r, ponderacion="lineal") == pytest.approx(1.0)
    # siempre el mismo color -> kappa 0
    assert M.kappa_cohen(r, ["AMARILLO"] * 4) == pytest.approx(0.0)


def test_kappa_conocido():
    # ejemplo clásico 2 clases: po = 0.7, pe = 0.5 -> kappa = 0.4
    reales = ["ROJO"] * 50 + ["NARANJA"] * 50
    pred = ["ROJO"] * 35 + ["NARANJA"] * 15 + ["ROJO"] * 15 + ["NARANJA"] * 35
    assert M.kappa_cohen(reales, pred, clases=["ROJO", "NARANJA"]) == pytest.approx(0.4)


def test_subtriage_y_recall_alta_prioridad():
    reales = ["ROJO", "NARANJA", "AMARILLO", "VERDE"]
    pred = ["NARANJA", "AMARILLO", "AMARILLO", "AMARILLO"]
    s = M.sub_sobre_triage(reales, pred)
    assert s["subtriage"] == pytest.approx(0.5)
    assert s["sobretriage"] == pytest.approx(0.25)
    assert s["recall_alta_prioridad"] == pytest.approx(0.5)   # NARANJA -> AMARILLO es subtriage grave


# ---------------------------------------------------------------- voz y estadística
def test_wer():
    w = M.wer("paciente con dolor de pecho", "yente con dolor del pecho")
    assert w["sustituciones"] == 2 and w["wer"] == pytest.approx(0.4)
    assert M.wer("Dolor, de cabeza.", "dolor de cabeza")["wer"] == 0


def test_wilson_y_percentil():
    lo, hi = M.wilson(10, 10)
    assert hi == 1.0 and 0.65 < lo < 0.75          # 10/10 no es "100 % seguro"
    assert M.percentil([1, 2, 3, 4], 50) == pytest.approx(2.5)


# ---------------------------------------------------------------- reglas (alineadas con sugerencia.js)
@pytest.mark.parametrize("datos,nivel", [
    ({"saturacion_o2": 88}, 1),
    ({"br_sangrado": True, "ta_sistolica": 80}, 0),
    ({"br_sangrado": True}, 1),
    ({"glasgow": 7}, 0),
    ({"estado_conciencia": "Responde a la voz"}, 1),
    ({"dolor_intensidad": 8}, 1),
    ({"frecuencia_cardiaca": 135}, 1),
    ({"saturacion_o2": 98, "dolor_intensidad": 3}, None),
])
def test_reglas(datos, nivel):
    assert RS.nivel_reglas(datos) == nivel


def test_color_final_no_baja_del_piso():
    assert RS.color_final({"dolor_intensidad": 9}, "VERDE") == ("NARANJA", True)
    assert RS.color_final({"dolor_intensidad": 9}, "ROJO") == ("ROJO", False)


# ---------------------------------------------------------------- runner de punta a punta (sin IA)
def test_runner_validacion_y_extraccion_simulada(tmp_path):
    r = E.main(["validacion", "--salida", str(tmp_path)])
    assert r["validacion"]["recall"] == 1.0
    r = E.main(["extraccion", "--motor", "simulado", "--repeticiones", "2", "--salida", str(tmp_path)])
    m = r["extraccion"]
    assert m["micro"]["f1"] == 1.0 and m["micro"]["tasa_alucinacion"] == 0 and m["consistencia"] == 1.0
    assert list(tmp_path.glob("*/reporte.md"))


# ---------------------------------------------------------------- rendimiento, recursos y chat (sin Ollama)
from evaluacion import instrumentacion as INS


class _Resp(dict):
    def __getattr__(self, k):
        return self.get(k)


def test_medidor_ollama_anota_tokens_y_velocidad(monkeypatch):
    ollama = pytest.importorskip("ollama")

    def chat_falso(self, **kw):
        return _Resp(message=_Resp(content="{}"), prompt_eval_count=200, eval_count=50,
                     prompt_eval_duration=int(0.5e9), eval_duration=int(1e9), load_duration=int(2e9))
    monkeypatch.setattr(ollama.Client, "chat", chat_falso)
    original = ollama.Client.chat
    with INS.MedidorOllama() as med:
        med.etapa = "extraccion"
        ollama.Client().chat(model="medgemma:4b", messages=[])
        ollama.Client().chat(model="medgemma:4b", messages=[])
    assert ollama.Client.chat is original                       # se restaura al salir
    r = med.resumen()["extraccion"]
    assert r["llamadas"] == 2 and r["tok_s_generacion_p50"] == pytest.approx(50)
    assert r["tok_s_lectura_p50"] == pytest.approx(400)
    assert r["recargas"] == 1                                   # la 2.ª llamada volvió a cargar (2 s)


def test_alerta_gpu_detecta_placa_dormida():
    rec = {"gpus": [{"nombre": "RTX 4050", "vram_max_mb": 3000, "uso_max": 0, "estados": {"P8": 10}}]}
    assert INS.alerta_gpu(rec, {"extraccion": {"tok_s_generacion_p50": 2.8}})
    assert INS.alerta_gpu(rec, {"extraccion": {"tok_s_generacion_p50": 50}}) is None


def test_chat_simulado_y_puntajes(tmp_path):
    r = E.main(["chat", "--motor", "simulado", "--salida", str(tmp_path)])
    assert r["chat"]["bloqueo_correcto"] == 1.0 and r["chat"]["n"] >= 10
    planilla = next(tmp_path.glob("*/detalle_chat.csv"))
    lineas = planilla.read_text(encoding="utf-8-sig").splitlines()
    puntuadas = [lineas[0]] + [l.rstrip(";") + ";5;4;" if i % 2 else l.rstrip(";") + ";3;5;"
                               for i, l in enumerate(lineas[1:])]
    planilla.write_text("\n".join(puntuadas), encoding="utf-8-sig")
    p = E.main(["puntajes", "--archivo", str(planilla), "--salida", str(tmp_path)])["puntajes"]
    assert p["relevancia_n"] == len(lineas) - 1
    assert 3 <= p["relevancia_media"] <= 5 and 4 <= p["fidelidad_media"] <= 5


def test_medidor_perplejidad_y_sin_soporte(monkeypatch):
    ollama = pytest.importorskip("ollama")
    import math

    def con_logprobs(self, logprobs=None, **kw):
        lp = [_Resp(token="x", logprob=math.log(0.5))] * 4 if logprobs else None
        return _Resp(message=_Resp(content="{}"), prompt_eval_count=10, eval_count=4, logprobs=lp,
                     prompt_eval_duration=int(1e9), eval_duration=int(1e9), load_duration=0, total_duration=int(3e9))
    monkeypatch.setattr(ollama.Client, "chat", con_logprobs)
    with INS.MedidorOllama() as med:
        ollama.Client().chat(model="m", messages=[])
    r = med.resumen()["general"]
    assert r["perplejidad_p50"] == pytest.approx(2.0)          # probabilidad 0,5 por token -> perplejidad 2
    assert r["solicitudes_por_minuto"] == pytest.approx(20)    # 3 s por solicitud
    assert r["primer_token_p50_s"] == pytest.approx(1.0)

    def sin_soporte(self, **kw):                                # cliente viejo: no conoce logprobs
        if "logprobs" in kw:
            raise TypeError("unexpected keyword argument 'logprobs'")
        return _Resp(message=_Resp(content="{}"), prompt_eval_count=1, eval_count=1, eval_duration=int(1e9))
    monkeypatch.setattr(ollama.Client, "chat", sin_soporte)
    with INS.MedidorOllama() as med:
        ollama.Client().chat(model="m", messages=[])
        ollama.Client().chat(model="m", messages=[])
    assert med.logprobs is False and med.resumen()["general"]["llamadas_con_logprobs"] == 0
