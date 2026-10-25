"""Gestión de cuentas y contraseñas (perfil admin).

Trabaja sobre la tabla `profesionales` de usuarios.db, la misma que usa /api/login.
Las contraseñas solo se guardan como hash: el administrador nunca las ve.
Para restablecer un acceso genera una clave temporal de un solo uso, que el
profesional debe cambiar al ingresar (POST /api/cuenta/password).

Rutas (ver docs/contrato_api.md, sección 13):
    GET  /api/admin/usuarios
    POST /api/admin/usuarios
    POST /api/admin/usuarios/<id>/restablecer
    POST /api/admin/usuarios/<id>/desbloquear
    POST /api/admin/usuarios/<id>/rol
    POST /api/admin/usuarios/<id>/activo
    GET  /api/admin/auditoria
    POST /api/cuenta/password
"""
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import (Blueprint, current_app, g, has_request_context, jsonify,
                   request, session)
from werkzeug.security import check_password_hash, generate_password_hash

from src.auth import obtener_profesional

bp = Blueprint("admin_usuarios", __name__)

ROLES = ("enfermeria", "medico", "auditor", "admin")
MAX_INTENTOS = 5
VENCE_DIAS = 90
HISTORIAL = 5
MIN_LARGO = 12
MAX_LARGO = 256
VIGENCIAS_HORAS = (1, 4, 24)
# Claves temporales: sin caracteres que se confunden al leerlas o dictarlas (0/O, 1/l/I).
ALFABETO_TEMPORAL = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
PATRON_USUARIO = re.compile(r"[A-Za-z0-9._-]{3,30}")


# ------------------------------------------------
# Utilidades
# ------------------------------------------------

def _ahora():
    return datetime.now().replace(microsecond=0)


def _conectar(base):
    conexion = sqlite3.connect(base)
    conexion.row_factory = sqlite3.Row
    return conexion


def _base():
    return current_app.config["BASE_USUARIOS"]


def _error(mensaje, estado, codigo):
    return jsonify({"ok": False, "mensaje": mensaje, "codigo": codigo}), estado


def _sin_cache(respuesta, estado=200):
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, estado


def auditar(base, actor, accion, cuenta=None):
    ip = request.remote_addr if has_request_context() else None
    conexion = _conectar(base)
    try:
        conexion.execute(
            "INSERT INTO auditoria_cuentas (fecha, actor, accion, cuenta, ip) VALUES (?, ?, ?, ?, ?)",
            (_ahora().isoformat(), actor, accion, cuenta, ip),
        )
        conexion.commit()
    finally:
        conexion.close()


# ------------------------------------------------
# Estructura de la base (se ejecuta al iniciar app.py)
# ------------------------------------------------

def migrar_usuarios(base):
    """Agrega a `profesionales` las columnas de seguridad y crea las tablas nuevas.
    Es idempotente: se puede ejecutar en cada arranque."""
    conexion = _conectar(base)
    try:
        columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(profesionales)")}
        nuevas = {
            "intentos_fallidos": "INTEGER NOT NULL DEFAULT 0",
            "bloqueada": "INTEGER NOT NULL DEFAULT 0",
            "debe_cambiar": "INTEGER NOT NULL DEFAULT 0",
            "password_cambiada": "TEXT",
            "temp_vence": "TEXT",
        }
        for columna, tipo in nuevas.items():
            if columna not in columnas:
                conexion.execute(f"ALTER TABLE profesionales ADD COLUMN {columna} {tipo}")

        # Las cuentas existentes empiezan a contar los 90 días desde hoy.
        conexion.execute(
            "UPDATE profesionales SET password_cambiada = ? WHERE password_cambiada IS NULL",
            (_ahora().isoformat(),),
        )
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS historial_passwords (
                profesional_id INTEGER NOT NULL,
                password_hash TEXT NOT NULL,
                creada TEXT NOT NULL
            )
        """)
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_cuentas (
                id INTEGER PRIMARY KEY,
                fecha TEXT NOT NULL,
                actor TEXT NOT NULL,
                accion TEXT NOT NULL,
                cuenta TEXT,
                ip TEXT
            )
        """)
        conexion.commit()
    finally:
        conexion.close()


# ------------------------------------------------
# Funciones que usa el login de app.py
# ------------------------------------------------

def estado_acceso(base, usuario):
    """Datos de seguridad de una cuenta activa, o None si no existe o está desactivada."""
    conexion = _conectar(base)
    try:
        fila = conexion.execute(
            """
            SELECT id, usuario, bloqueada, intentos_fallidos, debe_cambiar,
                   password_cambiada, temp_vence
            FROM profesionales
            WHERE usuario = ? AND activo = 1
            """,
            (usuario,),
        ).fetchone()
        return dict(fila) if fila else None
    finally:
        conexion.close()


