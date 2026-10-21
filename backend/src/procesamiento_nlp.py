
# Modelo de Procesamiento de Lenguaje Natural (BETO)

from transformers import pipeline
from pathlib import Path
import re

# Ruta del modelo entrenado
RUTA_MODELO = Path(__file__).resolve().parents[2] / "modelo_medico_entrenado"

print("Cargando modelo NLP...")

nlp = pipeline(
    "ner",
    model=str(RUTA_MODELO),
    tokenizer=str(RUTA_MODELO),
    aggregation_strategy="simple",
    device=-1
)

print("Modelo NLP cargado correctamente.")


def extraer_entidades(texto):
    """Ejecuta BETO y devuelve las entidades detectadas."""

    if not texto or not texto.strip():
        return []

    predicciones = nlp(texto)
    entidades = []

    for prediccion in predicciones:
        entidades.append({
            "tipo": prediccion["entity_group"],
            "texto": texto[
                prediccion["start"]:prediccion["end"]
            ].strip()
        })

    return entidades


def extraer_mediciones(texto):
    """Extrae mediciones explícitas mediante expresiones regulares."""

    texto = texto.lower()

    datos = {
        "tas": None,
        "tad": None,
        "pam": None,
        "frec_cardiaca": None,
        "frec_respiratoria": None,
        "saturacion": None,
        "temperatura": None,
        "glasgow": None,
        "dolor": None,
    }

    # Tensión arterial: TA 120/80, tensión arterial 120/80, etc.
    tension = re.search(
        r"\b(?:tensión arterial|tension arterial|"
        r"presión arterial|presion arterial|\bta)"
        r"\s*:?\s*(\d{2,3})\s*/\s*(\d{2,3})\b",
        texto
    )

    if tension:
        datos["tas"] = tension.group(1)
        datos["tad"] = tension.group(2)

    patrones = {
        "pam": (
            r"\b(?:pam|presión arterial media|"
            r"presion arterial media)\s*:?\s*(\d{2,3})\b"
        ),
        "frec_cardiaca": (
            r"\b(?:frecuencia cardíaca|frecuencia cardiaca|"
            r"fc|pulso)\s*:?\s*(\d{1,3})\b"
        ),
        "frec_respiratoria": (
            r"\b(?:frecuencia respiratoria|fr)\s*:?\s*(\d{1,2})\b"
        ),
        "saturacion": (
            r"\b(?:saturación|saturacion)"
            r"(?:\s+de\s+oxígeno)?\s*:?\s*(?:es\s+de\s+)?"
            r"(\d{2,3})\s*%?"
            r"|\b(?:spo2|sat\.?)\s*:?\s*(\d{2,3})\s*%?"
        ),
        "temperatura": (
            r"\b(?:temperatura|temp\.?)"
            r"(?:\s+de)?\s*:?\s*(\d{2}(?:[.,]\d)?)"
            r"\s*(?:°\s*)?(?:c(?:elsius)?)?"
        ),
        "glasgow": r"\bglasgow\s*:?\s*(\d{1,2})\b",
        "dolor": (
            r"\b(?:dolor|eva)\s*:?\s*(\d{1,2})(?:\s*/\s*10)?\b"
        ),
    }

    for campo, patron in patrones.items():
        coincidencia = re.search(patron, texto)

        if coincidencia:
            datos[campo] = coincidencia.group(1).replace(",", ".")

    return datos


def extraer_datos_planilla(texto):
    """Combina mediciones por reglas y entidades reconocidas por BETO."""

    campos = {
        "edad": None,
        "sexo": None,
        "motivo_consulta": None,
        "tas": None,
        "tad": None,
        "pam": None,
        "frec_cardiaca": None,
        "frec_respiratoria": None,
        "saturacion": None,
        "temperatura": None,
        "glasgow": None,
        "dolor": None,
        "localizacion_dolor": None,
    }

    if not texto or not texto.strip():
        return campos

    # 1. Extraer las mediciones explícitas
    campos.update(extraer_mediciones(texto))

    # 2. Ejecutar BETO para extraer las entidades de texto
    equivalencias = {
        "EDAD": "edad",
        "SEXO": "sexo",
        "MOTIVO_CONSULTA": "motivo_consulta",
        "TAS": "tas",
        "TAD": "tad",
        "PAM": "pam",
        "FREC_CARDIACA": "frec_cardiaca",
        "FREC_RESPIRATORIA": "frec_respiratoria",
        "SATURACION": "saturacion",
        "TEMPERATURA": "temperatura",
        "GLASGOW": "glasgow",
        "DOLOR": "dolor",
        "LOCALIZACION_DOLOR": "localizacion_dolor",
    }

    entidades = extraer_entidades(texto)

    for entidad in entidades:
        campo = equivalencias.get(entidad["tipo"])

        # Las reglas numéricas tienen prioridad para las mediciones
        if campo and campos[campo] is None:
            valor = entidad["texto"].strip()
            if campo == "saturacion" or campo == "temperatura":
                continue
            campos[campo] = valor

    return campos
