"""Reglas del hospital para el motor de sugerencia (propuesta Barby 28/10 · a revisar por el grupo).

Las carga la Jefatura de Guardia (perfil "jefatura") desde reglas.html. Cada regla dice:
"si se cumplen (todas | alguna de) estas condiciones, el color no puede ser menor que X",
con una explicación que se muestra en el "Por qué" de la sugerencia.

Ciclo de vida (en pantalla se muestran solo dos estados: ACTIVA e INACTIVA):
    borrador  -> recién creada, nunca activada; NO interviene (en pantalla: «Inactiva»).
    activa    -> la usa el motor desde la próxima sugerencia (no hace falta reiniciar nada).
    inactiva  -> estuvo activa y se apagó; se conserva para la trazabilidad.
[Dario 30/10] Editar una regla ya NO la apaga: conserva su estado y sube la versión (antes, guardar una
regla activa la pasaba a borrador aunque no se cambiara nada, y dejaba de intervenir sin que se notara).
Guardar sin cambios no crea una versión nueva.
Solo se pueden eliminar las reglas que nunca estuvieron activas; el resto se desactiva.
Cada cambio queda en reglas_eventos (quién, cuándo, qué versión y el contenido).

Rutas:
    GET  /api/reglas/campos            catálogo de datos y operadores (para armar el formulario)
    GET  /api/reglas/activas           reglas activas + si se usan las reglas de ejemplo (motor)
    GET  /api/reglas                   todas, con su historial (jefatura y auditor)
    POST /api/reglas                   crear borrador (jefatura)
    POST /api/reglas/<id>              editar (jefatura) -> vuelve a borrador
    POST /api/reglas/<id>/activar      (jefatura)
    POST /api/reglas/<id>/desactivar   (jefatura)
    POST /api/reglas/<id>/eliminar     solo borradores nunca activados (jefatura)
"""
import json
import shutil
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, session

from src.auth import obtener_profesional
from src.admin_usuarios import estado_acceso, requiere_cambio

bp = Blueprint("reglas_hospital", __name__)
logger = logging.getLogger("hrrg.sistema")

COLORES = ("ROJO", "NARANJA", "AMARILLO", "VERDE")
COMBINACIONES = ("todas", "alguna")
MAX_CONDICIONES = 8

# [Dario 29/10 · pedido de Francisco Navoni] Origen de cada regla. Las tres siguen fijando un piso
# (el color nunca baja de lo que dicen); el origen se muestra en la pantalla y en el «Por qué»
# para que el profesional sepa de dónde sale cada criterio y si ya está validado.
ORIGENES = {
    "manchester": "Sistema Manchester",
    "local": "Adaptación local HRRG",
    "provisoria": "Provisoria / en revisión",
}
ORIGEN_POR_DEFECTO = "provisoria"
MAX_VALIDADA_POR = 120
MAX_DISCRIMINADOR = 200

# [Dario 29/10 · D1] Grupos etarios (pedido de Francisco Navoni: "la edad debe ser una variable estructural").
# Se calculan solos a partir de la edad en años; una regla puede usar "Grupo etario es Lactante", etc.
# Mismos cortes en frontend/js/motor_reglas.js y evaluacion/reglas_seguridad.py (los tests los comparan).
GRUPOS_ETARIOS = [  # (nombre, edad mínima en años, edad máxima en años)
    ("Lactante", 0, 0),          # menos de 1 año
    ("Niño", 1, 11),
    ("Adolescente", 12, 17),
    ("Adulto", 18, 64),
    ("Adulto mayor", 65, 200),
]


def grupo_etario(edad):
    """Grupo etario para una edad en años (None si no hay edad válida)."""
    try:
        anios = _numero(edad)
    except (ValueError, TypeError):
        return None
    if anios < 0:
        return None
    for nombre, minimo, maximo in GRUPOS_ETARIOS:
        if anios < maximo + 1 and anios >= minimo:
            return nombre
    return None

# [Dario 29/10 · Etapa C] Tiempo objetivo máximo de atención por color (minutos).
# Por defecto, los de referencia del Sistema Manchester; la Jefatura los confirma o cambia en reglas.html
# y quedan en reglas_config (clave tiempos_objetivo). Los leen la pantalla En espera, la sala de espera
# y la API del hospital: es el ÚNICO lugar donde están.
TIEMPOS_POR_DEFECTO = {"ROJO": 0, "NARANJA": 10, "AMARILLO": 60, "VERDE": 120}
MAX_TIEMPO_MIN = 1440

