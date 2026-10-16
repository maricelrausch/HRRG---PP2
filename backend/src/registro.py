import sqlite3
import json
from datetime import datetime, timezone
from src.esquemas import Mediciones

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

# Consulta un episodio y su historial completo.
# Flask autoriza la lectura compartida según el rol de la sesión.
def obtener_episodio(
    ruta_base,
    codigo_episodio,
    profesional_usuario,
    permitir_lectura_compartida=False
):
    # Permite acceder a las columnas por su nombre.
    conexion = conectar_registro(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        # Busca el episodio solicitado.
        consulta = """
            SELECT codigo_episodio, codigo_paciente,
                   creado_en, profesional_usuario
            FROM episodios
            WHERE codigo_episodio = ?
        """
        parametros = [codigo_episodio]

        # Si no hay autorización compartida, limita la lectura al creador.
        if not permitir_lectura_compartida:
            consulta += " AND profesional_usuario = ?"
            parametros.append(profesional_usuario)

        episodio = conexion.execute(
            consulta,
            parametros
        ).fetchone()

        if episodio is None:
            return None

        # Recupera todos los eventos, conservando sus respectivos autores.
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

        # Convierte los eventos almacenados en una respuesta estructurada.
        resultado = dict(episodio)
        resultado["eventos"] = []

        for fila in eventos:
            evento = dict(fila)
            evento["datos"] = json.loads(evento.pop("datos_json"))
            resultado["eventos"].append(evento)

        return resultado

    finally:
        # Cierra la conexión incluso si ocurre un error.
        conexion.close()

def registrar_extraccion_demo(
    ruta_base,
    codigo_episodio,
    codigo_paciente,
    profesional_usuario,
    caso_simulado_id,
    version_esquema,
    latencia_ms
):
    """Registra metadatos de una extracción simulada exitosa.

    No guarda el relato, credenciales ni datos clínicos.
    El profesional debe provenir de la sesión del servidor.
    """
    textos = (
        codigo_episodio,
        codigo_paciente,
        profesional_usuario,
        caso_simulado_id,
        version_esquema
    )

    if any(
        not isinstance(valor, str) or not valor.strip()
        for valor in textos
    ):
        raise ValueError("Los identificadores son obligatorios.")

    if type(latencia_ms) is not int or latencia_ms < 0:
        raise ValueError("La latencia debe ser un entero no negativo.")

    codigo_episodio = codigo_episodio.strip()
    codigo_paciente = codigo_paciente.strip()
    profesional_usuario = profesional_usuario.strip()

    metadatos = {
        "version_evento": 1,
        "modo": "simulado",
        "origen": "caso_predefinido",
        "caso_simulado_id": caso_simulado_id.strip(),
        "version_esquema": version_esquema.strip(),
        "modelo": None,
        "latencia_ms": latencia_ms,
        "resultado": "correcto"
    }

    conexion = conectar_registro(ruta_base)

    try:
        with conexion:
            # Verificar y registrar en una misma transacción.
            conexion.execute("BEGIN IMMEDIATE")

            episodio = conexion.execute(
                """
                SELECT codigo_episodio
                FROM episodios
                WHERE codigo_episodio = ?
                  AND codigo_paciente = ?
                  AND profesional_usuario = ?
                """,
                (
                    codigo_episodio,
                    codigo_paciente,
                    profesional_usuario
                )
            ).fetchone()

            if episodio is None:
                raise ValueError(
                    "El episodio no existe o no corresponde "
                    "al paciente y profesional indicados."
                )

            fecha = datetime.now(timezone.utc).isoformat()

            cursor = conexion.execute(
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
                    "EXTRACCION_SIMULADA",
                    fecha,
                    profesional_usuario,
                    json.dumps(
                        metadatos,
                        ensure_ascii=False,
                        allow_nan=False
                    )
                )
            )

            evento_id = cursor.lastrowid
    finally:
        conexion.close()

    return {
        "id": evento_id,
        "codigo_episodio": codigo_episodio,
        "tipo": "EXTRACCION_SIMULADA",
        "ocurrido_en": fecha,
        "profesional_usuario": profesional_usuario,
        "datos": metadatos
    }


