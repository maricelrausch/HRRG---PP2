"""
C05 · Pruebas automáticas del esquema central, las validaciones y los casos simulados.

Solo usa src/esquemas.py, src/validacion.py y datos/casos_simulados.json
(no necesita Ollama, Flask ni internet).

Ejecutar desde la carpeta backend:   python -m pytest -q
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src import esquemas
from src.validacion import validar

RAIZ = Path(__file__).resolve().parent.parent
DATOS = json.loads((RAIZ / "datos" / "casos_simulados.json").read_text(encoding="utf-8"))
CASOS = DATOS["casos"]
EXTRACCION = DATOS.get("casos_extraccion", [])


# ---------- 1. Casos de demo, errores, faltantes y alias ----------
@pytest.mark.parametrize("caso", CASOS, ids=[c["id"] for c in CASOS])
def test_caso_simulado(caso):
    """Cada caso da el resultado esperado: válido/inválido, errores, faltantes, PAM."""
    r = validar(caso["entrada"])
    esp = caso["esperado"]
    assert r["valido"] is esp["valido"], r["errores"]
    if not esp["valido"]:
        texto = " | ".join(r["errores"])
        for fragmento in esp["errores_contienen"]:
            assert fragmento in texto, texto
        return
    if "faltantes" in esp:
        assert r["faltantes"] == esp["faltantes"]
    if "pam" in esp:
        assert r["datos"].get("pam") == esp["pam"]
    for campo, valor in esp.get("campos", {}).items():
        assert r["datos"][campo] == valor


# ---------- 2. Casos de extracción (respuesta "correcta" de MedGemma) ----------
@pytest.mark.parametrize("caso", EXTRACCION, ids=[c["id"] for c in EXTRACCION])
def test_extraccion_esperada_cumple_esquema(caso):
    """Lo que debería extraer el modelo respeta el esquema."""
    r = validar(caso["esperado_extraccion"])
    esp = caso["esperado_validacion"]
    assert r["valido"] is esp["valido"], r["errores"]


@pytest.mark.parametrize("caso", EXTRACCION, ids=[c["id"] for c in EXTRACCION])
def test_textos_ficticios_sin_datos_personales(caso):
    assert validar({"motivo_consulta": caso["texto"][:500]})["valido"], caso["id"]


# ---------- 3. Reglas puntuales del diccionario ----------
def test_vacio_es_faltante_y_cero_es_valor():
    r = validar({"dolor_intensidad": 0, "temperatura": ""})
    assert r["datos"]["dolor_intensidad"] == 0
    assert "temperatura" in r["faltantes"] and "dolor_intensidad" not in r["faltantes"]


def test_coma_decimal():
    assert validar({"temperatura": "37,8"})["datos"]["temperatura"] == 37.8


def test_signos_vitales_sin_decimales():
    assert not validar({"frecuencia_cardiaca": "104,5"})["valido"]


@pytest.mark.parametrize("campo,valor", [
    ("motivo_consulta", "Se llama Ana"),
    ("antecedentes_otros", "DNI 30123456"),
    ("motivo_consulta", "escribir a ana@mail.com"),
    ("aspecto_general", "vive en calle Belgrano"),
])
def test_privacidad(campo, valor):
    r = validar({campo: valor})
    assert not r["valido"] and "dato personal" in r["errores"][0]


def test_codigos_del_contrato_api():
    assert validar({"codigo_paciente": "PAC-DEMO-001", "codigo_episodio": "EPI-DEMO-001"})["valido"]
    assert not validar({"codigo_episodio": "Juan Pérez"})["valido"]


def test_faltantes_por_etapa():
    r = validar({"edad": 40, "sexo": "Masculino"}, etapa="medicion")
    assert r["faltantes"] == esquemas.OBLIGATORIOS["medicion"]


def test_nombres_unicos_y_alias():
    nombres = list(esquemas.DatosTriage.model_fields)
    assert len(nombres) == len(set(nombres))
    for viejo, nuevo in esquemas.ALIAS.items():
        assert nuevo in nombres and viejo not in nombres


# ---------- 4. Salida del modelo y decisión del profesional ----------
VALIDA = {"color": "Amarillo", "confidence": 0.7, "red_flags": ["dolor intenso"],
          "possible_discriminators": ["dolor moderado"], "rationale": "Dolor 7/10 con FC 98 lpm."}


def test_salida_modelo_valida():
    assert esquemas.SalidaModelo.model_validate_json(json.dumps(VALIDA)).color == "Amarillo"


@pytest.mark.parametrize("cambio", [{"color": "Violeta"}, {"confidence": 3}, {"rationale": ""}])
def test_salida_modelo_invalida(cambio):
    with pytest.raises(ValidationError):
        esquemas.SalidaModelo.model_validate({**VALIDA, **cambio})


def test_salida_json_roto():
    with pytest.raises(ValidationError):
        esquemas.SalidaModelo.model_validate_json("no es json")


def test_resultado_siempre_requiere_validacion_humana():
    r = esquemas.ResultadoHospital(**VALIDA, missing_data=[])
    assert r.human_validation_required is True


def test_decision_modificar_exige_motivo():
    with pytest.raises(ValidationError):
        esquemas.DecisionProfesional(codigo_episodio="EPI-1", id_profesional="medico",
                                     decision="modificar", color_final="Rojo")


def test_decision_aceptar():
    d = esquemas.DecisionProfesional(codigo_episodio="EPI-1", id_profesional="enfermeria",
                                     decision="aceptar", color_final="Amarillo")
    assert d.motivo_discrepancia is None


# ---------- 5. Documento y código alineados ----------
def test_diccionario_md_cubre_el_esquema():
    md = (RAIZ / "docs" / "diccionario_datos_v2.md").read_text(encoding="utf-8")
    campos = list(esquemas.DatosTriage.model_fields) + ["pam"] + list(esquemas.SalidaModelo.model_fields)
    faltan = [c for c in campos if f"| {c} |" not in md]
    assert not faltan, f"Faltan en el diccionario: {faltan}"