# Datos que puede usar una regla (mismos nombres que la pantalla de Medición).
# El DNI y el relato NO están: una regla no puede depender de datos identificatorios.
CATEGORIAS = ["Dolor torácico", "Dolor abdominal", "Disnea", "Trauma", "Fiebre",
              "Cefalea", "Síntoma neurológico", "Alteración de conciencia", "Convulsiones",
              "Hemorragia", "Intoxicación", "Reacción alérgica", "Embarazo / obstétrico",
              "Salud mental", "Otro"]   # [D3] misma lista que src/esquemas.py (un test lo comprueba)
CAMPOS = {
    "edad": {"etiqueta": "Edad", "tipo": "num", "unidad": "años", "min": 0, "max": 120},
    "ta_sistolica": {"etiqueta": "TA sistólica", "tipo": "num", "unidad": "mmHg", "min": 30, "max": 300},
    "ta_diastolica": {"etiqueta": "TA diastólica", "tipo": "num", "unidad": "mmHg", "min": 10, "max": 200},
    "pam": {"etiqueta": "PAM (presión arterial media)", "tipo": "num", "unidad": "mmHg", "min": 10, "max": 250},
    "frecuencia_cardiaca": {"etiqueta": "Frecuencia cardíaca", "tipo": "num", "unidad": "lpm", "min": 10, "max": 300},
    "frecuencia_respiratoria": {"etiqueta": "Frecuencia respiratoria", "tipo": "num", "unidad": "rpm", "min": 1, "max": 80},
    "saturacion_o2": {"etiqueta": "Saturación de oxígeno (SpO₂)", "tipo": "num", "unidad": "%", "min": 30, "max": 100},
    "temperatura": {"etiqueta": "Temperatura", "tipo": "num", "unidad": "°C", "min": 25, "max": 45},
    "glucemia": {"etiqueta": "Glucemia capilar", "tipo": "num", "unidad": "mg/dL", "min": 10, "max": 1000},
    "glasgow": {"etiqueta": "Escala de Glasgow", "tipo": "num", "unidad": "pts", "min": 3, "max": 15},
    "dolor_intensidad": {"etiqueta": "Intensidad del dolor", "tipo": "num", "unidad": "/10", "min": 0, "max": 10},
    "estado_conciencia": {"etiqueta": "Nivel de conciencia", "tipo": "opcion",
                          "opciones": ["Alerta", "Responde a la voz", "Responde al dolor", "No responde"]},
    "motivo_categoria": {"etiqueta": "Categoría del motivo", "tipo": "opcion", "opciones": CATEGORIAS},
    "sexo": {"etiqueta": "Sexo", "tipo": "opcion", "opciones": ["Femenino", "Masculino", "No informado"]},
    "grupo_etario": {"etiqueta": "Grupo etario (se calcula con la edad)", "tipo": "opcion",
                     "opciones": [g[0] for g in GRUPOS_ETARIOS],
                     "ayuda": "Lactante: menos de 1 año · Niño: 1 a 11 · Adolescente: 12 a 17 · "
                              "Adulto: 18 a 64 · Adulto mayor: 65 o más"},
    "br_sangrado": {"etiqueta": "Bandera roja: sangrado evidente", "tipo": "bool"},
    "br_convulsion": {"etiqueta": "Bandera roja: convulsión activa", "tipo": "bool"},
    "br_disnea": {"etiqueta": "Bandera roja: dificultad para respirar", "tipo": "bool"},
    "br_trauma": {"etiqueta": "Bandera roja: mecanismo de trauma", "tipo": "bool"},
    "ant_diabetes": {"etiqueta": "Antecedente: diabetes", "tipo": "bool"},
    "ant_cardio": {"etiqueta": "Antecedente: cardiovascular", "tipo": "bool"},
    "ant_resp": {"etiqueta": "Antecedente: respiratorio", "tipo": "bool"},
    "ant_anticoag": {"etiqueta": "Antecedente: anticoagulación", "tipo": "bool"},
    "ant_inmuno": {"etiqueta": "Antecedente: inmunosupresión", "tipo": "bool"},
    "ant_embarazo": {"etiqueta": "Antecedente: embarazo", "tipo": "bool"},
    "ant_medicacion": {"etiqueta": "Antecedente: medicación crítica", "tipo": "bool"},
}
OPERADORES = {
    "num": {"<": "menor que", "<=": "menor o igual que", ">": "mayor que",
            ">=": "mayor o igual que", "=": "igual a", "!=": "distinto de"},
    "opcion": {"es": "es", "no_es": "no es"},
    "bool": {"si": "está marcado (sí)", "no": "no está marcado (no)"},
}


# ------------------------------------------------
# Base de datos
# ------------------------------------------------

