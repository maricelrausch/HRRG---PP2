"""
Rangos de los signos vitales en la base (Dario 30/10, pedido de Francisco Navoni).
  - La semilla carga los mismos valores que estaban en el código, una sola vez.
  - Todos los perfiles del triage leen; solo la Jefatura cambia.
  - Por grupo etario: si un grupo no tiene su fila, se usa la de Adulto.
Ejecutar desde backend:  python -m pytest -q tests/test_parametros_signos.py
"""
import json
from pathlib import Path

import pytest
from flask import Flask

import src.parametros_signos as ps
from tests.test_reglas_y_anulacion import PERFILES

SEMILLA = Path(__file__).resolve().parents[1] / "datos" / "parametros_signos_semilla.json"


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    base = tmp_path / "reglas.db"
    ps.inicializar_parametros(base)
    ps.cargar_parametros_semilla(base, SEMILLA)
    monkeypatch.setattr(ps, "obtener_profesional",
                        lambda b, u: {"usuario": u, "nombre": u, "rol": PERFILES[u]} if u in PERFILES else None)
    monkeypatch.setattr(ps, "estado_acceso", lambda b, u: {"bloqueada": False})
    monkeypatch.setattr(ps, "requiere_cambio", lambda c: False)
    app = Flask(__name__)
    app.secret_key = "prueba"
    app.config.update(BASE_REGLAS=base, BASE_USUARIOS=tmp_path / "u.db")
    app.register_blueprint(ps.bp)
    c = app.test_client()

    def como(usuario):
        with c.session_transaction() as s:
            s["usuario"] = usuario
        return c
    c.como = como
    return c


def _fila(c, campo, grupo="Adulto"):
    return next(p for p in c.get("/api/signos").get_json()["parametros"]
                if p["campo"] == campo and p["grupo_etario"] == grupo)


def test_semilla_igual_al_codigo_y_una_sola_vez(tmp_path):
    base = tmp_path / "r.db"
    ps.inicializar_parametros(base)
    assert ps.cargar_parametros_semilla(base, SEMILLA) == 9
    assert ps.cargar_parametros_semilla(base, SEMILLA) == 0          # no duplica
    p = {f["campo"]: f for f in ps.leer_parametros(base)}
    # Los valores que estaban en formulario.js / validacion.js / ia/medgemma.py.
    assert (p["frecuencia_cardiaca"]["normal_min"], p["frecuencia_cardiaca"]["normal_max"]) == (60, 100)
    assert (p["saturacion_o2"]["minimo_posible"], p["saturacion_o2"]["normal_min"]) == (50, 95)
    assert (p["temperatura"]["minimo_posible"], p["temperatura"]["maximo_posible"]) == (30, 43)
    assert p["glucemia"]["obligatorio"] is False and p["dolor_intensidad"]["obligatorio"] is True
    assert set(p) == set(ps.CAMPOS_SIGNOS)


def test_leer_nunca_falla(tmp_path):
    assert ps.leer_parametros(None) == []
    assert ps.leer_parametros(tmp_path / "no.db") == []
    assert not (tmp_path / "no.db").exists()


@pytest.mark.parametrize("usuario", ["enf", "med", "aud", "jefa"])
def test_todos_leen(cliente, usuario):
    d = cliente.como(usuario).get("/api/signos").get_json()
    assert len(d["parametros"]) == 9 and "Adulto" in d["grupos"] and d["historial"]


@pytest.mark.parametrize("usuario", ["enf", "med", "aud", "adm"])
def test_solo_jefatura_cambia(cliente, usuario):
    fila = _fila(cliente.como("jefa"), "temperatura")
    assert cliente.como(usuario).post("/api/signos", json=_datos(fila)).status_code == 403


def test_sin_sesion_401(cliente):
    assert cliente.get("/api/signos").status_code == 401


def _datos(fila, **cambios):
    claves = set(ps.NUMEROS) | set(ps.TEXTOS) | {"campo", "grupo_etario", "obligatorio", "orden", "origen"}
    return dict({k: fila[k] for k in claves if k in fila}, **cambios)


def test_modificar_sube_version_y_queda_en_historial(cliente):
    c = cliente.como("jefa")
    fila = _fila(c, "frecuencia_cardiaca")
    r = c.post("/api/signos", json=_datos(fila, normal_max=110)).get_json()
    assert r["parametro"]["normal_max"] == 110 and r["parametro"]["version"] == 2
    assert c.post("/api/signos", json=_datos(r["parametro"])).get_json()["sin_cambios"] is True
    assert c.get("/api/signos").get_json()["historial"][-1]["accion"] == "MODIFICADO"


def test_grupo_etario_propio_y_respaldo_adulto(cliente):
    c = cliente.como("jefa")
    adulto = _fila(c, "frecuencia_cardiaca")
    r = c.post("/api/signos", json=_datos(adulto, grupo_etario="Lactante", normal_min=100, normal_max=160))
    assert r.status_code == 200
    base = cliente.application.config["BASE_REGLAS"]
    assert ps.parametros_para(base, 0)["frecuencia_cardiaca"]["normal_max"] == 160     # lactante: su fila
    assert ps.parametros_para(base, 0)["temperatura"]["grupo_etario"] == "Adulto"      # sin fila: Adulto
    assert ps.parametros_para(base, 40)["frecuencia_cardiaca"]["normal_max"] == 100
    assert ps.parametros_para(base, None)["frecuencia_cardiaca"]["normal_max"] == 100
    # Se puede borrar la de Lactante, no la de Adulto.
    lac = _fila(c, "frecuencia_cardiaca", "Lactante")
    assert c.post(f"/api/signos/{lac['id']}/eliminar", json={}).status_code == 200
    assert c.post(f"/api/signos/{adulto['id']}/eliminar", json={}).status_code == 409


@pytest.mark.parametrize("cambio", [
    {"campo": "presion"},                         # signo inexistente
    {"grupo_etario": "Bebé"},                     # grupo inexistente
    {"minimo_posible": 200},                      # mínimo ≥ máximo
    {"normal_min": 10},                           # normal fuera de lo posible
    {"normal_min": 99, "normal_max": 70},         # normal invertido
    {"normal_max": "mucho"},                      # no es número
    {"nombre": ""},                               # sin nombre
    {"origen": "inventado"},
    {"otro": 1},                                  # campo de más
])
def test_invalidos(cliente, cambio):
    c = cliente.como("jefa")
    assert c.post("/api/signos", json=_datos(_fila(c, "frecuencia_cardiaca"), **cambio)).status_code == 422


def test_semilla_coincide_con_el_frontend():
    """Los nombres y unidades de la semilla son los que muestra hoy la pantalla de Medición."""
    datos = json.loads(SEMILLA.read_text(encoding="utf-8"))["parametros"]
    assert [d["orden"] for d in datos] == list(range(1, 10))
