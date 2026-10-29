"""
Etapa C (Dario 29/10, pedido de Francisco Navoni): tiempos objetivo por color configurables.
  - Por defecto, los de referencia Manchester (0/10/60/120).
  - La Jefatura los guarda en /api/reglas/tiempos; enfermería y auditoría solo leen.
  - leer_tiempos() nunca falla: sin base o con datos rotos, devuelve los de referencia.
Ejecutar desde backend:  python -m pytest -q tests/test_tiempos_objetivo.py
"""
import sqlite3

import pytest

import src.reglas_hospital as rh
from tests.test_reglas_y_anulacion import cliente  # noqa: F401  (reutiliza la fixture)

NUEVOS = {"ROJO": 0, "NARANJA": 15, "AMARILLO": 60, "VERDE": 180}


def test_por_defecto_son_los_de_referencia(cliente):  # noqa: F811
    d = cliente.como("enf").get("/api/reglas/tiempos").get_json()
    assert d["tiempos"] == {"ROJO": 0, "NARANJA": 10, "AMARILLO": 60, "VERDE": 120}
    assert d["confirmados"] is False and d["actualizado"] is None


def test_jefatura_guarda_y_todos_leen(cliente):  # noqa: F811
    c = cliente.como("jefa")
    assert c.post("/api/reglas/tiempos", json={k: str(v) for k, v in NUEVOS.items()}).status_code == 200
    for usuario in ("enf", "med", "aud", "jefa"):
        d = cliente.como(usuario).get("/api/reglas/tiempos").get_json()
        assert d["tiempos"] == NUEVOS and d["confirmados"] is True and d["actualizado"]["por"] == "jefa"
    # Queda en el historial con los valores anteriores y los nuevos.
    con = sqlite3.connect(cliente.application.config["BASE_REGLAS"])
    accion = con.execute("SELECT accion FROM reglas_eventos ORDER BY id DESC").fetchone()[0]
    con.close()
    assert accion == "TIEMPOS OBJETIVO GUARDADOS"


@pytest.mark.parametrize("usuario", ["enf", "med", "aud", "adm"])
def test_solo_jefatura_puede_cambiarlos(cliente, usuario):  # noqa: F811
    assert cliente.como(usuario).post("/api/reglas/tiempos", json=NUEVOS).status_code == 403


@pytest.mark.parametrize("datos", [
    {"ROJO": 0, "NARANJA": 10, "AMARILLO": 60},                          # falta VERDE
    dict(NUEVOS, AZUL=240),                                              # color de más
    dict(NUEVOS, NARANJA="diez"),                                        # no es número
    dict(NUEVOS, NARANJA=10.5),                                          # no es entero
    dict(NUEVOS, VERDE=2000),                                            # fuera de rango
    dict(NUEVOS, NARANJA=90),                                            # NARANJA > AMARILLO
    dict(NUEVOS, ROJO=True),                                             # booleano
])
def test_tiempos_invalidos(cliente, datos):  # noqa: F811
    assert cliente.como("jefa").post("/api/reglas/tiempos", json=datos).status_code == 422


def test_leer_tiempos_nunca_falla(tmp_path):
    ref = {"ROJO": 0, "NARANJA": 10, "AMARILLO": 60, "VERDE": 120}
    assert rh.leer_tiempos(None) == ref
    assert rh.leer_tiempos(tmp_path / "no_existe.db") == ref
    assert not (tmp_path / "no_existe.db").exists()          # no crea la base por leer
    base = tmp_path / "r.db"
    rh.inicializar_reglas(base)
    con = sqlite3.connect(base)
    with con:
        con.execute("INSERT INTO reglas_config VALUES ('tiempos_objetivo', 'roto{', 'x', 'x')")
    con.close()
    assert rh.leer_tiempos(base) == ref


# ---- La API del hospital y la sala de espera usan los tiempos configurados ----
from tests.test_api_hospital import AUTH, cliente as cliente_api  # noqa: E402,F401


def test_api_y_sala_usan_los_tiempos_configurados(cliente_api, tmp_path):  # noqa: F811
    from src.sala_espera import bp as sala_bp
    app = cliente_api.application
    app.register_blueprint(sala_bp)
    base = tmp_path / "reglas_cfg.db"
    rh.inicializar_reglas(base)
    app.config["BASE_REGLAS"] = base

    # Sin configurar: AMARILLO de 75 min está vencido (referencia 60).
    amarillo = cliente_api.get("/api/cola-espera", headers=AUTH).get_json()["pacientes"][1]
    assert amarillo["tiempo_maximo_min"] == 60 and amarillo["vencido"]

    # La Jefatura sube AMARILLO a 90 min: deja de estar vencido en la API y la sala lo informa.
    con = sqlite3.connect(base)
    with con:
        con.execute("INSERT INTO reglas_config VALUES ('tiempos_objetivo', ?, 'jefa', 'x')",
                    ('{"ROJO": 0, "NARANJA": 10, "AMARILLO": 90, "VERDE": 120}',))
    con.close()
    amarillo = cliente_api.get("/api/cola-espera", headers=AUTH).get_json()["pacientes"][1]
    assert amarillo["tiempo_maximo_min"] == 90 and not amarillo["vencido"]
    sala = cliente_api.get("/api/sala/espera").get_json()
    assert sala["tiempos"]["AMARILLO"] == 90
    assert {e["objetivo_min"] for e in sala["episodios"] if e["color"] == "AMARILLO"} == {90}


def test_cola_informa_ingreso_triage_restante_y_proximos(cliente_api):  # noqa: F811
    """D5 (mail de Navoni, punto 4): hora de ingreso, hora del triage, tiempo restante y próximos a vencer."""
    pacientes = {p["codigo_episodio"]: p for p in
                 cliente_api.get("/api/cola-espera", headers=AUTH).get_json()["pacientes"]}
    amarillo_vencido, amarillo = pacientes["EPI-AMARI01"], pacientes["EPI-AMARI02"]   # 75 y 20 min, máx. 60
    assert amarillo_vencido["tiempo_restante_min"] < 0 and amarillo_vencido["vencido"]
    assert not amarillo_vencido["proximo_a_vencer"]
    assert amarillo["tiempo_restante_min"] in (39, 40) and not amarillo["proximo_a_vencer"]
    for p in pacientes.values():
        assert p["ingreso_en"] and p["triage_en"]
    assert pacientes["EPI-ROJO001"]["proximo_a_vencer"] is False
