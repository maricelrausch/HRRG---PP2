"""
Extracción única del relato (Tomás + Darío) para POST /api/extraer.

Firma que usa app.py (no cambia):
    extraer_datos(relato, esquema=ExtraccionIA) -> dict validado con el esquema

Qué toma de cada versión:
  - Tomás: salida forzada con el JSON Schema de ExtraccionIA, temperatura 0,
    contexto opcional del RAG.
  - Darío: reglas del prompt, reintento si el JSON viene roto y "anclaje":
    se descarta lo que el modelo inventa y no está en el relato.

Qué NO hace (a propósito):
  - No extrae edad, sexo ni signos vitales: vienen de la HCE y de enfermería
    (Identificacion y Mediciones). ExtraccionIA no tiene esos campos.
  - No asigna color Manchester.

Variables de entorno opcionales:
  MEDGEMMA_MODELO          (por defecto medgemma:4b)
  OLLAMA_HOST              (por defecto http://localhost:11434)
  HRRG_EXTRACCION_RAG      "1" usa el RAG si está disponible (por defecto), "0" lo apaga
"""
import json
import logging
import os
import re
import unicodedata

import ollama
from pydantic import ValidationError

try:
    from .esquemas import ExtraccionIA
except ImportError:
    from esquemas import ExtraccionIA

logger = logging.getLogger(__name__)