def _ahora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _conectar():
    conexion = sqlite3.connect(current_app.config["BASE_REGLAS"])
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar_reglas(ruta_base):
    conexion = sqlite3.connect(ruta_base)
    try:
        with conexion:
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS reglas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE,
                    nombre TEXT NOT NULL,
                    explicacion TEXT NOT NULL,
                    color TEXT NOT NULL CHECK (color IN ('ROJO','NARANJA','AMARILLO','VERDE')),
                    combinacion TEXT NOT NULL CHECK (combinacion IN ('todas','alguna')),
                    condiciones_json TEXT NOT NULL,
                    estado TEXT NOT NULL CHECK (estado IN ('borrador','activa','inactiva')),
                    version INTEGER NOT NULL CHECK (version >= 1),
                    fue_activada INTEGER NOT NULL DEFAULT 0,
                    creada_por TEXT NOT NULL,
                    creada_en TEXT NOT NULL,
                    actualizada_por TEXT NOT NULL,
                    actualizada_en TEXT NOT NULL
                )
            """)
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS reglas_eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    regla_id INTEGER,
                    fecha TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    accion TEXT NOT NULL,
                    version INTEGER,
                    datos_json TEXT NOT NULL
                )
            """)
            conexion.execute("""
                CREATE TABLE IF NOT EXISTS reglas_config (
                    clave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL,
                    actualizado_por TEXT NOT NULL,
                    actualizado_en TEXT NOT NULL
                )
            """)
    finally:
        conexion.close()
    _migrar_columnas(ruta_base)


# Columnas agregadas después de la primera versión de la tabla (en orden de aparición).
COLUMNAS_NUEVAS = {
    "origen": f"TEXT NOT NULL DEFAULT '{ORIGEN_POR_DEFECTO}'",   # Etapa A
    "validada_por": "TEXT NOT NULL DEFAULT ''",                     # Etapa A
    "discriminador": "TEXT NOT NULL DEFAULT ''",                    # D1: matriz de Navoni
    "validada_en": "TEXT NOT NULL DEFAULT ''",                      # D1: fecha de validación
}


def _migrar_columnas(ruta_base):
    """[Dario 29/10] Agrega las columnas nuevas a una base que no las tiene.
    Solo AGREGA columnas (no borra ni cambia reglas). Las reglas que ya existían quedan como
    «provisoria», sin validar y sin discriminador. Si había reglas, antes se guarda una copia de la
    base (reglas_hospital.db.antes-<primera columna nueva>.bak) para poder volver atrás."""
    conexion = sqlite3.connect(ruta_base)
    try:
        columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(reglas)")}
        faltan = [c for c in COLUMNAS_NUEVAS if c not in columnas]
        if not faltan:
            return
        hay_reglas = conexion.execute("SELECT COUNT(*) FROM reglas").fetchone()[0] > 0
    finally:
        conexion.close()
    if hay_reglas:
        copia = Path(str(ruta_base) + f".antes-{faltan[0]}.bak")
        if not copia.exists():
            shutil.copy2(ruta_base, copia)
            logger.info("REGLAS_BACKUP_ANTES_DE_MIGRAR | %s", copia.name)
    conexion = sqlite3.connect(ruta_base)
    try:
        with conexion:
            for columna in faltan:
                conexion.execute(f"ALTER TABLE reglas ADD COLUMN {columna} {COLUMNAS_NUEVAS[columna]}")
    finally:
        conexion.close()
    logger.info("REGLAS_MIGRADAS | columnas agregadas: %s", ", ".join(faltan))


