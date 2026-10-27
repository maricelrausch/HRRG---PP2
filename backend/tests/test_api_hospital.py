"""
Pruebas del web service para el sistema del hospital (src/api_hospital.py).

Arma una base de registro temporal con datos ficticios y una app Flask mínima
(no necesita Ollama ni internet).   Ejecutar desde backend:  python -m pytest -q tests/test_api_hospital.py
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask

from src.registro import inicializar_registro, registrar_medicion_demo
from src.api_hospital import bp

TOKEN = "token-de-prueba-0123456789"
AUTH = {"Authorization": "Bearer " + TOKEN}


def _episodio(con, codigo, color, minutos, motivo):
    t = (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()
    con.execute("INSERT INTO episodios VALUES (?,?,?,?)", (codigo, "PAC-" + codigo[4:], t, "enf1"))
    con.execute("INSERT INTO estados_episodio VALUES (?,?,?,?,1)", (codigo, "en_espera", t, "enf1"))
    ev = "INSERT INTO eventos (codigo_episodio,tipo,ocurrido_en,profesional_usuario,datos_json) VALUES (?,?,?,?,?)"
    con.execute(ev, (codigo, "DATOS_INGRESO_REGISTRADOS", t, "enf1", json.dumps(
        {"valores": {"edad": 58, "sexo": "Femenino", "motivo_categoria": motivo,
                     "tiempo_evolucion_valor": 6, "tiempo_evolucion_unidad": "horas",
                     "ant_diabetes": True, "br_disnea": True}})))
    if color:
        con.execute(ev, (codigo, "DECISION_REGISTRADA", t, "med1", json.dumps(
            {"decision": "aceptar", "color_final": color, "motivo": "", "version": 1})))


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    base = tmp_path / "triage.db"
    inicializar_registro(base)
    con = sqlite3.connect(base)
    _episodio(con, "EPI-VERDE01", "VERDE", 40, "Trauma")
    _episodio(con, "EPI-AMARI01", "AMARILLO", 75, "Cefalea")      # vencido (máx. 60)
    _episodio(con, "EPI-AMARI02", "AMARILLO", 20, "Fiebre")
    _episodio(con, "EPI-ROJO001", "ROJO", 2, "Disnea")
    _episodio(con, "EPI-SINCOL1", None, 1, "Otro")                # sin triage: no va en la cola
    con.commit()
    con.close()

    hace = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    m = registrar_medicion_demo(base, "EPI-AMARI01", "enf1", hace,
                                {"ta_sistolica": 150, "ta_diastolica": 95, "frecuencia_cardiaca": 110})

    app = Flask(__name__)
    app.config["BASE_REGISTRO_DEMO"] = base
    app.register_blueprint(bp)
    monkeypatch.setenv("HRRG_API_HOSPITAL_TOKEN", TOKEN)
    monkeypatch.delenv("HRRG_API_HOSPITAL_DNI", raising=False)
    c = app.test_client()
    c.base, c.medicion_id = base, m["id"]
    return c


def test_sin_token_configurado_la_api_esta_apagada(cliente, monkeypatch):
    monkeypatch.delenv("HRRG_API_HOSPITAL_TOKEN")
    assert cliente.get("/api/cola-espera", headers=AUTH).status_code == 503


@pytest.mark.parametrize("cabecera", [{}, {"Authorization": "Bearer otro-token-cualquiera-xx"},
                                      {"Authorization": TOKEN}])
def test_token_ausente_o_invalido(cliente, cabecera):
    r = cliente.get("/api/cola-espera", headers=cabecera)
    assert r.status_code == 401 and r.get_json()["codigo"] == "TOKEN_INVALIDO"


def test_solo_lectura(cliente):
    assert cliente.post("/api/cola-espera", headers=AUTH).status_code == 405


def test_cola_ordenada_por_prioridad_sin_los_sin_color(cliente):
    d = cliente.get("/api/cola-espera", headers=AUTH).get_json()
    assert d["ok"] and d["total"] == 4
    assert [p["codigo_episodio"] for p in d["pacientes"]] == \
        ["EPI-ROJO001", "EPI-AMARI01", "EPI-AMARI02", "EPI-VERDE01"]
    assert [p["posicion"] for p in d["pacientes"]] == [1, 2, 3, 4]
    amarillo = d["pacientes"][1]
    assert amarillo["prioridad"] == 3 and amarillo["vencido"] and amarillo["tiempo_maximo_min"] == 60
    assert d["por_color"] == {"ROJO": 1, "NARANJA": 0, "AMARILLO": 2, "VERDE": 1}


def test_cola_no_expone_dni_por_defecto(cliente):
    d = cliente.get("/api/cola-espera", headers=AUTH).get_json()
    assert all("dni" not in p for p in d["pacientes"])


def test_filtro_por_color_mantiene_la_posicion(cliente):
    d = cliente.get("/api/cola-espera?color=amarillo", headers=AUTH).get_json()
    assert [p["posicion"] for p in d["pacientes"]] == [2, 3]
    assert cliente.get("/api/cola-espera?color=AZUL", headers=AUTH).status_code == 400
    assert cliente.get("/api/cola-espera?otro=1", headers=AUTH).status_code == 400


def test_mediciones_del_episodio(cliente):
    d = cliente.get("/api/episodios/EPI-AMARI01/mediciones", headers=AUTH).get_json()
    assert d["episodio"]["estado"] == "en_espera"
    assert d["decision"]["color"] == "AMARILLO"
    assert d["datos_ingreso"]["motivo_categoria"] == "Cefalea"
    assert d["datos_ingreso"]["antecedentes"] == ["Diabetes"]
    assert d["datos_ingreso"]["banderas_rojas"] == ["Dificultad para respirar"]
    assert len(d["mediciones"]) == 1
    assert d["ultima_medicion"]["valores"]["ta_sistolica"] == 150
    assert "dni" not in d["episodio"]


def test_episodio_inexistente(cliente):
    r = cliente.get("/api/episodios/EPI-NOEXISTE/mediciones", headers=AUTH)
    assert r.status_code == 404 and r.get_json()["codigo"] == "EPISODIO_NO_ENCONTRADO"
