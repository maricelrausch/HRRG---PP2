# API de auditoría para otro sistema (propuesta Barby 30/10 · pedido del HRRG).
#
#   Da a un sistema externo (por ejemplo, el de calidad o el del hospital) acceso de SOLO LECTURA
#   a lo mismo que ve el perfil Auditoría en la pantalla: búsqueda de casos, historial completo
#   de cada episodio y exportación (JSON, Excel o PDF).
#
#   GET  /api/auditoria/casos                        Lista de casos (filtros: estado, desde, hasta; paginada)
#   POST /api/auditoria/casos/buscar     {"dni"}     Todas las atenciones de un paciente (el DNI va en el cuerpo)
#   GET  /api/auditoria/casos/<codigo_episodio>      Historial completo de un episodio
#   POST /api/auditoria/exportar                     {"formato": "json"|"excel"|"pdf", filtros, "clave"}
#
# Seguridad:
#   - Cada pedido trae  Authorization: Bearer <token>. El token se define en la variable de entorno
#     HRRG_API_AUDITORIA_TOKEN (mínimo 16 caracteres). Es DISTINTO del de la API del hospital, así
#     se puede revocar por separado. Sin esa variable, la API queda APAGADA (503).
#   - Devuelve el DNI COMPLETO (decisión del grupo 30/10): es dato personal. Con datos reales hace
#     falta HTTPS y autorización del hospital. El DNI nunca va en la URL ni en el log.
#   - Excel y PDF salen protegidos con la "clave" que manda el sistema (12 caracteres o más).
#   - Se registra cada acceso (ruta, IP, resultado y cantidad), sin datos de pacientes.
import hmac
import logging
import os
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from src.registro import buscar_episodios, obtener_episodio, obtener_estado_demo, exportar_episodios_demo

bp = Blueprint("api_auditoria", __name__)
logger = logging.getLogger("hrrg.sistema.api_auditoria")

VERSION_API = "1.0"
ESTADOS = ("en_ingreso", "en_espera", "finalizado", "anulado")
FORMATOS = ("json", "excel", "pdf")


# ---------------------------------------------------------------- utilidades
def _error(mensaje, estado, codigo):
    respuesta = jsonify({"ok": False, "codigo": codigo, "mensaje": mensaje})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, estado


def _responder(datos):
    respuesta = jsonify({"ok": True, "version_api": VERSION_API, "modo": "demo",
                         "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"), **datos})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200


def _base():
    return current_app.config["BASE_REGISTRO_DEMO"]


def _agregar_dni(registros):
    """Agrega el DNI completo a cada registro (por su codigo_paciente). Si falla el descifrado, error 503."""
    if not registros:
        return None
    from src.identificacion import dnis_de_pacientes
    from src.cifrado_identificacion import ErrorCifradoIdentificacion
    try:
        dnis = dnis_de_pacientes(_base(), [r["codigo_paciente"] for r in registros])
    except ErrorCifradoIdentificacion:
        logger.error("API_AUDITORIA_ERROR_CIFRADO")
        return _error("El servicio de identificación no está disponible.", 503, "IDENTIFICACION_NO_DISPONIBLE")
    except sqlite3.Error:
        logger.error("API_AUDITORIA_ERROR_DNI")
        return _error("No se pudo consultar la identificación de los pacientes.", 500, "ERROR_REGISTRO")
    for r in registros:
        r["dni"] = dnis.get(r["codigo_paciente"])
    return None


def _codigo_por_dni(dni):
    """Devuelve (codigo_paciente, None) o (None, respuesta_de_error)."""
    from src.identificacion import buscar_paciente_por_dni
    from src.cifrado_identificacion import ErrorCifradoIdentificacion
    if not isinstance(dni, (str, int)) or isinstance(dni, bool):
        return None, _error("Enviá el DNI como texto.", 422, "IDENTIFICACION_INVALIDA")
    try:
        paciente = buscar_paciente_por_dni(_base(), str(dni))
    except ValueError as error:
        return None, _error(str(error), 422, "IDENTIFICACION_INVALIDA")
    except ErrorCifradoIdentificacion:
        logger.error("API_AUDITORIA_ERROR_CIFRADO")
        return None, _error("El servicio de identificación no está disponible.", 503, "IDENTIFICACION_NO_DISPONIBLE")
    if paciente is None:
        return None, _error("No hay ningún paciente identificado con ese DNI.", 404, "PACIENTE_NO_ENCONTRADO")
    return paciente["codigo_paciente"], None


def _json_entrada(permitidos):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or set(datos) - permitidos:
        return None
    return datos


