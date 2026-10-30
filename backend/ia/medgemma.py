"""backend/ia/medgemma.py · Conexión con MedGemma vía Ollama.

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
from pathlib import Path

import ollama

MODELO = os.environ.get("MEDGEMMA_MODELO", "medgemma:4b")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
KEEP_ALIVE = os.environ.get("MEDGEMMA_KEEP_ALIVE", "30m")   # cuánto queda cargado el modelo sin uso
# Hilos de CPU para MedGemma. Vacío = los que elija Ollama (todos los núcleos físicos).
# Para repartir la CPU con Whisper: MEDGEMMA_HILOS=4, por ejemplo.
HILOS = int(os.environ.get("MEDGEMMA_HILOS") or 0)
NIVELES = {"ROJO": 0, "NARANJA": 1, "AMARILLO": 2, "VERDE": 3, "AZUL": 4}

# [Dario 29/10 · D3] A propósito NO se agregan acá los motivos nuevos de src/esquemas.py: MedGemma
# sigue eligiendo entre estas 8 (extracción ya evaluada); el profesional puede elegir las nuevas.
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


def _chat(system, user, schema=None, historial=None, max_tokens=None):
    """Llama al modelo. Con schema, Ollama fuerza la salida a ese JSON.
    keep_alive mantiene el modelo cargado en memoria entre pacientes."""
    mensajes = [{"role": "system", "content": system}]
    for h in historial or []:
        mensajes.append({"role": "user", "content": h["pregunta"]})
        mensajes.append({"role": "assistant", "content": h["respuesta"]})
    mensajes.append({"role": "user", "content": user})
    opciones = {"temperature": 0}
    if HILOS:
        opciones["num_thread"] = HILOS
    if max_tokens:
        opciones["num_predict"] = max_tokens
    r = _cli.chat(model=MODELO, messages=mensajes, format=schema,
                  options=opciones, keep_alive=KEEP_ALIVE)
    return _sin_pensamiento(r.message.content or "")


# MedGemma a veces "piensa" antes de responder: <unused94>thought ... <unused95>respuesta.
# Ese razonamiento es interno (suele estar en inglés) y nunca se muestra.
RX_TOKEN_INTERNO = re.compile(r"<unused\d+>")


def _sin_pensamiento(texto):
    if "<unused95>" in texto:                      # quedarse solo con la respuesta final
        texto = texto.split("<unused95>", 1)[1]
    elif "<unused94>" in texto:                    # se cortó pensando: no hay respuesta utilizable
        return ""
    return RX_TOKEN_INTERNO.sub("", texto).strip()


def precalentar():
    """Carga el modelo en memoria al arrancar Flask, así el primer paciente no espera."""
    try:
        _cli.generate(model=MODELO, prompt="", keep_alive=KEEP_ALIVE)
        print(f"[MedGemma] {MODELO} cargado en memoria (keep_alive={KEEP_ALIVE})")
    except Exception as e:
        print(f"[MedGemma] no se pudo precargar: {e}")


def _chat_json(system, user, schema, max_tokens=None):
    """Igual que _chat pero devuelve dict; reintenta una vez si el JSON viene roto."""
    ultimo_error = None
    for _ in range(2):
        try:
            return json.loads(_chat(system, user, schema, max_tokens=max_tokens))
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
# MedGemma solo extrae lo que necesita comprensión del lenguaje (motivo, síntomas, edad, sexo…).
# Los signos vitales escritos con números (TA 130/80, FC 95, 38,2 °C) se leen con reglas:
# es instantáneo, exacto y le ahorra al modelo la mitad del texto a generar.
NOMBRES_ANT = {"diabetes": "ant_diabetes", "cardiovascular": "ant_cardio", "respiratorio": "ant_resp",
               "anticoagulado": "ant_anticoag", "inmunosuprimido": "ant_inmuno",
               "embarazo": "ant_embarazo", "medicacion critica": "ant_medicacion"}

ANCLA_ANT = {"diabetes": r"diabet|insulina|azucar", "cardiovascular": r"cardi|corazon|hipertens|presion alta|infarto",
             "respiratorio": r"respirat|asma|epoc|pulmon|bronqu", "anticoagulado": r"anticoag|sintrom|warfarin|acenocum",
             "inmunosuprimido": r"inmuno|quimio|trasplant|transplant|vih|hiv|cortico",
             "embarazo": r"embaraz|gestacion|semanas de", "medicacion critica": r"medicac|toma pastillas|insulina|anticoag"}

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
        "dolor": _num(),
        "antecedentes": {"type": "array", "items": {"type": "string", "enum": list(NOMBRES_ANT)},
                         "maxItems": 7},
    },
    "required": ["edad", "sexo", "motivo_categoria", "motivo_consulta", "localizacion_dolor",
                 "sintomas_asociados", "tiempo_evolucion_valor", "tiempo_evolucion_unidad",
                 "dolor", "antecedentes"],
}

PROMPT_EXTRAER = """Sos un asistente de enfermería de guardia. Leés el relato de ingreso de un paciente
y extraés SOLO los datos que aparecen escritos. Reglas:
- Si un dato no aparece, usá null (o "No informado" en sexo y unidad de tiempo). No inventes ni estimes.
- "Mujer", "señora", "paciente femenina" -> Femenino. "Hombre", "señor", "varón" -> Masculino.
- edad: número entero de años.
- dolor: intensidad 0 a 10 solo si el relato da un número (ej. "8/10" -> 8); "leve" o "mucho" -> null.
- motivo_consulta: resumen breve (máx. 10 palabras). localizacion_dolor: dónde le duele.
- sintomas_asociados: otros síntomas que refiere, separados por coma.
- antecedentes: solo los que el relato menciona; si ninguno, lista vacía.
Respondé únicamente con el JSON."""

# Signos vitales escritos en el relato (texto ya normalizado: minúsculas, sin acentos)
_D = r"\s*:?\s*(?:de\s*)?"
RX_SIGNOS = {
    "ta": [r"\b(?:ta|tension(?: arterial)?|presion(?: arterial)?)" + _D + r"(\d{2,3})\s*/\s*(\d{2,3})"],
    "frec_cardiaca": [r"\b(?:fc|frecuencia cardiaca|pulso)" + _D + r"(\d{2,3})"],
    "frec_respiratoria": [r"\b(?:fr|frecuencia respiratoria)" + _D + r"(\d{1,2})"],
    "saturacion": [r"\b(?:sat(?:uracion)?(?: de oxigeno)?|spo2|o2)" + _D + r"(\d{2,3})"],
    "temperatura": [r"\b(?:temp(?:eratura)?|t)" + _D + r"(\d{2}(?:[.,]\d)?)",
                    r"\b(\d{2}[.,]\d)\s*(?:°|grados|c\b)", r"fiebre de (\d{2}(?:[.,]\d)?)"],
    "glasgow": [r"glasgow" + _D + r"(\d{1,2})"],
    "dolor": [r"\b(\d{1,2})\s*/\s*10\b", r"dolor" + _D + r"(\d{1,2})\s*(?:sobre|de|en)\s*10"],
}
RX_TIEMPO = r"\b(?:hace|desde hace)\s+(?:unos?\s+|unas?\s+)?(\d{1,4}|media)\s*(minutos?|min|horas?|hs|h|dias?)\b"
UNIDADES = {"min": "minutos", "minuto": "minutos", "minutos": "minutos", "h": "horas", "hs": "horas",
            "hora": "horas", "horas": "horas", "dia": "días", "dias": "días"}


def _signos_por_reglas(texto):
    t = _norm(texto).replace("°c", "° c")
    out = {}
    for campo, patrones in RX_SIGNOS.items():
        for p in patrones:
            m = re.search(p, t)
            if m:
                if campo == "ta":
                    out["tas"], out["tad"] = float(m.group(1)), float(m.group(2))
                else:
                    out[campo] = float(m.group(1).replace(",", "."))
                break
    return out


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
# [Dario 30/10] Una sola lista, la de src/extraccion.py (antes había dos copias distintas).
from src.extraccion import CLAVES_CATEGORIA, categorias_del_relato  # noqa: E402
LOCALIZACION = {"Dolor torácico": "Pecho", "Cefalea": "Cabeza", "Dolor abdominal": "Abdomen"}


def _anclar(d, texto):
    """Descarta lo que el modelo inventó: números que no están en el relato,
    categoría y localización que contradicen las palabras del relato."""
    t = _norm(texto)
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", t)]
    for k in LIMITES:
        v = d.get(k)
        if k == "tiempo_evolucion_valor" and "media" in t:
            continue
        if v is not None and not any(abs(float(v) - n) < 0.05 for n in nums):
            d[k] = None                                   # número que no aparece en el relato

    halladas = categorias_del_relato(t)
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
    d = _chat_json(PROMPT_EXTRAER, texto, SCHEMA_EXTRAER, max_tokens=300)

    # signos vitales: por reglas (los valores escritos ganan sobre lo que diga el modelo)
    for k in ("tas", "tad", "pam", "frec_cardiaca", "frec_respiratoria", "saturacion", "temperatura", "glasgow"):
        d[k] = None
    d.update(_signos_por_reglas(texto))
    # tiempo de evolución escrito con números ("hace 2 horas", "hace media hora")
    m = re.search(RX_TIEMPO, _norm(texto))
    if m and d.get("tiempo_evolucion_valor") is None:
        valor = 30 if m.group(1) == "media" else float(m.group(1))
        unidad = "minutos" if m.group(1) == "media" else UNIDADES.get(m.group(2), None)
        if unidad:
            d["tiempo_evolucion_valor"], d["tiempo_evolucion_unidad"] = valor, unidad
    # antecedentes: lista -> casillas ant_* que usa el formulario
    t = _norm(texto)
    lista = [a for a in (d.pop("antecedentes", None) or [])
             if a in NOMBRES_ANT and re.search(ANCLA_ANT[a], t)]      # solo si el relato lo dice
    for nombre, campo in NOMBRES_ANT.items():
        d[campo] = nombre in lista

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
                       r"temperatura|glasgow|glucemia|\bpam\b|/10|escala|intensidad|conciencia|mmhg|lpm|rpm|"
                       r"\d+(?:[.,]\d+)?\s*c\b|\d+\s*%)")
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
SIGNOS = [  # Respaldo si no se puede leer la tabla. campo, nombre, unidad, rango normal (adultos, orientativo)
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
# [Dario 30/10 · pedido de Navoni] Los rangos normales salen de la tabla parametros_signos (reglas_hospital.db),
# los mismos que ve la enfermera en la pantalla y edita la Jefatura, según el grupo etario del paciente.
BASE_PARAMETROS = Path.home() / ".hrrg_pp2" / "reglas_hospital.db"


def signos_para(datos):
    """Lista (campo, nombre, unidad, normal_min, normal_max) para la edad del paciente; SIGNOS si no hay tabla."""
    try:
        from src.parametros_signos import parametros_para
        p = parametros_para(BASE_PARAMETROS, (datos or {}).get("edad"))
    except Exception:  # noqa: BLE001  (sin tabla, la IA sigue con el respaldo)
        p = {}
    salida = []
    for k, n, u, lo, hi in SIGNOS:
        f = p.get(k)
        if f and f["normal_min"] is not None and f["normal_max"] is not None:
            salida.append((k, f["nombre"] or n, f["unidad"] or u, f["normal_min"], f["normal_max"]))
        else:
            salida.append((k, n, u, lo, hi))
    return salida


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
    for k, _, _, lo, hi in signos_para(datos):
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
    for k, n, u, lo, hi in signos_para(datos):
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
    (r"fiebr|febril|afebril|temperatura", ["temperatura"]),
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


RX_ALTERADO = re.compile(r"(alt[oa]s?\b|baj[oa]s?\b|elevad|aumentad|disminuid|alterad|taquic|bradic|taquip|"
                         r"hipotens|hipertens|hipox|desatur|febril|fiebre)")


def _afirmacion_falsa(motivo, datos, relato):
    """True si el motivo habla de algo no medido, o afirma normal/alterado contra lo medido."""
    m = _norm(motivo)
    if "desconocid" in m or "no medid" in m:
        return True
    est = _estado_signos(datos)
    for rx, campos in TEMA_CAMPOS:
        if re.search(rx, m):
            if any(est.get(c) is None for c in campos):
                # no medido: solo vale si es algo que el paciente contó ("me siento afiebrada") y no lo niega
                return bool(RX_NEGACION.search(m)) or not re.search(rx, _norm(relato))
            if RX_NEGACION.search(m):
                return any(est.get(c) != "normal" for c in campos)   # dice "normal" pero está alterado
            if RX_ALTERADO.search(m):
                return all(est.get(c) == "normal" for c in campos)   # dice "alterado" pero está normal
            return False
    if not RX_NEGACION.search(m):
        return False
    for k, rx in BANDERA_PALABRAS.items():                          # "sin sangrado" con la bandera marcada
        if re.search(rx, m) and datos.get(k):
            return True
    # "sin vómitos", "sin diarrea": síntoma que nadie preguntó -> no se puede afirmar
    tema = re.sub(RX_NEGACION, "", m).strip()
    palabras = [w for w in re.findall(r"[a-z]+", tema) if len(w) > 3]
    return bool(palabras) and not any(w[:5] in _norm(relato) for w in palabras)


def _signo_normal(motivo, datos):
    """[Dario 30/10] True si el motivo solo nombra un signo vital medido que está NORMAL («TA sistólica 120 mmHg»).
    No explica por qué sube el color, así que no se muestra como motivo. Una aclaración («sin fiebre») no se toca."""
    m = _norm(motivo)
    if RX_NEGACION.search(m) or RX_ALTERADO.search(m):
        return False
    est = _estado_signos(datos)
    if re.search(r"sistol", m):
        campos = ["ta_sistolica"]
    elif re.search(r"diastol", m):
        campos = ["ta_diastolica"]
    else:
        campos = next((c for rx, c in TEMA_CAMPOS if re.search(rx, m)), None)
    return bool(campos) and all(est.get(c) == "normal" for c in campos)


def datos_insuficientes(datos, relato=""):
    """Sin relato/motivo y con menos de 3 signos medidos no hay con qué sugerir un color."""
    est = _estado_signos(datos)
    medidos = sum(1 for v in est.values() if v is not None)
    hay_relato = bool((relato or "").strip() or datos.get("motivo_consulta") or datos.get("motivo_categoria"))
    banderas = any(datos.get(k) for k in BANDERAS)
    return not banderas and (medidos < 3 and not hay_relato or medidos == 0 and not (relato or "").strip())


def sugerir(datos, relato=""):
    if datos_insuficientes(datos, relato):
        return {"insuficiente": True, "nivel": None, "color": None, "motivos": [], "fuentes": [],
                "descartados": [], "modelo": MODELO}
    entrada = _entrada_legible(datos, relato)
    d = _chat_json(PROMPT_SUGERIR, entrada, SCHEMA_SUGERIR)
    color = str(d.get("color", "")).upper()
    motivos = [str(m).strip()[:120] for m in d.get("motivos", []) if str(m).strip()][:5]
    descartados = [m for m in motivos if _afirmacion_falsa(m, datos, relato)]
    motivos = [m for m in motivos if m not in descartados]
    normales = [m for m in motivos if _signo_normal(m, datos)]     # [Dario 30/10] no justifican el color
    motivos = [m for m in motivos if m not in normales]
    return {"nivel": NIVELES.get(color, NIVELES["AMARILLO"]),
            "color": color if color in NIVELES else "AMARILLO",
            "motivos": motivos,
            "fuentes": [_fuente(m, relato) for m in motivos],
            "descartados": descartados,
            "normales_omitidos": normales,
            "modelo": MODELO}


# ---------------------------------------------------------------- 3. chat
# Controles por FUERA del modelo: un modelo chico no siempre obedece "no diagnostiques".
# Si el modelo no llega a responder (o responde en inglés), no se muestra nada de lo que generó
RX_INGLES = re.compile(r"\b(the user|i need to|let me|the patient is|i should|based on the)\b", re.I)
SIN_RESPUESTA = ("No pude armar una respuesta para esa pregunta. Probá reformularla o preguntá "
                 "por qué se sugirió el color, qué datos faltan o qué lo haría subir.")

LIMITES_CHAT = [
    ("destino",
     r"(a (la|su) casa|mandar|lo mando|la mando|(dar|darle|dale|damos|demos|doy|dan|dariamos) (el |la )?alta|\b(el|al) alta\b|de alta|\bintern(o|a|ar|arlo|arla|amos|acion)\b|derivar|"
     r"derivacion|puede irse|se puede ir|que se vaya|ambulatori|lo despacho)",
     "No puedo decidir el alta, la internación ni la derivación. Eso lo define el profesional después "
     "de evaluar al paciente. La herramienta solo sugiere la prioridad de atención."),
    ("tratamiento",
     r"(medicac|medicament|remedio|dosis|le doy|darle|le damos|tratamiento|tratar|antibiot|analges|"
     r"ibuprofeno|paracetamol|diclofenac|dipirona|inyect|recet|calmante|suero|que le pongo)",
     "No puedo indicar medicación ni tratamientos. Esta herramienta solo ayuda a priorizar la atención; "
     "la indicación la define el médico o la médica que evalúe al paciente."),
    ("diagnostico",
     r"(diagnost|que (enfermedad|patologia)\b|que (tiene|le pasa)( al| el| la)?( paciente)?\W*$|^\W*tiene\b|\btiene (un|una)\b|es (un|una) (infarto|acv|"
     r"fractura|esguince)|\w+itis\b|infarto|acv\b|fractura|neumonia|covid|sera grave|es grave)",
     "No puedo hacer diagnósticos. Puedo explicarte por qué se sugirió este color, qué datos faltan "
     "o qué haría subir la prioridad."),
]
# Frases que nunca pueden salir del chat aunque el modelo las escriba
RX_SALIDA_PROHIBIDA = re.compile(
    r"(puede (irse|ir) a (su |la )?casa|ir a (su |la )?casa|dar(le)? (el )?alta|de alta\b|"
    r"(el|la) paciente (esta|se encuentra) bien|\by esta bien\b|no es grave|no hay riesgo|"
    r"se descarta|descartad|le (podes|puede|pueden) dar|administr|\bmg\b|diagnostico (es|probable)|"
    r"probablemente (tiene|sea)|compatible con)")
# Frases que minimizan un hallazgo: se quita la oración entera (no decide la herramienta si algo es grave)
RX_MINIMIZA = re.compile(
    r"(no (es|seria|parece) (un |una )?(indicador|signo|dato|motivo) de (alarma|gravedad|preocupacion)|"
    r"no (es|resulta|parece) (preocupante|alarmante|significativ|relevante|importante)|sin importancia|"
    r"no requiere (atencion|preocupacion)|no reviste gravedad|no hay (motivo|razon) de (alarma|preocupacion)|"
    r"ligeramente (elevad|alterad|aumentad|alt)|levemente (elevad|alterad|aumentad)|dentro de lo esperable)")
RX_INDICA = re.compile(
    r"(estabiliz|control (del|de la) (sangrado|hemorragia|via)|se (recomienda|sugiere (realizar|administrar|colocar))|"
    r"(se debe|debe(n|ria)?|hay que|es necesario|requiere|necesita) (ser )?(administr|colocar|realizar|controlar|"
    r"trasladar|derivar|internar|evaluar por|inmoviliz|vendar|suturar|canaliz|dar\b|indicar)|"
    r"via (venosa|periferica)|oxigeno suplementario|compresion|torniquete|reanimac|"
    r"hipovolem|shock (hipovolemico|septico|cardiogenico)|compatible con|sugestiv|sospecha de|cuadro de\b|"
    r"signos de (deshidratacion|infeccion|infarto|apendicitis|fractura|sepsis))")
RESPUESTA_BLOQUEADA = ("No puedo responder eso de forma segura: excede lo que esta herramienta puede decir. "
                       "Consultalo con el profesional a cargo.")
RX_PREGUNTA = re.compile(r"(\?|^\W*(que|por que|porque|como|cual|cuales|cuanto|cuanta|hay|tiene|puede|"
                         r"donde|cuando|quien|explica|explicame|resumi|resumime|resumir|resume|decime|me decis|puedes|podes|podrias|podria|me (das|dirias)|necesito saber|conviene)\b)")
AVISO_DATO = ("\n\nNota: lo que escribís en el chat no cambia la clasificación. Si es un dato del paciente, "
              "agregalo en el relato o en la medición para que se tenga en cuenta.")

RX_PREG_FALTAN = re.compile(r"(falta|faltan|faltante|que (datos|informacion) (no|hay que)|que (mas )?(hay que )?(medir|completar|registrar))")
RX_PREG_SUBIR = re.compile(r"(subir|subiria|suba\b|aumentar|aumentaria|empeor|pasar(ia)? a\b|mas urgente|"
                           r"cambiar de color|cambiaria el color|que tiene que pasar|escalar|discriminador)")


RX_PREG_TIEMPO = re.compile(r"(tiempo de espera|cuanto (tiempo )?(tiene que |debe |va a |puede )?esper|demora en (ser )?atend|"
                            r"cuando (lo|la) (atienden|ven)|espera (corresponde|maxima|de referencia))")
ESPERA = {"ROJO": "atención inmediata", "NARANJA": "muy urgente: hasta 10 minutos",
          "AMARILLO": "urgente: hasta 60 minutos", "VERDE": "normal: hasta 120 minutos",
          "AZUL": "no urgente: hasta 240 minutos"}


def _respuesta_tiempo(color):
    c = next((k for k in ESPERA if k in (color or "").upper()), None)
    if not c:
        return "Todavía no hay un color sugerido, así que no hay un tiempo de espera de referencia."
    return (f"Para {c} el tiempo de referencia es {ESPERA[c]} (guía de ejemplo del prototipo). "
            "Los tiempos reales los fija la guía del hospital.")


RX_PREG_PORQUE = re.compile(r"(por ?que|motivo|razon|explica|justifica|de donde sale|como se (llego|decidio))")
ETIQ_NOMBRE = {"REGLA": "Reglas y signos medidos", "GUÍA": "Confirmado por el profesional",
               "GUIA": "Confirmado por el profesional", "RELATO": "Según el relato", "IA": "Criterio de MedGemma"}


def _respuesta_porque(ctx, color):
    """Explica el color con lo mismo que muestra la tarjeta: origen + motivos agrupados por etiqueta."""
    motivos = [m for m in (ctx.get("motivos") or []) if m]
    if not motivos:
        return None
    grupos = {}
    for m in motivos:
        mt = re.match(r"\[([^\]]+)\]\s*(.*)", m)
        etiqueta, texto = (mt.group(1).upper(), mt.group(2)) if mt else ("IA", m)
        if etiqueta == "SIM" or not texto:
            continue
        grupos.setdefault(etiqueta, []).append(texto.rstrip("."))
    partes = []
    origen = (ctx.get("origen") or "").strip()
    if color:
        partes.append(f"Se sugiere {color}." + (f" {origen}" if origen else ""))
    for et in ("REGLA", "GUÍA", "GUIA", "RELATO", "IA"):
        if grupos.get(et):
            partes.append(f"{ETIQ_NOMBRE[et]}: " + "; ".join(grupos[et]) + ".")
    return " ".join(partes) if partes else None


def _respuesta_faltan(ctx):
    faltan = [f for f in (ctx.get("faltan") or []) if f]
    if not faltan:
        return "No falta ningún dato obligatorio del formulario."
    return ("Faltan registrar: " + ", ".join(faltan) + ". Completalos en la pantalla 2 (Medición) "
            "para que la sugerencia sea más confiable.")


def _respuesta_subir(ctx, color):
    texto = (ctx.get("subir") or "").strip()
    if (color or "").upper().startswith("ROJO"):
        return "La sugerencia ya está en ROJO, la prioridad más alta."
    if not texto or ":" not in texto:
        return "No hay discriminadores disponibles para este caso en la guía de ejemplo."
    titulo, items = texto.split(":", 1)
    lista = [i.strip() for i in items.split(";") if i.strip()]
    nivel = titulo.replace("si se cumple alguno", "").replace("Pasaría a", "").strip()
    return ("Según la guía de ejemplo, pasaría a " + nivel + " si se cumple alguno de estos: "
            + "; ".join(lista) + ". Los que se miden se evalúan solos con los signos cargados; "
            "los demás se confirman con Sí/No en la tarjeta.")


RX_RELLENO = re.compile(r"^\s*((de acuerdo|claro|por supuesto|entendido|perfecto|bien)[,.!]?\s*)?"
                        r"((aqu[ií]|ac[aá]) (tienes|ten[eé]s|est[aá])[^:.\n]*[:.]\s*)?", re.I)


def _cortar_oraciones(texto):
    """Quita oraciones que minimizan y lo que quedó cortado al final por el límite de largo."""
    texto = RX_RELLENO.sub("", texto, count=1)
    texto = texto[:1].upper() + texto[1:]
    oraciones = re.split(r"(?<=[.!?])\s+", texto.strip())
    ok = [o for o in oraciones if not RX_MINIMIZA.search(_norm(o)) and not RX_INDICA.search(_norm(o))]
    if ok and not re.search(r"[.!?)]$", ok[-1]):
        ok = ok[:-1] or ok                                 # última oración incompleta
    return " ".join(ok).strip()


PROMPT_CHAT = """Sos un asistente de triage para el equipo de enfermería de una guardia.
Respondé en español, en registro profesional y neutro (nunca coloquial), en 2 a 4 oraciones, sin listas.
Si un valor figura como (ALTERADO), nombralo como alterado (por ejemplo "frecuencia cardíaca alterada: 120 lpm")
sin opinar si es grave, leve o preocupante.
No interpretes el cuadro clínico (nada de "signos de…", "compatible con…") ni indiques acciones o procedimientos.
Solo hablás de ESTE caso y de la prioridad sugerida.
Nunca diagnostiques, nunca indiques medicación o tratamientos, nunca decidas alta, internación ni derivación,
y nunca afirmes que el paciente "está bien": la decisión es siempre del profesional.
Usá solo los datos de abajo. Si te preguntan algo que no está, decí que ese dato no fue registrado.
Para explicar el color, nombrá los motivos y reglas listados. Para "qué falta", usá la lista de datos faltantes.
Para "qué lo haría subir", nombrá los discriminadores listados abajo.

