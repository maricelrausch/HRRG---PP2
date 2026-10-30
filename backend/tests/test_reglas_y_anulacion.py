"""
Pruebas de las propuestas del 28/10 (Barby):
  - Reglas del hospital (src/reglas_hospital.py): validación, permisos por perfil y ciclo
    borrador → activa → inactiva, con historial.
  - Anular un caso cargado por error (src/registro.anular_episodio_demo): solo antes de la espera.
No necesitan Ollama, claves de identificación ni internet.
Ejecutar desde backend:  python -m pytest -q tests/test_reglas_y_anulacion.py
"""
import json
import sqlite3

import pytest
from flask import Flask

import src.reglas_hospital as rh
from src.registro import (
    inicializar_registro,
    crear_episodio,
    cambiar_estado_demo,
    registrar_decision_demo,
    anular_episodio_demo,
    EpisodioNoAnulableError,
    ConflictoEstadoError,
    obtener_estado_demo,
)

# ------------------------------------------------
# Reglas del hospital
# ------------------------------------------------

PERFILES = {
    "jefa": "jefatura",
    "enf": "enfermeria",
    "med": "medico",
    "aud": "auditor",
    "adm": "admin",
}

REGLA = {
    "nombre": "Hipoxemia",
    "explicacion": "SpO₂ menor a 92 %: posible compromiso respiratorio (regla HRRG de prueba)",
    "color": "NARANJA",
    "combinacion": "todas",
    "condiciones": [{"campo": "saturacion_o2", "operador": "<", "valor": "92"}],
}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    base = tmp_path / "reglas.db"
    rh.inicializar_reglas(base)
    monkeypatch.setattr(rh, "obtener_profesional",
                        lambda b, u: {"usuario": u, "nombre": u, "rol": PERFILES[u]} if u in PERFILES else None)
    monkeypatch.setattr(rh, "estado_acceso", lambda b, u: {"bloqueada": False})
    monkeypatch.setattr(rh, "requiere_cambio", lambda c: False)
    app = Flask(__name__)
    app.secret_key = "prueba"
    app.config["BASE_REGLAS"] = base
    app.config["BASE_USUARIOS"] = tmp_path / "u.db"
    app.register_blueprint(rh.bp)
    c = app.test_client()

    def como(usuario):
        with c.session_transaction() as s:
            s["usuario"] = usuario
        return c
    c.como = como
    return c


def test_sin_sesion_401(cliente):
    assert cliente.get("/api/reglas/activas").status_code == 401


def test_ciclo_completo_borrador_activa_inactiva(cliente):
    c = cliente.como("jefa")
    r = c.post("/api/reglas", json=REGLA)
    assert r.status_code == 201
    regla = r.get_json()["regla"]
    assert regla["codigo"] == "R-001" and regla["estado"] == "borrador" and regla["version"] == 1
    assert regla["condiciones"][0]["valor"] == 92          # "92" → número

    # El borrador no interviene.
    assert c.get("/api/reglas/activas").get_json()["reglas"] == []

    assert c.post(f"/api/reglas/{regla['id']}/activar", json={}).status_code == 200
    activas = c.get("/api/reglas/activas").get_json()
    assert [x["codigo"] for x in activas["reglas"]] == ["R-001"]

    # Editar una regla activa la vuelve a borrador y sube la versión.
    cambio = dict(REGLA, color="ROJO")
    r = c.post(f"/api/reglas/{regla['id']}", json=cambio).get_json()["regla"]
    assert r["estado"] == "borrador" and r["version"] == 2 and r["color"] == "ROJO"
    assert c.get("/api/reglas/activas").get_json()["reglas"] == []

    c.post(f"/api/reglas/{regla['id']}/activar", json={})
    assert c.post(f"/api/reglas/{regla['id']}/desactivar", json={}).status_code == 200

    # Ya estuvo activa: no se puede eliminar, solo desactivar.
    assert c.post(f"/api/reglas/{regla['id']}/eliminar", json={}).status_code == 409

    hist = c.get("/api/reglas").get_json()["reglas"][0]["historial"]
    assert [h["accion"] for h in hist] == [
        "CREADA (borrador)", "ACTIVADA", "EDITADA (pasó a borrador)", "ACTIVADA", "DESACTIVADA"]
    assert all(h["usuario"] == "jefa" for h in hist)


def test_borrador_nunca_activado_se_puede_eliminar(cliente):
    c = cliente.como("jefa")
    rid = c.post("/api/reglas", json=REGLA).get_json()["regla"]["id"]
    assert c.post(f"/api/reglas/{rid}/eliminar", json={}).status_code == 200
    assert c.get("/api/reglas").get_json()["reglas"] == []


@pytest.mark.parametrize("cambio, texto", [
    ({"color": "AZUL"}, "color"),
    ({"nombre": "x"}, "nombre"),
    ({"condiciones": []}, "condiciones"),
    ({"condiciones": [{"campo": "dni", "operador": "=", "valor": "1"}]}, "dato"),
    ({"condiciones": [{"campo": "saturacion_o2", "operador": "es", "valor": "92"}]}, "operador"),
    ({"condiciones": [{"campo": "saturacion_o2", "operador": "<", "valor": "abc"}]}, "número"),
    ({"condiciones": [{"campo": "saturacion_o2", "operador": "<", "valor": 150}]}, "entre"),
    ({"condiciones": [{"campo": "estado_conciencia", "operador": "es", "valor": "Dormido"}]}, "opción"),
    ({"extra": 1}, "campos"),
])
def test_validacion(cliente, cambio, texto):
    r = cliente.como("jefa").post("/api/reglas", json=dict(REGLA, **cambio))
    assert r.status_code == 422 and texto in r.get_json()["mensaje"]


