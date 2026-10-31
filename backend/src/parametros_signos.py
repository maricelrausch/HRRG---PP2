"""Rangos de los signos vitales (Dario 30/10, pedido de Francisco Navoni: nada de umbrales fijos en el código).

Antes estaban escritos en frontend/formulario.js (texto «Normal …», avisos), frontend/validacion.js
(rango posible) y backend/ia/medgemma.py (qué es «normal» para MedGemma). Ahora están en la tabla
parametros_signos de reglas_hospital.db, una fila por dato y GRUPO ETARIO (Adulto es la base: si un grupo
no tiene su fila, se usa la de Adulto). Los valores iniciales son los mismos que había en el código
(datos/parametros_signos_semilla.json) y NO son oficiales: la Jefatura los corrige en reglas.html.

Qué guarda cada fila:
    minimo_posible / maximo_posible  frena errores de tipeo (no es un criterio clínico).
    normal_min / normal_max          pinta el campo «fuera de lo normal» y se le informa a MedGemma.
    texto_bajo / texto_alto          «Bradicardia», «Taquicardia»…
    referencia                       texto debajo del campo; vacío = «Normal min–max».
    obligatorio                      si falta, la pantalla lo pide.
La marca ROJA de la pantalla no está acá: sale de las reglas activas (un solo lugar para cada umbral).

Rutas (misma sesión y permisos que las reglas):
    GET  /api/signos                 parámetros + grupos etarios + historial (todos los perfiles del triage)
    POST /api/signos                 crear o modificar una fila (jefatura)
    POST /api/signos/<id>/eliminar   borrar una fila de un grupo que no sea Adulto (jefatura)
"""
import json
import logging
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, session

from src.auth import obtener_profesional
from src.admin_usuarios import estado_acceso, requiere_cambio
from src.reglas_hospital import GRUPOS_ETARIOS, ORIGENES, _ahora, _numero, grupo_etario

bp = Blueprint("parametros_signos", __name__)
logger = logging.getLogger("hrrg.sistema")

GRUPO_BASE = "Adulto"
GRUPOS = [g[0] for g in GRUPOS_ETARIOS]
CAMPOS_SIGNOS = ["ta_sistolica", "ta_diastolica", "frecuencia_cardiaca", "frecuencia_respiratoria",
                 "saturacion_o2", "temperatura", "glucemia", "glasgow", "dolor_intensidad"]
TEXTOS = {"nombre": 60, "abreviatura": 20, "unidad": 20, "texto_bajo": 60, "texto_alto": 60,
          "referencia": 80, "validada_por": 120}
NUMEROS = ("minimo_posible", "maximo_posible", "normal_min", "normal_max")


# ------------------------------------------------ base
def inicializar_parametros(ruta_base):
    conexion = sqlite3.connect(ruta_base)
    try:
        with conexion:
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS parametros_signos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campo TEXT NOT NULL,
                    grupo_etario TEXT NOT NULL,
                    nombre TEXT NOT NULL,
                    abreviatura TEXT NOT NULL DEFAULT '',
                    unidad TEXT NOT NULL DEFAULT '',
                    minimo_posible REAL NOT NULL,
                    maximo_posible REAL NOT NULL,
                    normal_min REAL,
                    normal_max REAL,
                    texto_bajo TEXT NOT NULL DEFAULT '',
                    texto_alto TEXT NOT NULL DEFAULT '',
                    referencia TEXT NOT NULL DEFAULT '',
                    obligatorio INTEGER NOT NULL DEFAULT 0,
                    orden INTEGER NOT NULL DEFAULT 0,
                    origen TEXT NOT NULL DEFAULT 'provisoria',
                    validada_por TEXT NOT NULL DEFAULT '',
                    validada_en TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 1,
                    creada_por TEXT NOT NULL,
                    creada_en TEXT NOT NULL,
                    actualizada_por TEXT NOT NULL,
                    actualizada_en TEXT NOT NULL,
                    UNIQUE (campo, grupo_etario)
                )
            """)
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS parametros_signos_eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parametro_id INTEGER,
                    fecha TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    accion TEXT NOT NULL,
                    version INTEGER,
                    datos_json TEXT NOT NULL
                )
            """)
    finally:
        conexion.close()


def cargar_parametros_semilla(ruta_base, ruta_semilla):
    """Carga los valores iniciales (los que estaban en el código) si la tabla está vacía. Devuelve cuántos cargó."""
    conexion = sqlite3.connect(ruta_base)
    try:
        if conexion.execute("SELECT COUNT(*) FROM parametros_signos").fetchone()[0]:
            return 0
        with open(ruta_semilla, encoding="utf-8") as archivo:
            filas = json.load(archivo)["parametros"]
        ahora = _ahora()
        with conexion:
            for datos in filas:
                p, error = validar_parametro(dict(datos, grupo_etario=GRUPO_BASE))
                if error:
                    raise ValueError(f"Parámetro {datos.get('campo')} de la semilla inválido: {error}")
                cursor = conexion.execute(
                    f"INSERT INTO parametros_signos ({', '.join(p)}, version, creada_por, creada_en, actualizada_por, actualizada_en) "
                    f"VALUES ({', '.join('?' * len(p))}, 1, 'sistema', ?, 'sistema', ?)",
                    (*p.values(), ahora, ahora))
                conexion.execute(
                    "INSERT INTO parametros_signos_eventos (parametro_id, fecha, usuario, accion, version, datos_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (cursor.lastrowid, ahora, "sistema", "CARGADO (valores que estaban en el código)", 1,
                     json.dumps(p, ensure_ascii=False)))
    finally:
        conexion.close()
    logger.info("PARAMETROS_SIGNOS_CARGADOS | %d", len(filas))
    return len(filas)


