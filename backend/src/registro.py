import sqlite3
import json
from datetime import datetime, timezone
from src.esquemas import Mediciones

def conectar_registro(ruta_base):
    conexion = sqlite3.connect(ruta_base)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


# Prepara las tablas del registro de demostración.
# Conserva las tablas y los datos que ya existen.
def inicializar_registro(ruta_base):
    conexion = conectar_registro(ruta_base)

    try:
        with conexion:
            # Guarda la identificación de cada atención y su creador.
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS episodios (
                    codigo_episodio TEXT PRIMARY KEY,
                    codigo_paciente TEXT NOT NULL,
                    creado_en TEXT NOT NULL,
                    profesional_usuario TEXT NOT NULL
                )
            """)

            # Conserva los eventos del historial con fecha y autor.
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

            # Facilita la consulta del historial de cada episodio.
            conexion.execute("""
                CREATE INDEX IF NOT EXISTS idx_eventos_episodio
                ON eventos (codigo_episodio, id)
            """)

            # Guarda el estado operativo actual de cada episodio.
            # La versión permitirá detectar cambios simultáneos.
            # Estos estados no representan una prioridad clínica.
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS estados_episodio (
                    codigo_episodio TEXT PRIMARY KEY,
                    estado TEXT NOT NULL
                        CHECK (
                            estado IN (
                                'en_ingreso',
                                'en_espera',
                                'finalizado'
                            )
                        ),
                    actualizado_en TEXT NOT NULL,
                    profesional_usuario TEXT NOT NULL,
                    version INTEGER NOT NULL
                        CHECK (version >= 1),
                    FOREIGN KEY (codigo_episodio)
                        REFERENCES episodios (codigo_episodio)
                )
            """)

            # Facilita la búsqueda de episodios según su estado.
            conexion.execute("""
                CREATE INDEX IF NOT EXISTS idx_estados_episodio
                ON estados_episodio (estado, actualizado_en)
            """)

    finally:
        # Libera la conexión incluso si ocurre un error.
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

