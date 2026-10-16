
import json
import ollama
from pydantic import ValidationError

try:
    from .modelo import LLM_MODEL
    from .rag import buscar_informacion
except ImportError:
    from modelo import LLM_MODEL
    from rag import buscar_informacion

# Importamos los esquemas que ya existen en app.py.
# La importación se hace dentro de la función para evitar
# cargar app.py al iniciar este módulo.


def extraer_datos(relato, esquema):
    """
    Interpreta un relato y devuelve datos estructurados.
    Los campos que no aparecen en el relato deben quedar
    sin informar, salvo que el esquema tenga valores por defecto.
    """
    if not isinstance(relato, str) or not relato.strip():
        raise ValueError("El relato está vacío.")

    # Recuperar documentación pertinente.
    fragmentos = buscar_informacion(relato, cantidad=3)

    contexto = "\n\n".join(
        fragmento["texto"] for fragmento in fragmentos
    )

    # Generar un ejemplo del formato esperado por Pydantic.
    campos = esquema.model_fields
    formato = {}

    for nombre, campo in campos.items():
        if campo.is_required():
            formato[nombre] = None
        else:
            formato[nombre] = campo.default
        mensajes = [
        {
            "role": "system",
            "content": (
                "Sos un extractor de datos médicos. "
                "No diagnostiques ni asignes prioridades clínicas. "
                "Extraé únicamente información explícita del relato. "
                "No inventes edad, sexo, síntomas, mediciones ni antecedentes. "
                "Si un dato no aparece, devolvé null cuando el esquema lo permita. "
                "Respondé exclusivamente con un objeto JSON válido."
            )
        },
        {
            "role": "user",
            "content": (
                f"Relato:\n{relato}\n\n"
                f"Documentación de referencia:\n{contexto or 'Sin fragmentos relevantes.'}\n\n"
                f"Devolvé un JSON con estos campos:\n"
                f"{json.dumps(formato, ensure_ascii=False)}"
            )
        }
    ]

    respuesta = ollama.chat(
        model=LLM_MODEL,
        messages=mensajes,
        format=esquema.model_json_schema(),
        options={"temperature": 0}
    )

    contenido = respuesta["message"]["content"]

    try:
        datos = json.loads(contenido)
        validado = esquema.model_validate(datos)
    except (json.JSONDecodeError, ValidationError) as error:
        raise ValueError(
            "MedGemma no devolvió datos compatibles con el esquema."
        ) from error

    return validado.model_dump(mode="json")
