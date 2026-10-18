"""backend/ia_medgemma.py · Conexión con MedGemma vía Ollama.

Tres funciones para las rutas de Flask:
  extraer(texto)                     -> datos estructurados del relato (pantalla 1 -> 2)
  sugerir(datos)                     -> color Manchester sugerido + motivos (pantalla 3)
  consultar(pregunta, datos, color)  -> respuesta del chat "Consultar a la IA"
y disponible() para el indicador de estado.

Requiere: Ollama corriendo (ollama serve) y el modelo bajado (ollama pull medgemma:4b).
"""
import json
import os
import re
import unicodedata

import ollama

MODELO = os.environ.get("MEDGEMMA_MODELO", "medgemma:4b")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
NIVELES = {"ROJO": 0, "NARANJA": 1, "AMARILLO": 2, "VERDE": 3, "AZUL": 4}

CATEGORIAS = ["Dolor torácico", "Dolor abdominal", "Disnea", "Trauma", "Fiebre",
              "Cefalea", "Síntoma neurológico", "Otro"]
ANTECEDENTES = ["ant_diabetes", "ant_cardio", "ant_resp", "ant_anticoag",
                "ant_inmuno", "ant_embarazo", "ant_medicacion"]

_cli = ollama.Client(host=HOST, timeout=180)


# ---------------------------------------------------------------- utilidades
def _num():
    return {"type": ["number", "null"]}


def _txt():
    return {"type": ["string", "null"]}


def _chat(system, user, schema=None):
    """Llama al modelo. Con schema, Ollama fuerza la salida a ese JSON."""
    r = _cli.chat(
        model=MODELO,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        format=schema,
        options={"temperature": 0},
    )
    return r.message.content


def _chat_json(system, user, schema):
    """Igual que _chat pero devuelve dict; reintenta una vez si el JSON viene roto."""
    ultimo_error = None
    for _ in range(2):
        try:
            return json.loads(_chat(system, user, schema))
        except json.JSONDecodeError as e:
            ultimo_error = e
    raise ValueError(f"MedGemma devolvió JSON inválido: {ultimo_error}")


def _rango(v, lo, hi):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


def disponible():
    """True si Ollama responde y el modelo está instalado."""
    try:
        nombres = [m.model for m in _cli.list().models]
    except Exception:
        return False
    base = MODELO.split(":")[0]
    return any(n == MODELO or n.split(":")[0] == base for n in nombres)


# ---------------------------------------------------------------- 1. extracción
SCHEMA_EXTRAER = {
    "type": "object",
    "properties": {
        "edad": _num(),
        "sexo": {"type": "string", "enum": ["Femenino", "Masculino", "No informado"]},
        "motivo_categoria": {"type": "string", "enum": CATEGORIAS},
        "motivo_consulta": _txt(),
        "localizacion_dolor": _txt(),
        "sintomas_asociados": _txt(),
        "tiempo_evolucion_valor": _num(),
        "tiempo_evolucion_unidad": {"type": "string",
                                    "enum": ["minutos", "horas", "días", "No informado"]},
        "tas": _num(), "tad": _num(), "pam": _num(),
        "frec_cardiaca": _num(), "frec_respiratoria": _num(),
        "saturacion": _num(), "temperatura": _num(), "glasgow": _num(),
        "dolor": _num(),
        **{k: {"type": "boolean"} for k in ANTECEDENTES},
    },
    "required": ["edad", "sexo", "motivo_categoria", "motivo_consulta", "localizacion_dolor",
                 "sintomas_asociados", "tiempo_evolucion_valor", "tiempo_evolucion_unidad",
                 "tas", "tad", "pam", "frec_cardiaca", "frec_respiratoria", "saturacion",
                 "temperatura", "glasgow", "dolor", *ANTECEDENTES],
}