def cargar_semilla(ruta_base, ruta_semilla):
    """Carga las reglas de ejemplo de datos/reglas_semilla.json en la base, UNA sola vez cada tanda.

    Tanda 1 [Dario 29/10 · Etapa B]: las 9 reglas de seguridad del prototipo (origen «manchester»,
    sin validar), que antes estaban escritas en sugerencia.js.
      - Quedan ACTIVAS, porque son las mismas que ya intervenían: el color que ve enfermería no cambia
        (lo comprueba frontend/tests/semilla_equivalencia.test.js).
      - Se apaga la copia del código (usar_ejemplo = 0) para que no estén repetidas.
      - Si la Jefatura YA había apagado las reglas de ejemplo, se respeta: se cargan como BORRADOR.
    Tanda 2 [Dario 29/10 · D2]: las reglas que propone el mail de Francisco Navoni (fiebre y cefalea
      como adaptación local, fiebre en lactante, dolor torácico), con valores y colores A VALIDAR.
      Se cargan siempre como BORRADOR: se ven en la pantalla pero NO intervienen hasta que la
      Jefatura, con Enfermería y Guardia, complete los valores y las active.
    Cada regla del JSON dice a qué tanda pertenece ("tanda") y, si corresponde, "estado_inicial": "borrador".
    reglas_config.semilla_cargada guarda la última tanda cargada: si después la Jefatura edita,
    desactiva o elimina alguna, no se vuelve a cargar. Devuelve la cantidad de reglas cargadas."""
    conexion = sqlite3.connect(ruta_base)
    conexion.row_factory = sqlite3.Row
    try:
        fila = conexion.execute("SELECT valor FROM reglas_config WHERE clave = 'semilla_cargada'").fetchone()
        cargada = int(fila["valor"]) if fila and str(fila["valor"]).isdigit() else 0
        with open(ruta_semilla, encoding="utf-8") as archivo:
            semilla = json.load(archivo)
        version = int(semilla.get("version", 1))
        if cargada >= version:
            return 0
        estaban_en_uso = _usar_ejemplo(conexion)
        nuevas = []
        for i, datos in enumerate(semilla["reglas"], start=1):
            datos = dict(datos)
            tanda = int(datos.pop("tanda", 1))
            inicial = datos.pop("estado_inicial", None)
            if tanda <= cargada:
                continue
            regla, error = validar_regla(datos)
            if error:
                raise ValueError(f"Regla {i} de la semilla inválida: {error}")
            if inicial == "borrador" or not estaban_en_uso:
                estado, fue_activada = "borrador", 0
            else:
                estado, fue_activada = "activa", 1
            nuevas.append((regla, estado, fue_activada))
        ahora, usuario = _ahora(), "sistema"
        with conexion:
            for regla, estado, fue_activada in nuevas:
                cursor = conexion.execute(
                    """INSERT INTO reglas (nombre, explicacion, color, combinacion, condiciones_json, origen,
                           validada_por, discriminador, estado, version, fue_activada, creada_por, creada_en,
                           actualizada_por, actualizada_en)
                       VALUES (?, ?, ?, ?, ?, ?, '', ?, ?, 1, ?, ?, ?, ?, ?)""",
                    (regla["nombre"], regla["explicacion"], regla["color"], regla["combinacion"],
                     json.dumps(regla["condiciones"], ensure_ascii=False), regla["origen"],
                     regla["discriminador"], estado, fue_activada, usuario, ahora, usuario, ahora)
                )
                regla_id = cursor.lastrowid
                conexion.execute("UPDATE reglas SET codigo = ? WHERE id = ?", (f"R-{regla_id:03d}", regla_id))
                conexion.execute(
                    "INSERT INTO reglas_eventos (regla_id, fecha, usuario, accion, version, datos_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (regla_id, ahora, usuario, f"CARGADA DE EJEMPLO ({estado}, a validar)", 1,
                     json.dumps(regla, ensure_ascii=False))
                )
            ajustes = [("semilla_cargada", str(version))]
            if cargada == 0:
                ajustes.append(("usar_ejemplo", "0"))
            for clave, valor in ajustes:
                conexion.execute(
                    """INSERT INTO reglas_config (clave, valor, actualizado_por, actualizado_en) VALUES (?, ?, ?, ?)
                       ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor,
                           actualizado_por = excluded.actualizado_por, actualizado_en = excluded.actualizado_en""",
                    (clave, valor, usuario, ahora)
                )
            if cargada == 0:
                conexion.execute(
                    "INSERT INTO reglas_eventos (regla_id, fecha, usuario, accion, version, datos_json) VALUES (NULL, ?, ?, ?, NULL, ?)",
                    (ahora, usuario, "REGLAS DE EJEMPLO DEL CÓDIGO DESACTIVADAS (pasaron a la base)",
                     json.dumps({"reglas_cargadas": len(nuevas), "version_semilla": version}))
                )
    finally:
        conexion.close()
    logger.info("REGLAS_SEMILLA_CARGADAS | %d (tanda %d)", len(nuevas), version)
    return len(nuevas)


def validar_tiempos(datos):
    """Devuelve (tiempos, None) o (None, mensaje). Exige los 4 colores, minutos enteros entre 0 y 1440
    y que un color más urgente nunca tenga más tiempo que uno menos urgente."""
    if not isinstance(datos, dict) or set(datos) != set(COLORES):
        return None, "Enviá el tiempo de los 4 colores: ROJO, NARANJA, AMARILLO y VERDE."
    tiempos = {}
    for color in COLORES:
        valor = datos[color]
        try:
            numero = _numero(valor)
        except (ValueError, TypeError):
            return None, f"El tiempo de {color} tiene que ser un número de minutos."
        if not numero.is_integer() or not 0 <= numero <= MAX_TIEMPO_MIN:
            return None, f"El tiempo de {color} tiene que ser un número entero de minutos entre 0 y {MAX_TIEMPO_MIN}."
        tiempos[color] = int(numero)
    for mas, menos in zip(COLORES, COLORES[1:]):
        if tiempos[mas] > tiempos[menos]:
            return None, f"{mas} no puede tener más tiempo que {menos}."
    return tiempos, None


