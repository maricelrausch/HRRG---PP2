"""backend/evaluacion/reglas_seguridad.py · Copia en Python de reglas() de frontend/sugerencia.js.

Sirve para evaluar el COLOR FINAL que ve enfermería (piso de seguridad + sugerencia de MedGemma)
sin abrir el navegador. Mismos umbrales PROVISORIOS que el JS: si se cambian allá, cambiarlos acá
(tests/test_metricas.py tiene casos que avisan si se desalinean).

Nivel: 0 = ROJO, 1 = NARANJA, 2 = AMARILLO, 3 = VERDE, 4 = AZUL. None = ninguna regla se activó.
"""
from .metricas import COLORES, a_numero


def reglas(d: dict) -> list[tuple[int, str]]:
    n = lambda k: a_numero(d.get(k))           # noqa: E731
    out = []
    # Neurológico
    if d.get("br_convulsion"):
        out.append((0, "Convulsión activa"))
    g = n("glasgow")
    if g is not None and g <= 8:
        out.append((0, f"Glasgow {g:g}"))
    elif (d.get("estado_conciencia") and d.get("estado_conciencia") != "Alerta") or (g is not None and g < 15):
        out.append((1, "Alteración del nivel de conciencia"))
    # Respiratorio
    sat, fr = n("saturacion_o2"), n("frecuencia_respiratoria")
    if (sat is not None and sat < 90) or (fr is not None and (fr > 30 or fr < 8)) or d.get("br_disnea"):
        out.append((1, "Posible compromiso respiratorio"))
    # Circulatorio
    tas, fc = n("ta_sistolica"), n("frecuencia_cardiaca")
    hipo = tas is not None and tas < 90
    fc_alt = fc is not None and (fc > 130 or fc < 40)
    if d.get("br_sangrado") and hipo:
        out.append((0, "Sangrado con hipotensión"))
    else:
        if d.get("br_sangrado"):
            out.append((1, "Sangrado evidente"))
        if hipo or fc_alt:
            out.append((1, "Compromiso circulatorio"))
    # Otros
    t = n("temperatura")
    if d.get("ant_inmuno") and t is not None and t >= 38:
        out.append((1, "Fiebre en inmunosuprimido"))
    dolor = n("dolor_intensidad")
    if dolor is not None and dolor >= 8:
        out.append((1, "Dolor intenso"))
    return out


def nivel_reglas(d: dict):
    r = reglas(d)
    return min(lv for lv, _ in r) if r else None


def color_final(datos: dict, color_ia: str | None):
    """El color final nunca es menos urgente que lo que fijan las reglas."""
    lv_ia = COLORES.index(color_ia) if color_ia in COLORES else None
    lv_r = nivel_reglas(datos)
    candidatos = [x for x in (lv_ia, lv_r) if x is not None]
    if not candidatos:
        return None, False
    fin = min(candidatos)
    intervino = lv_r is not None and (lv_ia is None or lv_r < lv_ia)
    return COLORES[fin], intervino
