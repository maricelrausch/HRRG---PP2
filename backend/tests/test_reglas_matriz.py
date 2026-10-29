"""
D1 (Dario 29/10): la regla documenta todo lo que pide la matriz de Francisco Navoni
(variable, condición, grupo etario, motivo, discriminador, color, origen, quién validó, versión y fecha)
y la edad pasa a ser estructural con grupos etarios.
Ejecutar desde backend:  python -m pytest -q tests/test_reglas_matriz.py
"""
import sqlite3

import pytest

import src.reglas_hospital as rh
from evaluacion import reglas_seguridad as RS
from tests.test_reglas_y_anulacion import REGLA, cliente  # noqa: F401

# Mismos casos en frontend/tests/motor_reglas.test.js: si cambian los cortes, cambiar los dos.
EDADES = [(0, "Lactante"), ("0,5", "Lactante"), (1, "Niño"), (11, "Niño"), (12, "Adolescente"),
          (17, "Adolescente"), (18, "Adulto"), (64, "Adulto"), (65, "Adulto mayor"), (99, "Adulto mayor"),
          ("", None), (None, None), (-1, None), ("abc", None)]


@pytest.mark.parametrize("edad, grupo", EDADES)
def test_grupo_etario_igual_en_backend_y_evaluador(edad, grupo):
    assert rh.grupo_etario(edad) == grupo
    assert RS.grupo_etario(edad) == grupo


def test_regla_por_grupo_etario(cliente):  # noqa: F811
    regla = dict(REGLA, condiciones=[{"campo": "grupo_etario", "operador": "es", "valor": "Lactante"},
                                     {"campo": "temperatura", "operador": ">=", "valor": "38"}])
    r = cliente.como("jefa").post("/api/reglas", json=regla)
    assert r.status_code == 201
    mala = dict(REGLA, condiciones=[{"campo": "grupo_etario", "operador": "es", "valor": "Bebé"}])
    assert cliente.como("jefa").post("/api/reglas", json=mala).status_code == 422
    # El evaluador calcula el grupo con la edad.
    lista = [r.get_json()["regla"]]
    assert RS.reglas({"edad": 0, "temperatura": "38,5"}, lista)
    assert not RS.reglas({"edad": 5, "temperatura": "38,5"}, lista)


def test_discriminador_y_fecha_de_validacion(cliente):  # noqa: F811
    c = cliente.como("jefa")
    r = c.post("/api/reglas", json=dict(REGLA, discriminador="SpO₂ baja (Manchester)")).get_json()["regla"]
    assert r["discriminador"] == "SpO₂ baja (Manchester)" and r["validada_en"] == ""

    v = c.post(f"/api/reglas/{r['id']}", json=dict(REGLA, validada_por="Enfermería")).get_json()["regla"]
    assert v["validada_por"] == "Enfermería" and v["validada_en"]
    fecha = v["validada_en"]

    # Otra edición sin cambiar quién validó conserva la fecha.
    v2 = c.post(f"/api/reglas/{r['id']}", json=dict(REGLA, validada_por="Enfermería", color="ROJO")).get_json()["regla"]
    assert v2["validada_en"] == fecha
    # Borrar la validación borra la fecha.
    v3 = c.post(f"/api/reglas/{r['id']}", json=REGLA).get_json()["regla"]
    assert v3["validada_por"] == "" and v3["validada_en"] == ""

    assert c.post("/api/reglas", json=dict(REGLA, discriminador="x" * 201)).status_code == 422


def test_migracion_desde_la_version_de_la_etapa_a(tmp_path):
    """Una base que ya tenía origen y validada_por (Etapa A) recibe las columnas nuevas, con copia."""
    base = tmp_path / "reglas_hospital.db"
    con = sqlite3.connect(base)
    with con:
        con.execute("""CREATE TABLE reglas (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE,
            nombre TEXT NOT NULL, explicacion TEXT NOT NULL, color TEXT NOT NULL, combinacion TEXT NOT NULL,
            condiciones_json TEXT NOT NULL, estado TEXT NOT NULL, version INTEGER NOT NULL,
            fue_activada INTEGER NOT NULL DEFAULT 0, creada_por TEXT NOT NULL, creada_en TEXT NOT NULL,
            actualizada_por TEXT NOT NULL, actualizada_en TEXT NOT NULL,
            origen TEXT NOT NULL DEFAULT 'provisoria', validada_por TEXT NOT NULL DEFAULT '')""")
        con.execute("""INSERT INTO reglas (codigo, nombre, explicacion, color, combinacion, condiciones_json,
            estado, version, creada_por, creada_en, actualizada_por, actualizada_en, origen, validada_por)
            VALUES ('R-001','X','explicación','ROJO','todas','[]','activa',2,'j','t','j','t','local','Guardia')""")
    con.close()
    rh.inicializar_reglas(base)
    con = sqlite3.connect(base)
    con.row_factory = sqlite3.Row
    fila = con.execute("SELECT * FROM reglas").fetchone()
    con.close()
    assert fila["origen"] == "local" and fila["validada_por"] == "Guardia" and fila["version"] == 2
    assert fila["discriminador"] == "" and fila["validada_en"] == ""
    assert (tmp_path / "reglas_hospital.db.antes-discriminador.bak").exists()
