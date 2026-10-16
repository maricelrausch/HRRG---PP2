
from pathlib import Path

import chromadb
import ollama


# Rutas del proyecto
CARPETA_DOCUMENTOS = (
    Path(__file__).parent
    / "base_conocimiento"
    / "documentos"
)

CARPETA_BASE_DATOS = (
    Path(__file__).parent
    / "base_conocimiento"
    / "chroma_db"
)

# Modelos utilizados
EMBED_MODEL = "embeddinggemma"

# Base de datos vectorial persistente
cliente = chromadb.PersistentClient(
    path=str(CARPETA_BASE_DATOS)
)

coleccion = cliente.get_or_create_collection(
    name="documentacion_medica"
)

def leer_documentos():
    """Lee archivos de texto .txt de la carpeta de documentos."""

    documentos = []

    for archivo in CARPETA_DOCUMENTOS.glob("*.txt"):
        texto = archivo.read_text(encoding="utf-8").strip()

        if texto:
            documentos.append({
                "nombre": archivo.name,
                "texto": texto
            })

    return documentos


def dividir_texto(texto, tamano=700, solapamiento=100):
    """Divide el texto en fragmentos con un pequeño solapamiento."""

    if tamano <= 0 or not 0 <= solapamiento < tamano:
        raise ValueError("Los tamaños de fragmento no son válidos.")

    fragmentos = []
    inicio = 0

    while inicio < len(texto):
        fin = min(inicio + tamano, len(texto))
        fragmento = texto[inicio:fin].strip()

        if fragmento:
            fragmentos.append(fragmento)

        if fin == len(texto):
            break

        inicio = fin - solapamiento

    return fragmentos


def crear_embeddings(textos):
    """Convierte los fragmentos de texto en vectores numéricos."""

    respuesta = ollama.embed(
        model=EMBED_MODEL,
        input=textos
    )

    return respuesta["embeddings"]


def indexar_documentos():
    """Guarda los fragmentos y sus embeddings en ChromaDB."""

    documentos = leer_documentos()

    if not documentos:
        print("No se encontraron archivos .txt con contenido.")
        return

    ids = []
    textos = []
    metadatos = []

    for documento in documentos:
        fragmentos = dividir_texto(documento["texto"])

        for numero, fragmento in enumerate(fragmentos):
            ids.append(f'{documento["nombre"]}_{numero}')
            textos.append(fragmento)
            metadatos.append({
                "archivo": documento["nombre"],
                "fragmento": numero
            })

    if not textos:
        print("No hay fragmentos para indexar.")
        return

    embeddings = crear_embeddings(textos)

    # Reemplaza las versiones anteriores de estos documentos.
    nombres = {doc["nombre"] for doc in documentos}

    for nombre in nombres:
        existentes = coleccion.get(
            where={"archivo": nombre}
        )

        if existentes["ids"]:
            coleccion.delete(ids=existentes["ids"])

    coleccion.upsert(
        ids=ids,
        documents=textos,
        metadatas=metadatos,
        embeddings=embeddings
    )

    print(f"Se indexaron {len(textos)} fragmentos.")


def buscar_informacion(pregunta, cantidad=3):
    """Recupera los fragmentos más similares a una pregunta."""

    if not pregunta or not pregunta.strip():
        return []

    if coleccion.count() == 0:
        return []

    vector_pregunta = crear_embeddings([pregunta])[0]

    resultados = coleccion.query(
        query_embeddings=[vector_pregunta],
        n_results=min(cantidad, coleccion.count())
    )

    fragmentos = []

    for texto, metadata in zip(
        resultados["documents"][0],
        resultados["metadatas"][0]
    ):
        fragmentos.append({
            "texto": texto,
            "archivo": metadata["archivo"]
        })

    return fragmentos


if __name__ == "__main__":
    indexar_documentos()

    resultados = buscar_informacion(
        "¿Qué información contiene la documentación sobre hemorragias?"
    )

    for resultado in resultados:
        print(f'\nFuente: {resultado["archivo"]}')
        print(resultado["texto"])