def leer_tiempos(ruta_base):
    """Tiempos objetivo vigentes. NUNCA falla: si no hay base, no están cargados o algo está mal,
    devuelve los de referencia Manchester (así la sala de espera nunca se queda sin tiempos)."""
    if ruta_base and Path(ruta_base).exists():
        try:
            conexion = sqlite3.connect(ruta_base)
            try:
                fila = conexion.execute("SELECT valor FROM reglas_config WHERE clave = 'tiempos_objetivo'").fetchone()
            finally:
                conexion.close()
            if fila:
                tiempos, error = validar_tiempos(json.loads(fila[0]))
                if not error:
                    return tiempos
        except (sqlite3.Error, ValueError, TypeError):
            logger.warning("TIEMPOS_OBJETIVO_ILEGIBLES | se usan los de referencia")
    return dict(TIEMPOS_POR_DEFECTO)


def _usar_ejemplo(conexion):
    # [30/10] Ya no hay interruptor en la pantalla: solo se lee para respetar bases viejas al cargar la semilla.
    fila = conexion.execute("SELECT valor FROM reglas_config WHERE clave = 'usar_ejemplo'").fetchone()
    return True if fila is None else fila["valor"] == "1"


def _evento(conexion, regla_id, accion, version, datos):
    conexion.execute(
        "INSERT INTO reglas_eventos (regla_id, fecha, usuario, accion, version, datos_json) VALUES (?, ?, ?, ?, ?, ?)",
        (regla_id, _ahora(), g.profesional["usuario"], accion, version,
         json.dumps(datos, ensure_ascii=False))
    )


def _a_dict(fila, eventos=None):
    regla = {
        "id": fila["id"],
        "codigo": fila["codigo"],
        "nombre": fila["nombre"],
        "explicacion": fila["explicacion"],
        "color": fila["color"],
        "combinacion": fila["combinacion"],
        "condiciones": json.loads(fila["condiciones_json"]),
        "origen": fila["origen"],
        "validada_por": fila["validada_por"],
        "validada_en": fila["validada_en"],
        "discriminador": fila["discriminador"],
        "estado": fila["estado"],
        "version": fila["version"],
        "fue_activada": bool(fila["fue_activada"]),
        "creada_por": fila["creada_por"],
        "creada_en": fila["creada_en"],
        "actualizada_por": fila["actualizada_por"],
        "actualizada_en": fila["actualizada_en"],
    }
    if eventos is not None:
        regla["historial"] = eventos
    return regla


# ------------------------------------------------
# Validación
# ------------------------------------------------

def _numero(valor):
    if isinstance(valor, bool):
        raise ValueError
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        return float(valor.strip().replace(",", "."))
    raise ValueError


