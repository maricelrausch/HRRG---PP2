import argparse
import json
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

import sys

# Permite importar src/ al correr el script desde backend: python scripts/preparar_identificacion.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cifrado_identificacion import (
    RUTA_CLAVES,
    CifradoIdentificacion,
)
from src.identificacion import inicializar_identificacion
from src.migrar_identificacion import migrar_identificacion


# Usa la misma ubicación que app.py, sin importar ni iniciar Flask.
BASE = Path.home() / ".hrrg_pp2" / "triage_demo.db"

COLUMNAS_ANTERIORES = {
    "codigo_paciente",
    "dni",
    "creado_en",
    "profesional_usuario",
}

COLUMNAS_CIFRADAS = {
    "codigo_paciente",
    "dni_cifrado",
    "dni_indice",
    "creado_en",
    "profesional_usuario",
}


# Reconoce instalaciones nuevas, bases anteriores y bases ya cifradas.
# Ante una estructura desconocida, detiene la preparación.
def detectar_estado():
    if not BASE.exists():
        return "nueva"

    conexion = sqlite3.connect(
        BASE.as_uri() + "?mode=ro",
        uri=True,
    )
    try:
        tablas = {
            fila[0]
            for fila in conexion.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        columnas = {
            fila[1]
            for fila in conexion.execute(
                "PRAGMA table_info(identificacion_pacientes)"
            )
        }

        if "identificacion_pacientes" not in tablas:
            if "identificacion_control" in tablas:
                raise RuntimeError(
                    "La estructura de identificacion esta incompleta."
                )
            return "nueva"

        if columnas == COLUMNAS_ANTERIORES:
            if "identificacion_control" in tablas:
                raise RuntimeError(
                    "Hay una estructura mixta. Revisar antes de continuar."
                )
            return "anterior"

        if columnas == COLUMNAS_CIFRADAS:
            return "cifrada"

        raise RuntimeError(
            "La tabla tiene un formato desconocido. No se modifico."
        )
    finally:
        conexion.close()


# Conserva las claves existentes.
# Nunca genera reemplazos para una base que ya está cifrada.
def preparar_claves(estado):
    if RUTA_CLAVES.exists():
        CifradoIdentificacion()
        print("OK: claves existentes conservadas.")
        return

    if estado == "cifrada":
        raise RuntimeError(
            "La base esta cifrada y faltan sus claves. "
            "Recupera el archivo original desde su respaldo."
        )

    RUTA_CLAVES.parent.mkdir(parents=True, exist_ok=True)

    contenido = {
        "version": 1,
        "cifrado": Fernet.generate_key().decode("ascii"),
        "busqueda": secrets.token_hex(32),
    }

    # El modo exclusivo impide sobrescribir claves existentes.
    with RUTA_CLAVES.open("x", encoding="utf-8") as archivo:
        json.dump(contenido, archivo)

    CifradoIdentificacion()
    print("OK: claves locales creadas.")


# Crea y verifica un respaldo completo antes de migrar.
# El respaldo conserva el formato anterior, incluido el DNI sin cifrar.
def respaldar_base():
    carpeta = BASE.parent / "respaldos"
    carpeta.mkdir(parents=True, exist_ok=True)

    marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ruta = carpeta / f"triage_antes_cifrado_{marca}.db"

    origen = sqlite3.connect(
        BASE.as_uri() + "?mode=ro",
        uri=True,
    )
    try:
        destino = sqlite3.connect(ruta)
        try:
            origen.backup(destino)
            resultado = destino.execute(
                "PRAGMA integrity_check"
            ).fetchall()

            if resultado != [("ok",)]:
                raise RuntimeError(
                    "El respaldo no supero la verificacion."
                )
        finally:
            destino.close()
    finally:
        origen.close()

    print("OK: respaldo verificado:", ruta)


# Prepara instalaciones nuevas o verifica las existentes.
# Una base anterior requiere la opción explícita --migrar.
def main():
    parser = argparse.ArgumentParser(
        description="Prepara la identificacion cifrada sin iniciar Flask."
    )
    parser.add_argument(
        "--migrar",
        action="store_true",
        help="Respalda y migra una base con DNI sin cifrar.",
    )
    argumentos = parser.parse_args()

    estado = detectar_estado()

    if estado == "anterior" and not argumentos.migrar:
        raise RuntimeError(
            "La base necesita migracion. Con Flask detenido, ejecuta: "
            "python scripts/preparar_identificacion.py --migrar"
        )

    preparar_claves(estado)
    BASE.parent.mkdir(parents=True, exist_ok=True)

    if estado == "anterior":
        respaldar_base()
        cantidad = migrar_identificacion(BASE)
        print("OK: pacientes migrados:", cantidad)

    # Verifica también que las claves correspondan a la base.
    # En una instalación nueva crea las tablas de identificación.
    inicializar_identificacion(BASE)

    print("OK: identificacion preparada y claves verificadas.")
    print("Ya podes iniciar Flask.")


# Presenta errores sin imprimir claves, DNI ni trazas con datos internos.
if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, sqlite3.Error) as error:
        raise SystemExit(f"ERROR: {error}")
    