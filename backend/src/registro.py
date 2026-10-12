import sqlite3
import json
from datetime import datetime, timezone

def conectar_registro(ruta_base):
    conexion = sqlite3.connect(ruta_base)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def inicializar_registro(ruta_base):
    conexion = conectar_registro(ruta_base)

    try:
        with conexion:
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS episodios (
                    codigo_episodio TEXT PRIMARY KEY,
                    codigo_paciente TEXT NOT NULL,
                    creado_en TEXT NOT NULL,
                    profesional_usuario TEXT NOT NULL
                )
            """)

            conexion.execute("""
                CREATE TABLE IF NOT EXISTS eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo_episodio TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    ocurrido_en TEXT NOT NULL,
                    profesional_usuario TEXT NOT NULL,
                    datos_json TEXT NOT NULL,
                    FOREIGN KEY (codigo_episodio)
                        REFERENCES episodios (codigo_episodio)
                )
            """)

            conexion.execute("""
                CREATE INDEX IF NOT EXISTS idx_eventos_episodio
                ON eventos (codigo_episodio, id)
            """)
    finally:
        conexion.close()

def crear_episodio(
    ruta_base,
    codigo_episodio,
    codigo_paciente,
    profesional_usuario
):
    valores = (codigo_episodio, codigo_paciente, profesional_usuario)

    if any(not isinstance(valor, str) or not valor.strip()
           for valor in valores):
        raise ValueError(
            "El episodio, el paciente y el profesional son obligatorios."
        )

    codigo_episodio = codigo_episodio.strip()
    codigo_paciente = codigo_paciente.strip()
    profesional_usuario = profesional_usuario.strip()

    fecha = datetime.now(timezone.utc).isoformat()
    conexion = conectar_registro(ruta_base)

    try:
        with conexion:
            conexion.execute(
                """
                INSERT INTO episodios (
                    codigo_episodio,
                    codigo_paciente,
                    creado_en,
                    profesional_usuario
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    codigo_episodio,
                    codigo_paciente,
                    fecha,
                    profesional_usuario
                )
            )

            conexion.execute(
                """
                INSERT INTO eventos (
                    codigo_episodio,
                    tipo,
                    ocurrido_en,
                    profesional_usuario,
                    datos_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    codigo_episodio,
                    "EPISODIO_CREADO",
                    fecha,
                    profesional_usuario,
                    "{}"
                )
            )
    finally:
        conexion.close()

    return {
        "codigo_episodio": codigo_episodio,
        "codigo_paciente": codigo_paciente,
        "creado_en": fecha
    }

def obtener_episodio(ruta_base, codigo_episodio, profesional_usuario):
    conexion = conectar_registro(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        episodio = conexion.execute(
            """
            SELECT codigo_episodio, codigo_paciente,
                   creado_en, profesional_usuario
            FROM episodios
            WHERE codigo_episodio = ?
              AND profesional_usuario = ?
            """,
            (codigo_episodio, profesional_usuario)
        ).fetchone()

        if episodio is None:
            return None

        eventos = conexion.execute(
            """
            SELECT id, tipo, ocurrido_en,
                   profesional_usuario, datos_json
            FROM eventos
            WHERE codigo_episodio = ?
            ORDER BY id
            """,
            (codigo_episodio,)
        ).fetchall()

        resultado = dict(episodio)
        resultado["eventos"] = []

        for fila in eventos:
            evento = dict(fila)
            evento["datos"] = json.loads(evento.pop("datos_json"))
            resultado["eventos"].append(evento)

        return resultado
    finally:
        conexion.close()
        