def password_vencida(cuenta):
    if not cuenta or not cuenta["password_cambiada"]:
        return False
    cambiada = datetime.fromisoformat(cuenta["password_cambiada"])
    return _ahora() - cambiada > timedelta(days=VENCE_DIAS)


def requiere_cambio(cuenta):
    return bool(cuenta) and (bool(cuenta["debe_cambiar"]) or password_vencida(cuenta))


def temporal_vencida(cuenta):
    return bool(cuenta and cuenta["temp_vence"]) and datetime.fromisoformat(cuenta["temp_vence"]) < _ahora()


def registrar_fallo(base, usuario):
    """Suma un intento fallido. Devuelve True si la cuenta quedó bloqueada."""
    conexion = _conectar(base)
    try:
        conexion.execute(
            """
            UPDATE profesionales
            SET intentos_fallidos = intentos_fallidos + 1,
                bloqueada = CASE WHEN intentos_fallidos + 1 >= ? THEN 1 ELSE bloqueada END
            WHERE usuario = ? AND activo = 1
            """,
            (MAX_INTENTOS, usuario),
        )
        conexion.commit()
        fila = conexion.execute(
            "SELECT bloqueada, intentos_fallidos FROM profesionales WHERE usuario = ?",
            (usuario,),
        ).fetchone()
    finally:
        conexion.close()

    bloqueada = bool(fila and fila["bloqueada"])
    if bloqueada and fila["intentos_fallidos"] == MAX_INTENTOS:
        auditar(base, "sistema", "bloqueo automático por intentos fallidos", usuario)
    return bloqueada


def registrar_exito(base, usuario):
    conexion = _conectar(base)
    try:
        conexion.execute("UPDATE profesionales SET intentos_fallidos = 0 WHERE usuario = ?", (usuario,))
        conexion.commit()
    finally:
        conexion.close()


# ------------------------------------------------
# Política de contraseñas
# ------------------------------------------------

def validar_password(clave):
    """Devuelve el motivo del rechazo, o None si la contraseña cumple la política."""
    if not MIN_LARGO <= len(clave) <= MAX_LARGO:
        return f"La contraseña debe tener entre {MIN_LARGO} y {MAX_LARGO} caracteres."
    if not re.search(r"[A-ZÁÉÍÓÚÑ]", clave):
        return "La contraseña debe tener al menos una mayúscula."
    if not re.search(r"[a-záéíóúñ]", clave):
        return "La contraseña debe tener al menos una minúscula."
    if not re.search(r"\d", clave):
        return "La contraseña debe tener al menos un número."
    if not re.search(r"[^A-Za-z0-9ÁÉÍÓÚÑáéíóúñ\s]", clave):
        return "La contraseña debe tener al menos un símbolo."
    return None


def generar_temporal():
    """Clave de 3 bloques de 4 separados por guion, p. ej. K7qm-R2vx-9wLp (14 caracteres)."""
    while True:
        bloques = ["".join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(4)) for _ in range(3)]
        clave = "-".join(bloques)
        if validar_password(clave) is None:
            return clave


def _estado(fila):
    if not fila["activo"]:
        return "Desactivada"
    if fila["bloqueada"]:
        return "Bloqueada"
    if fila["debe_cambiar"]:
        return "Cambio pendiente"
    if password_vencida(fila):
        return "Vencida"
    return "Activa"


def _poner_temporal(conexion, profesional_id, horas):
    temporal = generar_temporal()
    vence = (_ahora() + timedelta(hours=horas)).isoformat()
    conexion.execute(
        """
        UPDATE profesionales
        SET password_hash = ?, debe_cambiar = 1, temp_vence = ?,
            bloqueada = 0, intentos_fallidos = 0
        WHERE id = ?
        """,
        (generate_password_hash(temporal), vence, profesional_id),
    )
    return temporal


# ------------------------------------------------
# Control de acceso de estas rutas
# ------------------------------------------------

@bp.before_request
def exigir_sesion():
    # Escrituras solo en JSON: un formulario de otro sitio no puede enviarlo (defensa CSRF).
    if request.method == "POST" and not request.is_json:
        return _error("La solicitud debe estar en formato JSON.", 415, "FORMATO_NO_SOPORTADO")

    usuario = session.get("usuario")
    profesional = obtener_profesional(_base(), usuario) if usuario else None
    cuenta = estado_acceso(_base(), usuario) if usuario else None

    if profesional is None or cuenta is None or cuenta["bloqueada"]:
        session.clear()
        return _error("Debés iniciar sesión para continuar.", 401, "SESION_REQUERIDA")

    g.profesional = profesional
    g.cuenta = cuenta

    # Cambiar la propia contraseña solo requiere sesión.
    if request.endpoint == "admin_usuarios.cambiar_propia":
        return None

    if requiere_cambio(cuenta):
        return _error("Tenés que cambiar tu contraseña antes de continuar.", 403, "CAMBIO_PASSWORD_REQUERIDO")

    if profesional["rol"] != "admin":
        return _error("Solo el perfil administrador puede gestionar cuentas.", 403, "PERMISO_DENEGADO")

    return None