# ---------------------------------------------------------------- autenticación
@bp.before_request
def verificar_token():
    token = os.environ.get("HRRG_API_AUDITORIA_TOKEN", "")
    ip = request.remote_addr
    if len(token) < 16:
        logger.warning("API_AUDITORIA_APAGADA ruta=%s ip=%s", request.path, ip)
        return _error("La API de auditoría no está habilitada.", 503, "API_DESHABILITADA")

    cabecera = request.headers.get("Authorization", "")
    dado = cabecera[7:] if cabecera.startswith("Bearer ") else ""
    if not hmac.compare_digest(dado.encode(), token.encode()):
        logger.warning("API_AUDITORIA_TOKEN_INVALIDO ruta=%s ip=%s", request.path, ip)
        respuesta, estado = _error("Token ausente o inválido.", 401, "TOKEN_INVALIDO")
        respuesta.headers["WWW-Authenticate"] = 'Bearer realm="hrrg-auditoria"'
        return respuesta, estado

    if request.method == "POST" and not request.is_json:
        return _error("Enviá el contenido como application/json.", 415, "FORMATO_NO_ADMITIDO")

    logger.info("API_AUDITORIA_ACCESO ruta=%s ip=%s", request.path, ip)
    return None


# ---------------------------------------------------------------- casos
@bp.route("/api/auditoria/casos", methods=["GET"])
def listar_casos():
    permitidos = {"estado", "desde", "hasta", "limite", "desplazamiento"}
    if set(request.args) - permitidos or any(len(request.args.getlist(k)) != 1 for k in request.args):
        return _error("Parámetro desconocido. Se aceptan estado, desde, hasta, limite y desplazamiento.",
                      400, "PARAMETROS_INVALIDOS")
    estado = request.args.get("estado") or None
    if estado is not None and estado not in ESTADOS:
        return _error("Estado inválido. Usá en_ingreso, en_espera, finalizado o anulado.", 400, "ESTADO_INVALIDO")
    try:
        limite = int(request.args.get("limite", "50"))
        desplazamiento = int(request.args.get("desplazamiento", "0"))
    except ValueError:
        return _error("El límite y el desplazamiento deben ser números enteros.", 422, "PAGINACION_INVALIDA")
    if not 1 <= limite <= 100 or desplazamiento < 0:
        return _error("El límite va de 1 a 100 y el desplazamiento no puede ser negativo.", 422, "PAGINACION_INVALIDA")

    try:
        resultado = buscar_episodios(_base(), limite=limite, desplazamiento=desplazamiento,
                                     desde=request.args.get("desde"), hasta=request.args.get("hasta"),
                                     estado=estado)
    except ValueError as error:
        return _error(str(error), 422, "FILTRO_INVALIDO")
    except sqlite3.Error:
        logger.error("API_AUDITORIA_ERROR_CASOS")
        return _error("No se pudieron consultar los casos.", 500, "ERROR_REGISTRO")

    error = _agregar_dni(resultado["episodios"])
    if error:
        return error
    logger.info("API_AUDITORIA_CASOS n=%d", len(resultado["episodios"]))
    return _responder({"total": resultado["total"], "limite": limite, "desplazamiento": desplazamiento,
                       "casos": resultado["episodios"]})


@bp.route("/api/auditoria/casos/buscar", methods=["POST"])
def buscar_por_dni():
    datos = _json_entrada({"dni"})
    if datos is None or "dni" not in datos:
        return _error('Enviá únicamente {"dni": "30123456"}.', 400, "CAMPOS_INVALIDOS")
    codigo, error = _codigo_por_dni(datos["dni"])
    if error:
        return error
    try:
        resultado = buscar_episodios(_base(), codigo_paciente=codigo, limite=100)
    except sqlite3.Error:
        logger.error("API_AUDITORIA_ERROR_BUSCAR")
        return _error("No se pudieron consultar los casos.", 500, "ERROR_REGISTRO")
    error = _agregar_dni(resultado["episodios"])
    if error:
        return error
    logger.info("API_AUDITORIA_BUSCAR_DNI n=%d", len(resultado["episodios"]))
    return _responder({"codigo_paciente": codigo, "total": resultado["total"], "casos": resultado["episodios"]})


