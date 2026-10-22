import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.cifrado_identificacion import (
    CifradoIdentificacion,
    ErrorCifradoIdentificacion,
)


# Define la estructura esperada después de la migración.
COLUMNAS_IDENTIFICACION = {
    "codigo_paciente",
    "dni_cifrado",
    "dni_indice",
    "creado_en",
    "profesional_usuario",
}

PRUEBA_CLAVES = "HRRG:identificacion:v1"


# Normaliza el DNI como texto y conserva los ceros iniciales.
# Esta validación no comprueba la identidad de la persona.
def normalizar_dni(dni):
    if not isinstance(dni, str):
        raise ValueError("El DNI debe enviarse como texto.")

    dni = dni.strip().replace(".", "").replace(" ", "")

    if not re.fullmatch(r"[0-9]{7,8}", dni):
        raise ValueError("El DNI debe contener 7 u 8 dígitos.")

    return dni


# Abre una base existente sin crear otra por un error en la ruta.
# Las consultas pueden solicitar una conexión de solo lectura.
def _conectar(ruta_base, solo_lectura=False):
    ruta = Path(ruta_base).resolve()
    modo = "ro" if solo_lectura else "rw"

    conexion = sqlite3.connect(
        ruta.as_uri() + f"?mode={modo}",
        uri=True,
    )
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


# Comprueba el esquema y verifica que ambas claves correspondan
# a esta base antes de permitir búsquedas o nuevas identificaciones.
def _verificar_base(conexion, cifrado):
    columnas = {
        fila["name"]
        for fila in conexion.execute(
            "PRAGMA table_info(identificacion_pacientes)"
        )
    }

    if columnas != COLUMNAS_IDENTIFICACION:
        raise ErrorCifradoIdentificacion(
            "La identificación requiere la migración al formato cifrado."
        )

    existe_control = conexion.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'identificacion_control'
        """
    ).fetchone()

    if existe_control is None:
        raise ErrorCifradoIdentificacion(
            "Falta el control de claves de la base."
        )

    controles = conexion.execute(
        """
        SELECT id, version, prueba_cifrada, prueba_indice
        FROM identificacion_control
        """
    ).fetchall()

    if (
        len(controles) != 1
        or controles[0]["id"] != 1
        or controles[0]["version"] != 1
    ):
        raise ErrorCifradoIdentificacion(
            "El control de identificación no es válido."
        )

    control = controles[0]
    prueba = cifrado.descifrar(control["prueba_cifrada"])
    indice = control["prueba_indice"]

    if (
        prueba != PRUEBA_CLAVES
        or not isinstance(indice, str)
        or not hmac.compare_digest(
            indice,
            cifrado.indice(PRUEBA_CLAVES),
        )
    ):
        raise ErrorCifradoIdentificacion(
            "Las claves no corresponden a esta base. "
            "No reemplaces el archivo de claves."
        )


# Prepara la identificación en una instalación nueva.
# Si hay una tabla anterior, exige la migración explícita.
# Nunca genera claves ni transforma automáticamente los DNI existentes.
def inicializar_identificacion(ruta_base):
    cifrado = CifradoIdentificacion()
    conexion = sqlite3.connect(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        with conexion:
            conexion.execute("BEGIN IMMEDIATE")

            tablas = {
                fila["name"]
                for fila in conexion.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }

            if "identificacion_pacientes" not in tablas:
                if "identificacion_control" in tablas:
                    raise ErrorCifradoIdentificacion(
                        "La estructura de identificación está incompleta."
                    )

                # Crea únicamente las tablas de identificación.
                # Los episodios y sus eventos permanecen separados.
                conexion.execute(
                    """
                    CREATE TABLE identificacion_pacientes (
                        codigo_paciente TEXT PRIMARY KEY,
                        dni_cifrado TEXT NOT NULL,
                        dni_indice TEXT NOT NULL UNIQUE,
                        creado_en TEXT NOT NULL,
                        profesional_usuario TEXT NOT NULL
                    )
                    """
                )

                conexion.execute(
                    """
                    CREATE TABLE identificacion_control (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        version INTEGER NOT NULL,
                        prueba_cifrada TEXT NOT NULL,
                        prueba_indice TEXT NOT NULL
                    )
                    """
                )

                # Vincula la base con las dos claves configuradas.
                conexion.execute(
                    """
                    INSERT INTO identificacion_control (
                        id, version, prueba_cifrada, prueba_indice
                    )
                    VALUES (1, 1, ?, ?)
                    """,
                    (
                        cifrado.cifrar(PRUEBA_CLAVES),
                        cifrado.indice(PRUEBA_CLAVES),
                    ),
                )

            _verificar_base(conexion, cifrado)

    finally:
        conexion.close()


# Busca por el índice HMAC y comprueba el DNI cifrado encontrado.
# Devuelve únicamente el código interno, sin exponer el documento.
def _buscar_codigo(conexion, cifrado, dni):
    paciente = conexion.execute(
        """
        SELECT codigo_paciente, dni_cifrado
        FROM identificacion_pacientes
        WHERE dni_indice = ?
        """,
        (cifrado.indice(dni),),
    ).fetchone()

    if paciente is None:
        return None

    if cifrado.descifrar(paciente["dni_cifrado"]) != dni:
        raise ErrorCifradoIdentificacion(
            "La identificación almacenada no coincide con su índice."
        )

    return paciente["codigo_paciente"]


# Consulta un DNI existente sin crear pacientes ni episodios.
# Devuelve None cuando no encuentra una identificación.
# La ruta Flask que la utilice deberá comprobar la sesión y los permisos.
def buscar_paciente_por_dni(ruta_base, dni):
    dni = normalizar_dni(dni)
    cifrado = CifradoIdentificacion()
    conexion = _conectar(ruta_base, solo_lectura=True)

    try:
        # Mantiene una misma vista de la base durante la consulta.
        conexion.execute("BEGIN")
        _verificar_base(conexion, cifrado)
        codigo = _buscar_codigo(conexion, cifrado, dni)

        if codigo is None:
            return None

        return {"codigo_paciente": codigo}

    finally:
        conexion.close()


# Recupera el paciente existente o registra una nueva identificación.
# Mantiene la respuesta que ya consume el frontend.
# El profesional debe provenir de la sesión del servidor.
def identificar_paciente_demo(ruta_base, dni, profesional_usuario):
    dni = normalizar_dni(dni)

    if (
        not isinstance(profesional_usuario, str)
        or not profesional_usuario.strip()
    ):
        raise ValueError("El profesional es obligatorio.")

    cifrado = CifradoIdentificacion()
    conexion = _conectar(ruta_base)

    try:
        with conexion:
            # Evita que dos solicitudes creen el mismo DNI simultáneamente.
            conexion.execute("BEGIN IMMEDIATE")
            _verificar_base(conexion, cifrado)

            codigo = _buscar_codigo(conexion, cifrado, dni)

            if codigo is not None:
                return {
                    "codigo_paciente": codigo,
                    "creado": False,
                }

            # El código interno sigue siendo independiente del DNI.
            codigo = "PAC-" + secrets.token_hex(10).upper()
            fecha = datetime.now(timezone.utc).isoformat()

            conexion.execute(
                """
                INSERT INTO identificacion_pacientes (
                    codigo_paciente,
                    dni_cifrado,
                    dni_indice,
                    creado_en,
                    profesional_usuario
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    codigo,
                    cifrado.cifrar(dni),
                    cifrado.indice(dni),
                    fecha,
                    profesional_usuario.strip(),
                ),
            )

            return {
                "codigo_paciente": codigo,
                "creado": True,
            }

    finally:
        conexion.close()