{caso}

Color sugerido: {color}
Motivos del color: {motivos}
Datos que faltan en el formulario: {faltan}
Qué subiría la prioridad (discriminadores de la guía de ejemplo): {subir}"""


SIN_IA_CHAT = ("Modo sin IA: puedo responder por qué se sugirió este color, qué datos faltan "
               "y qué lo haría subir de prioridad. Para otras consultas, activá la IA tocando el indicador de arriba.")


def consultar_detalle(pregunta, datos, sugerencia, contexto=None, historial=None, relato="", sin_ia=False):
    """Devuelve (respuesta, tipo): tipo = bloqueada | fija | sin_ia | modelo | modelo_filtrada."""
    q = _norm(pregunta)
    for _, rx, texto in LIMITES_CHAT:                     # 1. control previo: no se consulta al modelo
        if re.search(rx, q):
            return texto, "bloqueada"
    ctx = contexto or {}
    if RX_PREG_FALTAN.search(q):                          # respuestas exactas, sin pasar por el modelo
        return _respuesta_faltan(ctx), "fija"
    if RX_PREG_TIEMPO.search(q):
        return _respuesta_tiempo(sugerencia), "fija"
    if RX_PREG_SUBIR.search(q):
        return _respuesta_subir(ctx, sugerencia), "fija"
    if RX_PREG_PORQUE.search(q) and re.search(r"color|prioridad|sugerencia|nivel|este|eso|asi", q):
        r = _respuesta_porque(ctx, sugerencia)
        if r:
            return r, "fija"
    if sin_ia:                                             # modo sin IA: solo respuestas armadas
        return SIN_IA_CHAT, "sin_ia"
    sistema = PROMPT_CHAT.format(
        caso=_entrada_legible(datos or {}, relato),
        color=sugerencia or "sin sugerencia",
        motivos="; ".join(ctx.get("motivos") or []) or "no disponibles",
        faltan=", ".join(ctx.get("faltan") or []) or "ninguno",
        subir=ctx.get("subir") or "no disponible")
    hist = [h for h in (historial or [])[-4:] if h.get("pregunta") and h.get("respuesta")]
    try:
        resp = _chat(sistema, pregunta, historial=hist, max_tokens=700).strip()
        if not resp or RX_INGLES.search(resp):
            return SIN_RESPUESTA, "sin_respuesta"
    except Exception:                                      # Ollama caído: no es un error para el usuario
        return "MedGemma no está disponible en este momento. " + SIN_IA_CHAT, "sin_ia"
    tipo = "modelo"
    resp = RX_RELLENO.sub("", resp, count=1).strip()     # "De acuerdo, aquí tienes…" no aporta
    resp = resp[:1].upper() + resp[1:]
    if RX_SALIDA_PROHIBIDA.search(_norm(resp)):          # 2. control posterior
        resp, tipo = RESPUESTA_BLOQUEADA, "bloqueada"
    else:
        limpia = _cortar_oraciones(resp)
        tipo = "modelo" if limpia == resp.strip() else "modelo_filtrada"
        resp = limpia or RESPUESTA_BLOQUEADA
        if not limpia:
            tipo = "bloqueada"
    if not RX_PREGUNTA.search(q):                          # 3. parece un dato nuevo, no una pregunta
        resp += AVISO_DATO
    return resp, tipo


def consultar(pregunta, datos, sugerencia, contexto=None, historial=None, relato="", sin_ia=False):
    return consultar_detalle(pregunta, datos, sugerencia, contexto, historial, relato, sin_ia)[0]
