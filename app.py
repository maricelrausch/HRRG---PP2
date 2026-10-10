
from flask import Flask, json, render_template, request, jsonify, send_from_directory
from ollama import chat, embed
from PyPDF2 import PdfReader


import os
import math
import time


app = Flask(__name__)

# ------------------------------------------------
# Usuario y Contraseña Admin // Se puede modificar para más usuarios y contraseñas // Cambiar accesos
# ------------------------------------------------

usuario = {
    "admin": "admin123",
    "empleado": "empleado123"
}

# ------------------------------------------------
# Función para iniciar sesión //
# FALTA DEFINIR LA RUTA DESDE EL FRONTEND con @app.route("/login", methods=["POST"])
# ------------------------------------------------

def iniciar_sesion(username, password):
    if username in usuario and usuario[username] == password:
        return True
    else:
        return False

# ------------------------------------------------
# HOME / No hay un index.html definido, falta para el inicio de sesión.
# ------------------------------------------------

@app.route("/")
def inicio():
    return send_from_directory("frontend", "formulario.html")

# ------------------------------------------------
# Formulario Paciente // verificar ruta
# ------------------------------------------------

@app.route("/frontend", methods=["GET", "POST"])
def paciente_form():
    if request.method == "POST":

        # Datos que vienen del formulario (1)
        codigo_episodio = request.form.get("codigo_episodio")
        edad = request.form.get("edad")
        sexo = request.form.get("sexo")

        # Datos que vienen del formulario (2)
        motivo_consulta = request.form.get("motivo_consulta")

        # Datos que vienen del formulario (3)
        tas = request.form.get("tas")
        tad = request.form.get("tad")
        frec_cardiaca = request.form.get("frec_cardiacad")
        frec_respiratoria = request.form.get("frec_respiratoria")
        saturacion = request.form.get("saturacion")
        temperatura = request.form.get("temperatura")
        
        # Datos que vienen del formulario (4)
        glasgow = request.form.get("glasgow")
        dolor = request.form.get("dolor")
        localizacion_dolor = request.form.get("localizacion_dolor")

        # Datos que vienen del formulario (5)

        # Guardar en un json nuevo // agregar archivo
        with open("pacientes.json", "a") as f:
            f.write(json.dumps({"codigo_episodio": codigo_episodio, "edad": edad, "sexo": sexo, "tas": tas, "tad": tad, "frec_cardiaca": frec_cardiaca, "frec_respiratoria": frec_respiratoria, "saturacion": saturacion, "temperatura": temperatura, "glasgow": glasgow, "dolor": dolor, "localizacion_dolor": localizacion_dolor}) + "\n")

        return jsonify({"message": "Formulario recibido", "codigo_episodio": codigo_episodio, "edad": edad, "sexo": sexo, "tas": tas, "tad": tad, "frec_cardiaca": frec_cardiaca, "frec_respiratoria": frec_respiratoria, "saturacion": saturacion, "temperatura": temperatura, "glasgow": glasgow, "dolor": dolor, "localizacion_dolor": localizacion_dolor})
    return render_template("formulario.html")



# Carpeta de subida de archivos
app.config["UPLOAD_FOLDER"] = "docs"


# Memoria simple del documento
document_chunks = []
document_vectors = []


# Modelo de LLM y  Modelo de embedding    
LLM_MODEL = "qwen2.5:0.5b"
EMBED_MODEL = "embeddinggemma"


# PACIENTE

def get_patient_info():
    return 


# ------------------------------------------------
# EXTRAER TEXTO DEL PDF
# ------------------------------------------------

def extract_text(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text




# ------------------------------------------------
# DIVIDIR TEXTO
# ------------------------------------------------

def split_chunks(text, size=2000):
    text = text.replace("\n", " ")
    chunks = []
    for i in range(0, len(text), size):
        chunk = text[i:i + size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks[:5]


# ------------------------------------------------
# COSINE SIMILARITY
# ------------------------------------------------

def cosine_similarity(v1, v2):
    dot = sum(a*b for a,b in zip(v1,v2))

    n1 = math.sqrt(sum(a*a for a in v1))
    n2 = math.sqrt(sum(b*b for b in v2))

    if n1 == 0 or n2 == 0:
        return 0

    return dot/(n1*n2)


# ------------------------------------------------
# CREAR EMBEDDINGS
# ------------------------------------------------

def create_embeddings(chunks):
    vectors = []
    for chunk in chunks:
        e = embed(
            model = EMBED_MODEL,
            input = chunk
        )
        vectors.append(e["embeddings"][0])
    return vectors


# ------------------------------------------------
# BUSQUEDA SEMANTICA
# ------------------------------------------------

def search(question):
    q_vec = embed(
        model = EMBED_MODEL,
        input = question
    )["embeddings"][0]
    scores = []
    for chunk,vec in zip(document_chunks, document_vectors):
        s = cosine_similarity(q_vec,vec)
        scores.append((s,chunk))
    scores.sort(reverse=True,key=lambda x:x[0])
    return scores[:3]



# ------------------------------------------------
# SUBIR PDF ( MODIFICAR ) = CARPETA UPLOADS SIN CREAR / HAY Q AGREGAR LOS DOCUMENTOS PDF DE EJEMPLO
# ------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload():
    global document_chunks, document_vectors
    pdf = request.files["pdf_file"]
    os.makedirs("uploads", exist_ok=True)
    path = os.path.join("uploads", pdf.filename)
    pdf.save(path)
    text = extract_text(path)
    document_chunks = split_chunks(text)
    document_vectors = create_embeddings(document_chunks)
    return jsonify({
        "chunks": len(document_chunks)
    })


# ------------------------------------------------
# CHAT
# ------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat_api():


    data = request.json
    question = data["message"]


    steps = []


    # Paso 1
    steps.append("Pregunta recibida")


    # Paso 2: embedding de la pregunta
    q_vec = embed(
        model = EMBED_MODEL,
        input = question
    )["embeddings"][0]


    steps.append("Embedding de la pregunta generado")


    # Paso 3: búsqueda semántica
    scores = []


    for chunk,vec in zip(document_chunks, document_vectors):


        s = cosine_similarity(q_vec,vec)


        scores.append((s,chunk))


    scores.sort(reverse=True,key=lambda x:x[0])


    top_chunks = [chunk for score,chunk in scores[:3]]


    steps.append("Búsqueda semántica en el documento")


    context = "\n\n".join(top_chunks)


    steps.append("Contexto construido para el modelo")


    prompt = f"""
Usa el siguiente contexto del documento para responder.


Contexto:
{context}


Pregunta:
{question}
"""


    start = time.time()


    response = chat(
        model = LLM_MODEL,
        messages=[
            {"role":"user","content":prompt}
        ],
        options={
            "temperature":0.2,
            "num_predict":120
        }
    )


    elapsed = round(time.time() - start, 2)


    steps.append("Respuesta generada por el modelo")


    answer = response["message"]["content"].strip()


    return jsonify({
        "answer": answer,
        "time": elapsed,
        "steps": steps
    })




if __name__ == "__main__":


    app.run(debug=True)