PROMPT_EXTRAER = """Sos un asistente de enfermería de guardia. Leés el relato de ingreso de un paciente
y extraés SOLO los datos que aparecen escritos. Reglas:
- Si un dato no aparece, usá null (o "No informado" en sexo y unidad de tiempo). No inventes ni estimes.
- "Mujer", "señora", "paciente femenina" -> Femenino. "Hombre", "señor", "varón" -> Masculino.
- edad: número entero de años.
- dolor: intensidad 0 a 10 exactamente como la dice el relato (ej. "8/10" -> 8).
- tas/tad: presión sistólica/diastólica (ej. "TA 130/80" -> tas 130, tad 80).
- temperatura en °C, saturacion en %, frecuencias por minuto.
- motivo_consulta: resumen breve (máx. 10 palabras). localizacion_dolor: dónde le duele.
- sintomas_asociados: otros síntomas que refiere, separados por coma.
- Antecedentes (ant_*): true solo si el relato lo dice; si no, false.
  ant_cardio=cardiovascular, ant_resp=respiratorio, ant_anticoag=anticoagulado,
  ant_inmuno=inmunosuprimido, ant_medicacion=medicación crítica.
Respondé únicamente con el JSON."""

LIMITES = {"edad": (0, 120), "tiempo_evolucion_valor": (0, 10000),
           "tas": (40, 300), "tad": (20, 200), "pam": (30, 250),
           "frec_cardiaca": (20, 250), "frec_respiratoria": (4, 60),
           "saturacion": (50, 100), "temperatura": (30, 45),
           "glasgow": (3, 15), "dolor": (0, 10)}
ENTEROS = {"edad", "tas", "tad", "pam", "frec_cardiaca", "frec_respiratoria",
           "saturacion", "glasgow", "dolor", "tiempo_evolucion_valor"}


def _norm(s):
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


# Palabras del relato que definen la categoría (orden = prioridad). Corrigen al modelo cuando se confunde.
CLAVES_CATEGORIA = [
    ("Dolor torácico", r"\b(pecho|torax|toracic\w*|precordial\w*)\b"),
    ("Cefalea", r"\b(cabeza|cefalea|migran\w*|jaqueca)\b"),
    ("Dolor abdominal", r"\b(panza|abdomen|abdominal|estomago|barriga|epigastr\w*|vientre)\b"),
    ("Disnea", r"(falta de aire|\bahog\w*|\bdisnea\b|no puede respirar|cuesta respirar)"),
    ("Trauma", r"\b(golpe\w*|caida|cayo|choque|accidente|fractur\w*|torc\w*|herida|corte)\b"),
    ("Síntoma neurológico", r"(convulsi\w*|desmay\w*|paralisis|no puede hablar|hormigueo|perdida de fuerza)"),
    ("Fiebre", r"\b(fiebre|afiebrad\w*|febril)\b"),
]
LOCALIZACION = {"Dolor torácico": "Pecho", "Cefalea": "Cabeza", "Dolor abdominal": "Abdomen"}


def _anclar(d, texto):
    """Descarta lo que el modelo inventó: números que no están en el relato,
    categoría y localización que contradicen las palabras del relato."""
    t = _norm(texto)
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", t)]
    for k in LIMITES:
        v = d.get(k)
        if v is not None and not any(abs(float(v) - n) < 0.05 for n in nums):
            d[k] = None                                   # número que no aparece en el relato

    halladas = [c for c, rx in CLAVES_CATEGORIA if re.search(rx, t)]
    if halladas and d.get("motivo_categoria") not in halladas:
        d["motivo_categoria"] = halladas[0]

    loc = d.get("localizacion_dolor")
    if loc:
        palabras = [w for w in re.findall(r"[a-z]+", _norm(loc)) if len(w) > 3]
        sinonimo = LOCALIZACION.get(d["motivo_categoria"]) == loc and d["motivo_categoria"] in halladas
        if not sinonimo and not any(w in t for w in palabras):
            d["localizacion_dolor"] = None
    if not d.get("localizacion_dolor") and d.get("motivo_categoria") in halladas:
        d["localizacion_dolor"] = LOCALIZACION.get(d["motivo_categoria"])
    return d


