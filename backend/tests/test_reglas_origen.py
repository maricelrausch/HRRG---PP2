"""
Etapa A (Dario 29/10, pedido de Francisco Navoni): origen de cada regla y quién la validó.
  - Una base vieja (sin las columnas nuevas) se migra sin perder reglas y con copia de respaldo.
  - Crear y editar reglas con origen y validada_por.
  - Sin origen, la regla queda como «provisoria» (compatibilidad con la pantalla anterior).
Ejecutar desde backend:  python -m pytest -q tests/test_reglas_origen.py
"""
import json
import sqlite3

import pytest

import src.reglas_hospital as rh
from tests.test_reglas_y_anulacion import REGLA, cliente  # noqa: F401  (reutiliza la fixture)


def _base_vieja(ruta):
    """Base como la que hoy existe en las PCs y en el Docker: tabla reglas SIN origen ni validada_por."""
    con = sqlite3.connect(ruta)
    with con:
        con.execute("""CREATE TABLE reglas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE, nombre TEXT NOT NULL,
            explicacion TEXT NOT NULL, color TEXT NOT NULL, combinacion TEXT NOT NULL,
            condiciones_json TEXT NOT NULL, estado TEXT NOT NULL, version INTEGER NOT NULL,
            fue_activada INTEGER NOT NULL DEFAULT 0, creada_por TEXT NOT NULL, creada_en TEXT NOT NULL,
            actualizada_por TEXT NOT NULL, actualizada_en TEXT NOT NULL)""")
        con.execute("""INSERT INTO reglas (codigo, nombre, explicacion, color, combinacion, condiciones_json,
            estado, version, fue_activada, creada_por, creada_en, actualizada_por, actualizada_en)
            VALUES ('R-001', 'Hipoxemia', 'SpO2 baja', 'NARANJA', 'todas',
            '[{"campo": "saturacion_o2", "operador": "<", "valor": 92}]', 'activa', 3, 1,
            'jefa', '2026-10-28T10:00:00+00:00', 'jefa', '2026-10-28T10:00:00+00:00')""")
    con.close()


def test_migracion_base_vieja_conserva_reglas_y_hace_backup(tmp_path):
    base = tmp_path / "reglas_hospital.db"
    _base_vieja(base)
    rh.inicializar_reglas(base)

    con = sqlite3.connect(base)
    con.row_factory = sqlite3.Row
    fila = con.execute("SELECT * FROM reglas").fetchone()
    con.close()
    # La regla sigue igual (activa, versión 3) y queda marcada como provisoria y sin validar.
    assert fila["codigo"] == "R-001" and fila["estado"] == "activa" and fila["version"] == 3
    assert fila["origen"] == "provisoria" and fila["validada_por"] == ""
    # Copia de respaldo de la base anterior.
    assert (tmp_path / "reglas_hospital.db.antes-origen.bak").exists()

    # Correr la inicialización otra vez no cambia nada ni falla (se ejecuta en cada arranque).
    rh.inicializar_reglas(base)


def test_base_nueva_no_hace_backup(tmp_path):
    base = tmp_path / "nueva.db"
    rh.inicializar_reglas(base)
    con = sqlite3.connect(base)
    columnas = {f[1] for f in con.execute("PRAGMA table_info(reglas)")}
    con.close()
    assert {"origen", "validada_por"} <= columnas
    assert not (tmp_path / "nueva.db.antes-origen.bak").exists()


def test_crear_con_origen_y_validacion(cliente):  # noqa: F811
    c = cliente.como("jefa")
    r = c.post("/api/reglas", json=dict(REGLA, origen="local", validada_por="Jefatura de Enfermería"))
    assert r.status_code == 201
    regla = r.get_json()["regla"]
    assert regla["origen"] == "local" and regla["validada_por"] == "Jefatura de Enfermería"

    # Editar el origen funciona como cualquier edición: vuelve a borrador y sube la versión.
    c.post(f"/api/reglas/{regla['id']}/activar", json={})
    e = c.post(f"/api/reglas/{regla['id']}", json=dict(REGLA, origen="manchester")).get_json()["regla"]
    assert e["origen"] == "manchester" and e["validada_por"] == "" and e["estado"] == "borrador"


def test_sin_origen_queda_provisoria(cliente):  # noqa: F811
    regla = cliente.como("jefa").post("/api/reglas", json=REGLA).get_json()["regla"]
    assert regla["origen"] == "provisoria" and regla["validada_por"] == ""


@pytest.mark.parametrize("cambio", [{"origen": "otro"}, {"validada_por": "x" * 121}, {"validada_por": 5}])
def test_origen_invalido(cliente, cambio):  # noqa: F811
    r = cliente.como("jefa").post("/api/reglas", json=dict(REGLA, **cambio))
    assert r.status_code == 422


def test_catalogo_incluye_origenes(cliente):  # noqa: F811
    datos = cliente.como("enf").get("/api/reglas/campos").get_json()
    assert [o[0] for o in datos["origenes"]] == ["manchester", "local", "provisoria"]