LLM_MODEL = os.environ.get("MEDGEMMA_MODELO", "medgemma:4b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
USAR_RAG = os.environ.get("HRRG_EXTRACCION_RAG", "1") != "0"

_cliente = None


def _cli():
    """Cliente de Ollama con timeout; se crea al primer uso."""
    global _cliente
    if _cliente is None:
        _cliente = ollama.Client(host=OLLAMA_HOST, timeout=180)
    return _cliente


# ------------------------------------------------------------------ prompt
PROMPT_SISTEMA = """Sos un extractor de datos para el ingreso a una guardia.
Leés el relato de un paciente y devolvés SOLO lo que está dicho explícitamente.
Reglas:
- No diagnostiques ni asignes prioridad o color.
- Si un dato no aparece, devolvé null (o false en los campos sí/no). No inventes ni estimes.
- No extraigas edad, sexo, signos vitales ni escalas: no forman parte de este JSON.
- motivo_categoria: una de las opciones del esquema; si ninguna encaja, "Otro".
- motivo_consulta: resumen breve (máximo 10 palabras), sin nombres ni datos personales.
- tiempo_evolucion_valor y tiempo_evolucion_unidad: solo si el relato da una duración concreta
  ("hace 3 días", "media hora"). Expresiones vagas ("desde ayer", "unos minutos") -> null.
- dolor_localizacion: dónde le duele, con las palabras del relato o su término anatómico.
- sintomas_asociados: otros síntomas que refiere, separados por coma.
- br_* (banderas rojas): true si el relato lo menciona, aunque sea al pasar. Ejemplos:
  br_sangrado: sangra, sangrado, hemorragia, vómito con sangre.
  br_convulsion: convulsión, convulsiones, convulsionó.
  br_disnea: le falta el aire, no puede respirar, se ahoga, dificultad para respirar.
  br_trauma: golpe, caída, se cayó, choque, accidente, fractura.
  "Niega sangrado" o "sin sangrado" -> false.
- ant_* (antecedentes): true si el relato menciona ese antecedente. Ejemplos:
  ant_diabetes: diabético/a, usa insulina. ant_cardio: hipertenso, infarto, problemas del corazón.
  ant_resp: asma, EPOC. ant_anticoag: anticoagulado, toma sintrom o warfarina.
  ant_inmuno: quimioterapia, trasplante, VIH. ant_embarazo: embarazada.
  ant_medicacion: insulina, anticoagulantes, quimioterapia u otra medicación de riesgo.
- Ante la duda en una bandera roja, marcala true: la revisa el profesional.
Respondé únicamente con el objeto JSON."""


def _mensajes(relato, contexto):
    usuario = f"Relato:\n{relato}"
    if contexto:
        usuario += f"\n\nDocumentación de referencia (no es parte del relato):\n{contexto}"
    return [{"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": usuario}]


def _contexto_rag(relato):
    """Fragmentos del RAG de Tomás. Si ChromaDB o los embeddings fallan, sigue sin contexto."""
    if not USAR_RAG:
        return ""
    try:
        try:
            from .rag import buscar_informacion
        except ImportError:
            from rag import buscar_informacion
        fragmentos = buscar_informacion(relato, cantidad=3)
        return "\n\n".join(f["texto"] for f in fragmentos)
    except Exception:
        logger.warning("RAG_NO_DISPONIBLE_EXTRACCION")
        return ""


def _llamar_modelo(relato, esquema, contexto):
    """Devuelve un dict. Reintenta una vez si el JSON viene roto."""
    ultimo = None
    for _ in range(2):
        r = _cli().chat(model=LLM_MODEL,
                        messages=_mensajes(relato, contexto),
                        format=esquema.model_json_schema(),
                        options={"temperature": 0})
        try:
            datos = json.loads(r["message"]["content"])
            if isinstance(datos, dict):
                return datos
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            ultimo = e
    raise ValueError("MedGemma no devolvió un JSON válido.") from ultimo


# ------------------------------------------------------------------ anclaje
def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return s.encode("ascii", "ignore").decode()


# Palabras del relato que fijan la categoría (orden = prioridad).
CLAVES_CATEGORIA = [
    ("Dolor torácico", r"\b(pecho|torax|toracic\w*|precordi\w*)\b"),
    ("Cefalea", r"\b(cabeza|cefalea|migran\w*|jaqueca)\b"),
    ("Dolor abdominal", r"\b(panza|abdomen|abdominal|estomago|barriga|epigastr\w*|vientre|flanco)\b"),
    ("Disnea", r"(falta (de|el) aire|\bahog\w*|\bdisnea\b|no puede respirar|cuesta respirar)"),
    ("Trauma", r"\b(golpe\w*|caida|cayo|choque|accidente|fractur\w*|torc\w*|herida|corte)\b"),
    ("Síntoma neurológico", r"(convulsi\w*|desmay\w*|paralisis|no puede hablar|hormigueo|perdida de fuerza)"),
    ("Fiebre", r"\b(fiebre|afiebrad\w*|febril)\b"),
]

# Localización por defecto y términos aceptados aunque no estén literales en el relato.
LOCALIZACION = {
    "Dolor torácico": ("Tórax", {"torax", "pecho", "precordial", "retroesternal"}),
    "Dolor abdominal": ("Abdomen", {"abdomen", "epigastrio", "hipogastrio", "mesogastrio"}),
    "Cefalea": ("Cabeza", {"cabeza", "craneo", "frontal", "occipital"}),
}

NUMEROS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
           "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
           "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40, "media": 0.5}
UNIDADES = [(r"min(?:uto)?s?", "minutos", 1), (r"h(?:ora)?s?", "horas", 1),
            (r"dias?", "días", 1), (r"semanas?", "días", 7)]
RX_TIEMPO = re.compile(
    r"\b(?P<num>\d+(?:[.,]\d+)?|" + "|".join(NUMEROS) + r")\s+(?P<unidad>"
    + "|".join(u for u, _, _ in UNIDADES) + r")\b(?P<media>\s+y media)?")

NEGACION = r"\b(sin|niega|no presenta|no refiere|no tiene|ausencia de)\s+(\w+\s+){0,3}"
BANDERAS = {
    "br_sangrado": r"(sangr\w*|hemorrag\w*)",
    "br_convulsion": r"(convuls\w*)",
    "br_disnea": r"(falta (de|el) aire|ahog\w*|disnea|cuesta respirar|no puede respirar|dificultad para respirar)",
    "br_trauma": r"(golpe\w*|caida|cayo|choque|accidente|fractur\w*|torc\w*|herida|corte)",
}
ANTECEDENTES = {
    "ant_diabetes": r"(diabet\w*|insulina|glucemia alta)",
    "ant_cardio": r"(cardiac\w*|corazon|infarto|hipertens\w*|presion alta|arritmi\w*|marcapasos)",
    "ant_resp": r"(asma\w*|epoc|bronquit\w*|enfisema|pulmon\w*)",
    "ant_anticoag": r"(anticoagul\w*|sintrom|warfarina|acenocumarol|apixaban|rivaroxaban)",
    "ant_inmuno": r"(inmunosupr\w*|quimioterapia|trasplant\w*|vih|corticoides)",
    "ant_embarazo": r"(embaraz\w*|gestacion|semanas de gestacion)",
    "ant_medicacion": r"(medicacion critica|insulina|anticoagul\w*|quimioterapia)",
}
TEXTOS_ANCLADOS = ("sintomas_asociados", "dolor_caracteristicas", "alergias", "antecedentes_otros")
VACIAS = {"paciente", "refiere", "presenta", "dolor", "desde", "hace", "esta", "como", "tiene", "siente"}


def tiempo_del_relato(texto):
    """Duración explícita del relato -> (valor, unidad) o (None, None). 'media hora' -> 30 minutos."""
    t = _norm(texto)
    if re.search(r"\bmedia hora\b", t):
        return 30.0, "minutos"
    m = RX_TIEMPO.search(t)
    if not m:
        return None, None
    crudo, unidad_txt = m.group("num"), m.group("unidad")
    valor = NUMEROS.get(crudo)
    if valor is None:
        valor = float(crudo.replace(",", "."))
    if m.group("media"):
        valor += 0.5
    for rx, unidad, factor in UNIDADES:
        if re.fullmatch(rx, unidad_txt):
            return float(valor * factor), unidad
    return None, None


def _afirmado(rx, t):
    """True si el patrón aparece al menos una vez sin una negación delante."""
    for m in re.finditer(rx, t):
        previo = t[max(0, m.start() - 40):m.start()]
        if not re.search(NEGACION + r"$", previo):
            return True
    return False


SUFIJOS = ("aciones", "acion", "iendo", "ando", "ados", "adas", "idos", "idas", "ado", "ada",
           "ido", "ida", "ar", "er", "ir", "es", "as", "os", "s", "a", "o", "e")


def _raiz(w):
    for suf in SUFIJOS:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def _aparece(texto_campo, t):
    """Al menos una palabra significativa del campo está en el relato
    (comparando raíces: 'sudoración' ~ 'sudando', 'vómitos' ~ 'vomitar')."""
    palabras = [w for w in re.findall(r"[a-z]+", _norm(texto_campo)) if len(w) > 3 and w not in VACIAS]
    raices_relato = {_raiz(w) for w in re.findall(r"[a-z]+", t) if len(w) > 2}
    for w in palabras:
        r = _raiz(w)
        if any(x.startswith(r) or r.startswith(x) for x in raices_relato if len(x) >= 3):
            return True
    return False


def anclar(datos, relato):
    """Corrige o descarta lo que no surge del relato. Modifica y devuelve `datos`."""
    t = _norm(relato)

    # Categoría: si el relato tiene palabras clave, manda el relato.
    halladas = [c for c, rx in CLAVES_CATEGORIA if re.search(rx, t)]
    if halladas and datos.get("motivo_categoria") not in halladas:
        datos["motivo_categoria"] = halladas[0]

    # Tiempo de evolución: solo el que se puede leer en el relato.
    datos["tiempo_evolucion_valor"], datos["tiempo_evolucion_unidad"] = tiempo_del_relato(relato)

    # Localización: literal en el relato o término aceptado para la categoría.
    defecto, aceptados = LOCALIZACION.get(datos.get("motivo_categoria"), (None, set()))
    loc = datos.get("dolor_localizacion")
    if loc and not _aparece(loc, t) and not set(re.findall(r"[a-z]+", _norm(loc))) & aceptados:
        datos["dolor_localizacion"] = None
    if not datos.get("dolor_localizacion") and defecto and datos.get("motivo_categoria") in halladas:
        datos["dolor_localizacion"] = defecto

    # Sí/no: true solo si el modelo lo marcó Y el relato lo afirma (no negado).
    for campo, rx in {**BANDERAS, **ANTECEDENTES}.items():
        datos[campo] = datos.get(campo) is True and _afirmado(rx, t)

    # Síntomas: se queda solo con los que aparecen en el relato.
    if datos.get("sintomas_asociados"):
        items = [x.strip() for x in str(datos["sintomas_asociados"]).split(",") if x.strip()]
        datos["sintomas_asociados"] = ", ".join(x for x in items if _aparece(x, t)) or None

    # Otros textos libres: se descartan si no tienen ninguna palabra del relato.
    for campo in TEXTOS_ANCLADOS:
        if datos.get(campo) and not _aparece(datos[campo], t):
            datos[campo] = None
    return datos


# ------------------------------------------------------------------ validación
def _validar_por_campo(datos, esquema):
    """Valida campo por campo: lo inválido (incluye datos personales) queda null/false
    en vez de rechazar toda la extracción."""
    limpio = {}
    for nombre, campo in esquema.model_fields.items():
        valor = datos.get(nombre)
        try:
            esquema.model_validate({nombre: valor})
            limpio[nombre] = valor
        except ValidationError:
            limpio[nombre] = None if not campo.is_required() and campo.default is None else campo.default
    return esquema.model_validate(limpio)


# ------------------------------------------------------------------ función pública
def extraer_datos(relato, esquema=ExtraccionIA):
    """Relato -> dict validado con `esquema` (ExtraccionIA). Lanza ValueError si el
    relato está vacío o el modelo no devuelve JSON. Errores de conexión con Ollama
    se propagan (app.py los traduce a 503)."""
    if not isinstance(relato, str) or not relato.strip():
        raise ValueError("El relato está vacío.")
    relato = relato.strip()

    crudo = _llamar_modelo(relato, esquema, _contexto_rag(relato))
    datos = {k: crudo.get(k) for k in esquema.model_fields}        # descarta claves extra
    for k, v in datos.items():
        if isinstance(v, str):
            datos[k] = v.strip() or None

    if esquema is ExtraccionIA:
        anclar(datos, relato)

    return _validar_por_campo(datos, esquema).model_dump(mode="json")