def validar_regla(datos):
    """Devuelve (regla_normalizada, None) o (None, mensaje_de_error)."""
    if not isinstance(datos, dict):
        return None, "Enviá los datos de la regla."
    permitidos = {"nombre", "explicacion", "color", "combinacion", "condiciones", "origen", "validada_por",
                  "discriminador"}
    if set(datos) - permitidos:
        return None, "Hay campos que no corresponden a una regla."

    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not 3 <= len(nombre.strip()) <= 80:
        return None, "El nombre tiene que tener entre 3 y 80 caracteres."
    explicacion = datos.get("explicacion")
    if not isinstance(explicacion, str) or not 5 <= len(explicacion.strip()) <= 300:
        return None, "La explicación (lo que se muestra en el «Por qué») tiene que tener entre 5 y 300 caracteres."
    if datos.get("color") not in COLORES:
        return None, "Elegí el color: ROJO, NARANJA, AMARILLO o VERDE."
    if datos.get("combinacion") not in COMBINACIONES:
        return None, "Elegí si se tienen que cumplir todas las condiciones o alguna."
    # Si no se manda el origen (versiones anteriores de la pantalla), queda como provisoria.
    origen = datos.get("origen", ORIGEN_POR_DEFECTO)
    if origen not in ORIGENES:
        return None, "Elegí el origen de la regla: Manchester, adaptación local HRRG o provisoria."
    validada_por = datos.get("validada_por", "")
    if validada_por is None:
        validada_por = ""
    if not isinstance(validada_por, str) or len(validada_por.strip()) > MAX_VALIDADA_POR:
        return None, f"«Validada por» admite hasta {MAX_VALIDADA_POR} caracteres."
    # Discriminador Manchester o criterio clínico que respalda la regla (texto para la matriz; no se evalúa).
    discriminador = datos.get("discriminador", "")
    if discriminador is None:
        discriminador = ""
    if not isinstance(discriminador, str) or len(discriminador.strip()) > MAX_DISCRIMINADOR:
        return None, f"El discriminador admite hasta {MAX_DISCRIMINADOR} caracteres."

    condiciones = datos.get("condiciones")
    if not isinstance(condiciones, list) or not 1 <= len(condiciones) <= MAX_CONDICIONES:
        return None, f"La regla necesita entre 1 y {MAX_CONDICIONES} condiciones."

    limpias = []
    for i, cond in enumerate(condiciones, start=1):
        if not isinstance(cond, dict) or set(cond) - {"campo", "operador", "valor"}:
            return None, f"La condición {i} no es válida."
        campo = cond.get("campo")
        if campo not in CAMPOS:
            return None, f"Condición {i}: elegí un dato de la lista."
        info = CAMPOS[campo]
        operador = cond.get("operador")
        if operador not in OPERADORES[info["tipo"]]:
            return None, f"Condición {i}: el operador no corresponde a «{info['etiqueta']}»."
        if info["tipo"] == "num":
            try:
                valor = _numero(cond.get("valor"))
            except (ValueError, TypeError):
                return None, f"Condición {i}: escribí un número para «{info['etiqueta']}»."
            if not info["min"] <= valor <= info["max"]:
                return None, (f"Condición {i}: «{info['etiqueta']}» tiene que estar entre "
                              f"{info['min']:g} y {info['max']:g} {info['unidad']}.")
            valor = int(valor) if valor.is_integer() else valor
        elif info["tipo"] == "opcion":
            valor = cond.get("valor")
            if valor not in info["opciones"]:
                return None, f"Condición {i}: elegí una opción de «{info['etiqueta']}»."
        else:
            valor = None
        limpias.append({"campo": campo, "operador": operador, "valor": valor})

    return {
        "nombre": nombre.strip(),
        "explicacion": explicacion.strip(),
        "color": datos["color"],
        "combinacion": datos["combinacion"],
        "condiciones": limpias,
        "origen": origen,
        "validada_por": validada_por.strip(),
        "discriminador": discriminador.strip(),
    }, None


def _validada_en(regla, anterior=None):
    """Fecha de validación: se pone sola cuando se carga «Validada por»; si no cambia quién validó,
    se conserva la fecha anterior; si se borra, queda vacía."""
    if not regla["validada_por"]:
        return ""
    if anterior is not None and anterior["validada_por"] == regla["validada_por"] and anterior["validada_en"]:
        return anterior["validada_en"]
    return _ahora()


# ------------------------------------------------
# Control de acceso
# ------------------------------------------------

def _error(mensaje, estado, codigo):
    respuesta = jsonify({"ok": False, "mensaje": mensaje, "codigo": codigo})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta, estado


def _ok(**datos):
    respuesta = jsonify({"ok": True, **datos})
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


LECTURA_MOTOR = {"enfermeria", "medico", "auditor", "jefatura"}
LECTURA_COMPLETA = {"auditor", "jefatura"}


@bp.before_request
def exigir_sesion():
    # Escrituras solo en JSON (defensa CSRF, igual que la administración de cuentas).
    if request.method == "POST" and not request.is_json:
        return _error("La solicitud debe estar en formato JSON.", 415, "FORMATO_NO_SOPORTADO")

    base = current_app.config["BASE_USUARIOS"]
    usuario = session.get("usuario")
    profesional = obtener_profesional(base, usuario) if usuario else None
    cuenta = estado_acceso(base, usuario) if usuario else None
    if profesional is None or cuenta is None or cuenta["bloqueada"]:
        session.clear()
        return _error("Debés iniciar sesión para continuar.", 401, "SESION_REQUERIDA")
    if requiere_cambio(cuenta):
        return _error("Tenés que cambiar tu contraseña antes de continuar.", 403, "CAMBIO_PASSWORD_REQUERIDO")
    g.profesional = profesional

    rol = profesional["rol"]
    endpoint = request.endpoint or ""
    if endpoint in {"reglas_hospital.campos", "reglas_hospital.activas", "reglas_hospital.tiempos"}:
        permitido = rol in LECTURA_MOTOR
    elif request.method == "GET":
        permitido = rol in LECTURA_COMPLETA
    else:
        permitido = rol == "jefatura"
    if not permitido:
        return _error("Tu perfil no puede hacer esto. Las reglas las administra la Jefatura de Guardia.",
                      403, "PERMISO_DENEGADO")
    return None


# ------------------------------------------------
# Rutas
# ------------------------------------------------