def registrar_medicion_demo(
    ruta_base,
    codigo_episodio,
    profesional_usuario,
    medido_en,
    valores
):
    """Agrega una medición ficticia sin sobrescribir el historial."""

    for valor in (codigo_episodio, profesional_usuario):
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError("El episodio y el profesional son obligatorios.")

    codigo_episodio = codigo_episodio.strip()
    profesional_usuario = profesional_usuario.strip()

    if not isinstance(medido_en, str):
        raise ValueError("La fecha de medición debe ser texto ISO 8601.")

    fecha_medicion = datetime.fromisoformat(medido_en)

    if fecha_medicion.utcoffset() is None:
        raise ValueError("La fecha debe incluir la zona horaria.")

    fecha_registro = datetime.now(timezone.utc)
    fecha_medicion = fecha_medicion.astimezone(timezone.utc)

    if fecha_medicion > fecha_registro:
        raise ValueError("La medición no puede tener una fecha futura.")

    if not isinstance(valores, dict):
        raise ValueError("Las mediciones deben enviarse como un objeto.")

    # Reutiliza nombres, rangos y coherencia del esquema de Darío.
    medicion = Mediciones.model_validate(valores)
    datos = medicion.model_dump(mode="json", exclude_none=True)

    if not any(
        getattr(medicion, campo) is not None
        for campo in Mediciones.model_fields
    ):
        raise ValueError("Debe existir al menos una medición.")

    contenido = {
        "version_evento": 1,
        "modo": "demo",
        "origen": "medicion_profesional",
        "medido_en": fecha_medicion.isoformat(),
        "valores": datos
    }

    conexion = conectar_registro(ruta_base)

    try:
        with conexion:
            conexion.execute("BEGIN IMMEDIATE")

            episodio = conexion.execute(
                """
                SELECT codigo_episodio
                FROM episodios
                WHERE codigo_episodio = ?
                """,
                (codigo_episodio,)
            ).fetchone()

            if episodio is None:
                raise ValueError(
                    "El episodio no existe."
                )

            cursor = conexion.execute(
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
                    "MEDICION_REGISTRADA",
                    fecha_registro.isoformat(),
                    profesional_usuario,
                    json.dumps(
                        contenido,
                        ensure_ascii=False,
                        allow_nan=False
                    )
                )
            )

            evento_id = cursor.lastrowid
    finally:
        conexion.close()

    return {
        "id": evento_id,
        "codigo_episodio": codigo_episodio,
        "tipo": "MEDICION_REGISTRADA",
        "ocurrido_en": fecha_registro.isoformat(),
        "profesional_usuario": profesional_usuario,
        "datos": contenido
    }


def corregir_medicion_demo(
    ruta_base,
    codigo_episodio,
    evento_id,
    profesional_usuario,
    cambios,
    motivo
):
    """Agrega una corrección sin modificar el evento anterior.

    Para corregir nuevamente, se debe indicar el ID de la
    última corrección, formando una cadena de versiones.
    """
    for valor in (codigo_episodio, profesional_usuario):
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError("El episodio y el profesional son obligatorios.")

    codigo_episodio = codigo_episodio.strip()
    profesional_usuario = profesional_usuario.strip()

    if type(evento_id) is not int or evento_id <= 0:
        raise ValueError("El identificador del evento no es válido.")

    if not isinstance(motivo, str) or not 1 <= len(motivo.strip()) <= 200:
        raise ValueError("El motivo debe tener entre 1 y 200 caracteres.")

    motivo = motivo.strip()

    if not isinstance(cambios, dict) or not cambios:
        raise ValueError("Indicá al menos un campo para corregir.")

    if set(cambios) - set(Mediciones.model_fields):
        raise ValueError("Hay campos de medición no permitidos.")

    conexion = conectar_registro(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        with conexion:
            conexion.execute("BEGIN IMMEDIATE")

            anterior = conexion.execute(
                """
                SELECT id, tipo, datos_json
                FROM eventos
                WHERE id = ? AND codigo_episodio = ?
                """,
                (evento_id, codigo_episodio)
            ).fetchone()

            if anterior is None or anterior["tipo"] not in {
                "MEDICION_REGISTRADA",
                "MEDICION_CORREGIDA"
            }:
                raise ValueError("La medición no existe en ese episodio.")

            correcciones = conexion.execute(
                """
                SELECT datos_json
                FROM eventos
                WHERE codigo_episodio = ?
                  AND tipo = 'MEDICION_CORREGIDA'
                """,
                (codigo_episodio,)
            ).fetchall()

            if any(
                json.loads(fila["datos_json"]).get("evento_corregido_id")
                == evento_id
                for fila in correcciones
            ):
                raise ValueError(
                    "Ese registro ya fue corregido. "
                    "Usá el ID de su última corrección."
                )

            contenido_anterior = json.loads(anterior["datos_json"])
            valores_anteriores = contenido_anterior["valores"]

            # La PAM se recalcula; no se utiliza como dato de entrada.
            propuesta = {
                campo: valor
                for campo, valor in valores_anteriores.items()
                if campo in Mediciones.model_fields
            }
            propuesta.update(cambios)

            medicion = Mediciones.model_validate(propuesta)
            valores_nuevos = medicion.model_dump(
                mode="json",
                exclude_none=True
            )

            if not any(
                getattr(medicion, campo) is not None
                for campo in Mediciones.model_fields
            ):
                raise ValueError("La corrección no puede vaciar la medición.")

            if valores_nuevos == valores_anteriores:
                raise ValueError("La corrección no cambia ningún valor.")

            fecha = datetime.now(timezone.utc).isoformat()

            contenido = {
                "version_evento": 1,
                "modo": "demo",
                "origen": "correccion_profesional",
                "evento_corregido_id": evento_id,
                "medido_en": contenido_anterior["medido_en"],
                "motivo": motivo,
                "valores_anteriores": valores_anteriores,
                "valores": valores_nuevos
            }

            cursor = conexion.execute(
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
                    "MEDICION_CORREGIDA",
                    fecha,
                    profesional_usuario,
                    json.dumps(
                        contenido,
                        ensure_ascii=False,
                        allow_nan=False
                    )
                )
            )

            nuevo_id = cursor.lastrowid
    finally:
        conexion.close()

    return {
        "id": nuevo_id,
        "codigo_episodio": codigo_episodio,
        "tipo": "MEDICION_CORREGIDA",
        "ocurrido_en": fecha,
        "profesional_usuario": profesional_usuario,
        "datos": contenido
    }