# Web service para el sistema del hospital (Darío) · sugerencia del profesor, opcional.
#
#   Sistema del hospital → GET a esta API → la app devuelve JSON.
#
#   GET /api/cola-espera                                  Cola actual con prioridad y espera.
#   GET /api/episodios/<codigo_episodio>/mediciones       Datos de la evaluación (como el PDF).
#
# Seguridad:
#   - Solo lectura. Cada pedido tiene que traer:  Authorization: Bearer <token>
#     El token se define en la variable de entorno HRRG_API_HOSPITAL_TOKEN.
#     Sin esa variable la API queda APAGADA (responde 503): nunca queda abierta por olvido.
#   - El DNI es dato personal: NO se devuelve. Solo sale si además se define
#     HRRG_API_HOSPITAL_DNI=1 (para datos reales hace falta, además, HTTPS).
#   - Los pacientes se identifican por codigo_episodio / codigo_paciente (códigos internos).
#   - Se registra cada acceso (ruta, IP, resultado), sin datos de pacientes.
import hmac
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from src.registro import (listar_espera_demo, obtener_episodio, obtener_estado_demo,
                          _BANDERAS, _ANTECEDENTES)

bp = Blueprint("api_hospital", __name__)
logger = logging.getLogger("hrrg.sistema.api_hospital")   # va al mismo archivo de log del sistema

VERSION_API = "1.0"
COLORES = ("ROJO", "NARANJA", "AMARILLO", "VERDE")              # AZUL fuera (decisión del equipo)
PRIORIDAD = {c: i + 1 for i, c in enumerate(COLORES)}            # 1 = más urgente
OBJETIVO_MIN = {"ROJO": 0, "NARANJA": 10, "AMARILLO": 60, "VERDE": 120}


# ---------------------------------------------------------------- utilidades
def _error(mensaje, estado, codigo):
    return jsonify({"ok": False, "codigo": codigo, "mensaje": mensaje}), estado


def _ahora():
    return datetime.now(timezone.utc)


def _fecha(valor):
    fecha = datetime.fromisoformat(valor)
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _incluir_dni():
    return os.environ.get("HRRG_API_HOSPITAL_DNI") == "1"


def _agregar_dni(registros):
    """Solo con HRRG_API_HOSPITAL_DNI=1. Si el descifrado falla, sale sin DNI."""
    if not _incluir_dni() or not registros:
        return
    try:
        from src.identificacion import dnis_de_pacientes
        dnis = dnis_de_pacientes(current_app.config["BASE_REGISTRO_DEMO"],
                                 [r["codigo_paciente"] for r in registros])
        for r in registros:
            r["dni"] = dnis.get(r["codigo_paciente"])
    except Exception:
        logger.error("API_HOSPITAL_ERROR_DNI")


def _responder(datos):
    respuesta = jsonify({"ok": True, "version_api": VERSION_API, "modo": "demo",
                         "generado_en": _ahora().isoformat(timespec="seconds"), **datos})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200


# ---------------------------------------------------------------- autenticación
@bp.before_request
def verificar_token():
    token = os.environ.get("HRRG_API_HOSPITAL_TOKEN", "")
    ip = request.remote_addr
    if len(token) < 16:
        logger.warning("API_HOSPITAL_APAGADA ruta=%s ip=%s", request.path, ip)
        return _error("La API para el hospital no está habilitada.", 503, "API_DESHABILITADA")

    cabecera = request.headers.get("Authorization", "")
    dado = cabecera[7:] if cabecera.startswith("Bearer ") else ""
    if not hmac.compare_digest(dado.encode(), token.encode()):
        logger.warning("API_HOSPITAL_TOKEN_INVALIDO ruta=%s ip=%s", request.path, ip)
        respuesta, estado = _error("Token ausente o inválido.", 401, "TOKEN_INVALIDO")
        respuesta.headers["WWW-Authenticate"] = 'Bearer realm="hrrg"'
        return respuesta, estado

    logger.info("API_HOSPITAL_ACCESO ruta=%s ip=%s", request.path, ip)
    return None


