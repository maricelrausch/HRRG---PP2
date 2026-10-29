"""Reglas del hospital para el motor de sugerencia (propuesta Barby 28/10 · a revisar por el grupo).

Las carga la Jefatura de Guardia (perfil "jefatura") desde reglas.html. Cada regla dice:
"si se cumplen (todas | alguna de) estas condiciones, el color no puede ser menor que X",
con una explicación que se muestra en el "Por qué" de la sugerencia.

Ciclo de vida:
    borrador  -> se crea o se edita; NO interviene en la sugerencia.
    activa    -> la usa el motor desde la próxima sugerencia (no hace falta reiniciar nada).
    inactiva  -> deja de intervenir; se conserva para la trazabilidad.
Editar una regla activa la vuelve a borrador (hay que activarla de nuevo) y sube su versión.
Solo se pueden eliminar los borradores que nunca estuvieron activos; el resto se desactiva.
Cada cambio queda en reglas_eventos (quién, cuándo, qué versión y el contenido).

Rutas:
    GET  /api/reglas/campos            catálogo de datos y operadores (para armar el formulario)
    GET  /api/reglas/activas           reglas activas + si se usan las reglas de ejemplo (motor)
    GET  /api/reglas                   todas, con su historial (jefatura y auditor)
    POST /api/reglas                   crear borrador (jefatura)
    POST /api/reglas/<id>              editar (jefatura) -> vuelve a borrador
    POST /api/reglas/<id>/activar      (jefatura)
    POST /api/reglas/<id>/desactivar   (jefatura)
    POST /api/reglas/<id>/eliminar     solo borradores nunca activados (jefatura)
    POST /api/reglas/config            {"usar_ejemplo": bool} (jefatura)
"""
import json
import sqlite3
import logging
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request, session

from src.auth import obtener_profesional
from src.admin_usuarios import estado_acceso, requiere_cambio

bp = Blueprint("reglas_hospital", __name__)
logger = logging.getLogger("hrrg.sistema")

COLORES = ("ROJO", "NARANJA", "AMARILLO", "VERDE")
COMBINACIONES = ("todas", "alguna")
MAX_CONDICIONES = 8

# Datos que puede usar una regla (mismos nombres que la pantalla de Medición).
# El DNI y el relato NO están: una regla no puede depender de datos identificatorios.
CATEGORIAS = ["Dolor torácico", "Dolor abdominal", "Disnea", "Trauma", "Fiebre",
              "Cefalea", "Síntoma neurológico", "Otro"]