# Busca episodios por código exacto de paciente o de episodio.
# Devuelve una página de resultados; no modifica los registros.
def buscar_episodios(
    ruta_base,
    codigo_paciente=None,
    codigo_episodio=None,
    limite=50,
    desplazamiento=0
):
    condiciones = []
    parametros = []

    # Los valores se pasan como parámetros para evitar inyección SQL.
    if codigo_paciente:
        condiciones.append("codigo_paciente = ?")
        parametros.append(codigo_paciente)

    if codigo_episodio:
        condiciones.append("codigo_episodio = ?")
        parametros.append(codigo_episodio)

    filtro = (
        " WHERE " + " AND ".join(condiciones)
        if condiciones else ""
    )

    conexion = conectar_registro(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        # Consulta primero la cantidad total que coincide con los filtros.
        total = conexion.execute(
            "SELECT COUNT(*) FROM episodios" + filtro,
            parametros
        ).fetchone()[0]

        # Ordena de más reciente a más antiguo y limita la respuesta.
        filas = conexion.execute(
            """
            SELECT codigo_episodio, codigo_paciente,
                   creado_en, profesional_usuario
            FROM episodios
            """ + filtro + """
            ORDER BY creado_en DESC, codigo_episodio DESC
            LIMIT ? OFFSET ?
            """,
            parametros + [limite, desplazamiento]
        ).fetchall()

        return {
            "episodios": [dict(fila) for fila in filas],
            "total": total
        }
    finally:
        conexion.close()

# Identifica un episodio inexistente para que Flask pueda responder 404.
class EpisodioNoEncontradoError(ValueError):
    pass


# Identifica una modificación basada en una versión desactualizada.
# Flask podrá responder 409 y pedir que se vuelva a consultar el episodio.
class ConflictoEstadoError(ValueError):
    pass


# Guarda el estado operativo y agrega su evento al historial.
# El profesional debe obtenerse de la sesión autenticada en Flask.
# Esta función no determina prioridades clínicas ni colores.
def cambiar_estado_demo(
    ruta_base,
    codigo_episodio,
    profesional_usuario,
    nuevo_estado,
    version_esperada
):
    # Comprueba los identificadores antes de acceder a SQLite.
    for valor in (codigo_episodio, profesional_usuario):
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError(
                "El episodio y el profesional son obligatorios."
            )

    codigo_episodio = codigo_episodio.strip()
    profesional_usuario = profesional_usuario.strip()

    # Acepta solamente los estados operativos del prototipo.
    estados_permitidos = {"en_ingreso", "en_espera", "finalizado"}
    if (
        not isinstance(nuevo_estado, str)
        or nuevo_estado not in estados_permitidos
    ):
        raise ValueError("El estado solicitado no es válido.")

    # La versión 0 representa un episodio sin estado registrado.
    # Rechaza también booleanos, aunque Python los considere enteros.
    if type(version_esperada) is not int or version_esperada < 0:
        raise ValueError(
            "La versión esperada debe ser un entero no negativo."
        )

    conexion = conectar_registro(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        with conexion:
            # Evita que otra escritura se intercale entre la consulta
            # del estado y el guardado del cambio.
            conexion.execute("BEGIN IMMEDIATE")

            # Comprueba que exista la atención.
            episodio = conexion.execute(
                "SELECT codigo_episodio FROM episodios "
                "WHERE codigo_episodio = ?",
                (codigo_episodio,)
            ).fetchone()

            if episodio is None:
                raise EpisodioNoEncontradoError(
                    "El episodio no existe."
                )

            # Recupera el último estado operativo guardado.
            anterior = conexion.execute(
                """
                SELECT estado, version
                FROM estados_episodio
                WHERE codigo_episodio = ?
                """,
                (codigo_episodio,)
            ).fetchone()

            estado_anterior = anterior["estado"] if anterior else None
            version_actual = anterior["version"] if anterior else 0

            # Impide sobrescribir un cambio que otro profesional
            # haya realizado desde la última consulta.
            if version_esperada != version_actual:
                raise ConflictoEstadoError(
                    "El estado cambió. Actualizá el episodio "
                    "antes de volver a guardar."
                )

            # Evita crear eventos que no representan ningún cambio.
            if nuevo_estado == estado_anterior:
                raise ValueError(
                    "El episodio ya tiene ese estado."
                )

            # Genera la fecha en el servidor y aumenta la versión.
            fecha = datetime.now(timezone.utc).isoformat()
            nueva_version = version_actual + 1

            # Crea el estado inicial o actualiza el existente.
            # No modifica el profesional que creó el episodio.
            conexion.execute(
                """
                INSERT INTO estados_episodio (
                    codigo_episodio, estado, actualizado_en,
                    profesional_usuario, version
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(codigo_episodio) DO UPDATE SET
                    estado = excluded.estado,
                    actualizado_en = excluded.actualizado_en,
                    profesional_usuario = excluded.profesional_usuario,
                    version = excluded.version
                """,
                (
                    codigo_episodio,
                    nuevo_estado,
                    fecha,
                    profesional_usuario,
                    nueva_version
                )
            )

            # Conserva el estado anterior y el nuevo en el historial.
            contenido = {
                "version_evento": 1,
                "modo": "demo",
                "origen": "cambio_estado_profesional",
                "estado_anterior": estado_anterior,
                "estado_nuevo": nuevo_estado,
                "version_anterior": version_actual,
                "version": nueva_version
            }

            cursor = conexion.execute(
                """
                INSERT INTO eventos (
                    codigo_episodio, tipo, ocurrido_en,
                    profesional_usuario, datos_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    codigo_episodio,
                    "ESTADO_CAMBIADO",
                    fecha,
                    profesional_usuario,
                    json.dumps(
                        contenido,
                        ensure_ascii=False,
                        allow_nan=False
                    )
                )
            )

            evento_id = cursor.lastrowid

        # Devuelve el resultado solamente después de confirmar
        # el guardado del estado y su evento.
        return {
            "estado": {
                "codigo_episodio": codigo_episodio,
                "estado": nuevo_estado,
                "actualizado_en": fecha,
                "profesional_usuario": profesional_usuario,
                "version": nueva_version
            },
            "evento": {
                "id": evento_id,
                "codigo_episodio": codigo_episodio,
                "tipo": "ESTADO_CAMBIADO",
                "ocurrido_en": fecha,
                "profesional_usuario": profesional_usuario,
                "datos": contenido
            }
        }

    finally:
        # Libera la conexión incluso cuando ocurre un error.
        conexion.close()

# Consulta el estado operativo sin modificar el episodio.
# Flask deberá autorizar el acceso antes de llamar a esta función.
def obtener_estado_demo(ruta_base, codigo_episodio):
    # Comprueba que el código recibido sea un texto válido.
    if (
        not isinstance(codigo_episodio, str)
        or not codigo_episodio.strip()
    ):
        raise ValueError("El código de episodio es obligatorio.")

    codigo_episodio = codigo_episodio.strip()
    conexion = conectar_registro(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        # Consulta el episodio y su estado en una misma operación.
        # LEFT JOIN permite reconocer episodios que aún no tienen estado.
        fila = conexion.execute(
            """
            SELECT
                e.codigo_episodio,
                s.estado,
                s.actualizado_en,
                s.profesional_usuario,
                s.version
            FROM episodios AS e
            LEFT JOIN estados_episodio AS s
                ON s.codigo_episodio = e.codigo_episodio
            WHERE e.codigo_episodio = ?
            """,
            (codigo_episodio,)
        ).fetchone()

        # Distingue un episodio inexistente de uno sin estado asignado.
        if fila is None:
            raise EpisodioNoEncontradoError(
                "El episodio no existe."
            )

        # La versión 0 indica que todavía no se registró ningún estado.
        # No supone que el episodio esté en ingreso o en espera.
        resultado = dict(fila)
        if resultado["version"] is None:
            resultado["version"] = 0

        return resultado

    finally:
        # Cierra la conexión tanto si la consulta funciona como si falla.
        conexion.close()

        # Consulta una página de episodios cuyo estado actual es en_espera.
# No modifica registros ni asigna prioridades clínicas.
def listar_espera_demo(ruta_base, limite=50, desplazamiento=0):
    # Valida la paginación también en la función de almacenamiento.
    if type(limite) is not int or not 1 <= limite <= 100:
        raise ValueError("El límite debe estar entre 1 y 100.")

    if type(desplazamiento) is not int or desplazamiento < 0:
        raise ValueError(
            "El desplazamiento debe ser un entero no negativo."
        )

    conexion = conectar_registro(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        # Mantiene el total y los resultados dentro de la misma lectura.
        with conexion:
            conexion.execute("BEGIN")

            # Cuenta únicamente los episodios actualmente en espera.
            total = conexion.execute(
                """
                SELECT COUNT(*)
                FROM estados_episodio
                WHERE estado = 'en_espera'
                """
            ).fetchone()[0]

            # Ordena por la entrada al estado de espera actual.
            # Distingue al creador del episodio del autor del cambio.
            filas = conexion.execute(
                """
                SELECT
                    e.codigo_episodio,
                    e.codigo_paciente,
                    e.creado_en,
                    e.profesional_usuario AS profesional_creador,
                    s.estado,
                    s.actualizado_en AS en_espera_desde,
                    s.profesional_usuario AS profesional_estado,
                    s.version
                FROM estados_episodio AS s
                JOIN episodios AS e
                    ON e.codigo_episodio = s.codigo_episodio
                WHERE s.estado = 'en_espera'
                ORDER BY s.actualizado_en ASC, e.codigo_episodio ASC
                LIMIT ? OFFSET ?
                """,
                (limite, desplazamiento)
            ).fetchall()

        return {
            "episodios": [dict(fila) for fila in filas],
            "total": total,
            "limite": limite,
            "desplazamiento": desplazamiento
        }

    finally:
        # Libera la conexión incluso si falla la consulta.
        conexion.close()

        