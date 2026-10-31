"""
Pruebas de la API de auditoría para otro sistema (src/api_auditoria.py · propuesta Barby 30/10).

Arma una base temporal con datos ficticios, claves de identificación de prueba y una app Flask
mínima (no necesita Ollama, internet ni las claves reales).
Ejecutar desde backend:  python -m pytest -q tests/test_api_auditoria.py
"""
import io
import json
import secrets

import pytest
from cryptography.fernet import Fernet
from flask import Flask

import src.cifrado_identificacion as ci
from src.registro import inicializar_registro, crear_episodio, cambiar_estado_demo, registrar_decision_demo
from src.identificacion import inicializar_identificacion, identificar_paciente_demo
from src.api_auditoria import bp

TOKEN = "token-auditoria-0123456789"
AUTH = {"Authorization": "Bearer " + TOKEN}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    # Claves de identificación de prueba (nunca las reales).
    claves = tmp_path / "identificacion.json"
    claves.write_text(json.dumps({"version": 1, "cifrado": Fernet.generate_key().decode(),
                                  "busqueda": secrets.token_hex(32)}), encoding="utf-8")
    monkeypatch.setattr(ci.CifradoIdentificacion.__init__, "__defaults__", (claves,))

    base = tmp_path / "triage.db"
    inicializar_registro(base)
    inicializar_identificacion(base)
    pac = identificar_paciente_demo(base, "35111222", "enf1")["codigo_paciente"]
    otro = identificar_paciente_demo(base, "27456789", "enf1")["codigo_paciente"]
    for ep, p, estado, color in [("EPI-A1", pac, "en_espera", "AMARILLO"), ("EPI-A2", pac, "finalizado", "VERDE"),
                                 ("EPI-B1", otro, "en_espera", "NARANJA")]:
        crear_episodio(base, ep, p, "enf1")
        registrar_decision_demo(base, ep, "enf1", "aceptada", color, "", 0)
        cambiar_estado_demo(base, ep, "enf1", "en_espera", 0)
        if estado == "finalizado":
            cambiar_estado_demo(base, ep, "enf1", "finalizado", 1)

    app = Flask(__name__)
    app.config["BASE_REGISTRO_DEMO"] = base
    app.register_blueprint(bp)
    monkeypatch.setenv("HRRG_API_AUDITORIA_TOKEN", TOKEN)
    return app.test_client()


def test_apagada_sin_token_configurado(cliente, monkeypatch):
    monkeypatch.delenv("HRRG_API_AUDITORIA_TOKEN")
    assert cliente.get("/api/auditoria/casos", headers=AUTH).status_code == 503


def test_token_invalido(cliente):
    assert cliente.get("/api/auditoria/casos").status_code == 401
    assert cliente.get("/api/auditoria/casos", headers={"Authorization": "Bearer otro-token-cualquiera"}).status_code == 401


def test_lista_con_dni_completo_y_filtro_estado(cliente):
    r = cliente.get("/api/auditoria/casos", headers=AUTH).get_json()
    assert r["total"] == 3 and {c["dni"] for c in r["casos"]} == {"35111222", "27456789"}
    r = cliente.get("/api/auditoria/casos?estado=finalizado", headers=AUTH).get_json()
    assert r["total"] == 1 and r["casos"][0]["codigo_episodio"] == "EPI-A2"
    assert cliente.get("/api/auditoria/casos?estado=raro", headers=AUTH).status_code == 400
    assert cliente.get("/api/auditoria/casos?dni=35111222", headers=AUTH).status_code == 400   # el DNI no va en la URL


def test_buscar_por_dni(cliente):
    r = cliente.post("/api/auditoria/casos/buscar", json={"dni": "35.111.222"}, headers=AUTH)
    assert r.status_code == 200
    assert sorted(c["codigo_episodio"] for c in r.get_json()["casos"]) == ["EPI-A1", "EPI-A2"]
    assert cliente.post("/api/auditoria/casos/buscar", json={"dni": "11222333"}, headers=AUTH).status_code == 404
    assert cliente.post("/api/auditoria/casos/buscar", json={"dni": "12"}, headers=AUTH).status_code == 422


def test_historial(cliente):
    r = cliente.get("/api/auditoria/casos/EPI-A2", headers=AUTH).get_json()
    assert r["caso"]["dni"] == "35111222" and r["caso"]["estado"] == "finalizado"
    assert [e["tipo"] for e in r["eventos"]][-1] == "ESTADO_CAMBIADO"
    assert cliente.get("/api/auditoria/casos/EPI-NO", headers=AUTH).status_code == 404


def test_exportar_json(cliente):
    r = cliente.post("/api/auditoria/exportar", json={"formato": "json", "dni": "27456789"}, headers=AUTH).get_json()
    assert r["total"] == 1 and r["casos"][0]["dni"] == "27456789" and r["casos"][0]["historial"]


def test_exportar_excel_y_pdf_protegidos(cliente):
    msoffcrypto = pytest.importorskip("msoffcrypto")
    pikepdf = pytest.importorskip("pikepdf")
    clave = "clave-del-sistema-123"
    assert cliente.post("/api/auditoria/exportar", json={"formato": "excel"}, headers=AUTH).status_code == 422
    r = cliente.post("/api/auditoria/exportar", json={"formato": "excel", "clave": clave}, headers=AUTH)
    assert r.status_code == 200 and r.headers["Content-Disposition"].endswith('.xlsx"')
    archivo = msoffcrypto.OfficeFile(io.BytesIO(r.data))
    assert archivo.is_encrypted()
    r = cliente.post("/api/auditoria/exportar", json={"formato": "pdf", "clave": clave, "estado": "en_espera"}, headers=AUTH)
    assert r.status_code == 200
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(io.BytesIO(r.data))
    with pikepdf.open(io.BytesIO(r.data), password=clave) as pdf:
        assert len(pdf.pages) >= 1


def test_exportar_validaciones(cliente):
    assert cliente.post("/api/auditoria/exportar", json={"formato": "csv"}, headers=AUTH).status_code == 400
    assert cliente.post("/api/auditoria/exportar", json={"formato": "json", "clave": "x" * 12}, headers=AUTH).status_code == 400
    assert cliente.post("/api/auditoria/exportar", data="formato=json", headers=AUTH).status_code == 415
