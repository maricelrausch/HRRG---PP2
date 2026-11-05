"""
Pruebas del endpoint público para pantallas de sala (GET /api/sala/espera · Darío, campos nuevos Barby 30/10).
Ejecutar desde backend:  python -m pytest -q tests/test_sala_espera.py
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask

from src.registro import inicializar_registro
from src.sala_espera import bp


def _episodio(con, codigo, color, minutos):
    t = (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()
    con.execute("INSERT INTO episodios VALUES (?,?,?,?)", (codigo, "PAC-" + codigo[-4:], t, "enf1"))
    con.execute("INSERT INTO estados_episodio VALUES (?,?,?,?,1)", (codigo, "en_espera", t, "enf1"))
    con.execute("INSERT INTO eventos (codigo_episodio,tipo,ocurrido_en,profesional_usuario,datos_json) VALUES (?,?,?,?,?)",
                (codigo, "DECISION_REGISTRADA", t, "enf1", json.dumps({"decision": "aceptada", "color_final": color,
                                                                        "motivo": "", "version": 1})))


@pytest.fixture
def cliente(tmp_path):
    base = tmp_path / "triage.db"
    inicializar_registro(base)
    con = sqlite3.connect(base)
    _episodio(con, "EPI-0000VERDE", "VERDE", 30)
    _episodio(con, "EPI-000AMARIL", "AMARILLO", 75)   # superó 60 min
    _episodio(con, "EPI-00000ROJO", "ROJO", 5)
    con.commit()
    con.close()
    app = Flask(__name__)
    app.config["BASE_REGISTRO_DEMO"] = base
    app.register_blueprint(bp)
    return app.test_client()


def test_publico_sin_datos_personales(cliente):
    datos = cliente.get("/api/sala/espera").get_json()
    eps = datos["episodios"]
    assert [e["color"] for e in eps] == ["ROJO", "AMARILLO", "VERDE"]
    assert all(set(e) == {"codigo", "color", "espera_seg", "objetivo_min", "en_espera_desde", "vencido"} for e in eps)
    assert all(len(e["codigo"]) == 4 for e in eps)
    assert [e["vencido"] for e in eps] == [False, True, False]


def test_qr_svg_y_direcciones(cliente):
    pytest.importorskip("segno")
    r = cliente.get("/api/sala/qr.svg?destino=sala", base_url="http://192.168.1.35:5000")
    assert r.status_code == 200 and r.mimetype == "image/svg+xml" and b"<svg" in r.data
    d = cliente.get("/api/sala/qr", base_url="http://192.168.1.35:5000").get_json()
    assert d["direcciones"] == {"sala": "http://192.168.1.35:5000/sala.html"}
    assert cliente.get("/api/sala/qr.svg?destino=otro").status_code == 400
    assert cliente.get("/api/sala/qr.svg?destino=datos").status_code == 400   # [31/10] se sacó el QR al JSON
