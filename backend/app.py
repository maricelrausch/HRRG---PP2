from flask import Flask, json, request, jsonify, send_from_directory, session, g
from ollama import chat, embed
from PyPDF2 import PdfReader
from werkzeug.security import generate_password_hash
from pathlib import Path
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from src.auth import iniciar_sesion, profesional_activo, obtener_profesional
from src.registro import inicializar_registro, crear_episodio, obtener_episodio
from src.registro import (
    registrar_medicion_demo,
    corregir_medicion_demo,
)
from pydantic import ValidationError
from src.esquemas import ExtraccionIA, OBLIGATORIOS
from src.registro import buscar_episodios
import os
import math
import time
import sqlite3
import click
import secrets
import logging
import re
import secrets



# ------------------------------------------------
# Ubicación del backend y del frontend.
# ------------------------------------------------

CARPETA_BACKEND = Path(__file__).resolve().parent
CARPETA_PROYECTO = CARPETA_BACKEND.parent
CARPETA_FRONTEND = CARPETA_PROYECTO / "frontend"

app = Flask(
    __name__,
    static_folder=str(CARPETA_FRONTEND),
    static_url_path=""
)

app.config["DEMO_DOCUMENTAL_HABILITADA"] = False
# D03: respuesta predefinida para probar la integración.
app.config["EXTRACCION_SIMULADA_HABILITADA"] = True
# Selecciona explícitamente la extracción; la demo funciona sin cargar modelos.
app.config["MODO_EXTRACCION"] = os.environ.get("HRRG_MODO_EXTRACCION", "simulado")
# BETO es experimental y se habilita por separado cuando esté instalado.
app.config["BETO_HABILITADO"] = os.environ.get("HRRG_BETO_HABILITADO") == "1"
# ------------------------------------------------
# Formato común para los errores de la API.
# ------------------------------------------------

def respuesta_error(mensaje, estado, codigo):
    return jsonify({
        "ok": False,
        "mensaje": mensaje,
        "codigo": codigo
    }), estado


# ------------------------------------------------
# Almacenamiento local fuera del repositorio.
# ------------------------------------------------

CARPETA_DATOS = Path.home() / ".hrrg_pp2"
CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
BASE_USUARIOS = CARPETA_DATOS / "usuarios.db"
BASE_REGISTRO_DEMO = CARPETA_DATOS / "triage_demo.db"

inicializar_registro(BASE_REGISTRO_DEMO)


# -----------------------------------------------
# Registro de eventos del sistema.
# -----------------------------------------------

logger_sistema = logging.getLogger("hrrg.sistema")
logger_sistema.setLevel(logging.INFO)
logger_sistema.propagate = False

if not logger_sistema.handlers:
    manejador = RotatingFileHandler(
        CARPETA_DATOS / "sistema.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8"
    )

    manejador.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    ))

    logger_sistema.addHandler(manejador)

#----------------------------------------
# Clave privada para firmar las sesiones.
#----------------------------------------
ARCHIVO_CLAVE = CARPETA_DATOS / "session.key"

try:
    with ARCHIVO_CLAVE.open("x", encoding="utf-8") as archivo:
        archivo.write(secrets.token_hex(32))
except FileExistsError:
    pass

app.config["SECRET_KEY"] = ARCHIVO_CLAVE.read_text(
    encoding="utf-8"
).strip()
#--------------------------------------
# Configuración de la cookie de sesión.
#--------------------------------------

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

