"""
Etapa B (Dario 29/10): las reglas de ejemplo pasaron del código a la base (datos/reglas_semilla.json).
  - cargar_semilla(): carga una sola vez, activas y "manchester / sin validar"; apaga las del código;
    respeta si la Jefatura ya las había apagado; no se vuelve a cargar si la Jefatura las edita.
  - evaluacion/reglas_seguridad.py ahora lee la semilla: tiene que dar EXACTAMENTE los mismos colores
    que la versión anterior (copiada abajo como referencia, reglas_v1) en miles de casos en los límites.
Ejecutar desde backend:  python -m pytest -q tests/test_reglas_semilla.py
"""
import json
import random
import sqlite3
from pathlib import Path

import pytest

import src.reglas_hospital as rh
from evaluacion import reglas_seguridad as RS
from evaluacion.metricas import a_numero

SEMILLA = Path(__file__).resolve().parent.parent / "datos" / "reglas_semilla.json"


# ---- Referencia: la versión ANTERIOR de evaluacion/reglas_seguridad.py, sin cambios ----
def reglas_v1(d: dict) -> list[tuple[int, str]]:
    n = lambda k: a_numero(d.get(k))           # noqa: E731
    out = []
    # Neurológico
    if d.get("br_convulsion"):
        out.append((0, "Convulsión activa"))
    g = n("glasgow")
    if g is not None and g <= 8:
        out.append((0, f"Glasgow {g:g}"))
    elif (d.get("estado_conciencia") and d.get("estado_conciencia") != "Alerta") or (g is not None and g < 15):
        out.append((1, "Alteración del nivel de conciencia"))
    # Respiratorio
    sat, fr = n("saturacion_o2"), n("frecuencia_respiratoria")
    if (sat is not None and sat < 90) or (fr is not None and (fr > 30 or fr < 8)) or d.get("br_disnea"):
        out.append((1, "Posible compromiso respiratorio"))
    # Circulatorio
    tas, fc = n("ta_sistolica"), n("frecuencia_cardiaca")
    hipo = tas is not None and tas < 90
    fc_alt = fc is not None and (fc > 130 or fc < 40)
    if d.get("br_sangrado") and hipo:
        out.append((0, "Sangrado con hipotensión"))
    else:
        if d.get("br_sangrado"):
            out.append((1, "Sangrado evidente"))
        if hipo or fc_alt:
            out.append((1, "Compromiso circulatorio"))
    # Otros
    t = n("temperatura")
    if d.get("ant_inmuno") and t is not None and t >= 38:
        out.append((1, "Fiebre en inmunosuprimido"))
    dolor = n("dolor_intensidad")
    if dolor is not None and dolor >= 8:
        out.append((1, "Dolor intenso"))
    return out


def _nivel_v1(d):
    r = reglas_v1(d) + simulacion_v1(d)
    return min(lv for lv, _ in r) if r else None


# ---- [Dario 30/10] Tanda 3: los umbrales de la simulación de MedGemma (frontend/sugerencia.js, medgemma()) ----
def simulacion_v1(d: dict) -> list[tuple[int, str]]:
    n = lambda k: a_numero(d.get(k))           # noqa: E731
    dolor, t, out = n("dolor_intensidad"), n("temperatura"), []
    if dolor is not None and 5 <= dolor < 8:
        out.append((2, "Dolor moderado"))
    if t is not None and 37.5 <= t < 38.5:
        out.append((2, "Febrícula"))
    if t is not None and t >= 38.5:
        out.append((2, "Fiebre"))
    return out


VALORES = {
    "saturacion_o2": ["", 85, 89, "89,5", 90, 91, 98], "frecuencia_respiratoria": ["", 6, 7, 8, 9, 30, 31],
    "ta_sistolica": ["", 70, 89, 90, 91, 120], "frecuencia_cardiaca": ["", 35, 39, 40, 41, 130, 131],
    "glasgow": ["", 3, 8, 9, 14, 15], "temperatura": ["", 36.5, 37.4, "37,5", 37.9, "38", 38, "38,2", 38.4, 38.5, 39],
    "dolor_intensidad": ["", 0, 4, 5, 7, 8, 10],
    "estado_conciencia": ["", "Alerta", "Responde a la voz", "Responde al dolor", "No responde"],
    "br_convulsion": [True, False, None], "br_disnea": [True, False, None],
    "br_sangrado": [True, False, None], "ant_inmuno": [True, False, None],
}


def test_misma_clasificacion_que_la_version_anterior():
    azar = random.Random(20261029)
    casos = json.loads((SEMILLA.parent / "casos_simulados.json").read_text(encoding="utf-8"))
    lista = [c["entrada"] for c in casos["casos"] if isinstance(c.get("entrada"), dict)]
    for _ in range(20000):
        d = {}
        for campo, valores in VALORES.items():
            v = azar.choice(valores)
            if v is not None:
                d[campo] = v
        lista.append(d)
    for d in lista:
        assert RS.nivel_reglas(d) == _nivel_v1(d), d


def _base(tmp_path, usar_ejemplo=None):
    base = tmp_path / "reglas.db"
    rh.inicializar_reglas(base)
    if usar_ejemplo is not None:
        con = sqlite3.connect(base)
        with con:
            con.execute("INSERT INTO reglas_config VALUES ('usar_ejemplo', ?, 'jefa', '2026-10-28')",
                        ("1" if usar_ejemplo else "0",))
        con.close()
    return base


