import re
import secrets
import sqlite3
from datetime import datetime, timezone


# Crea la tabla de identificación sin modificar los episodios existentes.
# Esta tabla no contiene relatos, mediciones ni decisiones.
def inicializar_identificacion(ruta_base):
    conexion = sqlite3.connect(ruta_base)

    try:
        with conexion:
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS identificacion_pacientes (
                    codigo_paciente TEXT PRIMARY KEY,
                    dni TEXT NOT NULL UNIQUE,
                    creado_en TEXT NOT NULL,
                    profesional_usuario TEXT NOT NULL
                )
            """)
    finally:
        conexion.close()


# Normaliza el DNI como texto para conservar posibles ceros iniciales.
# La validación de 7 u 8 dígitos es una convención del prototipo;
# no comprueba la identidad de la persona.
def normalizar_dni(dni):
    if not isinstance(dni, str):
        raise ValueError("El DNI debe enviarse como texto.")

    dni = dni.strip().replace(".", "").replace(" ", "")

    if not re.fullmatch(r"[0-9]{7,8}", dni):
        raise ValueError("El DNI debe contener 7 u 8 dígitos.")

    return dni


# Recupera el código asociado al DNI o crea uno si es la primera visita.
# El profesional debe provenir de la sesión autenticada del servidor.
def identificar_paciente_demo(ruta_base, dni, profesional_usuario):
    dni = normalizar_dni(dni)

    if (
        not isinstance(profesional_usuario, str)
        or not profesional_usuario.strip()
    ):
        raise ValueError("El profesional es obligatorio.")

    conexion = sqlite3.connect(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        with conexion:
            # Evita crear dos pacientes si llegan solicitudes simultáneas.
            conexion.execute("BEGIN IMMEDIATE")

            existente = conexion.execute(
                """
                SELECT codigo_paciente
                FROM identificacion_pacientes
                WHERE dni = ?
                """,
                (dni,)
            ).fetchone()

            if existente is not None:
                resultado = {
                    "codigo_paciente": existente["codigo_paciente"],
                    "creado": False
                }
            else:
                # Genera un código independiente del DNI.
                # No cambia el autor de identificaciones ya existentes.
                codigo = "PAC-" + secrets.token_hex(10).upper()
                fecha = datetime.now(timezone.utc).isoformat()

                conexion.execute(
                    """
                    INSERT INTO identificacion_pacientes (
                        codigo_paciente, dni, creado_en,
                        profesional_usuario
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        codigo,
                        dni,
                        fecha,
                        profesional_usuario.strip()
                    )
                )

                resultado = {
                    "codigo_paciente": codigo,
                    "creado": True
                }

        # Devuelve el código interno sin repetir el DNI en la respuesta.
        return resultado
    finally:
        conexion.close()