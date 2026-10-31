"""
D4 (Dario 29/10, mail de Francisco Navoni, punto 5): condición especial del episodio
(policial, judicial, custodia…) registrada APARTE de la prioridad clínica.
Ejecutar desde backend:  python -m pytest -q tests/test_condicion_especial.py
"""
import pydantic
import pytest

from src.registro import registrar_datos_ingreso_demo, listar_espera_demo, exportar_episodios_demo
from src.esquemas import DatosTriage
from tests.test_api_hospital import AUTH, cliente  # noqa: F401


def test_se_guarda_y_se_informa_aparte_del_color(cliente):  # noqa: F811
    registrar_datos_ingreso_demo(cliente.base, "EPI-VERDE01", "enf1",
                                 {"edad": 40, "motivo_categoria": "Trauma", "condicion_especial": "Custodia policial"})
    espera = {e["codigo_episodio"]: e for e in listar_espera_demo(cliente.base, limite=100)["episodios"]}
    assert espera["EPI-VERDE01"]["condicion_especial"] == "Custodia policial"
    assert espera["EPI-VERDE01"]["color_final"] == "VERDE"            # el color clínico no cambia
    assert espera["EPI-AMARI02"]["condicion_especial"] is None

    cola = {p["codigo_episodio"]: p for p in cliente.get("/api/cola-espera", headers=AUTH).get_json()["pacientes"]}
    assert cola["EPI-VERDE01"]["condicion_especial"] == "Custodia policial" and cola["EPI-VERDE01"]["color"] == "VERDE"
    ficha = cliente.get("/api/episodios/EPI-VERDE01/mediciones", headers=AUTH).get_json()
    assert ficha["datos_ingreso"]["condicion_especial"] == "Custodia policial"


def test_valor_invalido_se_rechaza(cliente):  # noqa: F811
    with pytest.raises(pydantic.ValidationError):
        registrar_datos_ingreso_demo(cliente.base, "EPI-VERDE01", "enf1", {"condicion_especial": "Azul"})


def test_no_es_un_dato_clinico():
    # No está en los datos que van a la IA ni a la validación clínica.
    assert "condicion_especial" not in DatosTriage.model_fields


def test_exportacion_incluye_la_condicion(cliente):  # noqa: F811
    registrar_datos_ingreso_demo(cliente.base, "EPI-AMARI02", "enf1", {"condicion_especial": "Judicial"})
    resultado = exportar_episodios_demo(cliente.base)
    filas = resultado["filas"] if isinstance(resultado, dict) and "filas" in resultado else resultado
    texto = repr(filas)
    assert "Judicial" in texto
