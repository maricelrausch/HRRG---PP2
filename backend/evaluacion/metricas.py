"""backend/evaluacion/metricas.py · Funciones de métricas (Python puro, sin Ollama ni dependencias nuevas).

Se usan desde evaluacion/evaluar.py y se prueban en tests/test_metricas.py.

Contenido
  1. Extracción campo a campo  -> VP / FP / FN, precisión, recall, F1, tasa de alucinación
  2. Clasificación (color)     -> matriz de confusión, precisión/recall/F1 por color,
                                  kappa de Cohen ponderado, subtriage / sobretriage
  3. Detección de errores      -> recall y precisión de la validación (casos E vs F/A/D)
  4. Voz                       -> WER (tasa de error de palabras)
  5. Estadística               -> intervalos de confianza (Wilson y bootstrap), percentiles

Criterio de conteo en la extracción (por campo y por caso):
  esperado con valor, predicho igual      -> VP (acierto)
  esperado con valor, predicho vacío      -> FN (omisión)
  esperado vacío,     predicho con valor  -> FP (ALUCINACIÓN: el modelo inventó un dato)
  esperado con valor, predicho distinto   -> FP + FN (valor incorrecto: cuenta como error y omisión)
  esperado vacío,     predicho vacío      -> VN (no entra en precisión/recall)
Para booleanos (banderas rojas, antecedentes) "con valor" = True.
"""
from __future__ import annotations

import math
import random
import re
import unicodedata
from collections import Counter, defaultdict

# ------------------------------------------------------------------ normalización

def norm(s) -> str:
    """minúsculas, sin acentos ni signos, espacios simples."""
    s = unicodedata.normalize("NFKD", str(s or "").lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/.,]", " ", s)).strip()


def vacio(v) -> bool:
    return v is None or v is False or (isinstance(v, str) and not v.strip())


