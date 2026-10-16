"""
C04 · Validaciones técnicas (antes de la IA), con el esquema central de src/esquemas.py.

    from src.validacion import validar
    r = validar(datos)                    # todas las etapas
    r = validar(datos, etapa="ingreso")   # solo faltantes de esa etapa ("ingreso" o "medicion")

Devuelve:
    valido     True/False
    errores    lista de textos en español (bloquean: hay que corregir)
    faltantes  campos obligatorios vacíos (NO bloquean: se informan como missing_data)
    datos      datos limpios y con tipos correctos (None si hay errores)

No asigna gravedad clínica: solo controla tipos, rangos, opciones, coherencia y privacidad.
"""
from pydantic import ValidationError

from .esquemas import OBLIGATORIOS, DatosTriage, errores_en_espanol


def validar(datos: dict, etapa: str | None = None) -> dict:
    if etapa is not None and etapa not in OBLIGATORIOS:
        raise ValueError(f"etapa debe ser una de {list(OBLIGATORIOS)}")
    try:
        d = DatosTriage.model_validate(datos or {})
    except ValidationError as e:
        return {"valido": False, "errores": errores_en_espanol(e), "faltantes": [], "datos": None}
    return {"valido": True, "errores": [], "faltantes": d.faltantes(etapa),
            "datos": d.model_dump(exclude_none=True)}


def es_numero(valor) -> bool:
    """Compatibilidad con módulos anteriores (reglas.py)."""
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)