def extraer(texto):
    d = _chat_json(PROMPT_EXTRAER, texto, SCHEMA_EXTRAER)

    # números: fuera de rango -> null (descarta alucinaciones)
    for k, (lo, hi) in LIMITES.items():
        v = _rango(d.get(k), lo, hi)
        d[k] = (int(round(v)) if k in ENTEROS else round(v, 1)) if v is not None else None

    # textos
    for k in ("motivo_consulta", "localizacion_dolor", "sintomas_asociados"):
        v = d.get(k)
        d[k] = v.strip()[:200] if isinstance(v, str) and v.strip() else None
    if d.get("sexo") not in ("Femenino", "Masculino"):
        d["sexo"] = None
    if d.get("tiempo_evolucion_unidad") not in ("minutos", "horas", "días"):
        d["tiempo_evolucion_unidad"] = None
    if d.get("motivo_categoria") not in CATEGORIAS:
        d["motivo_categoria"] = "Otro"
    for k in ANTECEDENTES:
        d[k] = bool(d.get(k))

    _anclar(d, texto)
    d["_modelo"] = MODELO
    return d


# ---------------------------------------------------------------- 2. sugerencia
SCHEMA_SUGERIR = {
    "type": "object",
    "properties": {
        "color": {"type": "string", "enum": list(NIVELES)},
        "motivos": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
    },
    "required": ["color", "motivos"],
}

PROMPT_SUGERIR = """Sos un asistente de triage con el sistema Manchester:
ROJO = inmediato, NARANJA = muy urgente (10 min), AMARILLO = urgente (60 min),
VERDE = normal (120 min), AZUL = no urgente (240 min).
Con el relato y los datos del paciente, sugerí UN color y hasta 4 motivos breves (máx. 12 palabras cada uno).
Usá SOLO lo que dicen el relato y los datos: no menciones síntomas, zonas ni antecedentes que no estén.
NUNCA afirmes que algo está normal o ausente ("sin fiebre", "sin vómitos") si no fue medido o dicho:
lo que figura en "No medido" es desconocido, no normal.
Si hay BANDERAS ROJAS marcadas por enfermería, nunca sugieras VERDE ni AZUL y mencionalas en los motivos.
Fijate en los valores alterados marcados con (ALTERADO) y tenelos en cuenta.
Orientación general:
- compromiso de vía aérea, shock, inconsciencia -> ROJO
- dolor intenso (8-10), dolor torácico, signos vitales muy alterados -> NARANJA
- dolor moderado (5-7), fiebre, vómitos persistentes -> AMARILLO
- dolor leve (1-4) o problema reciente con signos vitales normales -> VERDE
- problema menor no reciente, sin dolor ni alteraciones -> AZUL
Ante la duda real entre dos colores, elegí el más urgente.
No diagnostiques ni indiques tratamientos: es una sugerencia que valida el profesional.
Respondé únicamente con el JSON."""


def _datos_utiles(datos):
    """Saca vacíos y antecedentes en false para que el prompt sea corto."""
    return {k: v for k, v in (datos or {}).items()
            if v not in (None, "", False) and not str(k).startswith("_")}


# Origen de cada motivo: qué lo aporta realmente
RX_MEDIDO = re.compile(r"(frecuencia|\bfc\b|\bfr\b|saturaci|spo2|oxigeno|presion|tension|\bta\b|"
                       r"temperatura|glasgow|glucemia|\bpam\b|/10|escala|intensidad|conciencia|mmhg|lpm|rpm)")
RX_DECLARADO = re.compile(r"(tiempo|evolucion|\bhace\b|horas?\b|dias?\b|minutos?\b|\bedad\b|anos\b|"
                          r"antecedente|diabet|hipertens|anticoag|embaraz|inmuno|alergi|medicacion)")
VACIAS = {"paciente", "refiere", "presenta", "dolor", "con", "sin", "para", "desde", "hace", "esta", "como"}


