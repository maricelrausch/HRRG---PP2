"""backend/evaluacion/reglas_seguridad.py · Piso de seguridad para la evaluación sin navegador.

[Dario 29/10 · Etapa B] Antes este archivo tenía los umbrales escritos a mano (copia de reglas() de
frontend/sugerencia.js). Ahora lee las MISMAS reglas que se cargan en la base
(backend/datos/reglas_semilla.json) y las evalúa igual que frontend/js/motor_reglas.js:
  - "todas" / "alguna" de las condiciones;
  - un dato que falta NUNCA cumple una condición;
  - la PAM se calcula con la TA si no viene cargada.
Así no hay umbrales repetidos en el código. tests/test_reglas_semilla.py comprueba que da los mismos
colores que la versión anterior.

Nivel: 0 = ROJO, 1 = NARANJA, 2 = AMARILLO, 3 = VERDE. None = ninguna regla se activó.
"""
import json
from functools import lru_cache
from pathlib import Path

from .metricas import COLORES

RUTA_SEMILLA = Path(__file__).resolve().parent.parent / "datos" / "reglas_semilla.json"
NIVEL = {"ROJO": 0, "NARANJA": 1, "AMARILLO": 2, "VERDE": 3}


@lru_cache(maxsize=1)
def reglas_semilla() -> tuple:
    """Las reglas de la semilla que arrancan ACTIVAS (las de tanda 2 arrancan en borrador: no intervienen)."""
    with open(RUTA_SEMILLA, encoding="utf-8") as archivo:
        return tuple(r for r in json.load(archivo)["reglas"] if r.get("estado_inicial") != "borrador")


def _numero(v):
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        n = float(str(v).strip().replace(",", "."))
    except ValueError:
        return None
    return n if n == n and n not in (float("inf"), float("-inf")) else None


GRUPOS_ETARIOS = [("Lactante", 0, 0), ("Niño", 1, 11), ("Adolescente", 12, 17),
                  ("Adulto", 18, 64), ("Adulto mayor", 65, 200)]   # mismos cortes que src/reglas_hospital.py


def grupo_etario(edad):
    a = _numero(edad)
    if a is None or a < 0:
        return None
    return next((n for n, mn, mx in GRUPOS_ETARIOS if mn <= a < mx + 1), None)


def _valor(d: dict, campo: str):
    if campo == "grupo_etario":
        return d.get("grupo_etario") or grupo_etario(d.get("edad"))
    if campo == "pam":
        p = _numero(d.get("pam"))
        if p is not None:
            return p
        s, di = _numero(d.get("ta_sistolica")), _numero(d.get("ta_diastolica"))
        return round((s + 2 * di) / 3) if s is not None and di is not None else None
    return d.get(campo)


_OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b, "=": lambda a, b: a == b, "!=": lambda a, b: a != b}


def cumple(cond: dict, d: dict) -> bool:
    v, op = _valor(d, cond["campo"]), cond["operador"]
    if op in _OPS:
        a, b = _numero(v), _numero(cond.get("valor"))
        return a is not None and b is not None and _OPS[op](a, b)
    if op == "es":
        return v == cond.get("valor")
    if op == "no_es":
        return v not in (None, "") and v != cond.get("valor")
    if op == "si":
        return v is True
    if op == "no":
        return v is False
    return False


def reglas(d: dict, lista=None) -> list[tuple[int, str]]:
    """Reglas que se cumplen como (nivel, explicación), de la más urgente a la menos urgente."""
    out = []
    for r in (reglas_semilla() if lista is None else lista):
        conds = r.get("condiciones") or []
        if not conds or r.get("color") not in NIVEL:
            continue
        ok = any(cumple(c, d) for c in conds) if r.get("combinacion") == "alguna" else all(cumple(c, d) for c in conds)
        if ok:
            out.append((NIVEL[r["color"]], r["explicacion"]))
    return sorted(out, key=lambda x: x[0])


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