# ---------------------------------------------------------------- cola de espera
@bp.route("/api/cola-espera", methods=["GET"])
def cola_espera():
    """Pacientes en espera YA clasificados (los sin color no pasaron por el triage),
    ordenados por prioridad y, dentro de cada color, por quien espera más."""
    if set(request.args) - {"color"}:
        return _error("Parámetro desconocido. Solo se acepta ?color=", 400, "PARAMETROS_INVALIDOS")
    filtro = request.args.get("color", "").upper() or None
    if filtro and filtro not in COLORES:
        return _error("Color inválido. Usá ROJO, NARANJA, AMARILLO o VERDE.", 400, "COLOR_INVALIDO")

    try:
        episodios, desplazamiento = [], 0
        while True:
            pagina = listar_espera_demo(current_app.config["BASE_REGISTRO_DEMO"],
                                        limite=100, desplazamiento=desplazamiento)
            episodios += pagina["episodios"]
            desplazamiento += len(pagina["episodios"])
            if not pagina["episodios"] or desplazamiento >= pagina["total"]:
                break
    except (sqlite3.Error, ValueError):
        logger.error("API_HOSPITAL_ERROR_COLA")
        return _error("No se pudo consultar la cola de espera.", 500, "ERROR_REGISTRO")

    ahora = _ahora()
    cola = []
    for ep in episodios:
        color = ep.get("color_final")
        if color not in PRIORIDAD:
            continue
        espera = max(0, int((ahora - _fecha(ep["en_espera_desde"])).total_seconds() // 60))
        cola.append({
            "codigo_episodio": ep["codigo_episodio"],
            "codigo_paciente": ep["codigo_paciente"],
            "color": color,
            "prioridad": PRIORIDAD[color],
            "en_espera_desde": ep["en_espera_desde"],
            "espera_min": espera,
            "tiempo_maximo_min": OBJETIVO_MIN[color],
            "vencido": color != "ROJO" and espera > OBJETIVO_MIN[color],
            "motivo_categoria": ep.get("motivo_categoria"),
        })

    cola.sort(key=lambda p: (p["prioridad"], -p["espera_min"]))
    for i, p in enumerate(cola, start=1):
        p["posicion"] = i                     # puesto en la cola completa (aun filtrando)
    if filtro:
        cola = [p for p in cola if p["color"] == filtro]

    _agregar_dni(cola)
    resumen = {c: sum(1 for p in cola if p["color"] == c) for c in COLORES}
    return _responder({"total": len(cola), "por_color": resumen, "pacientes": cola})


# ---------------------------------------------------------------- mediciones
def _armar_mediciones(eventos):
    """Cada medición con sus correcciones ya aplicadas (como en el PDF/Excel)."""
    por_id, raiz = {}, {}
    for ev in eventos:
        d = ev["datos"]
        if ev["tipo"] == "MEDICION_REGISTRADA":
            raiz[ev["id"]] = ev["id"]
            por_id[ev["id"]] = {"medicion_id": ev["id"], "medido_en": d["medido_en"],
                                "registrado_en": ev["ocurrido_en"],
                                "profesional": ev["profesional_usuario"],
                                "valores": dict(d.get("valores", {})), "corregida": False}
        elif ev["tipo"] == "MEDICION_CORREGIDA" and d.get("evento_corregido_id") in raiz:
            r = raiz[d["evento_corregido_id"]]
            raiz[ev["id"]] = r
            por_id[r]["valores"] = dict(d.get("valores", {}))   # la corrección trae la versión completa
            por_id[r]["corregida"] = True
    return sorted(por_id.values(), key=lambda m: (_fecha(m["medido_en"]), m["medicion_id"]))


@bp.route("/api/episodios/<codigo_episodio>/mediciones", methods=["GET"])
def mediciones_episodio(codigo_episodio):
    if request.args:
        return _error("Esta ruta no acepta parámetros.", 400, "PARAMETROS_INVALIDOS")
    try:
        ep = obtener_episodio(current_app.config["BASE_REGISTRO_DEMO"], codigo_episodio.strip(),
                              profesional_usuario=None, permitir_lectura_compartida=True)
    except sqlite3.Error:
        logger.error("API_HOSPITAL_ERROR_EPISODIO")
        return _error("No se pudo consultar el episodio.", 500, "ERROR_REGISTRO")
    if ep is None:
        return _error("El episodio no existe.", 404, "EPISODIO_NO_ENCONTRADO")

    eventos = ep["eventos"]
    ingreso, decision = None, None
    for ev in eventos:
        d = ev["datos"]
        if ev["tipo"] == "DATOS_INGRESO_REGISTRADOS":
            v = d.get("valores", {})
            ingreso = {
                "edad": v.get("edad"), "sexo": v.get("sexo"),
                "motivo_categoria": v.get("motivo_categoria"),
                "motivo_consulta": v.get("motivo_consulta"),
                "tiempo_evolucion": ({"valor": v["tiempo_evolucion_valor"],
                                      "unidad": v.get("tiempo_evolucion_unidad")}
                                     if v.get("tiempo_evolucion_valor") is not None else None),
                "banderas_rojas": [t for k, t in _BANDERAS.items() if v.get(k)],
                "antecedentes": [t for k, t in _ANTECEDENTES.items() if v.get(k)]
                                + [x for x in (v.get("antecedentes_otros"),) if x],
                "registrado_en": ev["ocurrido_en"],
            }
        elif ev["tipo"] == "DECISION_REGISTRADA":
            decision = {"color": d.get("color_final"), "decision": d.get("decision"),
                        "motivo": d.get("motivo"), "profesional": ev["profesional_usuario"],
                        "registrada_en": ev["ocurrido_en"],
                        "escalado_rojo": "Escalado manual" in (d.get("motivo") or "")}

    try:
        estado = obtener_estado_demo(current_app.config["BASE_REGISTRO_DEMO"], ep["codigo_episodio"])["estado"]
    except (sqlite3.Error, ValueError):
        estado = None
    mediciones = _armar_mediciones(eventos)
    datos = {
        "episodio": {
            "codigo_episodio": ep["codigo_episodio"],
            "codigo_paciente": ep["codigo_paciente"],
            "creado_en": ep["creado_en"],
            "estado": estado,
        },
        "datos_ingreso": ingreso,
        "decision": decision,
        "ultima_medicion": mediciones[-1] if mediciones else None,
        "mediciones": mediciones,
    }
    _agregar_dni([datos["episodio"]])
    return _responder(datos)