@bp.get("/api/reglas/campos")
def campos():
    # Los operadores van como lista de pares para conservar el orden (jsonify ordena las claves).
    operadores = {tipo: [[k, t] for k, t in ops.items()] for tipo, ops in OPERADORES.items()}
    return _ok(campos=CAMPOS, operadores=operadores, colores=list(COLORES), max_condiciones=MAX_CONDICIONES,
               origenes=[[k, t] for k, t in ORIGENES.items()])


@bp.get("/api/reglas/activas")
def activas():
    conexion = _conectar()
    try:
        filas = conexion.execute(
            "SELECT * FROM reglas WHERE estado = 'activa' ORDER BY id"
        ).fetchall()
    finally:
        conexion.close()
    return _ok(reglas=[_a_dict(f) for f in filas])


@bp.get("/api/reglas")
def listar():
    conexion = _conectar()
    try:
        filas = conexion.execute("SELECT * FROM reglas ORDER BY id").fetchall()
        eventos = {}
        for ev in conexion.execute(
            "SELECT regla_id, fecha, usuario, accion, version FROM reglas_eventos ORDER BY id"
        ):
            eventos.setdefault(ev["regla_id"], []).append(
                {"fecha": ev["fecha"], "usuario": ev["usuario"], "accion": ev["accion"], "version": ev["version"]}
            )
    finally:
        conexion.close()
    # [30/10] historial_general: cambios que no son de una regla (tiempos por color, carga de ejemplos…).
    return _ok(reglas=[_a_dict(f, eventos.get(f["id"], [])) for f in filas],
               historial_general=eventos.get(None, []))


@bp.post("/api/reglas")
def crear():
    regla, error = validar_regla(request.get_json(silent=True))
    if error:
        return _error(error, 422, "REGLA_INVALIDA")
    ahora, usuario = _ahora(), g.profesional["usuario"]
    conexion = _conectar()
    try:
        with conexion:
            cursor = conexion.execute(
                """INSERT INTO reglas (nombre, explicacion, color, combinacion, condiciones_json, origen,
                       validada_por, validada_en, discriminador, estado, version, creada_por, creada_en,
                       actualizada_por, actualizada_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'borrador', 1, ?, ?, ?, ?)""",
                (regla["nombre"], regla["explicacion"], regla["color"], regla["combinacion"],
                 json.dumps(regla["condiciones"], ensure_ascii=False), regla["origen"], regla["validada_por"],
                 _validada_en(regla), regla["discriminador"], usuario, ahora, usuario, ahora)
            )
            regla_id = cursor.lastrowid
            conexion.execute("UPDATE reglas SET codigo = ? WHERE id = ?", (f"R-{regla_id:03d}", regla_id))
            _evento(conexion, regla_id, "CREADA (borrador)", 1, regla)
            fila = conexion.execute("SELECT * FROM reglas WHERE id = ?", (regla_id,)).fetchone()
    finally:
        conexion.close()
    logger.info("REGLA_CREADA | %s | R-%03d", usuario, regla_id)
    return _ok(regla=_a_dict(fila)), 201


def _buscar(conexion, regla_id):
    return conexion.execute("SELECT * FROM reglas WHERE id = ?", (regla_id,)).fetchone()


@bp.post("/api/reglas/<int:regla_id>")
def editar(regla_id):
    regla, error = validar_regla(request.get_json(silent=True))
    if error:
        return _error(error, 422, "REGLA_INVALIDA")
    conexion = _conectar()
    try:
        with conexion:
            fila = _buscar(conexion, regla_id)
            if fila is None:
                return _error("La regla no existe.", 404, "REGLA_NO_ENCONTRADA")
            # Guardar sin cambios: no hay versión nueva ni evento (y la regla sigue como estaba).
            actual = {"nombre": fila["nombre"], "explicacion": fila["explicacion"], "color": fila["color"],
                      "combinacion": fila["combinacion"], "condiciones": json.loads(fila["condiciones_json"]),
                      "origen": fila["origen"], "validada_por": fila["validada_por"],
                      "discriminador": fila["discriminador"]}
            if actual == regla:
                return _ok(regla=_a_dict(fila), sin_cambios=True)
            version = fila["version"] + 1
            conexion.execute(
                """UPDATE reglas SET nombre = ?, explicacion = ?, color = ?, combinacion = ?, condiciones_json = ?,
                       origen = ?, validada_por = ?, validada_en = ?, discriminador = ?,
                       version = ?, actualizada_por = ?, actualizada_en = ? WHERE id = ?""",
                (regla["nombre"], regla["explicacion"], regla["color"], regla["combinacion"],
                 json.dumps(regla["condiciones"], ensure_ascii=False), regla["origen"], regla["validada_por"],
                 _validada_en(regla, fila), regla["discriminador"],
                 version, g.profesional["usuario"], _ahora(), regla_id)
            )
            accion = "EDITADA (sigue activa)" if fila["estado"] == "activa" else "EDITADA"
            _evento(conexion, regla_id, accion, version, regla)
            fila = _buscar(conexion, regla_id)
    finally:
        conexion.close()
    logger.info("REGLA_EDITADA | %s | R-%03d v%d", g.profesional["usuario"], regla_id, version)
    return _ok(regla=_a_dict(fila))


