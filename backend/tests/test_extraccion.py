"""
Pruebas de la extracción única (src/extraccion.py) sin Ollama ni ChromaDB:
el modelo se reemplaza por respuestas fijas.

Ejecutar desde la carpeta backend:   python -m pytest -q tests/test_extraccion.py
"""
import json
from pathlib import Path

import pytest

from src import extraccion
from src.esquemas import ExtraccionIA

RAIZ = Path(__file__).resolve().parent.parent
CASOS = json.loads((RAIZ / "datos" / "casos_simulados.json").read_text(encoding="utf-8"))["casos_extraccion"]
CAMPOS = set(ExtraccionIA.model_fields)


class ModeloFalso:
    """Imita ollama.Client: devuelve las respuestas en orden y guarda las llamadas."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def chat(self, **kw):
        self.llamadas.append(kw)
        r = self.respuestas.pop(0)
        return {"message": {"content": r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)}}


@pytest.fixture
def modelo(monkeypatch):
    monkeypatch.setattr(extraccion, "USAR_RAG", False)

    def usar(*respuestas):
        falso = ModeloFalso(*respuestas)
        monkeypatch.setattr(extraccion, "_cliente", falso)
        return falso
    return usar


# ---------- 1. Con la respuesta "correcta", el resultado coincide con lo esperado ----------
@pytest.mark.parametrize("caso", CASOS, ids=[c["id"] for c in CASOS])
def test_casos_ficticios(modelo, caso):
    esperado = {k: v for k, v in caso["esperado_extraccion"].items() if k in CAMPOS}
    modelo(esperado)
    r = extraccion.extraer_datos(caso["texto"], ExtraccionIA)
    for campo in ("motivo_categoria", "tiempo_evolucion_valor", "tiempo_evolucion_unidad",
                  "dolor_localizacion", "br_sangrado"):
        if campo in esperado:
            assert r[campo] == esperado[campo], (campo, r[campo])
    assert set(r) == CAMPOS                      # siempre todos los campos, nada extra


# ---------- 2. Anclaje: lo inventado se descarta ----------
def test_descarta_tiempo_inventado(modelo):
    modelo({"tiempo_evolucion_valor": 2, "tiempo_evolucion_unidad": "horas"})
    r = extraccion.extraer_datos("Consulta por dolor de panza desde ayer.")
    assert r["tiempo_evolucion_valor"] is None and r["tiempo_evolucion_unidad"] is None


def test_media_hora(modelo):
    modelo({"tiempo_evolucion_valor": 0.5, "tiempo_evolucion_unidad": "horas"})
    r = extraccion.extraer_datos("Me duele el pecho desde hace media hora, como una presión, y estoy sudando.")
    assert (r["tiempo_evolucion_valor"], r["tiempo_evolucion_unidad"]) == (30, "minutos")
    assert r["motivo_categoria"] == "Dolor torácico" and r["dolor_localizacion"] == "Tórax"


def test_corrige_categoria_y_localizacion(modelo):
    modelo({"motivo_categoria": "Cefalea", "dolor_localizacion": "Rodilla"})
    r = extraccion.extraer_datos("Me duele mucho la panza desde hace 6 horas.")
    assert r["motivo_categoria"] == "Dolor abdominal"
    assert r["dolor_localizacion"] == "Abdomen"


def test_acepta_termino_anatomico(modelo):
    modelo({"motivo_categoria": "Dolor abdominal", "dolor_localizacion": "Epigastrio"})
    r = extraccion.extraer_datos("Me duele mucho la panza, acá arriba, desde hace unas 6 horas.")
    assert r["dolor_localizacion"] == "Epigastrio"


def test_negaciones_y_banderas_inventadas(modelo):
    modelo({"br_sangrado": True, "br_convulsion": True, "ant_diabetes": True})
    r = extraccion.extraer_datos("Mujer con dolor abdominal de 12 horas. Niega fiebre, niega sangrado.")
    assert r["br_sangrado"] is False          # negado
    assert r["br_convulsion"] is False        # no aparece
    assert r["ant_diabetes"] is False         # no aparece


def test_bandera_afirmada_se_mantiene(modelo):
    modelo({"br_sangrado": True, "ant_diabetes": True})
    r = extraccion.extraer_datos("Vómitos con sangre desde hace 1 hora. Toma pastillas para la diabetes.")
    assert r["br_sangrado"] is True and r["ant_diabetes"] is True


def test_sintomas_inventados(modelo):
    modelo({"sintomas_asociados": "Vómitos, diarrea", "alergias": "Penicilina"})
    r = extraccion.extraer_datos("Me torcí el tobillo jugando al fútbol, me duele al apoyar.")
    assert r["sintomas_asociados"] is None and r["alergias"] is None


# ---------- 3. Robustez ----------
def test_dato_personal_se_anula_sin_romper(modelo):
    modelo({"motivo_consulta": "Se llama Juan, dolor de pecho", "dolor_localizacion": "Tórax"})
    r = extraccion.extraer_datos("Dolor de pecho hace 40 minutos.")
    assert r["motivo_consulta"] is None and r["dolor_localizacion"] == "Tórax"


def test_reintenta_json_roto(modelo):
    falso = modelo("{no es json", {"motivo_consulta": "Dolor torácico"})
    r = extraccion.extraer_datos("Dolor de pecho hace 40 minutos.")
    assert r["motivo_consulta"] == "Dolor torácico" and len(falso.llamadas) == 2


def test_json_roto_dos_veces(modelo):
    modelo("{", "[]")
    with pytest.raises(ValueError):
        extraccion.extraer_datos("Dolor de pecho.")


def test_relato_vacio(modelo):
    with pytest.raises(ValueError):
        extraccion.extraer_datos("   ")


def test_ignora_campos_extra_como_signos_vitales(modelo):
    modelo({"motivo_consulta": "Dolor torácico", "edad": 62, "frecuencia_cardiaca": 112})
    r = extraccion.extraer_datos("Varón de 62 años con dolor de pecho. FC 112.")
    assert "edad" not in r and "frecuencia_cardiaca" not in r


def test_usa_esquema_y_temperatura_cero(modelo):
    falso = modelo({})
    extraccion.extraer_datos("Dolor de pecho.")
    kw = falso.llamadas[0]
    assert kw["format"] == ExtraccionIA.model_json_schema() and kw["options"]["temperature"] == 0


def test_rag_que_falla_no_rompe(modelo, monkeypatch):
    monkeypatch.setattr(extraccion, "USAR_RAG", True)
    import sys, types
    roto = types.ModuleType("src.rag")
    roto.buscar_informacion = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sin chroma"))
    monkeypatch.setitem(sys.modules, "src.rag", roto)
    falso = ModeloFalso({"motivo_consulta": "Dolor torácico"})
    monkeypatch.setattr(extraccion, "_cliente", falso)
    assert extraccion.extraer_datos("Dolor de pecho.")["motivo_consulta"] == "Dolor torácico"


def test_sintomas_por_raiz_y_por_item(modelo):
    modelo({"sintomas_asociados": "Sudoración, fiebre, náuseas"})
    r = extraccion.extraer_datos("Me duele el pecho hace 20 minutos y estoy sudando. Tengo ganas de vomitar y náuseas.")
    assert r["sintomas_asociados"] == "Sudoración, náuseas"
