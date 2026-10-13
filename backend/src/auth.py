import sqlite3

from werkzeug.security import check_password_hash


def iniciar_sesion(base_usuarios, username, password):
    conexion = sqlite3.connect(base_usuarios)

    try:
        profesional = conexion.execute(
            """
            SELECT password_hash
            FROM profesionales
            WHERE usuario = ? AND activo = 1
            """,
            (username,)
        ).fetchone()
    finally:
        conexion.close()

    if profesional is None:
        return False

    return check_password_hash(profesional[0], password)

def profesional_activo(base_usuarios, usuario):
    conexion = sqlite3.connect(base_usuarios)

    try:
        profesional = conexion.execute(
            """
            SELECT id
            FROM profesionales
            WHERE usuario = ? AND activo = 1
            """,
            (usuario,)
        ).fetchone()
    finally:
        conexion.close()

    return profesional is not None