def _cambiar_estado(regla_id, nuevo, accion):
    conexion = _conectar()
    try:
        with conexion:
            fila = _buscar(conexion, regla_id)
            if fila is None:
                return _error("La regla no existe.", 404, "REGLA_NO_ENCONTRADA")
            if fila["estado"] == nuevo:
                return _error("La regla ya está en ese estado.", 409, "SIN_CAMBIOS")
            conexion.execute(
                "UPDATE reglas SET estado = ?, fue_activada = MAX(fue_activada, ?), actualizada_por = ?, "
                "actualizada_en = ? WHERE id = ?",
                (nuevo, 1 if nuevo == "activa" else 0, g.profesional["usuario"], _ahora(), regla_id)
            )
            _evento(conexion, regla_id, accion, fila["version"], {"estado_anterior": fila["estado"]})
            fila = _buscar(conexion, regla_id)
    finally:
        conexion.close()
    logger.info("REGLA_%s | %s | R-%03d", nuevo.upper(), g.profesional["usuario"], regla_id)
    return _ok(regla=_a_dict(fila))


@bp.post("/api/reglas/<int:regla_id>/activar")
def activar(regla_id):
    return _cambiar_estado(regla_id, "activa", "ACTIVADA")


@bp.post("/api/reglas/<int:regla_id>/desactivar")
def desactivar(regla_id):
    return _cambiar_estado(regla_id, "inactiva", "DESACTIVADA")


@bp.post("/api/reglas/<int:regla_id>/eliminar")
def eliminar(regla_id):
    conexion = _conectar()
    try:
        with conexion:
            fila = _buscar(conexion, regla_id)
            if fila is None:
                return _error("La regla no existe.", 404, "REGLA_NO_ENCONTRADA")
            if fila["estado"] != "borrador" or fila["fue_activada"]:
                return _error("Solo se pueden eliminar borradores que nunca se activaron. "
                              "Las demás se desactivan, para que quede el registro.", 409, "NO_ELIMINABLE")
            conexion.execute("DELETE FROM reglas WHERE id = ?", (regla_id,))
            _evento(conexion, regla_id, f"ELIMINADA ({fila['codigo']}, borrador)", fila["version"],
                    {"nombre": fila["nombre"]})
    finally:
        conexion.close()
    logger.info("REGLA_ELIMINADA | %s | R-%03d", g.profesional["usuario"], regla_id)
    return _ok()


@bp.get("/api/reglas/tiempos")
def tiempos():
    conexion = _conectar()
    try:
        fila = conexion.execute(
            "SELECT actualizado_por, actualizado_en FROM reglas_config WHERE clave = 'tiempos_objetivo'"
        ).fetchone()
    finally:
        conexion.close()
    return _ok(tiempos=leer_tiempos(current_app.config["BASE_REGLAS"]), por_defecto=TIEMPOS_POR_DEFECTO,
               confirmados=fila is not None,
               actualizado=None if fila is None else {"por": fila["actualizado_por"], "en": fila["actualizado_en"]})


@bp.post("/api/reglas/tiempos")
def guardar_tiempos():
    tiempos_nuevos, error = validar_tiempos(request.get_json(silent=True))
    if error:
        return _error(error, 422, "TIEMPOS_INVALIDOS")
    anteriores = leer_tiempos(current_app.config["BASE_REGLAS"])
    conexion = _conectar()
    try:
        with conexion:
            conexion.execute(
                """INSERT INTO reglas_config (clave, valor, actualizado_por, actualizado_en)
                   VALUES ('tiempos_objetivo', ?, ?, ?)
                   ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor,
                       actualizado_por = excluded.actualizado_por, actualizado_en = excluded.actualizado_en""",
                (json.dumps(tiempos_nuevos), g.profesional["usuario"], _ahora())
            )
            _evento(conexion, None, "TIEMPOS OBJETIVO GUARDADOS", None,
                    {"anteriores": anteriores, "nuevos": tiempos_nuevos})
    finally:
        conexion.close()
    logger.info("TIEMPOS_OBJETIVO | %s | %s", g.profesional["usuario"], tiempos_nuevos)
    return _ok(tiempos=tiempos_nuevos)

