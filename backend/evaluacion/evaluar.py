"""backend/evaluacion/evaluar.py · Evaluación reproducible del prototipo IngenIA Salud – Triage.

Uso (desde la carpeta backend, con el venv activado; Ollama corriendo para las suites con IA):

    python -m evaluacion.evaluar validacion                 # sin IA, tarda segundos
    python -m evaluacion.evaluar extraccion                 # MedGemma sobre los casos CF
    python -m evaluacion.evaluar extraccion --repeticiones 3   # además mide consistencia
    python -m evaluacion.evaluar triage                     # color IA y color final (con reglas)
    python -m evaluacion.evaluar voz                        # WER de Whisper (audios en evaluacion/audios)
    python -m evaluacion.evaluar todo --repeticiones 3
    python -m evaluacion.evaluar extraccion triage --repeticiones 3   # varias suites juntas

Opciones:
    --motor unificada | medgemma | simulado
          unificada = src.extraccion.extraer_datos (/api/extraer, la que usa formulario.js)  [por defecto]
          medgemma  = ia.medgemma.extraer (/api/analizar; la pantalla actual no la usa)
          simulado  = devuelve lo esperado (prueba que el script funciona; da 100 %)
    --repeticiones N   corre cada caso N veces (consistencia y tiempos más estables)
    --etiqueta TEXTO   nombre corto para la carpeta de resultados (ej. "whisper-base")

Salida: evaluacion/resultados/<fecha>_<suite>[_etiqueta]/
    reporte.md          tablas listas para el informe
    resultados.json     todo (para comparar corridas)
    detalle_*.csv       caso por caso, para revisar errores

Los casos son FICTICIOS (datos/casos_simulados.json). Los colores de la maqueta NO tienen
validez clínica: las métricas de triage son técnicas hasta tener referencia del HRRG
(cargarla en evaluacion/referencia_triage.json, ver README).
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from importlib import metadata
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from evaluacion import metricas as M                       # noqa: E402
from evaluacion import reglas_seguridad as RS              # noqa: E402

CASOS = BACKEND / "datos" / "casos_simulados.json"
REFERENCIA_TRIAGE = Path(__file__).with_name("referencia_triage.json")
AUDIOS = Path(__file__).with_name("audios")
RESULTADOS = Path(__file__).with_name("resultados")

# Campos que se evalúan en la extracción: tipo de comparación, tolerancia y grupo
CAMPOS = {
    "edad":                    ("numero", 0, "estructurado"),
    "motivo_categoria":        ("categoria", 0, "estructurado"),
    "tiempo_evolucion_valor":  ("numero", 0, "estructurado"),
    "tiempo_evolucion_unidad": ("categoria", 0, "estructurado"),
    "temperatura":             ("numero", 0.1, "estructurado"),
    "dolor_intensidad":        ("numero", 0, "estructurado"),
    "frecuencia_cardiaca":     ("numero", 0, "estructurado"),
    "frecuencia_respiratoria": ("numero", 0, "estructurado"),
    "saturacion_o2":           ("numero", 0, "estructurado"),
    "estado_conciencia":       ("categoria", 0, "estructurado"),
    "br_sangrado":             ("booleano", 0, "estructurado"),
    "motivo_consulta":         ("texto", 0, "texto"),
    "dolor_localizacion":      ("texto", 0, "texto"),
}

# Metas de aceptación (provisorias: se acuerdan con el equipo y el docente)
METAS = {
    "validacion.recall":                (">=", 1.00, "Detecta todos los datos con error"),
    "validacion.especificidad":         (">=", 1.00, "No rechaza datos correctos"),
    "extraccion.f1_estructurado":       (">=", 0.90, "F1 de campos estructurados"),
    "extraccion.tasa_alucinacion":      ("<=", 0.02, "Datos inventados sobre campos que debían quedar vacíos"),
    "extraccion.fallos":                ("<=", 0.00, "Respuestas sin JSON válido / errores"),
    "extraccion.consistencia":          (">=", 0.90, "Misma salida al repetir el caso"),
    "extraccion.p95_segundos":          ("<=", 30.0, "Tiempo de extracción (p95) en la PC de prueba"),
    "triage.recall_alta_prioridad":     (">=", 1.00, "Ningún ROJO/NARANJA clasificado como menos urgente"),
    "triage.subtriage":                 ("<=", 0.05, "Casos con color menos urgente que la referencia"),
    "triage.kappa_lineal":              (">=", 0.60, "Concordancia ponderada con la referencia"),
    "voz.wer":                          ("<=", 0.15, "Error de palabras del dictado"),
}


# ================================================================= utilidades

def cargar_casos():
    return json.loads(CASOS.read_text(encoding="utf-8"))


def entorno(motor: str) -> dict:
    info = {"fecha": datetime.now().isoformat(timespec="seconds"), "motor": motor,
            "python": platform.python_version(), "sistema": platform.platform(),
            "procesador": platform.processor() or platform.machine()}
    try:
        info["commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND,
                                        capture_output=True, text=True, timeout=5).stdout.strip()
        info["rama"] = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=BACKEND,
                                      capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        pass
    paquetes = {}
    for p in ("flask", "ollama", "pydantic", "faster-whisper", "ctranslate2", "chromadb", "numpy"):
        try:
            paquetes[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            pass
    info["paquetes"] = paquetes
    return info


def info_modelo(nombre: str) -> dict:
    try:
        import ollama
        s = ollama.show(nombre)
        det = getattr(s, "details", None) or s.get("details", {})
        get = (lambda k: getattr(det, k, None)) if not isinstance(det, dict) else det.get
        return {"modelo": nombre, "parametros": get("parameter_size"),
                "cuantizacion": get("quantization_level"), "familia": get("family")}
    except Exception as e:
        return {"modelo": nombre, "aviso": f"no se pudo consultar Ollama: {type(e).__name__}"}


def pct(x, dec=1):
    return "—" if x is None else f"{100 * x:.{dec}f} %"


def num(x, dec=2):
    return "—" if x is None else f"{x:.{dec}f}"


def chequear(clave, valor):
    if clave not in METAS or valor is None:
        return "—"
    op, meta, _ = METAS[clave]
    ok = valor >= meta - 1e-9 if op == ">=" else valor <= meta + 1e-9
    return "✅" if ok else "❌"


def ic(lo_hi):
    lo, hi = lo_hi
    return "—" if lo is None else f"{100 * lo:.0f}–{100 * hi:.0f} %"


def escribir_csv(ruta, filas):
    if not filas:
        return
    claves = list(dict.fromkeys(k for f in filas for k in f))
    with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:      # utf-8-sig: Excel lo abre bien
        w = csv.DictWriter(fh, fieldnames=claves, delimiter=";")
        w.writeheader()
        w.writerows(filas)


# ================================================================= motores de extracción

def obtener_motor(nombre: str):
    from src.esquemas import ALIAS

    def renombrar(d):
        return {ALIAS.get(k, k): v for k, v in (d or {}).items() if not str(k).startswith("_")}

    if nombre == "medgemma":
        from ia import medgemma as ia
        return (lambda texto, caso: renombrar(ia.extraer(texto))), ia.MODELO
    if nombre == "unificada":
        from src import extraccion as ex
        return (lambda texto, caso: renombrar(ex.extraer_datos(texto))), ex.LLM_MODEL
    if nombre == "simulado":
        def eco(texto, caso):
            d = {k: None for k in CAMPOS}
            d.update(caso["esperado_extraccion"])
            return d
        return eco, "simulado"
    raise SystemExit(f"Motor desconocido: {nombre}")


# ================================================================= suite 1: validación (sin IA)

def suite_validacion(casos):
    from src.validacion import validar
    filas, det = [], []
    for c in casos["casos"]:
        esp = c["esperado"]
        r = validar(c["entrada"])
        debe = not esp["valido"]
        rechazado = not r["valido"]
        texto_err = " | ".join(r["errores"])
        mensaje_ok = all(t.lower() in texto_err.lower() for t in esp.get("errores_contienen", []))
        falt_ok = (sorted(r["faltantes"]) == sorted(esp["faltantes"])) if "faltantes" in esp and r["valido"] else None
        pam_ok = None
        if "pam" in esp and r["valido"]:
            from src.esquemas import DatosTriage
            pam_ok = DatosTriage.model_validate(c["entrada"]).pam == esp["pam"]
        filas.append({"debe_rechazar": debe, "rechazado": rechazado, "mensaje_ok": mensaje_ok})
        det.append({"caso": c["id"], "tipo": c["tipo"], "debe_rechazar": debe, "rechazado": rechazado,
                    "correcto": debe == rechazado, "mensaje_ok": mensaje_ok if rechazado else "",
                    "faltantes_ok": "" if falt_ok is None else falt_ok,
                    "pam_ok": "" if pam_ok is None else pam_ok, "errores": texto_err})
    m = M.evaluar_deteccion(filas)
    fal = [d["faltantes_ok"] for d in det if d["faltantes_ok"] != ""]
    pam = [d["pam_ok"] for d in det if d["pam_ok"] != ""]
    m["faltantes_correctos"] = sum(fal) / len(fal) if fal else None
    m["pam_correcta"] = sum(pam) / len(pam) if pam else None
    m["n"] = len(filas)
    return m, det


def md_validacion(m):
    return "\n".join([
        "## 1. Validación de datos (sin IA)", "",
        f"Casos: {m['n']} (E = con error, deben rechazarse; D/F/A = válidos, deben aceptarse).", "",
        "| Métrica | Valor | Meta |", "|---|---|---|",
        f"| Recall (errores detectados) | {pct(m['recall'])} | {chequear('validacion.recall', m['recall'])} |",
        f"| Precisión (rechazos justificados) | {pct(m['precision'])} | |",
        f"| Especificidad (válidos aceptados) | {pct(m['especificidad'])} | {chequear('validacion.especificidad', m['especificidad'])} |",
        f"| F1 | {pct(m['f1'])} | |",
        f"| Mensaje de error señala el campo correcto | {pct(m['mensaje_correcto'])} | |",
        f"| Faltantes informados correctamente | {pct(m['faltantes_correctos'])} | |",
        f"| PAM calculada correctamente | {pct(m['pam_correcta'])} | |",
        f"| VP / FP / FN / VN | {m['vp']} / {m['fp']} / {m['fn']} / {m['vn']} | |", ""])


# ================================================================= suite 2: extracción

def suite_extraccion(casos, motor_nombre, repeticiones):
    motor, modelo = obtener_motor(motor_nombre)
    filas, det, tiempos, fallos, salidas = [], [], [], 0, {}
    campos_motor = None
    lista = casos["casos_extraccion"]
    total = len(lista) * repeticiones
    k = 0
    for rep in range(repeticiones):
        for c in lista:
            k += 1
            print(f"  [{k}/{total}] {c['id']} (repetición {rep + 1})", flush=True)
            t0 = time.perf_counter()
            try:
                pred = motor(c["texto"], c)
                error = ""
            except Exception as e:                       # JSON roto, Ollama caído, etc.
                pred, error = None, f"{type(e).__name__}: {str(e)[:150]}"
            seg = time.perf_counter() - t0
            tiempos.append(seg)
            if pred is None:
                fallos += 1
                det.append({"caso": c["id"], "repeticion": rep + 1, "campo": "(todo)",
                            "resultado": "FALLO", "esperado": "", "predicho": error, "segundos": round(seg, 2)})
                continue
            if campos_motor is None:
                campos_motor = [f for f in CAMPOS if f in pred]
            salidas.setdefault(c["id"], []).append({f: pred.get(f) for f in campos_motor})
            esperado = c["esperado_extraccion"]
            for campo in campos_motor:
                tipo, tol, grupo = CAMPOS[campo]
                e = esperado.get(campo)                      # lo que no figura debe quedar vacío
                p = pred.get(campo)
                res = M.comparar_campo(e, p, tipo, tol)
                filas.append({"caso": c["id"], "rep": rep, "campo": campo, "grupo": grupo, "resultado": res})
                det.append({"caso": c["id"], "repeticion": rep + 1, "campo": campo, "resultado": res,
                            "esperado": "" if e is None else e, "predicho": "" if p is None else p,
                            "segundos": round(seg, 2)})

    resumen = M.resumir_extraccion(filas) if filas else {}
    # IC 95 % por bootstrap remuestreando CASOS
    por_caso = {}
    for f in filas:
        por_caso.setdefault((f["caso"], f["rep"]), []).append(f)
    bloques = list(por_caso.values())

    def f1_de(muestra, grupo=None):
        fs = [f for b in muestra for f in b if grupo is None or f["grupo"] == grupo]
        return M.resumir_extraccion(fs)["micro"]["f1"] if fs else None

    def aluc_de(muestra):
        fs = [f for b in muestra for f in b]
        return M.resumir_extraccion(fs)["micro"]["tasa_alucinacion"] if fs else None

    consist = None
    if repeticiones > 1 and salidas:
        iguales = [all(s == v[0] for s in v[1:]) for v in salidas.values() if len(v) > 1]
        consist = sum(iguales) / len(iguales) if iguales else None

    out = {"modelo": modelo, "motor": motor_nombre, "repeticiones": repeticiones,
           "casos": len(lista), "campos_evaluados": campos_motor or [],
           "campos_no_evaluados": [f for f in CAMPOS if f not in (campos_motor or [])],
           "fallos": fallos, "tasa_fallos": fallos / total if total else None,
           "consistencia": consist, "tiempos": M.resumen_tiempos(tiempos), **resumen}
    if bloques:
        out["ic95_f1_micro"] = M.bootstrap(bloques, f1_de)
        out["ic95_f1_estructurado"] = M.bootstrap(bloques, lambda b: f1_de(b, "estructurado"))
        out["ic95_alucinacion"] = M.bootstrap(bloques, aluc_de)
    return out, det


def md_extraccion(m):
    if not m.get("micro"):
        return "## 2. Extracción\n\nNo hubo resultados (¿Ollama corriendo?).\n"
    mi, g = m["micro"], m["por_grupo"]
    est, txt = g.get("estructurado", {}), g.get("texto", {})
    t = m["tiempos"]
    l = ["## 2. Extracción del relato", "",
         f"Motor: `{m['motor']}` · modelo `{m['modelo']}` · {m['casos']} casos × {m['repeticiones']} repeticiones.",
         f"Campos evaluados: {', '.join(m['campos_evaluados'])}.",
         (f"No evaluados (el motor no los devuelve): {', '.join(m['campos_no_evaluados'])}." if m["campos_no_evaluados"] else ""),
         "", "| Métrica | Valor | IC 95 % | Meta |", "|---|---|---|---|",
         f"| Precisión (micro) | {pct(mi['precision'])} | | |",
         f"| Recall (micro) | {pct(mi['recall'])} | | |",
         f"| F1 (micro) | {pct(mi['f1'])} | {ic(m.get('ic95_f1_micro', (None, None)))} | |",
         f"| F1 (macro, promedio por campo) | {pct(m['macro_f1'])} | | |",
         f"| F1 campos estructurados | {pct(est.get('f1'))} | {ic(m.get('ic95_f1_estructurado', (None, None)))} | {chequear('extraccion.f1_estructurado', est.get('f1'))} |",
         f"| F1 texto libre (comparación laxa) | {pct(txt.get('f1'))} | | |",
         f"| Tasa de alucinación | {pct(mi['tasa_alucinacion'])} | {ic(m.get('ic95_alucinacion', (None, None)))} | {chequear('extraccion.tasa_alucinacion', mi['tasa_alucinacion'])} |",
         f"| Valores incorrectos (dato presente pero mal leído) | {mi['valor_incorrecto']} | | |",
         f"| Fallos (sin JSON / error) | {m['fallos']} ({pct(m['tasa_fallos'])}) | | {chequear('extraccion.fallos', m['tasa_fallos'])} |",
         f"| Consistencia entre repeticiones | {pct(m['consistencia'])} | | {chequear('extraccion.consistencia', m['consistencia'])} |",
         f"| Tiempo por relato: media / p50 / p95 | {num(t.get('media'), 1)} / {num(t.get('p50'), 1)} / {num(t.get('p95'), 1)} s | | {chequear('extraccion.p95_segundos', t.get('p95'))} |",
         "", "### Por campo", "",
         "| Campo | Precisión | Recall | F1 | Alucinaciones | Mal leídos |", "|---|---|---|---|---|---|"]
    for campo, c in m["por_campo"].items():
        l.append(f"| {campo} | {pct(c['precision'], 0)} | {pct(c['recall'], 0)} | {pct(c['f1'], 0)} | "
                 f"{c['alucinaciones']} | {c['valor_incorrecto']} |")
    l.append("")
    return "\n".join(l)


# ================================================================= suite 3: triage

def casos_triage(casos):
    """Casos con color de referencia: maqueta (D), CF con color_esperado y referencia del HRRG."""
    out = []
    for c in casos["casos"]:
        if c.get("nivel_maqueta"):
            out.append({"id": c["id"], "origen": "maqueta (sin validez clínica)", "relato": c.get("relato", ""),
                        "datos": c["entrada"], "referencia": c["nivel_maqueta"]})
    for c in casos["casos_extraccion"]:
        if c.get("color_esperado"):
            out.append({"id": c["id"], "origen": "guía (C07)", "relato": c["texto"],
                        "datos": None, "referencia": c["color_esperado"]})
    if REFERENCIA_TRIAGE.exists():
        for c in json.loads(REFERENCIA_TRIAGE.read_text(encoding="utf-8")):
            out.append({"id": c["id"], "origen": c.get("origen", "referencia HRRG"), "relato": c.get("relato", ""),
                        "datos": c.get("datos"), "referencia": c["color_referencia"]})
    return out


def suite_triage(casos, motor_nombre):
    from src.validacion import validar
    lista = casos_triage(casos)
    if motor_nombre == "simulado":
        sugerir = lambda datos, relato: {"color": None}          # noqa: E731
        extraer = None
    else:
        from ia import medgemma as ia
        sugerir, extraer = ia.sugerir, ia.extraer
    det, reales, col_ia, col_fin, tiempos = [], [], [], [], []
    for i, c in enumerate(lista, 1):
        print(f"  [{i}/{len(lista)}] {c['id']}", flush=True)
        datos = c["datos"]
        if datos is None and extraer:                              # solo relato: se extrae primero
            datos = extraer(c["relato"])
        v = validar(datos or {})
        datos_ok = v["datos"] or {}
        t0 = time.perf_counter()
        try:
            r = sugerir(datos_ok, c["relato"])
            color = M.normalizar_color(r.get("color"))
            err = ""
        except Exception as e:
            color, err = None, f"{type(e).__name__}: {str(e)[:120]}"
        tiempos.append(time.perf_counter() - t0)
        final, intervino = RS.color_final(datos_ok, color)
        ref = M.normalizar_color(c["referencia"])
        reales.append(ref)
        col_ia.append(color)
        col_fin.append(final)
        det.append({"caso": c["id"], "origen": c["origen"], "referencia": ref, "color_ia": color or "",
                    "color_final": final or "", "regla_intervino": intervino,
                    "reglas": "; ".join(t for _, t in RS.reglas(datos_ok)), "error": err})
    out = {"n": len(lista),
           "origenes": sorted({c["origen"] for c in lista}),
           "ia": M.evaluar_clasificacion(reales, col_ia),
           "final": M.evaluar_clasificacion(reales, col_fin),
           "intervencion_reglas": (sum(d["regla_intervino"] for d in det) / len(det)) if det else None,
           "tiempos": M.resumen_tiempos(tiempos)}
    return out, det


def md_triage(m):
    l = ["## 3. Color de triage", "",
         f"Casos: {m['n']} · referencia: {', '.join(m['origenes']) or '—'}.", "",
         "> Mientras la referencia sea la maqueta, estas cifras miden coherencia técnica, **no** desempeño clínico.", "",
         "| Métrica | MedGemma sola | Final (con reglas de seguridad) | Meta |", "|---|---|---|---|"]
    for nombre, clave, fmt in (("Exactitud", "exactitud", pct), ("Subtriage", "subtriage", pct),
                               ("Subtriage de 2 o más niveles", "subtriage_2_o_mas_niveles", pct),
                               ("Sobretriage", "sobretriage", pct),
                               ("Recall alta prioridad (ROJO+NARANJA)", "recall_alta_prioridad", pct)):
        a, b = m["ia"]["resumen"].get(clave), m["final"]["resumen"].get(clave)
        l.append(f"| {nombre} | {fmt(a)} | {fmt(b)} | {chequear('triage.' + clave, b)} |")
    for nombre, clave in (("Kappa de Cohen", "kappa"), ("Kappa ponderado lineal", "kappa_lineal"),
                          ("Kappa ponderado cuadrático", "kappa_cuadratica")):
        a, b = m["ia"][clave], m["final"][clave]
        l.append(f"| {nombre} | {num(a)} ({M.interpretar_kappa(a)}) | {num(b)} ({M.interpretar_kappa(b)}) | "
                 f"{chequear('triage.' + clave, b)} |")
    l += [f"| Casos donde la regla subió el color | | {pct(m['intervencion_reglas'])} | |",
          f"| Tiempo de sugerencia p95 | {num(m['tiempos'].get('p95'), 1)} s | | |", "",
          "### Matriz de confusión (final) · filas = referencia, columnas = sistema", "",
          "| | " + " | ".join(M.COLORES) + " |", "|---" * (len(M.COLORES) + 1) + "|"]
    for r in M.COLORES:
        l.append(f"| **{r}** | " + " | ".join(str(m["final"]["matriz"][r][p]) for p in M.COLORES) + " |")
    l += ["", "### Por color (final)", "", "| Color | Precisión | Recall | F1 | Casos |", "|---|---|---|---|---|"]
    for c, v in m["final"]["por_color"].items():
        l.append(f"| {c} | {pct(v['precision'], 0)} | {pct(v['recall'], 0)} | {pct(v['f1'], 0)} | {v['soporte']} |")
    l.append("")
    return "\n".join(l)


# ================================================================= suite 4: voz

def suite_voz():
    audios = sorted(p for p in AUDIOS.glob("*") if p.suffix.lower() in (".wav", ".mp3", ".webm", ".m4a", ".ogg"))
    pares = [(a, a.with_suffix(".txt")) for a in audios if a.with_suffix(".txt").exists()]
    if not pares:
        return {"n": 0, "aviso": f"Sin audios con su .txt en {AUDIOS}"}, []
    from ia import transcripcion as tr
    det, refs, hips, tiempos, rtf = [], [], [], [], []
    for i, (a, t) in enumerate(pares, 1):
        print(f"  [{i}/{len(pares)}] {a.name}", flush=True)
        ref = t.read_text(encoding="utf-8").strip()
        t0 = time.perf_counter()
        hip, info = tr._transcribir(str(a))
        seg = time.perf_counter() - t0
        w = M.wer(ref, hip)
        dur = getattr(info, "duration", None)
        refs.append(ref)
        hips.append(hip)
        tiempos.append(seg)
        if dur:
            rtf.append(seg / dur)
        det.append({"audio": a.name, "wer": round(w["wer"], 3), "S": w["sustituciones"], "D": w["borrados"],
                    "I": w["inserciones"], "duracion_s": round(dur or 0, 1), "demora_s": round(seg, 2),
                    "referencia": ref, "transcripcion": hip})
    total = M.wer(" ".join(refs), " ".join(hips))           # WER global (ponderado por palabras)
    return {"n": len(pares), "modelo": tr.MODELO_WHISPER, "beam": tr.BEAM, "hilos": tr.HILOS,
            "wer": total["wer"], "detalle_wer": total, "tiempos": M.resumen_tiempos(tiempos),
            "rtf_medio": sum(rtf) / len(rtf) if rtf else None}, det


def md_voz(m):
    if not m.get("n"):
        return f"## 4. Dictado por voz\n\n{m.get('aviso', 'Sin datos')}\n"
    t = m["tiempos"]
    return "\n".join([
        "## 4. Dictado por voz (Whisper)", "",
        f"Modelo `{m['modelo']}` · beam {m['beam']} · {m['hilos']} hilos · {m['n']} audios.", "",
        "| Métrica | Valor | Meta |", "|---|---|---|",
        f"| WER global | {pct(m['wer'])} | {chequear('voz.wer', m['wer'])} |",
        f"| Sustituciones / borrados / inserciones | {m['detalle_wer']['sustituciones']} / "
        f"{m['detalle_wer']['borrados']} / {m['detalle_wer']['inserciones']} | |",
        f"| Demora media / p95 | {num(t.get('media'), 1)} / {num(t.get('p95'), 1)} s | |",
        f"| Factor de tiempo real (demora ÷ duración) | {num(m['rtf_medio'])} | <1 = más rápido que hablar |", ""])


# ================================================================= principal

def main(argv=None):
    ap = argparse.ArgumentParser(description="Evaluación del prototipo IngenIA Salud – Triage")
    ap.add_argument("suite", nargs="+", choices=["validacion", "extraccion", "triage", "voz", "todo"],
                    help="una o varias: validacion extraccion triage voz | todo")
    ap.add_argument("--motor", default="unificada", choices=["unificada", "medgemma", "simulado"])
    ap.add_argument("--repeticiones", type=int, default=1)
    ap.add_argument("--etiqueta", default="")
    ap.add_argument("--salida", default=str(RESULTADOS))
    a = ap.parse_args(argv)

    casos = cargar_casos()
    orden = ["validacion", "extraccion", "triage", "voz"]
    suites = orden if "todo" in a.suite else [s for s in orden if s in a.suite]
    nombre = (datetime.now().strftime("%Y-%m-%d_%H%M") + "_" + ("todo" if "todo" in a.suite else "-".join(suites))
              + (f"_{a.etiqueta}" if a.etiqueta else ""))
    carpeta = Path(a.salida) / nombre
    carpeta.mkdir(parents=True, exist_ok=True)

    env = entorno(a.motor)
    if a.motor != "simulado" and any(s in suites for s in ("extraccion", "triage")):
        env["modelo_llm"] = info_modelo(obtener_motor(a.motor)[1])
    resultados = {"entorno": env, "metas": METAS}
    md = [f"# Evaluación · IngenIA Salud – Triage", "",
          f"Fecha: {env['fecha']} · commit `{env.get('commit', '—')}` ({env.get('rama', '—')}) · "
          f"Python {env['python']} · {env['sistema']}", "",
          "Paquetes: " + ", ".join(f"{k} {v}" for k, v in env["paquetes"].items()), "",
          "Casos **ficticios** de `datos/casos_simulados.json` "
          f"(versión {casos.get('version', '—')}, {casos.get('fecha', '—')}).", ""]
    if "modelo_llm" in env:
        ml = env["modelo_llm"]
        md += [f"Modelo: `{ml.get('modelo')}` · {ml.get('parametros') or '—'} · cuantización {ml.get('cuantizacion') or '—'}", ""]

    for s in suites:
        print(f"\n== {s} ==", flush=True)
        if s == "validacion":
            m, det = suite_validacion(casos)
            md.append(md_validacion(m))
        elif s == "extraccion":
            m, det = suite_extraccion(casos, a.motor, max(1, a.repeticiones))
            md.append(md_extraccion(m))
        elif s == "triage":
            m, det = suite_triage(casos, a.motor)
            md.append(md_triage(m))
        else:
            m, det = suite_voz()
            md.append(md_voz(m))
        resultados[s] = m
        escribir_csv(carpeta / f"detalle_{s}.csv", det)

    md += ["---", "",
           "**Cómo se cuenta:** VP = dato correcto · FN = dato que estaba y no se extrajo · "
           "FP (alucinación) = dato inventado en un campo que debía quedar vacío · "
           "valor mal leído = cuenta como FP y FN. Booleanos: 'con valor' = verdadero. "
           "IC 95 % por bootstrap remuestreando casos (2000 iteraciones). "
           "Kappa: escala de Landis y Koch. Subtriage = color menos urgente que la referencia.", ""]
    (carpeta / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2, default=str),
                                             encoding="utf-8")
    (carpeta / "reporte.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nListo: {carpeta}\n  reporte.md · resultados.json · detalle_*.csv")
    return resultados


if __name__ == "__main__":
    main()