def _leer(base):
    con = sqlite3.connect(base)
    con.row_factory = sqlite3.Row
    reglas = con.execute("SELECT * FROM reglas ORDER BY id").fetchall()
    config = {f["clave"]: f["valor"] for f in con.execute("SELECT * FROM reglas_config")}
    con.close()
    return reglas, config


def test_semilla_se_carga_activa_y_apaga_las_del_codigo(tmp_path):
    base = _base(tmp_path)
    assert rh.cargar_semilla(base, SEMILLA) == 16
    reglas, config = _leer(base)
    assert len(reglas) == 16 and [r["codigo"] for r in reglas][:2] == ["R-001", "R-002"]
    # Tanda 1: las 9 del prototipo, activas.
    assert all(r["estado"] == "activa" and r["origen"] == "manchester" and r["validada_por"] == "" for r in reglas[:9])
    # Tanda 2 (mail de Navoni): en borrador, nunca activadas.
    assert all(r["estado"] == "borrador" and r["fue_activada"] == 0 for r in reglas[9:13])
    # Tanda 3 (umbrales de la simulación): activas, porque ya intervenían en el color.
    assert [r["nombre"] for r in reglas[13:]] == ["Dolor moderado", "Febrícula", "Fiebre"]
    assert all(r["estado"] == "activa" and r["color"] == "AMARILLO" for r in reglas[13:])
    assert config["usar_ejemplo"] == "0" and config["semilla_cargada"] == "3"


def test_base_ya_sembrada_con_la_tanda_1_recibe_las_tandas_2_y_3(tmp_path):
    base = _base(tmp_path)
    con = sqlite3.connect(base)
    with con:   # como quedó una base con la Etapa B: tanda 1 cargada y la copia del código encendida a mano
        con.execute("INSERT INTO reglas_config VALUES ('semilla_cargada', '1', 'sistema', 'x')")
        con.execute("INSERT INTO reglas_config VALUES ('usar_ejemplo', '1', 'jefa', 'x')")
    con.close()
    assert rh.cargar_semilla(base, SEMILLA) == 7
    reglas, config = _leer(base)
    assert len(reglas) == 7 and all(r["estado"] == "borrador" for r in reglas[:4])
    assert all(r["estado"] == "activa" for r in reglas[4:])
    assert config["usar_ejemplo"] == "1" and config["semilla_cargada"] == "3"   # no toca la decisión de la Jefatura
    assert rh.cargar_semilla(base, SEMILLA) == 0


def test_semilla_no_se_carga_dos_veces(tmp_path):
    base = _base(tmp_path)
    rh.cargar_semilla(base, SEMILLA)
    con = sqlite3.connect(base)
    with con:
        con.execute("UPDATE reglas SET estado = 'inactiva' WHERE codigo = 'R-001'")   # la Jefatura la apagó
    con.close()
    assert rh.cargar_semilla(base, SEMILLA) == 0
    reglas, _ = _leer(base)
    assert len(reglas) == 16 and reglas[0]["estado"] == "inactiva"


def test_base_con_tandas_1_y_2_recibe_solo_la_tanda_3_activa(tmp_path):
    """La base de cada uno (ya con 13 reglas, semilla_cargada = 2) recibe solo las 3 nuevas, activas."""
    base = _base(tmp_path, usar_ejemplo=False)
    con = sqlite3.connect(base)
    with con:
        con.execute("INSERT INTO reglas_config VALUES ('semilla_cargada', '2', 'sistema', 'x')")
    con.close()
    assert rh.cargar_semilla(base, SEMILLA) == 3
    reglas, _ = _leer(base)
    assert [(r["codigo"], r["estado"]) for r in reglas] == [("R-001", "activa"), ("R-002", "activa"), ("R-003", "activa")]


def test_respeta_si_la_jefatura_ya_habia_apagado_las_de_ejemplo(tmp_path):
    base = _base(tmp_path, usar_ejemplo=False)
    rh.cargar_semilla(base, SEMILLA)
    reglas, config = _leer(base)
    assert all(r["estado"] == "borrador" and r["fue_activada"] == 0 for r in reglas[:13])
    assert all(r["estado"] == "activa" for r in reglas[13:])      # la tanda 3 fuerza «activa»
    assert config["usar_ejemplo"] == "0"


def test_semilla_valida_y_no_pisa_reglas_existentes(tmp_path):
    base = _base(tmp_path)
    con = sqlite3.connect(base)
    with con:
        con.execute("""INSERT INTO reglas (codigo, nombre, explicacion, color, combinacion, condiciones_json, estado,
            version, creada_por, creada_en, actualizada_por, actualizada_en) VALUES ('R-001', 'Propia', 'propia regla',
            'ROJO', 'todas', '[]', 'activa', 1, 'jefa', 'x', 'jefa', 'x')""")
    con.close()
    rh.cargar_semilla(base, SEMILLA)
    reglas, _ = _leer(base)
    assert reglas[0]["nombre"] == "Propia" and len(reglas) == 17 and reglas[1]["codigo"] == "R-002"
