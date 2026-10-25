import hashlib
import hmac
import json
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


# Ubica las claves fuera del repositorio y separadas de SQLite.
RUTA_CLAVES = (
    Path.home() / ".hrrg_pp2_claves" / "identificacion.json"
)


# Permite distinguir problemas de claves de errores de datos.
class ErrorCifradoIdentificacion(RuntimeError):
    pass


# Carga claves existentes. Nunca genera reemplazos automáticamente:
# perder una clave no debe provocar nuevas identificaciones del paciente.
class CifradoIdentificacion:
    def __init__(self, ruta_claves=RUTA_CLAVES):
        try:
            datos = json.loads(
                Path(ruta_claves).read_text(encoding="utf-8")
            )
            if datos["version"] != 1:
                raise ValueError("Versión de claves no admitida.")

            self._fernet = Fernet(datos["cifrado"].encode("ascii"))
            self._clave_busqueda = bytes.fromhex(datos["busqueda"])

            if len(self._clave_busqueda) != 32:
                raise ValueError("Longitud de clave incorrecta.")

        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ErrorCifradoIdentificacion(
                "No se pudieron cargar las claves de identificación. "
                "Revisá el archivo de claves; no lo reemplaces."
            ) from error

    # Cifra el DNI previamente normalizado.
    # El resultado cambia en cada cifrado, aunque el DNI sea el mismo.
    def cifrar(self, dni):
        return self._fernet.encrypt(
            dni.encode("utf-8")
        ).decode("ascii")

    # Recupera el DNI y verifica que el contenido no haya sido alterado.
    def descifrar(self, contenido):
        try:
            return self._fernet.decrypt(
                contenido.encode("ascii")
            ).decode("utf-8")
        except (InvalidToken, UnicodeError, AttributeError) as error:
            raise ErrorCifradoIdentificacion(
                "No se pudo verificar la identificación cifrada."
            ) from error

    # Genera un índice estable para buscar el DNI normalizado.
    # Usa HMAC con una clave propia, no un hash simple del documento.
    def indice(self, dni):
        return hmac.new(
            self._clave_busqueda,
            b"HRRG:DNI:v1:" + dni.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()