CAMPOS = {
    "edad": {"etiqueta": "Edad", "tipo": "num", "unidad": "años", "min": 0, "max": 120},
    "ta_sistolica": {"etiqueta": "TA sistólica", "tipo": "num", "unidad": "mmHg", "min": 30, "max": 300},
    "ta_diastolica": {"etiqueta": "TA diastólica", "tipo": "num", "unidad": "mmHg", "min": 10, "max": 200},
    "pam": {"etiqueta": "PAM (presión arterial media)", "tipo": "num", "unidad": "mmHg", "min": 10, "max": 250},
    "frecuencia_cardiaca": {"etiqueta": "Frecuencia cardíaca", "tipo": "num", "unidad": "lpm", "min": 10, "max": 300},
    "frecuencia_respiratoria": {"etiqueta": "Frecuencia respiratoria", "tipo": "num", "unidad": "rpm", "min": 1, "max": 80},
    "saturacion_o2": {"etiqueta": "Saturación de oxígeno (SpO₂)", "tipo": "num", "unidad": "%", "min": 30, "max": 100},
    "temperatura": {"etiqueta": "Temperatura", "tipo": "num", "unidad": "°C", "min": 25, "max": 45},
    "glucemia": {"etiqueta": "Glucemia capilar", "tipo": "num", "unidad": "mg/dL", "min": 10, "max": 1000},
    "glasgow": {"etiqueta": "Escala de Glasgow", "tipo": "num", "unidad": "pts", "min": 3, "max": 15},
    "dolor_intensidad": {"etiqueta": "Intensidad del dolor", "tipo": "num", "unidad": "/10", "min": 0, "max": 10},
    "estado_conciencia": {"etiqueta": "Nivel de conciencia", "tipo": "opcion",
                          "opciones": ["Alerta", "Responde a la voz", "Responde al dolor", "No responde"]},
    "motivo_categoria": {"etiqueta": "Categoría del motivo", "tipo": "opcion", "opciones": CATEGORIAS},
    "sexo": {"etiqueta": "Sexo", "tipo": "opcion", "opciones": ["Femenino", "Masculino", "No informado"]},
    "br_sangrado": {"etiqueta": "Bandera roja: sangrado evidente", "tipo": "bool"},
    "br_convulsion": {"etiqueta": "Bandera roja: convulsión activa", "tipo": "bool"},
    "br_disnea": {"etiqueta": "Bandera roja: dificultad para respirar", "tipo": "bool"},
    "br_trauma": {"etiqueta": "Bandera roja: mecanismo de trauma", "tipo": "bool"},
    "ant_diabetes": {"etiqueta": "Antecedente: diabetes", "tipo": "bool"},
    "ant_cardio": {"etiqueta": "Antecedente: cardiovascular", "tipo": "bool"},
    "ant_resp": {"etiqueta": "Antecedente: respiratorio", "tipo": "bool"},
    "ant_anticoag": {"etiqueta": "Antecedente: anticoagulación", "tipo": "bool"},
    "ant_inmuno": {"etiqueta": "Antecedente: inmunosupresión", "tipo": "bool"},
    "ant_embarazo": {"etiqueta": "Antecedente: embarazo", "tipo": "bool"},
    "ant_medicacion": {"etiqueta": "Antecedente: medicación crítica", "tipo": "bool"},
}
OPERADORES = {
    "num": {"<": "menor que", "<=": "menor o igual que", ">": "mayor que",
            ">=": "mayor o igual que", "=": "igual a", "!=": "distinto de"},
    "opcion": {"es": "es", "no_es": "no es"},
    "bool": {"si": "está marcado (sí)", "no": "no está marcado (no)"},
}


# ------------------------------------------------
# Base de datos
# ------------------------------------------------

