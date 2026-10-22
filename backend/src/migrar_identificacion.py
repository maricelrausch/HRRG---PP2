import sqlite3

from src.cifrado_identificacion import CifradoIdentificacion
from src.identificacion import normalizar_dni


# Migra únicamente la identificación de pacientes.
# Conserva los códigos, las fechas y los profesionales originales.
# Si una comprobación falla, revierte todos los cambios de la transacción.
def migrar_identificacion(ruta_base):
    cifrado = CifradoIdentificacion()
    conexion = sqlite3.connect(ruta_base)
    conexion.row_factory = sqlite3.Row

    try:
        # Activa la comprobación de relaciones y el borrado de contenido
        # eliminado dentro de SQLite. Los respaldos previos no se modifican.
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.execute("PRAGMA secure_delete = ON")
        conexion.execute("BEGIN IMMEDIATE")

        # Exige el esquema original para evitar modificar una base
        # que ya fue migrada o que tiene una estructura diferente.
        columnas = {
            fila["name"]
            for fila in conexion.execute(
                "PRAGMA table_info(identificacion_pacientes)"
            )
        }

        esperadas = {
            "codigo_paciente",
            "dni",
            "creado_en",
            "profesional_usuario",
        }

        if columnas != esperadas:
            raise ValueError(
                "La tabla no tiene el formato original esperado. "
                "No se realizó la migración."
            )

        # Evita eliminar índices, disparadores o relaciones personalizados
        # que no estén contemplados por esta migración.
        objetos = conexion.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE tbl_name = 'identificacion_pacientes'
              AND type IN ('index', 'trigger')
              AND sql IS NOT NULL
            """
        ).fetchall()

        if objetos:
            raise ValueError(
                "La tabla tiene índices o disparadores adicionales. "
                "Es necesario revisarlos antes de migrar."
            )

        tablas = conexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

        for tabla in tablas:
            nombre = tabla["name"].replace('"', '""')
            referencias = conexion.execute(
                f'PRAGMA foreign_key_list("{nombre}")'
            ).fetchall()

            if any(
                fila["table"] == "identificacion_pacientes"
                for fila in referencias
            ):
                raise ValueError(
                    "Hay claves foráneas hacia identificación. "
                    "Es necesario adaptar la migración."
                )

        # Lee los registros originales sin imprimir documentos
        # ni incluirlos en mensajes de error.
        pacientes = conexion.execute(
            """
            SELECT codigo_paciente, dni, creado_en,
                   profesional_usuario
            FROM identificacion_pacientes
            """
        ).fetchall()

        # Guarda el DNI cifrado y un índice HMAC para buscarlo.
        # El índice permite localizar al paciente sin guardar el DNI visible.
        conexion.execute(
            """
            CREATE TABLE identificacion_pacientes_cifrada (
                codigo_paciente TEXT PRIMARY KEY,
                dni_cifrado TEXT NOT NULL,
                dni_indice TEXT NOT NULL UNIQUE,
                creado_en TEXT NOT NULL,
                profesional_usuario TEXT NOT NULL
            )
            """
        )

        for paciente in pacientes:
            dni = normalizar_dni(paciente["dni"])
            contenido = cifrado.cifrar(dni)

            # Comprueba cada cifrado antes de incorporarlo.
            if cifrado.descifrar(contenido) != dni:
                raise ValueError("Falló la verificación del cifrado.")

            conexion.execute(
                """
                INSERT INTO identificacion_pacientes_cifrada (
                    codigo_paciente, dni_cifrado, dni_indice,
                    creado_en, profesional_usuario
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    paciente["codigo_paciente"],
                    contenido,
                    cifrado.indice(dni),
                    paciente["creado_en"],
                    paciente["profesional_usuario"],
                ),
            )

        # Guarda una comprobación de ambas claves.
        # El módulo de identificación deberá verificarla para impedir
        # que otras claves válidas se utilicen sobre esta misma base.
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

        prueba = "HRRG:identificacion:v1"
        conexion.execute(
            """
            INSERT INTO identificacion_control (
                id, version, prueba_cifrada, prueba_indice
            )
            VALUES (1, 1, ?, ?)
            """,
            (cifrado.cifrar(prueba), cifrado.indice(prueba)),
        )

        # Verifica que todos los pacientes conservaron su código,
        # fecha y profesional antes de reemplazar la tabla.
        diferencias = conexion.execute(
            """
            SELECT codigo_paciente, creado_en, profesional_usuario
            FROM identificacion_pacientes
            EXCEPT
            SELECT codigo_paciente, creado_en, profesional_usuario
            FROM identificacion_pacientes_cifrada
            """
        ).fetchall()

        cantidad = conexion.execute(
            "SELECT COUNT(*) FROM identificacion_pacientes_cifrada"
        ).fetchone()[0]

        if diferencias or cantidad != len(pacientes):
            raise ValueError("No se conservaron todos los registros.")

        # Reemplaza la tabla dentro de la misma transacción.
        # Las tablas de episodios, mediciones y eventos no se modifican.
        conexion.execute("DROP TABLE identificacion_pacientes")
        conexion.execute(
            """
            ALTER TABLE identificacion_pacientes_cifrada
            RENAME TO identificacion_pacientes
            """
        )

        # Comprueba la integridad antes de confirmar el cambio.
        integridad = conexion.execute(
            "PRAGMA integrity_check"
        ).fetchall()

        if [fila[0] for fila in integridad] != ["ok"]:
            raise ValueError("Falló la comprobación de integridad.")

        if conexion.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Falló la comprobación de relaciones.")

        conexion.commit()
        return cantidad

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()

        