def inicializar_usuarios():
    conexion = sqlite3.connect(BASE_USUARIOS)

    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS profesionales (
                id INTEGER PRIMARY KEY,
                usuario TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1,
                rol TEXT NOT NULL DEFAULT 'sin_asignar'
            )
        """)

        columnas = {
            fila[1]
            for fila in conexion.execute(
                "PRAGMA table_info(profesionales)"
            ).fetchall()
        }

        if "rol" not in columnas:
            conexion.execute("""
                ALTER TABLE profesionales
                ADD COLUMN rol TEXT NOT NULL DEFAULT 'sin_asignar'
            """)

        conexion.commit()
    finally:
        conexion.close()


inicializar_usuarios()


#--------------------------------------------
# Ruta para iniciar sesión desde el frontend.
#--------------------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    if not request.is_json:
        return respuesta_error(
            mensaje="La solicitud debe estar en formato JSON.",
            estado=415,
            codigo="FORMATO_NO_SOPORTADO"
        )

    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return respuesta_error(
            mensaje="El JSON recibido debe ser un objeto válido.",
            estado=400,
            codigo="JSON_INVALIDO"
        )

    usuario = datos.get("usuario")
    password = datos.get("password")

    if not isinstance(usuario, str) or not isinstance(password, str):
        return respuesta_error(
            mensaje="Debés enviar usuario y contraseña como texto.",
            estado=400,
            codigo="TIPOS_INVALIDOS"
        )

    usuario = usuario.strip()

    if not usuario or not 1 <= len(password) <= 256:
        return respuesta_error(
            mensaje="Revisá el usuario y la contraseña.",
            estado=400,
            codigo="DATOS_INVALIDOS"
        )

    if not iniciar_sesion(BASE_USUARIOS, usuario, password):
        logger_sistema.warning("LOGIN_RECHAZADO")

        return respuesta_error(
            mensaje="Usuario o contraseña incorrectos.",
            estado=401,
            codigo="CREDENCIALES_INVALIDAS"
        )
    

    # Reemplazamos la sesión anterior.
    session.clear()
    session.permanent = True
    session["usuario"] = usuario
    logger_sistema.info("LOGIN_CORRECTO")

    return jsonify({
        "ok": True,
        "mensaje": "Sesión iniciada correctamente.",
        "usuario": usuario
    }), 200

#------------------------------------
# Ruta para cerrar la sesión.
#------------------------------------

@app.route("/api/logout", methods=["POST"])
def logout():
    if not request.is_json:
        return respuesta_error(
            mensaje="La solicitud debe estar en formato JSON.",
            estado=415,
            codigo="FORMATO_NO_SOPORTADO"
        )

    session.clear()
    logger_sistema.info("LOGOUT_PROCESADO")
    return jsonify({
        "ok": True,
        "mensaje": "Sesión cerrada correctamente."
    }), 200

# -----------------------------------------------
# Devuelve el profesional autenticado y el modo de extracción configurado.
# -----------------------------------------------

@app.route("/api/sesion", methods=["GET"])
def consultar_sesion():
    profesional = g.profesional

    respuesta = jsonify({
        "ok": True,
        "usuario": profesional["usuario"],
        "nombre": profesional["nombre"],
        "rol": profesional["rol"],
        "modo_extraccion": app.config["MODO_EXTRACCION"]
    })

    # Evita reutilizar información de sesión almacenada en caché.
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200

#-----------------------------------------------
# Control de acceso antes de ejecutar las rutas.
#-----------------------------------------------


@app.before_request
def verificar_acceso():
    if (
        request.endpoint in {"chat_api", "upload"}
        and not app.config["DEMO_DOCUMENTAL_HABILITADA"]
    ):
        return respuesta_error(
            "La demo documental está deshabilitada.",
            503,
            "DEMO_DESHABILITADA"
        )

# Estas rutas requieren una cuenta activa con un rol autorizado.
    rutas_protegidas = {
        "paciente_form",
        "chat_api",
        "upload",
        "consultar_sesion",
        "crear_episodio_demo",
        "consultar_episodio_demo",
        "extraer",
        "agregar_medicion_demo",
        "agregar_correccion_demo",
        "analizar_paciente",
        "listar_episodios_demo",
    }

    if request.endpoint not in rutas_protegidas:
        return None

    usuario = session.get("usuario")
    profesional = (
        obtener_profesional(BASE_USUARIOS, usuario)
        if usuario else None
    )

    if profesional is None:
        session.clear()
        return respuesta_error(
            "Debés iniciar sesión para continuar.",
            401,
            "SESION_REQUERIDA"
        )

    if profesional["rol"] not in {"enfermeria", "medico", "auditor"}:
        return respuesta_error(
            "Tu cuenta todavía no tiene un perfil asignado.",
            403,
            "ROL_NO_ASIGNADO"
        )

    g.profesional = profesional

    # El auditor solo puede usar las consultas autorizadas.
    if profesional["rol"] == "auditor":
        consultas_permitidas = {
            "consultar_sesion",
            "consultar_episodio_demo",
            "listar_episodios_demo",
        }

        if (
            request.endpoint not in consultas_permitidas
            or request.method not in {"GET", "HEAD"}
        ):
            return respuesta_error(
                "Tu perfil tiene acceso de solo lectura.",
                403,
                "PERMISO_DENEGADO"
            )

    return None
#---------------------------------------
# Alta de cuentas desde la terminal de administración.
#---------------------------------------


@app.cli.command("crear-profesional")
@click.option("--usuario", prompt="Usuario")
@click.option("--nombre", prompt="Nombre del profesional")
@click.option(
    "--password",
    prompt="Contraseña",
    hide_input=False,
    confirmation_prompt="Repetí la contraseña"
)
def crear_profesional(usuario, nombre, password):
    usuario = usuario.strip()
    nombre = nombre.strip()

    if not usuario or not nombre:
        raise click.ClickException(
            "El usuario y el nombre no pueden estar vacíos."
        )

    if not 12 <= len(password) <= 256:
        raise click.ClickException(
            "La contraseña debe tener entre 12 y 256 caracteres."
        )

    password_hash = generate_password_hash(password)

    conexion = sqlite3.connect(BASE_USUARIOS)

    try:
        conexion.execute(
            """
            INSERT INTO profesionales (usuario, nombre, password_hash)
            VALUES (?, ?, ?)
            """,
            (usuario, nombre, password_hash)
        )
        conexion.commit()

    except sqlite3.IntegrityError:
        conexion.rollback()
        raise click.ClickException("Ese usuario ya existe.")

    finally:
        conexion.close()

    click.echo("Cuenta creada correctamente.")
    # Cambio de contraseña desde la terminal de administración.
@app.cli.command("cambiar-password")
@click.option("--usuario", prompt="Usuario a modificar")
@click.option(
    "--password",
    prompt="Nueva contraseña",
    hide_input=False,
    confirmation_prompt="Repetí la nueva contraseña"
)
def cambiar_password(usuario, password):
    usuario = usuario.strip()

    if not usuario:
        raise click.ClickException("El usuario no puede estar vacío.")

    if not 12 <= len(password) <= 256:
        raise click.ClickException(
            "La contraseña debe tener entre 12 y 256 caracteres."
        )

    password_hash = generate_password_hash(password)
    conexion = sqlite3.connect(BASE_USUARIOS)

    try:
        resultado = conexion.execute(
            """
            UPDATE profesionales
            SET password_hash = ?
            WHERE usuario = ? AND activo = 1
            """,
            (password_hash, usuario)
        )

        if resultado.rowcount == 0:
            conexion.rollback()
            raise click.ClickException(
                "El usuario no existe o está desactivado."
            )

        conexion.commit()

    finally:
        conexion.close()

    click.echo("Contraseña actualizada correctamente.")


# -----------------------------------------------
# Crear un episodio ficticio para demostraciones.
# -----------------------------------------------

@app.route("/api/demo/episodios", methods=["POST"])
def crear_episodio_demo():
    if not request.is_json:
        return respuesta_error(
            "La solicitud debe estar en formato JSON.",
            415,
            "FORMATO_NO_SOPORTADO"
        )

    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return respuesta_error(
            "El JSON recibido debe ser un objeto válido.",
            400,
            "JSON_INVALIDO"
        )

        # El paciente es obligatorio. El código de episodio puede omitirse
    # para que el servidor lo genere.
    campos_permitidos = {"codigo_paciente", "codigo_episodio"}

    if (
        "codigo_paciente" not in datos
        or set(datos) - campos_permitidos
    ):
        return respuesta_error(
            "Enviá codigo_paciente y, opcionalmente, codigo_episodio.",
            400,
            "CAMPOS_INVALIDOS"
        )

    # Valida los identificadores recibidos antes de crear el episodio.
    for campo in datos:
        valor = datos[campo]
        if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 100:
            return respuesta_error(
                f"{campo} debe ser un texto de entre 1 y 100 caracteres.",
                422,
                "IDENTIFICADOR_INVALIDO"
            )
    # Genera el código una sola vez al crear una atención.
    # SQLite impide guardar dos episodios con el mismo código.
    # El formato también es compatible con la ruta /api/extraer.
    
    codigo_episodio = (
        datos["codigo_episodio"].strip()
        if "codigo_episodio" in datos
        else "EPI-" + secrets.token_hex(10).upper()
    )
    try:
        episodio = crear_episodio(
            ruta_base=BASE_REGISTRO_DEMO,
            codigo_episodio=codigo_episodio,
            codigo_paciente=datos["codigo_paciente"],
            profesional_usuario=session["usuario"]
        )
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorname == "SQLITE_CONSTRAINT_PRIMARYKEY":
            return respuesta_error(
                "Ya existe un episodio con ese código.",
                409,
                "EPISODIO_EXISTENTE"
            )

        logger_sistema.error("ERROR_INTEGRIDAD_CREAR_EPISODIO_DEMO")
        return respuesta_error(
            "No se pudo registrar el episodio.",
            500,
            "ERROR_REGISTRO"
        )
    except sqlite3.Error:
        logger_sistema.error("ERROR_BASE_CREAR_EPISODIO_DEMO")
        return respuesta_error(
            "No se pudo registrar el episodio.",
            500,
            "ERROR_REGISTRO"
        )

    return jsonify({
        "ok": True,
        "modo": "demo",
        "episodio": episodio
    }), 201

# -----------------------------------------------
# Consultar un episodio ficticio y su historial.
# -----------------------------------------------

@app.route(
    "/api/demo/episodios/<codigo_episodio>",
    methods=["GET"]
)

# Permite a médicos y enfermeros consultar episodios
# creados por otros profesionales, según su rol en el servidor.
def consultar_episodio_demo(codigo_episodio):
    try:
  
        episodio = obtener_episodio(
            ruta_base=BASE_REGISTRO_DEMO,
            codigo_episodio=codigo_episodio,
            profesional_usuario=g.profesional["usuario"],
            permitir_lectura_compartida=(
                g.profesional["rol"] in {"medico", "enfermeria", "auditor"}
            )
        )
    except (sqlite3.Error, ValueError):
        logger_sistema.error("ERROR_CONSULTAR_EPISODIO_DEMO")
        return respuesta_error(
            "No se pudo consultar el episodio.",
            500,
            "ERROR_REGISTRO"
        )

    if episodio is None:
        return respuesta_error(
            "El episodio no existe o no tenés permiso para consultarlo.",
            404,
            "EPISODIO_NO_ENCONTRADO"
        )

    respuesta = jsonify({
        "ok": True,
        "modo": "demo",
        "episodio": episodio
    })
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200

# ------------------------------------------------
# HOME / No hay un index.html definido, falta para el inicio de sesión.
# ------------------------------------------------

@app.route("/")
def inicio():
    return send_from_directory(
        str(CARPETA_FRONTEND),
        "index.html"
    )

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
        frec_cardiaca = request.form.get("frec_cardiaca")
        frec_respiratoria = request.form.get("frec_respiratoria")
        saturacion = request.form.get("saturacion")
        temperatura = request.form.get("temperatura")
        
        # Datos que vienen del formulario (4)
        glasgow = request.form.get("glasgow")
        dolor = request.form.get("dolor")
        localizacion_dolor = request.form.get("localizacion_dolor")

        # Datos que vienen del formulario (5)

                # Reunimos los datos recibidos en un diccionario.
        datos_paciente = {
            "codigo_episodio": codigo_episodio,
            "edad": edad,
            "sexo": sexo,
            "motivo_consulta": motivo_consulta,
            "tas": tas,
            "tad": tad,
            "frec_cardiaca": frec_cardiaca,
            "frec_respiratoria": frec_respiratoria,
            "saturacion": saturacion,
            "temperatura": temperatura,
            "glasgow": glasgow,
            "dolor": dolor,
            "localizacion_dolor": localizacion_dolor
        }

        # Guardamos una consulta por línea.
        with open("pacientes.jsonl", "a", encoding="utf-8") as archivo:
            archivo.write(
                json.dumps(datos_paciente, ensure_ascii=False) + "\n"
            )

        # Devolvemos una respuesta al frontend.
        return jsonify({
            "message": "Formulario recibido",
            "datos": datos_paciente
        })
    # Mostramos el formulario cuando se abre esta dirección.
    return send_from_directory(str(CARPETA_FRONTEND), "formulario.html")



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


@app.cli.command("asignar-rol")
@click.option("--usuario", prompt="Usuario")
@click.option(
    "--rol",
    type=click.Choice(["enfermeria", "medico", "auditor"]),
    prompt="Rol"
)


#---------------------------------------
#Función para utilizar diferentes roles de inicio de sesión
#---------------------------------------
def asignar_rol(usuario, rol):
    conexion = sqlite3.connect(BASE_USUARIOS)

    try:
        resultado = conexion.execute(
            """
            UPDATE profesionales
            SET rol = ?
            WHERE usuario = ?
            """,
            (rol, usuario.strip())
        )

        if resultado.rowcount == 0:
            raise click.ClickException("Ese usuario no existe.")

        conexion.commit()
    finally:
        conexion.close()

    click.echo(f"Perfil '{rol}' asignado correctamente.")

# ------------------------------------------------
# D03: extracción simulada con casos ficticios.
# ------------------------------------------------

@app.route("/api/extraer", methods=["POST"])
def extraer():
    # Comprueba el modo configurado antes de procesar la solicitud.
    modo = app.config["MODO_EXTRACCION"]
    if modo not in {"simulado", "ia"}:
        return respuesta_error("Modo de extracción no válido.", 503, "CONFIGURACION_INVALIDA")
    if modo == "simulado" and not app.config["EXTRACCION_SIMULADA_HABILITADA"]:
        return respuesta_error(
            "La extracción simulada está deshabilitada.",
            503,
            "EXTRACCION_DESHABILITADA"
        )

    if not request.is_json:
        return respuesta_error(
            "La solicitud debe estar en formato JSON.",
            415,
            "FORMATO_NO_SOPORTADO"
        )

    entrada = request.get_json(silent=True)

    if not isinstance(entrada, dict):
        return respuesta_error(
            "El JSON recibido debe ser un objeto válido.",
            400,
            "JSON_INVALIDO"
        )

    campos = {"codigo_paciente", "codigo_episodio", "texto"}

    if set(entrada) != campos:
        return respuesta_error(
            "Enviá únicamente codigo_paciente, codigo_episodio y texto.",
            422,
            "CAMPOS_INVALIDOS"
        )

    if any(not isinstance(entrada[campo], str) for campo in campos):
        return respuesta_error(
            "Todos los campos deben ser texto.",
            422,
            "TIPOS_INVALIDOS"
        )

    entrada = {
        campo: valor.strip()
        for campo, valor in entrada.items()
    }

    for campo in ("codigo_paciente", "codigo_episodio"):
        if not re.fullmatch(
            r"[A-Z]{2,4}-[A-Z0-9-]{3,20}",
            entrada[campo]
        ):
            return respuesta_error(
                f"El formato de {campo} no es válido.",
                422,
                "IDENTIFICADOR_INVALIDO"
            )

    if not 1 <= len(entrada["texto"]) <= 5000:
        return respuesta_error(
            "El relato debe tener entre 1 y 5000 caracteres.",
            422,
            "TEXTO_INVALIDO"
        )

    # El modo real usa la función de Tomás; nunca cae silenciosamente a la demo.
    if modo == "ia":
        return ejecutar_extraccion_ia(entrada)

    ruta_casos = CARPETA_BACKEND / "datos" / "casos_simulados.json"

    try:
        contenido = json.loads(
            ruta_casos.read_text(encoding="utf-8")
        )

        if not isinstance(contenido, dict):
            raise ValueError("Estructura de casos inválida")

        casos = contenido.get("casos")

        if not isinstance(casos, list):
            raise ValueError("Lista de casos inválida")

        casos_demo = []

        for caso in casos:
            if not isinstance(caso, dict):
                raise ValueError("Caso inválido")

            if caso.get("tipo") != "demo":
                continue

            if (
                not isinstance(caso.get("id"), str)
                or not caso["id"].strip()
                or not isinstance(caso.get("relato"), str)
                or not caso["relato"].strip()
                or not isinstance(caso.get("entrada"), dict)
            ):
                raise ValueError("Caso demo incompleto")

            casos_demo.append(caso)

        if not casos_demo:
            raise ValueError("No hay casos demo disponibles")

    except (OSError, UnicodeError, ValueError):
        logger_sistema.error("ERROR_CARGAR_CASOS_EXTRACCION")
        return respuesta_error(
            "No se pudieron cargar los casos simulados.",
            500,
            "ERROR_CASOS_SIMULADOS"
        )

    texto_normalizado = " ".join(entrada["texto"].split())

    coincidencias = [
        caso
        for caso in casos_demo
        if " ".join(caso["relato"].split()) == texto_normalizado
    ]

    if len(coincidencias) != 1:
        return respuesta_error(
            "Usá el relato exacto de un único caso de demostración.",
            422,
            "CASO_SIMULADO_NO_IDENTIFICADO"
        )

    caso = coincidencias[0]

    # Solo se toman campos del esquema de extracción.
    # Se excluyen mediciones, identificación y prioridad clínica.
    datos_caso = {
        campo: valor
        for campo, valor in caso["entrada"].items()
        if campo in ExtraccionIA.model_fields
    }

    try:
        datos = ExtraccionIA.model_validate(
            datos_caso
        ).model_dump(mode="json")

    except ValidationError:
        logger_sistema.error("ERROR_ESQUEMA_CASO_SIMULADO")
        return respuesta_error(
            "El caso simulado no cumple el esquema de extracción.",
            500,
            "CASO_SIMULADO_INVALIDO"
        )

    faltantes = [
        campo
        for campo in OBLIGATORIOS["ingreso"]
        if campo in ExtraccionIA.model_fields
        and datos[campo] is None
    ]

    respuesta = jsonify({
        "ok": True,
        "modo": "simulado",
        "caso_simulado_id": caso["id"],
        "codigo_paciente": entrada["codigo_paciente"],
        "codigo_episodio": entrada["codigo_episodio"],
        "version_esquema": "ExtraccionIA-v2",
        "modelo": None,
        "datos": datos,
        "campos_faltantes": faltantes,
        "advertencias": [
            "Respuesta simulada predefinida; no proviene de MedGemma.",
            "El caso puede incluir datos ficticios adicionales al relato.",
            "Los datos requieren revisión humana.",
            "Esta respuesta no asigna prioridad Manchester."
        ]
    })

    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200

# ------------------------------------------------
# Validar el formato y los campos de las solicitudes
# de mediciones y correcciones.
# ------------------------------------------------
def leer_entrada_historial(campos):
    if not request.is_json:
        return None, respuesta_error(
            "La solicitud debe estar en formato JSON.",
            415,
            "FORMATO_NO_SOPORTADO"
        )

    entrada = request.get_json(silent=True)

    if not isinstance(entrada, dict):
        return None, respuesta_error(
            "El JSON recibido debe ser un objeto válido.",
            400,
            "JSON_INVALIDO"
        )

    # Rechaza campos adicionales, incluido un autor enviado por el cliente.
    if set(entrada) != set(campos):
        return None, respuesta_error(
            "Los campos enviados no coinciden con los requeridos.",
            422,
            "CAMPOS_INVALIDOS"
        )

    return entrada, None


# ------------------------------------------------
# Registrar una nueva medición en un episodio.
# El profesional responsable se obtiene de la sesión.
# ------------------------------------------------
@app.route(
    "/api/demo/episodios/<codigo_episodio>/mediciones",
    methods=["POST"]
)

# Recibe el episodio de la URL y agrega un evento al historial.
def agregar_medicion_demo(codigo_episodio):
    entrada, error = leer_entrada_historial({"medido_en", "valores"})

    if error is not None:
        return error

    try:
        evento = registrar_medicion_demo(
            ruta_base=BASE_REGISTRO_DEMO,
            codigo_episodio=codigo_episodio,
            profesional_usuario=g.profesional["usuario"],
            medido_en=entrada["medido_en"],
            valores=entrada["valores"]
        )

    # No devuelve los valores recibidos ni detalles internos de Pydantic.
    except ValidationError:
        return respuesta_error(
            "Revisá los campos, rangos y coherencia de las mediciones.",
            422,
            "MEDICION_INVALIDA"
        )

    except ValueError:
        return respuesta_error(
            "Revisá la fecha, las mediciones y que el episodio exista.",
            422,
            "REGISTRO_INVALIDO"
        )

    except sqlite3.Error:
        logger_sistema.error("ERROR_GUARDAR_MEDICION_DEMO")
        return respuesta_error(
            "No se pudo guardar la medición.",
            500,
            "ERROR_REGISTRO"
        )

    # Confirma el guardado e incluye el ID para futuras correcciones.
    respuesta = jsonify({
        "ok": True,
        "modo": "demo",
        "evento": evento
    })
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 201

# ------------------------------------------------
# Corregir una medición mediante un nuevo evento.
# Conserva el original, el motivo y el autor de la corrección.
# ------------------------------------------------
@app.route(
    "/api/demo/episodios/<codigo_episodio>"
    "/mediciones/<int:evento_id>/correcciones",
    methods=["POST"]
)
def agregar_correccion_demo(codigo_episodio, evento_id):
    entrada, error = leer_entrada_historial({"cambios", "motivo"})

    if error is not None:
        return error

    try:
        evento = corregir_medicion_demo(
            ruta_base=BASE_REGISTRO_DEMO,
            codigo_episodio=codigo_episodio,
            evento_id=evento_id,
            profesional_usuario=g.profesional["usuario"],
            cambios=entrada["cambios"],
            motivo=entrada["motivo"]
        )

    # Rechaza valores que no cumplen el esquema de Darío.
    except ValidationError:
        return respuesta_error(
            "Los valores corregidos no cumplen el esquema de mediciones.",
            422,
            "MEDICION_INVALIDA"
        )

    # Incluye intentos sobre una versión que ya fue corregida.
    except ValueError:
        return respuesta_error(
            "Revisá los cambios, el motivo y que el registro "
            "sea la última versión de esa medición.",
            422,
            "CORRECCION_INVALIDA"
        )

    except sqlite3.Error:
        logger_sistema.error("ERROR_GUARDAR_CORRECCION_DEMO")
        return respuesta_error(
            "No se pudo guardar la corrección.",
            500,
            "ERROR_REGISTRO"
        )

    # Devuelve la nueva versión con su identificador y autor.
    respuesta = jsonify({
        "ok": True,
        "modo": "demo",
        "evento": evento
    })
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 201


# Ejecuta MedGemma solo cuando se solicita el modo IA.
# Las importaciones diferidas permiten iniciar la demo sin ChromaDB ni BETO.
def ejecutar_extraccion_ia(entrada):
    try:
        from src.extraccion import extraer_datos
        from src.extraccion import LLM_MODEL
    except Exception:
        logger_sistema.error("ERROR_INICIALIZAR_IA")
        return respuesta_error("No se pudo inicializar el servicio de IA.", 503, "IA_NO_DISPONIBLE")

    try:
        datos = ExtraccionIA.model_validate(
            extraer_datos(entrada["texto"], ExtraccionIA)
        ).model_dump(mode="json")
    except (ValueError, ValidationError):
        return respuesta_error("La IA devolvió datos incompatibles con el esquema.", 502, "SALIDA_IA_INVALIDA")
    except Exception:
        # No expone relatos ni detalles internos en la respuesta o en el log.
        logger_sistema.error("ERROR_SERVICIO_EXTRACCION_IA")
        return respuesta_error("No se pudo completar la extracción con IA.", 503, "IA_NO_DISPONIBLE")

    # Mantiene la estructura compartida, identificando el origen real.
    respuesta = jsonify({
        "ok": True, "modo": "ia", "caso_simulado_id": None,
        "codigo_paciente": entrada["codigo_paciente"],
        "codigo_episodio": entrada["codigo_episodio"],
        "version_esquema": "ExtraccionIA-v2", "modelo": LLM_MODEL,
        "datos": datos,
        "campos_faltantes": [campo for campo in OBLIGATORIOS["ingreso"]
                             if campo in ExtraccionIA.model_fields and datos.get(campo) is None],
        "advertencias": ["Datos extraídos por IA; requieren revisión profesional.",
                         "Esta respuesta no asigna prioridad Manchester."]
    })
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200


# Conserva la ruta experimental de BETO protegida por sesión y rol.
# Su respuesta conserva el formato de Tomás; falta acordar su contrato definitivo.
@app.route("/api/analizar", methods=["POST"])
def analizar_paciente():
    if not app.config["BETO_HABILITADO"]:
        return respuesta_error("BETO está deshabilitado en esta integración.", 503, "BETO_DESHABILITADO")
    entrada, error = leer_entrada_historial({"texto"})
    if error is not None:
        return error
    texto = entrada["texto"]
    if not isinstance(texto, str) or not 1 <= len(texto.strip()) <= 5000:
        return respuesta_error("El relato debe tener entre 1 y 5000 caracteres.", 422, "TEXTO_INVALIDO")
    try:
        from src.procesamiento_nlp import extraer_datos_planilla
        resultado = extraer_datos_planilla(texto.strip())
    except Exception:
        logger_sistema.error("ERROR_SERVICIO_BETO")
        return respuesta_error("BETO no está disponible o no pudo procesar el relato.", 503, "BETO_NO_DISPONIBLE")
    respuesta = jsonify(resultado)
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200

# Lista episodios ficticios para buscar casos y abrir su historial.
# La sesión y el rol se verifican en verificar_acceso().
@app.route("/api/demo/episodios", methods=["GET"])
def listar_episodios_demo():
    permitidos = {
        "codigo_paciente",
        "codigo_episodio",
        "limite",
        "desplazamiento"
    }

    # Rechaza parámetros desconocidos o repetidos.
    if (
        set(request.args) - permitidos
        or any(len(request.args.getlist(k)) != 1 for k in request.args)
    ):
        return respuesta_error(
            "Los parámetros de búsqueda no son válidos.",
            400,
            "PARAMETROS_INVALIDOS"
        )

    # Valida los códigos opcionales sin convertirlos a números.
    filtros = {}
    for campo in ("codigo_paciente", "codigo_episodio"):
        valor = request.args.get(campo)

        if valor is not None:
            valor = valor.strip()
            if not 1 <= len(valor) <= 100:
                return respuesta_error(
                    f"{campo} debe tener entre 1 y 100 caracteres.",
                    422,
                    "IDENTIFICADOR_INVALIDO"
                )

        filtros[campo] = valor

    # Limita la cantidad de episodios devueltos por solicitud.
    try:
        limite = int(request.args.get("limite", "50"))
        desplazamiento = int(request.args.get("desplazamiento", "0"))
    except ValueError:
        return respuesta_error(
            "El límite y el desplazamiento deben ser números enteros.",
            422,
            "PAGINACION_INVALIDA"
        )

    if not 1 <= limite <= 100 or desplazamiento < 0:
        return respuesta_error(
            "El límite debe estar entre 1 y 100 y el desplazamiento no puede ser negativo.",
            422,
            "PAGINACION_INVALIDA"
        )

    # Consulta la base compartida; no filtra por el creador del episodio.
    try:
        resultado = buscar_episodios(
            ruta_base=BASE_REGISTRO_DEMO,
            codigo_paciente=filtros["codigo_paciente"],
            codigo_episodio=filtros["codigo_episodio"],
            limite=limite,
            desplazamiento=desplazamiento
        )
    except sqlite3.Error:
        logger_sistema.error("ERROR_LISTAR_EPISODIOS_DEMO")
        return respuesta_error(
            "No se pudieron consultar los episodios.",
            500,
            "ERROR_REGISTRO"
        )

    # Devuelve los resultados sin permitir su almacenamiento en caché.
    respuesta = jsonify({
        "ok": True,
        "modo": "demo",
        "episodios": resultado["episodios"],
        "total": resultado["total"],
        "limite": limite,
        "desplazamiento": desplazamiento
    })
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200

if __name__ == "__main__":


    app.run(debug=True)