def _a_dict(fila):
    d = dict(fila)
    d["obligatorio"] = bool(d["obligatorio"])
    return d


def leer_parametros(ruta_base):
    """Todas las filas. Nunca falla: sin base o sin tabla devuelve []."""
    if not ruta_base or not Path(ruta_base).exists():
        return []
    try:
        conexion = sqlite3.connect(ruta_base)
        conexion.row_factory = sqlite3.Row
        try:
            return [_a_dict(f) for f in conexion.execute("SELECT * FROM parametros_signos ORDER BY orden, campo, grupo_etario")]
        finally:
            conexion.close()
    except sqlite3.Error:
        return []


def parametros_para(ruta_base, edad=None):
    """{campo: fila} para la edad del paciente: la fila de su grupo etario o, si no hay, la de Adulto."""
    grupo = grupo_etario(edad) or GRUPO_BASE
    filas = leer_parametros(ruta_base)
    base = {f["campo"]: f for f in filas if f["grupo_etario"] == GRUPO_BASE}
    propio = {f["campo"]: f for f in filas if f["grupo_etario"] == grupo}
    return {**base, **propio}


# ------------------------------------------------ validación
def validar_parametro(datos):
    """Devuelve (parametro_normalizado, None) o (None, mensaje)."""
    if not isinstance(datos, dict):
        return None, "Enviá los datos del parámetro."
    permitidos = set(NUMEROS) | set(TEXTOS) | {"campo", "grupo_etario", "obligatorio", "orden", "origen"}
    if set(datos) - permitidos:
        return None, "Hay campos que no corresponden a un parámetro."
    if datos.get("campo") not in CAMPOS_SIGNOS:
        return None, "Elegí un signo vital de la lista."
    if datos.get("grupo_etario") not in GRUPOS:
        return None, "Elegí un grupo etario de la lista."
    p = {"campo": datos["campo"], "grupo_etario": datos["grupo_etario"]}
    for k, largo in TEXTOS.items():
        v = datos.get(k, "")
        v = "" if v is None else v
        if not isinstance(v, str) or len(v.strip()) > largo:
            return None, f"«{k}» admite hasta {largo} caracteres."
        p[k] = v.strip()
    if not p["nombre"]:
        return None, "El nombre es obligatorio."
    for k in NUMEROS:
        v = datos.get(k)
        if v in (None, "") and k.startswith("normal"):
            p[k] = None
            continue
        try:
            p[k] = _numero(v)
        except (ValueError, TypeError):
            return None, f"«{k}» tiene que ser un número."
    if p["minimo_posible"] >= p["maximo_posible"]:
        return None, "El mínimo posible tiene que ser menor que el máximo posible."
    for k in ("normal_min", "normal_max"):
        if p[k] is not None and not p["minimo_posible"] <= p[k] <= p["maximo_posible"]:
            return None, "El rango normal tiene que estar dentro del rango posible."
    if p["normal_min"] is not None and p["normal_max"] is not None and p["normal_min"] > p["normal_max"]:
        return None, "En el rango normal, el mínimo no puede ser mayor que el máximo."
    p["obligatorio"] = 1 if datos.get("obligatorio") in (True, 1, "1", "si", "sí") else 0
    try:
        p["orden"] = int(datos.get("orden") or 0)
    except (ValueError, TypeError):
        return None, "El orden tiene que ser un número entero."
    origen = datos.get("origen", "provisoria")
    if origen not in ORIGENES:
        return None, "Elegí el origen: Manchester, adaptación local HRRG o provisoria."
    p["origen"] = origen
    return p, None


# ------------------------------------------------ acceso (mismo criterio que las reglas)
LECTURA = {"enfermeria", "medico", "auditor", "jefatura"}


def _error(mensaje, estado, codigo):
    respuesta = jsonify({"ok": False, "mensaje": mensaje, "codigo": codigo})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, estado


def _ok(**datos):
    respuesta = jsonify({"ok": True, **datos})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@bp.before_request