def _ahora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _conectar():
    conexion = sqlite3.connect(current_app.config["BASE_REGLAS"])
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar_reglas(ruta_base):
    conexion = sqlite3.connect(ruta_base)
    try:
        with conexion:
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS reglas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE,
                    nombre TEXT NOT NULL,
                    explicacion TEXT NOT NULL,
                    color TEXT NOT NULL CHECK (color IN ('ROJO','NARANJA','AMARILLO','VERDE')),
                    combinacion TEXT NOT NULL CHECK (combinacion IN ('todas','alguna')),
                    condiciones_json TEXT NOT NULL,
                    estado TEXT NOT NULL CHECK (estado IN ('borrador','activa','inactiva')),
                    version INTEGER NOT NULL CHECK (version >= 1),
                    fue_activada INTEGER NOT NULL DEFAULT 0,
                    creada_por TEXT NOT NULL,
                    creada_en TEXT NOT NULL,
                    actualizada_por TEXT NOT NULL,
                    actualizada_en TEXT NOT NULL
                )
            """)
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS reglas_eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    regla_id INTEGER,
                    fecha TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    accion TEXT NOT NULL,
                    version INTEGER,
                    datos_json TEXT NOT NULL
                )
            """)
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS reglas_config (
                    clave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL,
                    actualizado_por TEXT NOT NULL,
                    actualizado_en TEXT NOT NULL
                )
            """)
    finally:
        conexion.close()


def _usar_ejemplo(conexion):
    fila = conexion.execute("SELECT valor FROM reglas_config WHERE clave = 'usar_ejemplo'").fetchone()
    return True if fila is None else fila["valor"] == "1"


def _evento(conexion, regla_id, accion, version, datos):
    conexion.execute(
        "INSERT INTO reglas_eventos (regla_id, fecha, usuario, accion, version, datos_json) VALUES (?, ?, ?, ?, ?, ?)",
        (regla_id, _ahora(), g.profesional["usuario"], accion, version,
         json.dumps(datos, ensure_ascii=False))
    )


def _a_dict(fila, eventos=None):
    regla = {
        "id": fila["id"],
        "codigo": fila["codigo"],
        "nombre": fila["nombre"],
        "explicacion": fila["explicacion"],
        "color": fila["color"],
        "combinacion": fila["combinacion"],
        "condiciones": json.loads(fila["condiciones_json"]),
        "estado": fila["estado"],
        "version": fila["version"],
        "fue_activada": bool(fila["fue_activada"]),
        "creada_por": fila["creada_por"],
        "creada_en": fila["creada_en"],
        "actualizada_por": fila["actualizada_por"],
        "actualizada_en": fila["actualizada_en"],
    }
    if eventos is not None:
        regla["historial"] = eventos
    return regla


# ------------------------------------------------
# Validación
# ------------------------------------------------

def _numero(valor):
    if isinstance(valor, bool):
        raise ValueError
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        return float(valor.strip().replace(",", "."))
    raise ValueError


def validar_regla(datos):
    """Devuelve (regla_normalizada, None) o (None, mensaje_de_error)."""
    if not isinstance(datos, dict):
        return None, "Enviá los datos de la regla."
    permitidos = {"nombre", "explicacion", "color", "combinacion", "condiciones"}
    if set(datos) - permitidos:
        return None, "Hay campos que no corresponden a una regla."

    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not 3 <= len(nombre.strip()) <= 80:
        return None, "El nombre tiene que tener entre 3 y 80 caracteres."
    explicacion = datos.get("explicacion")
    if not isinstance(explicacion, str) or not 5 <= len(explicacion.strip()) <= 300:
        return None, "La explicación (lo que se muestra en el «Por qué») tiene que tener entre 5 y 300 caracteres."
    if datos.get("color") not in COLORES:
        return None, "Elegí el color: ROJO, NARANJA, AMARILLO o VERDE."
    if datos.get("combinacion") not in COMBINACIONES:
        return None, "Elegí si se tienen que cumplir todas las condiciones o alguna."

    condiciones = datos.get("condiciones")
    if not isinstance(condiciones, list) or not 1 <= len(condiciones) <= MAX_CONDICIONES:
        return None, f"La regla necesita entre 1 y {MAX_CONDICIONES} condiciones."

    limpias = []
    for i, cond in enumerate(condiciones, start=1):
        if not isinstance(cond, dict) or set(cond) - {"campo", "operador", "valor"}:
            return None, f"La condición {i} no es válida."
        campo = cond.get("campo")
        if campo not in CAMPOS:
            return None, f"Condición {i}: elegí un dato de la lista."
        info = CAMPOS[campo]
        operador = cond.get("operador")
        if operador not in OPERADORES[info["tipo"]]:
            return None, f"Condición {i}: el operador no corresponde a «{info['etiqueta']}»."
        if info["tipo"] == "num":
            try:
                valor = _numero(cond.get("valor"))
            except (ValueError, TypeError):
                return None, f"Condición {i}: escribí un número para «{info['etiqueta']}»."
            if not info["min"] <= valor <= info["max"]:
                return None, (f"Condición {i}: «{info['etiqueta']}» tiene que estar entre "
                              f"{info['min']:g} y {info['max']:g} {info['unidad']}.")
            valor = int(valor) if valor.is_integer() else valor
        elif info["tipo"] == "opcion":
            valor = cond.get("valor")
            if valor not in info["opciones"]:
                return None, f"Condición {i}: elegí una opción de «{info['etiqueta']}»."
        else:
            valor = None
        limpias.append({"campo": campo, "operador": operador, "valor": valor})

    return {
        "nombre": nombre.strip(),
        "explicacion": explicacion.strip(),
        "color": datos["color"],
        "combinacion": datos["combinacion"],
        "condiciones": limpias,
    }, None


# ------------------------------------------------
# Control de acceso
# ------------------------------------------------

def _error(mensaje, estado, codigo):
    respuesta = jsonify({"ok": False, "mensaje": mensaje, "codigo": codigo})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, estado


def _ok(**datos):
    respuesta = jsonify({"ok": True, **datos})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


LECTURA_MOTOR = {"enfermeria", "medico", "auditor", "jefatura"}
LECTURA_COMPLETA = {"auditor", "jefatura"}


@bp.before_request
def exigir_sesion():
    # Escrituras solo en JSON (defensa CSRF, igual que la administración de cuentas).
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

    rol = profesional["rol"]
    endpoint = request.endpoint or ""
    if endpoint in {"reglas_hospital.campos", "reglas_hospital.activas"}:
        permitido = rol in LECTURA_MOTOR
    elif request.method == "GET":
        permitido = rol in LECTURA_COMPLETA
    else:
        permitido = rol == "jefatura"
    if not permitido:
        return _error("Tu perfil no puede hacer esto. Las reglas las administra la Jefatura de Guardia.",
                      403, "PERMISO_DENEGADO")
    return None


# ------------------------------------------------
# Rutas
# ------------------------------------------------

@bp.get("/api/reglas/campos")
def campos():
    # Los operadores van como lista de pares para conservar el orden (jsonify ordena las claves).
    operadores = {tipo: [[k, t] for k, t in ops.items()] for tipo, ops in OPERADORES.items()}
    return _ok(campos=CAMPOS, operadores=operadores, colores=list(COLORES), max_condiciones=MAX_CONDICIONES)


@bp.get("/api/reglas/activas")
def activas():
    conexion = _conectar()
    try:
        filas = conexion.execute(
            "SELECT * FROM reglas WHERE estado = 'activa' ORDER BY id"
        ).fetchall()
        usar = _usar_ejemplo(conexion)
    finally:
        conexion.close()
    return _ok(reglas=[_a_dict(f) for f in filas], usar_ejemplo=usar)


@bp.get("/api/reglas")
def listar():
    conexion = _conectar()
    try:
        filas = conexion.execute("SELECT * FROM reglas ORDER BY id").fetchall()
        eventos = {}
        for ev in conexion.execute(
            "SELECT regla_id, fecha, usuario, accion, version FROM reglas_eventos ORDER BY id"
        ):
            eventos.setdefault(ev["regla_id"], []).append(
                {"fecha": ev["fecha"], "usuario": ev["usuario"], "accion": ev["accion"], "version": ev["version"]}
            )
        config = conexion.execute(
            "SELECT valor, actualizado_por, actualizado_en FROM reglas_config WHERE clave = 'usar_ejemplo'"
        ).fetchone()
    finally:
        conexion.close()
    return _ok(
        reglas=[_a_dict(f, eventos.get(f["id"], [])) for f in filas],
        usar_ejemplo=True if config is None else config["valor"] == "1",
        config_actualizada=None if config is None else {"por": config["actualizado_por"], "en": config["actualizado_en"]},
    )


@bp.post("/api/reglas")
def crear():
    regla, error = validar_regla(request.get_json(silent=True))
    if error:
        return _error(error, 422, "REGLA_INVALIDA")
    ahora, usuario = _ahora(), g.profesional["usuario"]
    conexion = _conectar()
    try:
        with conexion:
            cursor = conexion.execute(
                """INSERT INTO reglas (nombre, explicacion, color, combinacion, condiciones_json, estado,
                       version, creada_por, creada_en, actualizada_por, actualizada_en)
                   VALUES (?, ?, ?, ?, ?, 'borrador', 1, ?, ?, ?, ?)""",
                (regla["nombre"], regla["explicacion"], regla["color"], regla["combinacion"],
                 json.dumps(regla["condiciones"], ensure_ascii=False), usuario, ahora, usuario, ahora)
            )
            regla_id = cursor.lastrowid
            conexion.execute("UPDATE reglas SET codigo = ? WHERE id = ?", (f"R-{regla_id:03d}", regla_id))
            _evento(conexion, regla_id, "CREADA (borrador)", 1, regla)
            fila = conexion.execute("SELECT * FROM reglas WHERE id = ?", (regla_id,)).fetchone()
    finally:
        conexion.close()
    logger.info("REGLA_CREADA | %s | R-%03d", usuario, regla_id)
    return _ok(regla=_a_dict(fila)), 201


def _buscar(conexion, regla_id):
    return conexion.execute("SELECT * FROM reglas WHERE id = ?", (regla_id,)).fetchone()


@bp.post("/api/reglas/<int:regla_id>")
def editar(regla_id):
    regla, error = validar_regla(request.get_json(silent=True))
    if error:
        return _error(error, 422, "REGLA_INVALIDA")
    conexion = _conectar()
    try:
        with conexion:
            fila = _buscar(conexion, regla_id)
            if fila is None:
                return _error("La regla no existe.", 404, "REGLA_NO_ENCONTRADA")
            version = fila["version"] + 1
            conexion.execute(
                """UPDATE reglas SET nombre = ?, explicacion = ?, color = ?, combinacion = ?, condiciones_json = ?,
                       estado = 'borrador', version = ?, actualizada_por = ?, actualizada_en = ? WHERE id = ?""",
                (regla["nombre"], regla["explicacion"], regla["color"], regla["combinacion"],
                 json.dumps(regla["condiciones"], ensure_ascii=False), version,
                 g.profesional["usuario"], _ahora(), regla_id)
            )
            accion = "EDITADA (pasó a borrador)" if fila["estado"] == "activa" else "EDITADA"
            _evento(conexion, regla_id, accion, version, regla)
            fila = _buscar(conexion, regla_id)
    finally:
        conexion.close()
    logger.info("REGLA_EDITADA | %s | R-%03d v%d", g.profesional["usuario"], regla_id, version)
    return _ok(regla=_a_dict(fila))


def _cambiar_estado(regla_id, nuevo, accion):
    conexion = _conectar()
    try:
        with conexion:
            fila = _buscar(conexion, regla_id)
            if fila is None:
                return _error("La regla no existe.", 404, "REGLA_NO_ENCONTRADA")
            if fila["estado"] == nuevo:
                return _error("La regla ya está en ese estado.", 409, "SIN_CAMBIOS")
            conexion.execute(
                "UPDATE reglas SET estado = ?, fue_activada = MAX(fue_activada, ?), actualizada_por = ?, "
                "actualizada_en = ? WHERE id = ?",
                (nuevo, 1 if nuevo == "activa" else 0, g.profesional["usuario"], _ahora(), regla_id)
            )
            _evento(conexion, regla_id, accion, fila["version"], {"estado_anterior": fila["estado"]})
            fila = _buscar(conexion, regla_id)
    finally:
        conexion.close()
    logger.info("REGLA_%s | %s | R-%03d", nuevo.upper(), g.profesional["usuario"], regla_id)
    return _ok(regla=_a_dict(fila))


@bp.post("/api/reglas/<int:regla_id>/activar")
def activar(regla_id):
    return _cambiar_estado(regla_id, "activa", "ACTIVADA")


@bp.post("/api/reglas/<int:regla_id>/desactivar")
def desactivar(regla_id):
    return _cambiar_estado(regla_id, "inactiva", "DESACTIVADA")


@bp.post("/api/reglas/<int:regla_id>/eliminar")
def eliminar(regla_id):
    conexion = _conectar()
    try:
        with conexion:
            fila = _buscar(conexion, regla_id)
            if fila is None:
                return _error("La regla no existe.", 404, "REGLA_NO_ENCONTRADA")
            if fila["estado"] != "borrador" or fila["fue_activada"]:
                return _error("Solo se pueden eliminar borradores que nunca se activaron. "
                              "Las demás se desactivan, para que quede el registro.", 409, "NO_ELIMINABLE")
            conexion.execute("DELETE FROM reglas WHERE id = ?", (regla_id,))
            _evento(conexion, regla_id, f"ELIMINADA ({fila['codigo']}, borrador)", fila["version"],
                    {"nombre": fila["nombre"]})
    finally:
        conexion.close()
    logger.info("REGLA_ELIMINADA | %s | R-%03d", g.profesional["usuario"], regla_id)
    return _ok()


@bp.post("/api/reglas/config")
def configurar():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or set(datos) != {"usar_ejemplo"} or not isinstance(datos["usar_ejemplo"], bool):
        return _error("Enviá únicamente usar_ejemplo (true o false).", 400, "CAMPOS_INVALIDOS")
    conexion = _conectar()
    try:
        with conexion:
            conexion.execute(
                """INSERT INTO reglas_config (clave, valor, actualizado_por, actualizado_en)
                   VALUES ('usar_ejemplo', ?, ?, ?)
                   ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor,
                       actualizado_por = excluded.actualizado_por, actualizado_en = excluded.actualizado_en""",
                ("1" if datos["usar_ejemplo"] else "0", g.profesional["usuario"], _ahora())
            )
            _evento(conexion, None,
                    "REGLAS DE EJEMPLO " + ("ACTIVADAS" if datos["usar_ejemplo"] else "DESACTIVADAS"),
                    None, datos)
    finally:
        conexion.close()
    logger.info("REGLAS_EJEMPLO | %s | %s", g.profesional["usuario"], datos["usar_ejemplo"])
    return _ok(usar_ejemplo=datos["usar_ejemplo"])