def _datos_json():
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else {}


def _buscar(conexion, profesional_id):
    return conexion.execute("SELECT * FROM profesionales WHERE id = ?", (profesional_id,)).fetchone()


# ------------------------------------------------
# Rutas del administrador
# ------------------------------------------------

@bp.get("/api/admin/usuarios")
def listar():
    conexion = _conectar(_base())
    try:
        filas = conexion.execute("SELECT * FROM profesionales ORDER BY nombre").fetchall()
    finally:
        conexion.close()

    usuarios = []
    for fila in filas:
        cambiada = fila["password_cambiada"]
        usuarios.append({
            "id": fila["id"],
            "usuario": fila["usuario"],
            "nombre": fila["nombre"],
            "rol": fila["rol"],
            "estado": _estado(fila),
            "dias_desde_cambio": (_ahora() - datetime.fromisoformat(cambiada)).days if cambiada else None,
            "propia": fila["usuario"] == g.profesional["usuario"],
        })
    return _sin_cache(jsonify({"ok": True, "usuarios": usuarios, "roles": list(ROLES)}))


@bp.post("/api/admin/usuarios")
def crear():
    datos = _datos_json()
    usuario = str(datos.get("usuario", "")).strip()
    nombre = str(datos.get("nombre", "")).strip()
    rol = datos.get("rol")

    if not PATRON_USUARIO.fullmatch(usuario):
        return _error("Usuario: de 3 a 30 caracteres, sin espacios (letras, números, punto o guion).", 400, "DATOS_INVALIDOS")
    if not 2 <= len(nombre) <= 80:
        return _error("Escribí el nombre del profesional.", 400, "DATOS_INVALIDOS")
    if rol not in ROLES:
        return _error("Elegí un rol válido.", 400, "DATOS_INVALIDOS")

    temporal = generar_temporal()
    vence = (_ahora() + timedelta(hours=24)).isoformat()
    conexion = _conectar(_base())
    try:
        conexion.execute(
            """
            INSERT INTO profesionales
                (usuario, nombre, password_hash, rol, debe_cambiar, temp_vence, password_cambiada)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (usuario, nombre, generate_password_hash(temporal), rol, vence, _ahora().isoformat()),
        )
        conexion.commit()
    except sqlite3.IntegrityError:
        return _error("Ese usuario ya existe.", 409, "USUARIO_EXISTENTE")
    finally:
        conexion.close()

    auditar(_base(), g.profesional["usuario"], f"alta de cuenta (perfil {rol})", usuario)
    return _sin_cache(jsonify({"ok": True, "temporal": temporal, "vence_horas": 24}), 201)


@bp.post("/api/admin/usuarios/<int:profesional_id>/restablecer")
def restablecer(profesional_id):
    horas = _datos_json().get("horas", 24)
    if horas not in VIGENCIAS_HORAS:
        return _error("Vigencia inválida.", 400, "DATOS_INVALIDOS")

    conexion = _conectar(_base())
    try:
        fila = _buscar(conexion, profesional_id)
        if fila is None or not fila["activo"]:
            return _error("La cuenta no existe o está desactivada.", 404, "CUENTA_NO_ENCONTRADA")
        temporal = _poner_temporal(conexion, profesional_id, horas)
        conexion.commit()
    finally:
        conexion.close()

    auditar(_base(), g.profesional["usuario"], f"restablecer contraseña (clave temporal {horas} h)", fila["usuario"])
    return _sin_cache(jsonify({"ok": True, "temporal": temporal, "vence_horas": horas}))


@bp.post("/api/admin/usuarios/<int:profesional_id>/desbloquear")
def desbloquear(profesional_id):
    conexion = _conectar(_base())
    try:
        fila = _buscar(conexion, profesional_id)
        if fila is None:
            return _error("La cuenta no existe.", 404, "CUENTA_NO_ENCONTRADA")
        conexion.execute(
            "UPDATE profesionales SET bloqueada = 0, intentos_fallidos = 0 WHERE id = ?",
            (profesional_id,),
        )
        conexion.commit()
    finally:
        conexion.close()

    auditar(_base(), g.profesional["usuario"], "desbloquear cuenta", fila["usuario"])
    return _sin_cache(jsonify({"ok": True}))


@bp.post("/api/admin/usuarios/<int:profesional_id>/rol")
def cambiar_rol(profesional_id):
    rol = _datos_json().get("rol")
    if rol not in ROLES:
        return _error("Elegí un rol válido.", 400, "DATOS_INVALIDOS")

    conexion = _conectar(_base())
    try:
        fila = _buscar(conexion, profesional_id)
        if fila is None:
            return _error("La cuenta no existe.", 404, "CUENTA_NO_ENCONTRADA")
        if fila["usuario"] == g.profesional["usuario"]:
            return _error("No podés cambiar tu propio perfil.", 409, "OPERACION_SOBRE_SI_MISMO")
        conexion.execute("UPDATE profesionales SET rol = ? WHERE id = ?", (rol, profesional_id))
        conexion.commit()
    finally:
        conexion.close()

    auditar(_base(), g.profesional["usuario"], f"cambio de perfil: {fila['rol']} → {rol}", fila["usuario"])
    return _sin_cache(jsonify({"ok": True}))


@bp.post("/api/admin/usuarios/<int:profesional_id>/activo")
def cambiar_activo(profesional_id):
    activo = _datos_json().get("activo")
    if not isinstance(activo, bool):
        return _error("Indicá si la cuenta queda activa (true/false).", 400, "DATOS_INVALIDOS")

    conexion = _conectar(_base())
    try:
        fila = _buscar(conexion, profesional_id)
        if fila is None:
            return _error("La cuenta no existe.", 404, "CUENTA_NO_ENCONTRADA")
        if fila["usuario"] == g.profesional["usuario"]:
            return _error("No podés desactivar tu propia cuenta.", 409, "OPERACION_SOBRE_SI_MISMO")
        conexion.execute("UPDATE profesionales SET activo = ? WHERE id = ?", (int(activo), profesional_id))
        conexion.commit()
    finally:
        conexion.close()

    auditar(_base(), g.profesional["usuario"], "reactivar cuenta" if activo else "desactivar cuenta", fila["usuario"])
    return _sin_cache(jsonify({"ok": True}))


@bp.get("/api/admin/auditoria")
def ver_auditoria():
    conexion = _conectar(_base())
    try:
        filas = conexion.execute(
            "SELECT fecha, actor, accion, cuenta FROM auditoria_cuentas ORDER BY id DESC LIMIT 100"
        ).fetchall()
    finally:
        conexion.close()
    return _sin_cache(jsonify({"ok": True, "eventos": [dict(f) for f in filas]}))


# ------------------------------------------------
# Cambio de la propia contraseña (cualquier perfil)
# ------------------------------------------------

@bp.post("/api/cuenta/password")
def cambiar_propia():
    datos = _datos_json()
    actual = datos.get("actual")
    nueva = datos.get("nueva")
    if not isinstance(actual, str) or not isinstance(nueva, str):
        return _error("Completá la contraseña actual y la nueva.", 400, "TIPOS_INVALIDOS")

    conexion = _conectar(_base())
    try:
        fila = _buscar(conexion, g.cuenta["id"])
        if not check_password_hash(fila["password_hash"], actual):
            return _error("La contraseña actual no es correcta.", 400, "PASSWORD_ACTUAL_INCORRECTA")

        motivo = validar_password(nueva)
        if motivo:
            return _error(motivo, 400, "PASSWORD_DEBIL")

        anteriores = [fila["password_hash"]] + [
            r["password_hash"] for r in conexion.execute(
                "SELECT password_hash FROM historial_passwords WHERE profesional_id = ?", (fila["id"],)
            )
        ]
        if any(check_password_hash(h, nueva) for h in anteriores):
            return _error(f"No podés repetir ninguna de tus últimas {HISTORIAL} contraseñas.", 400, "PASSWORD_REPETIDA")

        nuevo_hash = generate_password_hash(nueva)
        conexion.execute(
            """
            UPDATE profesionales
            SET password_hash = ?, debe_cambiar = 0, temp_vence = NULL, password_cambiada = ?
            WHERE id = ?
            """,
            (nuevo_hash, _ahora().isoformat(), fila["id"]),
        )
        conexion.execute(
            "INSERT INTO historial_passwords (profesional_id, password_hash, creada) VALUES (?, ?, ?)",
            (fila["id"], nuevo_hash, _ahora().isoformat()),
        )
        conexion.execute(
            """
            DELETE FROM historial_passwords
            WHERE profesional_id = ? AND rowid NOT IN (
                SELECT rowid FROM historial_passwords
                WHERE profesional_id = ? ORDER BY creada DESC, rowid DESC LIMIT ?
            )
            """,
            (fila["id"], fila["id"], HISTORIAL),
        )
        conexion.commit()
    finally:
        conexion.close()

    auditar(_base(), fila["usuario"], "cambio de contraseña propia", fila["usuario"])
    return _sin_cache(jsonify({"ok": True, "mensaje": "Contraseña actualizada."}))