def exigir_sesion():
    if request.method == "POST" and not request.is_json:
        return _error("La solicitud debe estar en formato JSON.", 415, "FORMATO_NO_SOPORTADO")
    base = current_app.config["BASE_USUARIOS"]
    usuario = session.get("usuario")
    profesional = obtener_profesional(base, usuario) if usuario else None
    cuenta = estado_acceso(base, usuario) if usuario else None
    if profesional is None or cuenta is None or cuenta["bloqueada"]:
        session.clear()
        return _error("Debés iniciar sesión para continuar.", 401, "SESION_REQUERIDA")
    if requiere_cambio(cuenta):
        return _error("Tenés que cambiar tu contraseña antes de continuar.", 403, "CAMBIO_PASSWORD_REQUERIDO")
    g.profesional = profesional
    permitido = profesional["rol"] in LECTURA if request.method == "GET" else profesional["rol"] == "jefatura"
    if not permitido:
        return _error("Tu perfil no puede hacer esto. Los rangos los administra la Jefatura de Guardia.",
                      403, "PERMISO_DENEGADO")
    return None


# ------------------------------------------------ rutas
def _conectar():
    conexion = sqlite3.connect(current_app.config["BASE_REGLAS"])
    conexion.row_factory = sqlite3.Row
    return conexion


def _evento(conexion, parametro_id, accion, version, datos):
    conexion.execute(
        "INSERT INTO parametros_signos_eventos (parametro_id, fecha, usuario, accion, version, datos_json) VALUES (?, ?, ?, ?, ?, ?)",
        (parametro_id, _ahora(), g.profesional["usuario"], accion, version, json.dumps(datos, ensure_ascii=False)))


@bp.get("/api/signos")
def listar():
    conexion = _conectar()
    try:
        historial = [dict(f) for f in conexion.execute(
            """SELECT e.fecha, e.usuario, e.accion, e.version, p.campo, p.grupo_etario
               FROM parametros_signos_eventos e LEFT JOIN parametros_signos p ON p.id = e.parametro_id
               ORDER BY e.id""")]
    finally:
        conexion.close()
    return _ok(parametros=leer_parametros(current_app.config["BASE_REGLAS"]), grupos=GRUPOS,
               grupo_base=GRUPO_BASE, campos=CAMPOS_SIGNOS, historial=historial)


@bp.post("/api/signos")
def guardar():
    p, error = validar_parametro(request.get_json(silent=True))
    if error:
        return _error(error, 422, "PARAMETRO_INVALIDO")
    ahora, usuario = _ahora(), g.profesional["usuario"]
    conexion = _conectar()
    try:
        with conexion:
            fila = conexion.execute("SELECT * FROM parametros_signos WHERE campo = ? AND grupo_etario = ?",
                                    (p["campo"], p["grupo_etario"])).fetchone()
            if fila is None:
                p["validada_en"] = ahora if p["validada_por"] else ""
                cursor = conexion.execute(
                    f"INSERT INTO parametros_signos ({', '.join(p)}, version, creada_por, creada_en, actualizada_por, actualizada_en) "
                    f"VALUES ({', '.join('?' * len(p))}, 1, ?, ?, ?, ?)", (*p.values(), usuario, ahora, usuario, ahora))
                pid, version, accion = cursor.lastrowid, 1, "CREADO"
            else:
                actual = {k: fila[k] for k in p if k != "validada_en"}
                if {k: (bool(v) if k == "obligatorio" else v) for k, v in actual.items()} == \
                   {k: (bool(v) if k == "obligatorio" else v) for k, v in p.items()}:
                    return _ok(parametro=_a_dict(fila), sin_cambios=True)
                p["validada_en"] = (fila["validada_en"] if p["validada_por"] and p["validada_por"] == fila["validada_por"]
                                    else (ahora if p["validada_por"] else ""))
                pid, version, accion = fila["id"], fila["version"] + 1, "MODIFICADO"
                sets = ", ".join(f"{k} = ?" for k in p)
                conexion.execute(f"UPDATE parametros_signos SET {sets}, version = ?, actualizada_por = ?, actualizada_en = ? WHERE id = ?",
                                 (*p.values(), version, usuario, ahora, pid))
            _evento(conexion, pid, accion, version, p)
            fila = conexion.execute("SELECT * FROM parametros_signos WHERE id = ?", (pid,)).fetchone()
    finally:
        conexion.close()
    logger.info("PARAMETRO_SIGNOS_%s | %s | %s %s v%d", accion, usuario, p["campo"], p["grupo_etario"], version)
    return _ok(parametro=_a_dict(fila))


@bp.post("/api/signos/<int:parametro_id>/eliminar")
def eliminar(parametro_id):
    conexion = _conectar()
    try:
        with conexion:
            fila = conexion.execute("SELECT * FROM parametros_signos WHERE id = ?", (parametro_id,)).fetchone()
            if fila is None:
                return _error("El parámetro no existe.", 404, "PARAMETRO_NO_ENCONTRADO")
            if fila["grupo_etario"] == GRUPO_BASE:
                return _error("Los rangos de Adulto son la base y no se pueden eliminar; se pueden modificar.",
                              409, "NO_ELIMINABLE")
            conexion.execute("DELETE FROM parametros_signos WHERE id = ?", (parametro_id,))
            _evento(conexion, None, f"ELIMINADO ({fila['campo']} · {fila['grupo_etario']})", fila["version"], dict(fila))
    finally:
        conexion.close()
    return _ok()