def test_bool_y_opcion_validos(cliente):
    regla = dict(REGLA, combinacion="alguna", condiciones=[
        {"campo": "br_sangrado", "operador": "si"},
        {"campo": "estado_conciencia", "operador": "no_es", "valor": "Alerta"},
        {"campo": "temperatura", "operador": ">=", "valor": "38,5"},
    ])
    r = cliente.como("jefa").post("/api/reglas", json=regla)
    assert r.status_code == 201
    conds = r.get_json()["regla"]["condiciones"]
    assert conds[0]["valor"] is None and conds[2]["valor"] == 38.5


@pytest.mark.parametrize("usuario, ruta, metodo, esperado", [
    ("enf", "/api/reglas/activas", "get", 200),
    ("med", "/api/reglas/campos", "get", 200),
    ("aud", "/api/reglas", "get", 200),
    ("enf", "/api/reglas", "get", 403),
    ("enf", "/api/reglas", "post", 403),
    ("aud", "/api/reglas", "post", 403),
    ("adm", "/api/reglas/activas", "get", 403),
    ("adm", "/api/reglas", "post", 403),
])
def test_permisos(cliente, usuario, ruta, metodo, esperado):
    c = cliente.como(usuario)
    r = c.get(ruta) if metodo == "get" else c.post(ruta, json=REGLA)
    assert r.status_code == esperado


def test_ya_no_existe_el_interruptor_de_reglas_de_ejemplo(cliente):
    # [Dario 30/10] Se sacó la "copia de respaldo" de las reglas escritas en el código: ahora todas están en la base.
    c = cliente.como("jefa")
    assert c.post("/api/reglas/config", json={"usar_ejemplo": True}).status_code in (404, 405)
    assert "usar_ejemplo" not in c.get("/api/reglas/activas").get_json()


def test_post_sin_json_rechazado(cliente):
    r = cliente.como("jefa").post("/api/reglas", data="nombre=x")
    assert r.status_code == 415


# ------------------------------------------------
# Anular un caso cargado por error
# ------------------------------------------------

@pytest.fixture
def base(tmp_path):
    ruta = tmp_path / "triage.db"
    inicializar_registro(ruta)
    return ruta


_N = [0]


def _nuevo(base):
    _N[0] += 1
    ep = f"EPI-PRUEBA{_N[0]:03d}"
    crear_episodio(base, ep, "PAC-PRUEBA", "enf1")
    return ep


def test_anular_en_ingreso(base):
    ep = _nuevo(base)
    cambiar_estado_demo(base, ep, "enf1", "en_ingreso", 0)
    r = anular_episodio_demo(base, ep, "enf1", "Datos cargados por error", 1)
    assert r["estado"]["estado"] == "anulado" and r["evento"]["tipo"] == "EPISODIO_ANULADO"
    assert r["evento"]["datos"]["motivo"] == "Datos cargados por error"
    # Un caso anulado no vuelve a ninguna lista ni recibe decisiones.
    with pytest.raises(ValueError):
        cambiar_estado_demo(base, ep, "enf1", "en_espera", 2)
    with pytest.raises(ValueError):
        registrar_decision_demo(base, ep, "enf1", "aceptada", "VERDE", "", 0)


def test_anular_sin_estado(base):
    ep = _nuevo(base)
    assert anular_episodio_demo(base, ep, "enf1", "Caso duplicado", 0)["estado"]["version"] == 1


def test_no_se_anula_en_espera(base):
    ep = _nuevo(base)
    cambiar_estado_demo(base, ep, "enf1", "en_espera", 0)
    with pytest.raises(EpisodioNoAnulableError):
        anular_episodio_demo(base, ep, "enf1", "Error", 1)


def test_no_se_anula_con_decision(base):
    ep = _nuevo(base)
    registrar_decision_demo(base, ep, "enf1", "aceptada", "VERDE", "", 0)
    with pytest.raises(EpisodioNoAnulableError):
        anular_episodio_demo(base, ep, "enf1", "Error", 0)


def test_anular_exige_motivo_y_version(base):
    ep = _nuevo(base)
    with pytest.raises(ValueError):
        anular_episodio_demo(base, ep, "enf1", "  ", 0)
    with pytest.raises(ConflictoEstadoError):
        anular_episodio_demo(base, ep, "enf1", "Error", 3)


def test_migracion_base_vieja(tmp_path):
    """Una base creada antes del estado 'anulado' se actualiza sin perder datos."""
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE episodios (codigo_episodio TEXT PRIMARY KEY, codigo_paciente TEXT NOT NULL,
            creado_en TEXT NOT NULL, profesional_usuario TEXT NOT NULL);
        CREATE TABLE estados_episodio (codigo_episodio TEXT PRIMARY KEY,
            estado TEXT NOT NULL CHECK (estado IN ('en_ingreso','en_espera','finalizado')),
            actualizado_en TEXT NOT NULL, profesional_usuario TEXT NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            FOREIGN KEY (codigo_episodio) REFERENCES episodios (codigo_episodio));
        INSERT INTO episodios VALUES ('EPI-VIEJO', 'PAC-1', '2026-10-01T10:00:00+00:00', 'enf1');
        INSERT INTO estados_episodio VALUES ('EPI-VIEJO', 'en_ingreso', '2026-10-01T10:00:00+00:00', 'enf1', 1);
    """)
    con.commit()
    con.close()
    inicializar_registro(ruta)
    inicializar_registro(ruta)          # dos veces: no falla ni duplica
    assert obtener_estado_demo(ruta, "EPI-VIEJO")["estado"] == "en_ingreso"
    assert anular_episodio_demo(ruta, "EPI-VIEJO", "enf1", "Error", 1)["estado"]["estado"] == "anulado"