def _fuente(motivo, relato):
    """'medido' = signos que cargó enfermería · 'relato' = lo dijo el paciente · 'ia' = criterio del modelo."""
    m = _norm(motivo)
    if re.search(r"sangr|hemorrag|convuls|disnea|dificultad para respirar|trauma", m):
        return "medido"                 # banderas rojas que marca enfermería -> se muestran como REGLA
    if RX_MEDIDO.search(m):
        return "medido"
    if RX_DECLARADO.search(m):          # tiempo, edad, antecedentes: datos que cuenta el paciente
        return "relato"
    palabras = [w for w in re.findall(r"[a-z]+", m) if len(w) > 3 and w not in VACIAS]
    r = _norm(relato)
    if palabras and sum(w[:5] in r for w in palabras) >= max(1, len(palabras) // 2):
        return "relato"
    return "ia"


# ---- Presentación legible de los datos para el modelo + control de afirmaciones falsas ----
SIGNOS = [  # campo, nombre, unidad, rango normal (adultos, orientativo)
    ("ta_sistolica", "TA sistólica", "mmHg", 90, 140),
    ("ta_diastolica", "TA diastólica", "mmHg", 60, 90),
    ("frecuencia_cardiaca", "Frecuencia cardíaca", "lpm", 60, 100),
    ("frecuencia_respiratoria", "Frecuencia respiratoria", "rpm", 12, 20),
    ("saturacion_o2", "Saturación de oxígeno", "%", 95, 100),
    ("temperatura", "Temperatura", "°C", 36, 37.5),
    ("glucemia", "Glucemia", "mg/dL", 70, 140),
    ("glasgow", "Glasgow", "pts", 15, 15),
    ("dolor_intensidad", "Intensidad del dolor", "/10", 0, 3),
]
BANDERAS = {"br_sangrado": "Sangrado evidente", "br_convulsion": "Convulsión activa",
            "br_disnea": "Dificultad para respirar", "br_trauma": "Mecanismo de trauma"}
ANTECED = {"ant_diabetes": "Diabetes", "ant_cardio": "Cardiovascular", "ant_resp": "Respiratorio",
           "ant_anticoag": "Anticoagulación", "ant_inmuno": "Inmunosupresión",
           "ant_embarazo": "Embarazo", "ant_medicacion": "Medicación crítica"}


def _num_campo(datos, k):
    try:
        return float(str(datos.get(k, "")).replace(",", "."))
    except ValueError:
        return None


def _estado_signos(datos):
    """{campo: 'normal' | 'alterado' | None (no medido)}"""
    est = {}
    for k, _, _, lo, hi in SIGNOS:
        v = _num_campo(datos, k)
        est[k] = None if v is None else ("normal" if lo <= v <= hi else "alterado")
    c = str(datos.get("estado_conciencia") or "")
    est["estado_conciencia"] = None if not c else ("normal" if c == "Alerta" else "alterado")
    return est


def _entrada_legible(datos, relato):
    est = _estado_signos(datos)
    lineas = []
    if relato and relato.strip():
        lineas.append(f"Relato del paciente: {relato.strip()}")
    ident = [f"{n}: {datos.get(k)}" for k, n in (("edad", "Edad"), ("sexo", "Sexo"),
             ("motivo_categoria", "Categoría"), ("motivo_consulta", "Motivo"),
             ("dolor_localizacion", "Localización"), ("sintomas_asociados", "Síntomas"))] 
    lineas += [x for x in ident if not x.endswith(": None") and not x.endswith(": ")]
    banderas = [n for k, n in BANDERAS.items() if datos.get(k)]
    lineas.append("BANDERAS ROJAS marcadas por enfermería: " + (", ".join(banderas) if banderas else "ninguna"))
    ant = [n for k, n in ANTECED.items() if datos.get(k)]
    if ant:
        lineas.append("Antecedentes: " + ", ".join(ant))
    medidos, faltan = [], []
    for k, n, u, lo, hi in SIGNOS:
        if est[k] is None:
            faltan.append(n)
        else:
            medidos.append(f"{n}: {datos.get(k)} {u}" + (" (ALTERADO)" if est[k] == "alterado" else ""))
    if est["estado_conciencia"] is None:
        faltan.append("Conciencia")
    else:
        medidos.append(f"Conciencia: {datos.get('estado_conciencia')}" + (" (ALTERADO)" if est["estado_conciencia"] == "alterado" else ""))
    lineas.append("Medido: " + ("; ".join(medidos) if medidos else "nada"))
    lineas.append("No medido (DESCONOCIDO, no asumir normal): " + (", ".join(faltan) if faltan else "nada"))
    return "\n".join(lineas)


# Afirmaciones de normalidad o ausencia ("sin fiebre", "signos vitales normales")
RX_NEGACION = re.compile(r"(^|\b)(sin|no presenta|no refiere|niega|ausencia|normal|normales|estable|conservad|adecuad)")
TEMA_CAMPOS = [  # palabra en el motivo -> campos que tienen que estar medidos y normales
    (r"fiebre|febril|afebril|temperatura", ["temperatura"]),
    (r"taquicard|bradicard|frecuencia cardiaca|\bfc\b|pulso", ["frecuencia_cardiaca"]),
    (r"frecuencia respiratoria|\bfr\b|taquipne|respirat", ["frecuencia_respiratoria"]),
    (r"saturaci|oxigen|spo2", ["saturacion_o2"]),
    (r"presion|tension|hipotens|hipertens|\bta\b", ["ta_sistolica", "ta_diastolica"]),
    (r"conciencia|glasgow|alerta|orientad", ["estado_conciencia"]),
    (r"glucemia|glucosa", ["glucemia"]),
    (r"signos vitales|vitales|hemodinamic", ["ta_sistolica", "frecuencia_cardiaca", "frecuencia_respiratoria",
                                             "saturacion_o2", "temperatura", "estado_conciencia"]),
]
BANDERA_PALABRAS = {"br_sangrado": r"sangr|hemorrag", "br_convulsion": r"convuls",
                    "br_disnea": r"disnea|respirar|aire", "br_trauma": r"trauma|golpe|caida"}


def _afirmacion_falsa(motivo, datos, relato):
    """True si el motivo afirma normalidad/ausencia de algo no medido, alterado o contradicho."""
    m = _norm(motivo)
    if not RX_NEGACION.search(m):
        return False
    est = _estado_signos(datos)
    for rx, campos in TEMA_CAMPOS:
        if re.search(rx, m):
            return any(est.get(c) != "normal" for c in campos)      # no medido o alterado
    for k, rx in BANDERA_PALABRAS.items():                          # "sin sangrado" con la bandera marcada
        if re.search(rx, m) and datos.get(k):
            return True
    # "sin vómitos", "sin diarrea": síntoma que nadie preguntó -> no se puede afirmar
    tema = re.sub(RX_NEGACION, "", m).strip()
    palabras = [w for w in re.findall(r"[a-z]+", tema) if len(w) > 3]
    return bool(palabras) and not any(w[:5] in _norm(relato) for w in palabras)


def sugerir(datos, relato=""):
    entrada = _entrada_legible(datos, relato)
    d = _chat_json(PROMPT_SUGERIR, entrada, SCHEMA_SUGERIR)
    color = str(d.get("color", "")).upper()
    motivos = [str(m).strip()[:120] for m in d.get("motivos", []) if str(m).strip()][:5]
    descartados = [m for m in motivos if _afirmacion_falsa(m, datos, relato)]
    motivos = [m for m in motivos if m not in descartados]
    return {"nivel": NIVELES.get(color, NIVELES["AMARILLO"]),
            "color": color if color in NIVELES else "AMARILLO",
            "motivos": motivos,
            "fuentes": [_fuente(m, relato) for m in motivos],
            "descartados": descartados,
            "modelo": MODELO}


# ---------------------------------------------------------------- 3. chat
def consultar(pregunta, datos, sugerencia):
    sistema = ("Sos un asistente de triage para enfermería. Respondé en español rioplatense, "
               "breve (máx. 5 líneas), solo sobre este caso. No diagnostiques ni indiques "
               "tratamientos. Si un dato falta, decilo. La decisión final es del profesional.\n"
               f"Datos del caso: {json.dumps(_datos_utiles(datos), ensure_ascii=False)}\n"
               f"Color sugerido actualmente: {sugerencia}")
    return _chat(sistema, pregunta).strip()
