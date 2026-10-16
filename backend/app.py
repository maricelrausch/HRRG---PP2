import os
import math
import time
import sqlite3
import click
import secrets
import logging
import ollama


import sys
from pathlib import Path

from flask import request, jsonify
from flask import Flask, json, request, jsonify, send_from_directory, session, g
from ollama import chat, embed
from PyPDF2 import PdfReader
from werkzeug.security import generate_password_hash
from pathlib import Path
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from src.auth import iniciar_sesion, profesional_activo, obtener_profesional
from src.registro import inicializar_registro, crear_episodio, obtener_episodio
import re
from pydantic import ValidationError
from src.esquemas import ExtraccionIA, OBLIGATORIOS
from src.modelo import responder
from src.extraccion import extraer_datos
from src.procesamiento_nlp import extraer_datos_planilla

RUTA_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(RUTA_SRC))


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
# Consultar el usuario de la sesión actual desde el frontend.
# -----------------------------------------------

@app.route("/api/sesion", methods=["GET"])
def consultar_sesion():
    profesional = g.profesional

    respuesta = jsonify({
        "ok": True,
        "usuario": profesional["usuario"],
        "nombre": profesional["nombre"],
        "rol": profesional["rol"]
    })

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

    rutas_protegidas = {
        "paciente_form",
        "chat_api",
        "upload",
        "consultar_sesion",
        "crear_episodio_demo",
        "consultar_episodio_demo",
        "extraer"
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
            "consultar_episodio_demo"
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

    campos = {"codigo_paciente", "codigo_episodio"}

    if set(datos) != campos:
        return respuesta_error(
            "Enviá únicamente codigo_paciente y codigo_episodio.",
            400,
            "CAMPOS_INVALIDOS"
        )

    for campo in campos:
        valor = datos[campo]
        if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 100:
            return respuesta_error(
                f"{campo} debe ser un texto de entre 1 y 100 caracteres.",
                422,
                "IDENTIFICADOR_INVALIDO"
            )

    try:
        episodio = crear_episodio(
            ruta_base=BASE_REGISTRO_DEMO,
            codigo_episodio=datos["codigo_episodio"],
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
def consultar_episodio_demo(codigo_episodio):
    try:
        episodio = obtener_episodio(
            ruta_base=BASE_REGISTRO_DEMO,
            codigo_episodio=codigo_episodio,
            profesional_usuario=session["usuario"]
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





# ------------------------------------------------
# Configuración y comunicación con Ollama.
# ------------------------------------------------

LLM_MODEL = "qwen2.5:0.5b"


def consultar_ollama(mensaje, historial=None):
    """
    Envía un mensaje a Ollama y devuelve su respuesta.
    El historial es opcional y contiene mensajes anteriores.
    """

    mensajes = [
        {
            "role": "system",
            "content": (
                "Sos un asistente conversacional en español. "
                "Respondé de forma clara y ordenada. "
                "No inventes datos que no te proporcionaron."
            )
        }
    ]

    if historial:
        mensajes.extend(historial)

    mensajes.append({
        "role": "user",
        "content": mensaje
    })

    try:
        respuesta = ollama.chat(
            model=LLM_MODEL,
            messages=mensajes,
            options={
                "temperature": 0.2,
                "num_predict": 300
            }
        )

        return respuesta["message"]["content"].strip()

    except ollama.ResponseError:
        logger_sistema.exception("ERROR_RESPUESTA_OLLAMA")
        return None

    except Exception:
        logger_sistema.exception("ERROR_CONEXION_OLLAMA")
        return None



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
    print(">>> ENTRO EN LA RUTA DE EXTRACCION")
    if not app.config["EXTRACCION_SIMULADA_HABILITADA"]:
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

    
    try:
        datos = extraer_datos(entrada["texto"], ExtraccionIA)

    except Exception:
        logger_sistema.exception("ERROR_EXTRACCION_MEDGEMMA")
        return respuesta_error(
            "No se pudieron extraer los datos con MedGemma.",
            500,
            "ERROR_EXTRACCION_IA"
        )

    faltantes = [
        campo
        for campo in OBLIGATORIOS["ingreso"]
        if campo in ExtraccionIA.model_fields
        and datos.get(campo) is None
    ]

    respuesta = jsonify({
        "ok": True,
        "modo": "ia",
        "caso_simulado_id": None,
        "codigo_paciente": entrada["codigo_paciente"],
        "codigo_episodio": entrada["codigo_episodio"],
        "version_esquema": "ExtraccionIA-v2",
        "modelo": "medgemma:4b",
        "datos": datos,
        "campos_faltantes": faltantes,
        "advertencias": [
            "Datos extraídos por IA; requieren revisión profesional.",
            "Los datos no mencionados pueden quedar sin informar.",
            "Esta respuesta no asigna prioridad Manchester."
        ]
    })

    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, 200




# ---
# MODELO MED GEMMA // CHAT
# ----



@app.route("/api/chat", methods=["POST"])
def chat_api():
    from flask import request, jsonify
    import time

    inicio = time.time()

    data = request.get_json(silent=True) or {}
    mensaje = data.get("message", "").strip()

    if not mensaje:
        return jsonify({
            "error": "El mensaje está vacío."
        }), 400

    try:
        respuesta = responder(mensaje)

        return jsonify({
            "answer": respuesta,
            "time": round(time.time() - inicio, 2),
            "steps": [
                "Búsqueda de información con RAG",
                "Generación de respuesta con MedGemma"
            ]
        })

    except Exception:
        app.logger.exception("Error al procesar la consulta")
        return jsonify({
            "error": "No se pudo procesar la consulta."
        }), 500


@app.route("/api/analizar", methods=["POST"])
def analizar_paciente():
    try:
        datos = request.get_json()

        if not datos or "texto" not in datos:
            return jsonify({"error": "Falta el texto médico"}), 400

        resultado = extraer_datos_planilla(datos["texto"])
        print("RESULTADO NLP:", resultado)
        return jsonify(resultado)

    except Exception as e:
        app.logger.exception("Error al extraer datos médicos")
        return jsonify({
            "error": "Error interno durante la extracción",
            "detalle": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)



