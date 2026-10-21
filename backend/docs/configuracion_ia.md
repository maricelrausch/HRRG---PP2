# Documentación Técnica: Configuración e Integración de MedGemma (4B) con RAG y Ollama

## 1. Visión General del Sistema
Este componente actúa como el **módulo de generación de respuestas médicas** dentro de una arquitectura RAG (*Retrieval-Augmented Generation*). 

El sistema combina:
* **LLM Core:** `medgemma:4b` (Modelo de lenguaje enfocado en el dominio médico, ejecutado localmente a través de Ollama).
* **Módulo RAG (`rag.py`):** Encargado de recuperar fragmentos de texto y fuentes documentales relevantes según la consulta ingresada.
* **Orquestación en Python:** Control del flujo de datos, construcción de *prompts* con contexto y gestión de excepciones.

---

## 2. Requisitos y Pre-requisitos

### 2.1. Entorno de Ejecución
* **Ollama Server:** Instalado y en ejecución localmente.
* **Modelo Descargado:** El modelo `medgemma:4b` debe estar disponible localmente en Ollama:
  ```bash
  ollama pull medgemma:4b
  ```

### 2.2. Librerías de Python
* `ollama` (Cliente oficial de Python para Ollama).
* Módulo interno `rag.py` que exporte la función `buscar_informacion(pregunta)`.

---

## 3. Arquitectura del Código y Flujo de Trabajo

El proceso de generación de respuesta sigue un flujo secuencial en 4 pasos:

```text
[Entrada de Usuario] ──► 1. Validación de Entrada
                               │
                               ▼
                        2. Recuperación RAG (buscar_informacion)
                               │
                               ▼
                        3. Ensamblado de Contexto y Prompt System
                               │
                               ▼
                        4. Inferencia con MedGemma via Ollama
                               │
                               ▼
                        [Respuesta Salida / Manejo de Error]
```

### Detalle de Pasos:

1. **Validación:** Verifica que la consulta no esté vacía ni contenga únicamente espacios en blanco.
2. **Búsqueda RAG:** Invoca a `buscar_informacion(pregunta)` y formatea los fragmentos retornados incluyendo el nombre del archivo fuente y el texto extraído. Si no hay coincidencias, establece un aviso por defecto.
3. **Instrucciones del Sistema (System Prompt):**
   * Configura el rol del modelo como *Asistente de información médica*.
   * Exige respuestas en español y con claridad.
   * Delimita estrictamente que diferencie entre información respaldada por fuentes e inferencias propias.
   * Prohíbe inventar datos y presentar la respuesta como un diagnóstico médico definitivo.
4. **Configuración del LLM:**
   * **Modelo:** `medgemma:4b`
   * **Temperatura:** `0.2` (Configuración de baja variabilidad/creatividad para priorizar precisión, coherencia y fidelidad al contexto recuperado).

---

## 4. Código Fuente Implementado

```python
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
```

---

## 5. Manejo de Errores y Casos Borde

* **Respuesta vacía o nula:** Capturado antes de realizar llamadas al sistema RAG o al modelo.
* **Fallos del servicio Ollama (`ollama.ResponseError`):** Se capturan errores específicos como modelo no encontrado, servicio caído o parámetros inválidos.
* **Excepciones generales:** Evita que el programa falle por errores inesperados de conexión o formateo de datos.