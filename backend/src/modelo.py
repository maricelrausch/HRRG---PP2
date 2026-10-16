
import ollama

try:
    from .rag import buscar_informacion
except ImportError:
    from rag import buscar_informacion


# Modelo que responderá las preguntas médicas.
# Usamos el nombre del modelo instalado en Ollama.
LLM_MODEL = "medgemma:4b"


def responder(pregunta):
    """
    Busca información en el RAG y la utiliza como contexto
    para generar una respuesta con MedGemma.
    """

    if not pregunta or not pregunta.strip():
        return "Error: la pregunta está vacía."

    # 1. Recuperar información relacionada con la pregunta.
    fragmentos = buscar_informacion(pregunta)

    # 2. Construir el contexto a partir de los documentos.
    if fragmentos:
        contexto = "\n\n".join(
            f"Fuente: {fragmento['archivo']}\n"
            f"{fragmento['texto']}"
            for fragmento in fragmentos
        )
    else:
        contexto = "No se encontró documentación relevante."

    # 3. Preparar las instrucciones para el modelo.
    mensajes = [
        {
            "role": "system",
            "content": (
                "Sos un asistente de información médica. "
                "Respondé en español, con claridad. "
                "Diferenciá la información de las fuentes "
                "de tus propias inferencias. "
                "Si falta información, indicá qué falta. "
                "No inventes datos ni presentes tu respuesta "
                "como un diagnóstico definitivo. "
                "Si no hay documentación relevante, aclaralo."
            )
        },
        {
            "role": "user",
            "content": (
                f"Pregunta:\n{pregunta}\n\n"
                f"Documentación recuperada:\n{contexto}"
            )
        }
    ]

    # 4. Consultar a MedGemma mediante Ollama.
    try:
        respuesta = ollama.chat(
            model=LLM_MODEL,
            messages=mensajes,
            options={"temperature": 0.2}
        )

        return respuesta["message"]["content"].strip()

    except ollama.ResponseError as error:
        return f"Error de Ollama o del modelo: {error}"

    except Exception as error:
        return f"No se pudo generar la respuesta: {error}"


if __name__ == "__main__":
    pregunta = input("Escribí una pregunta: ")
    resultado = responder(pregunta)

    print("\nRespuesta del modelo:")
    print(resultado)