@bp.route("/api/auditoria/casos/<codigo_episodio>", methods=["GET"])
def historial_caso(codigo_episodio):
    if request.args:
        return _error("Esta ruta no acepta parámetros.", 400, "PARAMETROS_INVALIDOS")
    try:
        ep = obtener_episodio(_base(), codigo_episodio.strip(), profesional_usuario=None,
                              permitir_lectura_compartida=True)
    except sqlite3.Error:
        logger.error("API_AUDITORIA_ERROR_EPISODIO")
        return _error("No se pudo consultar el episodio.", 500, "ERROR_REGISTRO")
    if ep is None:
        return _error("El episodio no existe.", 404, "EPISODIO_NO_ENCONTRADO")
    try:
        estado = obtener_estado_demo(_base(), ep["codigo_episodio"])
    except (sqlite3.Error, ValueError):
        estado = None
    caso = {
        "codigo_episodio": ep["codigo_episodio"],
        "codigo_paciente": ep["codigo_paciente"],
        "creado_en": ep["creado_en"],
        "profesional_ingreso": ep.get("profesional_usuario"),
        "estado": estado.get("estado") if estado else None,
    }
    error = _agregar_dni([caso])
    if error:
        return error
    return _responder({"caso": caso, "eventos": ep["eventos"]})


# ---------------------------------------------------------------- exportación
@bp.route("/api/auditoria/exportar", methods=["POST"])
def exportar():
    datos = _json_entrada({"formato", "estado", "desde", "hasta", "dni", "clave"})
    if datos is None or datos.get("formato") not in FORMATOS:
        return _error('Enviá "formato": "json", "excel" o "pdf" (y, si querés, estado, desde, hasta, dni y clave).',
                      400, "CAMPOS_INVALIDOS")
    formato = datos["formato"]
    estado = datos.get("estado") or None
    if estado is not None and estado not in ESTADOS:
        return _error("Estado inválido. Usá en_ingreso, en_espera, finalizado o anulado.", 400, "ESTADO_INVALIDO")
    clave = datos.get("clave")
    if formato != "json":
        if not isinstance(clave, str) or not 12 <= len(clave) <= 256:
            return _error("Para Excel o PDF enviá una \"clave\" de 12 caracteres o más: protege el archivo.",
                          422, "CLAVE_INVALIDA")
    elif clave is not None:
        return _error("La clave solo se usa para Excel o PDF.", 400, "CAMPOS_INVALIDOS")

    codigo = None
    if datos.get("dni"):
        codigo, error = _codigo_por_dni(datos["dni"])
        if error:
            return error

    try:
        filas = exportar_episodios_demo(
            _base(),
            estado=None if codigo else estado,
            desde=None if codigo else datos.get("desde"),
            hasta=None if codigo else datos.get("hasta"),
            codigo_paciente=codigo,
        )
    except ValueError as error:
        return _error(str(error), 422, "FILTRO_INVALIDO")
    except sqlite3.Error:
        logger.error("API_AUDITORIA_ERROR_EXPORTAR")
        return _error("No se pudo exportar el historial de casos.", 500, "ERROR_REGISTRO")

    error = _agregar_dni(filas)
    if error:
        return error

    if codigo:
        filtros = "Un solo paciente (todas sus atenciones)"
    else:
        filtros = "Estado: " + (estado or "todos")
        if datos.get("desde") or datos.get("hasta"):
            filtros += " · Fechas: " + (datos.get("desde") or "…") + " a " + (datos.get("hasta") or "…")
    logger.info("API_AUDITORIA_EXPORTAR formato=%s n=%d paciente=%s", formato, len(filas), "sí" if codigo else "no")

    if formato == "json":
        return _responder({"filtros": filtros, "total": len(filas), "casos": filas})

    from src.exportacion import (generar_xlsx, generar_pdf, proteger_xlsx, proteger_pdf,
                                 TEXTO_IDENTIFICACION_API)
    marca = datetime.now().strftime("%Y%m%d_%H%M")
    try:
        if formato == "pdf":
            contenido = proteger_pdf(generar_pdf(filas, filtros, "API de auditoría", TEXTO_IDENTIFICACION_API), clave)
            mime, nombre = "application/pdf", f"auditoria_triage_{marca}.pdf"
        else:
            contenido = proteger_xlsx(generar_xlsx(filas, filtros, "API de auditoría", TEXTO_IDENTIFICACION_API), clave)
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            nombre = f"auditoria_triage_{marca}.xlsx"
    except ImportError:
        return _error("Faltan librerías de exportación en el servidor (python -m pip install -r requirements.txt).",
                      503, "EXPORTACION_NO_DISPONIBLE")

    respuesta = current_app.response_class(contenido, mimetype=mime)
    respuesta.headers["Content-Disposition"] = f'attachment; filename="{nombre}"'
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200