def a_numero(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return None


# Sinónimos para comparar textos libres (localización / motivo) de forma laxa
SINONIMOS = {
    "pecho": "torax", "toracico": "torax", "toracica": "torax", "precordial": "torax",
    "panza": "abdomen", "abdominal": "abdomen", "barriga": "abdomen", "estomago": "abdomen",
    "epigastrio": "abdomen", "vientre": "abdomen",
    "cabeza": "cefalea", "cefalea": "cefalea",
    "febril": "fiebre", "fiebre": "fiebre", "temperatura": "fiebre",
    "faringe": "garganta", "garganta": "garganta",
    "vomitos": "vomito", "vomito": "vomito", "sangre": "sangrado", "sangrado": "sangrado",
}
VACIAS = {"dolor", "de", "del", "la", "el", "en", "con", "y", "a", "por", "que", "se", "lo", "los", "las",
          "un", "una", "muy", "mucho", "intenso", "fuerte", "leve", "consulta", "paciente", "refiere"}


def _tokens(s):
    out = set()
    for w in re.sub(r"[^\w\s]", " ", norm(s)).split():
        if w in VACIAS or len(w) < 3:
            continue
        out.add(SINONIMOS.get(w, w)[:6])      # sinónimo y raíz corta: "derecho/derecha" -> "derech"
    return out


def texto_coincide(esperado, predicho) -> bool:
    """Coincidencia LAXA de texto libre: comparten al menos un concepto (tras sinónimos)."""
    a, b = _tokens(esperado), _tokens(predicho)
    if not a:
        return not b
    return bool(a & b)


def valores_coinciden(esperado, predicho, tipo: str, tolerancia: float = 0.0) -> bool:
    if tipo == "numero":
        a, b = a_numero(esperado), a_numero(predicho)
        return a is not None and b is not None and abs(a - b) <= tolerancia + 1e-9
    if tipo == "booleano":
        return bool(esperado) == bool(predicho)
    if tipo == "texto":
        return texto_coincide(esperado, predicho)
    return norm(esperado) == norm(predicho)          # categoría


# ------------------------------------------------------------------ 1. extracción

def comparar_campo(esperado, predicho, tipo, tolerancia=0.0) -> str:
    """Devuelve 'VP', 'FN', 'FP' (alucinación), 'ERR' (valor incorrecto) o 'VN'."""
    e, p = vacio(esperado), vacio(predicho)
    if e and p:
        return "VN"
    if e and not p:
        return "FP"
    if not e and p:
        return "FN"
    return "VP" if valores_coinciden(esperado, predicho, tipo, tolerancia) else "ERR"


def prf(vp, fp, fn):
    precision = vp / (vp + fp) if vp + fp else None
    recall = vp / (vp + fn) if vp + fn else None
    if precision is None or recall is None or precision + recall == 0:
        f1 = None if precision is None and recall is None else 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def resumir_extraccion(resultados):
    """resultados: lista de dicts {caso, campo, grupo, resultado('VP'|'FP'|'FN'|'ERR'|'VN')}.

    Devuelve métricas micro (todos los campos juntos), macro (promedio por campo),
    por campo y por grupo (estructurado / texto).
    ERR cuenta como FP y FN a la vez (estándar en extracción de entidades)."""
    def contar(filas):
        c = Counter(f["resultado"] for f in filas)
        vp, err = c["VP"], c["ERR"]
        fp, fn, vn = c["FP"] + err, c["FN"] + err, c["VN"]
        p, r, f1 = prf(vp, fp, fn)
        negativos = c["FP"] + vn                 # campos que debían quedar vacíos
        return {"vp": vp, "fp": fp, "fn": fn, "vn": vn, "valor_incorrecto": err,
                "alucinaciones": c["FP"], "precision": p, "recall": r, "f1": f1,
                "tasa_alucinacion": c["FP"] / negativos if negativos else None,
                "exactitud": (vp + vn) / len(filas) if filas else None, "n": len(filas)}

    por_campo = defaultdict(list)
    por_grupo = defaultdict(list)
    for f in resultados:
        por_campo[f["campo"]].append(f)
        por_grupo[f["grupo"]].append(f)
    campos = {k: contar(v) for k, v in sorted(por_campo.items())}
    f1s = [m["f1"] for m in campos.values() if m["f1"] is not None]
    return {"micro": contar(resultados),
            "macro_f1": sum(f1s) / len(f1s) if f1s else None,
            "por_grupo": {k: contar(v) for k, v in sorted(por_grupo.items())},
            "por_campo": campos}


# ------------------------------------------------------------------ 2. clasificación (color)

COLORES = ["ROJO", "NARANJA", "AMARILLO", "VERDE", "AZUL"]   # 0 = más urgente
NIVEL = {c: i for i, c in enumerate(COLORES)}


def normalizar_color(c):
    if c is None:
        return None
    c = norm(c).upper()
    return c if c in NIVEL else None


def matriz_confusion(reales, predichos, clases=COLORES):
    m = {r: {p: 0 for p in clases} for r in clases}
    for r, p in zip(reales, predichos):
        if r in m and p in m[r]:
            m[r][p] += 1
    return m


def metricas_por_clase(reales, predichos, clases=COLORES):
    out = {}
    for c in clases:
        vp = sum(1 for r, p in zip(reales, predichos) if r == c and p == c)
        fp = sum(1 for r, p in zip(reales, predichos) if r != c and p == c)
        fn = sum(1 for r, p in zip(reales, predichos) if r == c and p != c)
        p_, r_, f1 = prf(vp, fp, fn)
        out[c] = {"precision": p_, "recall": r_, "f1": f1, "soporte": vp + fn}
    return out


def kappa_cohen(reales, predichos, clases=COLORES, ponderacion: str | None = None):
    """Kappa de Cohen. ponderacion: None (nominal), 'lineal' o 'cuadratica' (escala ordinal,
    lo habitual para comparar triage con 5 niveles)."""
    n = len(reales)
    if n == 0:
        return None
    k = len(clases)
    idx = {c: i for i, c in enumerate(clases)}

    def peso(i, j):
        if ponderacion == "lineal":
            return abs(i - j) / (k - 1)
        if ponderacion == "cuadratica":
            return ((i - j) / (k - 1)) ** 2
        return 0.0 if i == j else 1.0

    obs = [[0] * k for _ in range(k)]
    for r, p in zip(reales, predichos):
        obs[idx[r]][idx[p]] += 1
    fila = [sum(obs[i]) for i in range(k)]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    d_obs = sum(peso(i, j) * obs[i][j] for i in range(k) for j in range(k)) / n
    d_esp = sum(peso(i, j) * fila[i] * col[j] for i in range(k) for j in range(k)) / (n * n)
    if d_esp == 0:
        return 1.0 if d_obs == 0 else 0.0
    return 1 - d_obs / d_esp


def sub_sobre_triage(reales, predichos):
    """Subtriage = el sistema asigna MENOS urgencia que la referencia (el error peligroso).
    Sobretriage = asigna MÁS urgencia (consume recursos, pero es seguro)."""
    n = len(reales)
    sub = [(r, p) for r, p in zip(reales, predichos) if NIVEL[p] > NIVEL[r]]
    sobre = [(r, p) for r, p in zip(reales, predichos) if NIVEL[p] < NIVEL[r]]
    graves = [i for i, r in enumerate(reales) if NIVEL[r] <= NIVEL["NARANJA"]]
    graves_ok = [i for i in graves if NIVEL[predichos[i]] <= NIVEL["NARANJA"]]
    return {
        "n": n,
        "exactitud": sum(1 for r, p in zip(reales, predichos) if r == p) / n if n else None,
        "subtriage": len(sub) / n if n else None,
        "sobretriage": len(sobre) / n if n else None,
        "subtriage_2_o_mas_niveles": sum(1 for r, p in sub if NIVEL[p] - NIVEL[r] >= 2) / n if n else None,
        # sensibilidad para alta prioridad: de los ROJO/NARANJA reales, cuántos quedaron en ROJO/NARANJA
        "recall_alta_prioridad": len(graves_ok) / len(graves) if graves else None,
        "casos_alta_prioridad": len(graves),
    }


def evaluar_clasificacion(reales, predichos):
    pares = [(normalizar_color(r), normalizar_color(p)) for r, p in zip(reales, predichos)]
    pares = [(r, p) for r, p in pares if r and p]
    R = [r for r, _ in pares]
    P = [p for _, p in pares]
    return {"resumen": sub_sobre_triage(R, P),
            "kappa": kappa_cohen(R, P),
            "kappa_lineal": kappa_cohen(R, P, ponderacion="lineal"),
            "kappa_cuadratica": kappa_cohen(R, P, ponderacion="cuadratica"),
            "por_color": metricas_por_clase(R, P),
            "matriz": matriz_confusion(R, P)}


def interpretar_kappa(k):
    """Escala de Landis y Koch (1977)."""
    if k is None:
        return "—"
    for lim, txt in ((0, "pobre"), (0.20, "leve"), (0.40, "aceptable"), (0.60, "moderada"),
                     (0.80, "considerable")):
        if k <= lim:
            return txt
    return "casi perfecta"


# ------------------------------------------------------------------ 3. detección de errores

def evaluar_deteccion(filas):
    """filas: [{"debe_rechazar": bool, "rechazado": bool, "mensaje_ok": bool}]
    Positivo = 'el dato tiene un error y debe rechazarse'."""
    vp = sum(1 for f in filas if f["debe_rechazar"] and f["rechazado"])
    fn = sum(1 for f in filas if f["debe_rechazar"] and not f["rechazado"])
    fp = sum(1 for f in filas if not f["debe_rechazar"] and f["rechazado"])
    vn = sum(1 for f in filas if not f["debe_rechazar"] and not f["rechazado"])
    p, r, f1 = prf(vp, fp, fn)
    con_error = [f for f in filas if f["debe_rechazar"] and f["rechazado"]]
    return {"vp": vp, "fp": fp, "fn": fn, "vn": vn, "precision": p, "recall": r, "f1": f1,
            "especificidad": vn / (vn + fp) if vn + fp else None,
            "mensaje_correcto": (sum(1 for f in con_error if f.get("mensaje_ok")) / len(con_error)
                                 if con_error else None)}


# ------------------------------------------------------------------ 4. voz

def wer(referencia: str, hipotesis: str) -> dict:
    """Word Error Rate = (sustituciones + borrados + inserciones) / palabras de la referencia.
    Se normaliza (minúsculas, sin acentos ni puntuación) antes de comparar."""
    def palabras(s):
        return re.sub(r"[^\w\s]", " ", norm(s)).split()
    r, h = palabras(referencia), palabras(hipotesis)
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            costo = 0 if r[i - 1] == h[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + costo)
    # reconstrucción para separar S / D / I
    i, j, S, D, I = len(r), len(h), 0, 0, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (r[i - 1] != h[j - 1]):
            S += r[i - 1] != h[j - 1]
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            D, i = D + 1, i - 1
        else:
            I, j = I + 1, j - 1
    n = len(r)
    return {"wer": (S + D + I) / n if n else (0.0 if not h else 1.0),
            "sustituciones": S, "borrados": D, "inserciones": I, "palabras_referencia": n}


# ------------------------------------------------------------------ 5. estadística

def wilson(aciertos: int, n: int, z: float = 1.96):
    """Intervalo de confianza 95 % de una proporción (Wilson): correcto aun con pocos casos."""
    if n == 0:
        return None, None
    p = aciertos / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centro - margen), min(1.0, centro + margen)


def bootstrap(items, estadistico, repeticiones=2000, semilla=42, alfa=0.05):
    """IC por bootstrap por CASO (se remuestrean casos, no campos). Devuelve (inf, sup)."""
    if not items:
        return None, None
    rnd = random.Random(semilla)
    valores = []
    for _ in range(repeticiones):
        muestra = [items[rnd.randrange(len(items))] for _ in items]
        v = estadistico(muestra)
        if v is not None:
            valores.append(v)
    if not valores:
        return None, None
    valores.sort()
    lo = valores[int(alfa / 2 * len(valores))]
    hi = valores[min(len(valores) - 1, int((1 - alfa / 2) * len(valores)))]
    return lo, hi


def percentil(valores, q):
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    k = (len(v) - 1) * q / 100
    f, c = math.floor(k), math.ceil(k)
    return v[f] if f == c else v[f] + (v[c] - v[f]) * (k - f)


def resumen_tiempos(valores):
    v = [x for x in valores if x is not None]
    if not v:
        return {"n": 0}
    return {"n": len(v), "media": sum(v) / len(v), "p50": percentil(v, 50),
            "p90": percentil(v, 90), "p95": percentil(v, 95), "max": max(v)}
