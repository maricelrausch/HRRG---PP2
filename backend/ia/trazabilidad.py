"""backend/ia/trazabilidad.py · Registro de trazabilidad, constancia y exportación.

Cada episodio de triage queda registrado como una secuencia de EVENTOS que no se modifican ni se borran
(solo se agregan). Cada evento lleva un hash encadenado con el anterior: si alguien altera un evento
en la base, la verificación lo detecta.

Usa la misma base SQLite que ya tenía el proyecto (src/registro.py): ~/.hrrg_pp2/triage_demo.db,
tablas `episodios` y `eventos` (se agrega la columna `hash` si falta).

Rutas (se montan dentro de /api, ver ia/rutas.py):
  POST /api/traza/evento                 registra un evento enviado por la pantalla
  GET  /api/traza/episodios              lista de episodios con su resumen
  GET  /api/traza/episodio/<id>          línea de tiempo completa de un episodio
  GET  /api/traza/constancia/<id>        constancia imprimible (HTML; "Guardar como PDF" desde el navegador)
  GET  /api/traza/exportar.csv           todos los episodios en CSV (concordancia IA vs profesional)
"""
import csv
import hashlib
import html
import io
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, session

bp = Blueprint("traza", __name__, url_prefix="/traza")

NIVELES = ["ROJO", "NARANJA", "AMARILLO", "VERDE", "AZUL"]
TIPOS = {  # tipos de evento aceptados y su nombre legible
    "inicio": "Inicio del episodio",
    "extraccion_ia": "Extracción de datos con MedGemma",
    "extraccion_sin_ia": "Relato pasado sin IA (carga manual)",
    "ia_no_disponible": "MedGemma no disponible",
    "modo": "Cambio de modo (IA prendida / apagada)",
    "datos_revisados": "Datos revisados por el profesional",
    "sugerencia_ia": "Sugerencia de MedGemma",
    "sugerencia_insuficiente": "Datos insuficientes para sugerir",
    "prioridad_mostrada": "Prioridad mostrada al profesional",
    "discriminador": "Discriminador confirmado por el profesional",
    "chat": "Consulta al asistente",
    "decision": "Decisión del profesional",
}
_bloqueo = threading.Lock()
_listo = set()


# ------------------------------------------------------------------ base de datos
def _ruta_base():
    try:
        r = current_app.config.get("BASE_REGISTRO")
    except RuntimeError:
        r = None
    return Path(r) if r else Path.home() / ".hrrg_pp2" / "triage_demo.db"


def _conectar():
    ruta = _ruta_base()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta, timeout=10)
    con.row_factory = sqlite3.Row
    if str(ruta) not in _listo:
        with con:
            con.execute("""CREATE TABLE IF NOT EXISTS episodios (
                codigo_episodio TEXT PRIMARY KEY, codigo_paciente TEXT NOT NULL,
                creado_en TEXT NOT NULL, profesional_usuario TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, codigo_episodio TEXT NOT NULL, tipo TEXT NOT NULL,
                ocurrido_en TEXT NOT NULL, profesional_usuario TEXT NOT NULL, datos_json TEXT NOT NULL,
                FOREIGN KEY (codigo_episodio) REFERENCES episodios (codigo_episodio))""")
            columnas = [c["name"] for c in con.execute("PRAGMA table_info(eventos)")]
            if "hash" not in columnas:
                con.execute("ALTER TABLE eventos ADD COLUMN hash TEXT")
        _listo.add(str(ruta))
    return con


def _hash(prev, episodio, tipo, cuando, usuario, datos_json):
    base = "|".join([prev or "INICIO", episodio, tipo, cuando, usuario, datos_json])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _usuario(sugerido=None):
    """Usuario de la sesión de Flask si hay login real; si no, el de la pantalla (login de demo)."""
    u = session.get("usuario") if session else None
    if u:
        return str(u)
    s = str(sugerido or "").strip()[:60]
    return (s + " (demo)") if s else "sin usuario"


ID_VALIDO = re.compile(r"^[A-Za-z0-9\-_.]{3,80}$")


def registrar(episodio, tipo, datos, ep_visible="", usuario=None):
    """Agrega un evento al episodio (lo crea si no existe). Nunca modifica eventos anteriores."""
    if not episodio or not ID_VALIDO.match(str(episodio)) or tipo not in TIPOS:
        return None
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    usuario = usuario or "sin usuario"
    datos_json = json.dumps(datos or {}, ensure_ascii=False, sort_keys=True, default=str)
    with _bloqueo:
        con = _conectar()
        try:
            with con:
                con.execute("INSERT OR IGNORE INTO episodios VALUES (?, ?, ?, ?)",
                            (episodio, (ep_visible or episodio)[:40], ahora, usuario))
                fila = con.execute("SELECT hash FROM eventos WHERE codigo_episodio=? ORDER BY id DESC LIMIT 1",
                                   (episodio,)).fetchone()
                h = _hash(fila["hash"] if fila else None, episodio, tipo, ahora, usuario, datos_json)
                cur = con.execute("INSERT INTO eventos (codigo_episodio, tipo, ocurrido_en, profesional_usuario, "
                                  "datos_json, hash) VALUES (?, ?, ?, ?, ?, ?)",
                                  (episodio, tipo, ahora, usuario, datos_json, h))
                return cur.lastrowid
        finally:
            con.close()


def registrar_desde_pedido(cuerpo, tipo, datos):
    """Para las rutas de IA: el pedido trae {"traza": {"id", "ep", "usuario"}}. Si falla, no corta la IA."""
    try:
        t = (cuerpo or {}).get("traza") or {}
        if t.get("id"):
            registrar(t["id"], tipo, datos, t.get("ep", ""), _usuario(t.get("usuario")))
    except Exception as e:                                   # la trazabilidad nunca rompe la atención
        print(f"[Trazabilidad] no se pudo registrar {tipo}: {e}")


def _eventos(con, episodio):
    filas = con.execute("SELECT * FROM eventos WHERE codigo_episodio=? ORDER BY id", (episodio,)).fetchall()
    out, prev, integro = [], None, True
    for f in filas:
        datos = json.loads(f["datos_json"] or "{}")
        ok = None
        if f["hash"]:
            ok = _hash(prev, f["codigo_episodio"], f["tipo"], f["ocurrido_en"],
                       f["profesional_usuario"], f["datos_json"]) == f["hash"]
            integro = integro and ok
            prev = f["hash"]
        out.append({"id": f["id"], "tipo": f["tipo"], "nombre": TIPOS.get(f["tipo"], f["tipo"]),
                    "cuando": f["ocurrido_en"], "usuario": f["profesional_usuario"], "datos": datos, "hash_ok": ok})
    return out, integro


def _resumen(ep_fila, eventos, integro):
    """Lo que importa para auditar: qué sugirió la IA, qué se mostró y qué decidió el profesional."""
    r = {"episodio": ep_fila["codigo_episodio"], "codigo": ep_fila["codigo_paciente"],
         "inicio": ep_fila["creado_en"], "usuario": ep_fila["profesional_usuario"],
         "fin": eventos[-1]["cuando"] if eventos else ep_fila["creado_en"],
         "modo": "", "color_ia": "", "color_mostrado": "", "origen_color": "", "reglas": "",
         "decision": "", "color_final": "", "motivo": "", "concordancia_ia": "", "concordancia_sugerencia": "",
         "correcciones": 0, "consultas_chat": 0, "chat_bloqueadas": 0, "motivos_filtrados": 0,
         "eventos": len(eventos), "integridad": "OK" if integro else "ALTERADO"}
    for e in eventos:
        d = e["datos"]
        if e["tipo"] in ("extraccion_ia", "extraccion_sin_ia", "modo", "prioridad_mostrada"):
            r["modo"] = d.get("modo") or r["modo"] or ("con IA" if e["tipo"] == "extraccion_ia" else "sin IA")
        if e["tipo"] == "sugerencia_ia":
            r["color_ia"] = d.get("color") or ""
            r["motivos_filtrados"] += len(d.get("descartados") or [])
        if e["tipo"] == "datos_revisados":
            r["correcciones"] = len(d.get("correcciones") or [])
        if e["tipo"] == "prioridad_mostrada":
            r["color_mostrado"] = d.get("color") or ""
            r["origen_color"] = d.get("origen") or ""
            r["reglas"] = "; ".join(d.get("reglas") or [])
            r["modo"] = d.get("modo") or r["modo"]
        if e["tipo"] == "chat":
            r["consultas_chat"] += 1
            r["chat_bloqueadas"] += 1 if d.get("tipo_respuesta") == "bloqueada" else 0
        if e["tipo"] == "decision":
            r["decision"] = d.get("decision") or ""
            r["color_final"] = d.get("color_final") or ""
            r["motivo"] = d.get("motivo") or ""
    if r["color_ia"] and r["color_final"]:
        r["concordancia_ia"] = "sí" if r["color_ia"] == r["color_final"] else "no"
    if r["color_mostrado"] and r["color_final"]:
        r["concordancia_sugerencia"] = "sí" if r["color_mostrado"] == r["color_final"] else "no"
    return r


def _todos():
    con = _conectar()
    try:
        out = []
        for ep in con.execute("SELECT * FROM episodios ORDER BY creado_en DESC").fetchall():
            ev, integro = _eventos(con, ep["codigo_episodio"])
            if ev and any(e["hash_ok"] is not None for e in ev):     # solo los del registro con trazabilidad
                out.append(_resumen(ep, ev, integro))
        return out
    finally:
        con.close()


# ------------------------------------------------------------------ rutas
@bp.post("/evento")
def evento():
    j = request.get_json(silent=True) or {}
    tipo = str(j.get("tipo", ""))
    if tipo not in TIPOS:
        return jsonify(error="Tipo de evento desconocido."), 400
    if not ID_VALIDO.match(str(j.get("episodio", ""))):
        return jsonify(error="Episodio inválido."), 400
    datos = j.get("datos") if isinstance(j.get("datos"), dict) else {}
    if len(json.dumps(datos, default=str)) > 60000:
        return jsonify(error="Evento demasiado grande."), 413
    nuevo = registrar(j["episodio"], tipo, datos, str(j.get("ep", "")), _usuario(j.get("usuario")))
    return jsonify(ok=True, id=nuevo)


@bp.get("/episodios")
def episodios():
    return jsonify(episodios=_todos())


@bp.get("/episodio/<episodio>")
def episodio(episodio):
    con = _conectar()
    try:
        ep = con.execute("SELECT * FROM episodios WHERE codigo_episodio=?", (episodio,)).fetchone()
        if not ep:
            return jsonify(error="Episodio inexistente."), 404
        ev, integro = _eventos(con, episodio)
        return jsonify(resumen=_resumen(ep, ev, integro), eventos=ev)
    finally:
        con.close()


CAMPOS_CSV = ["episodio", "codigo", "inicio", "fin", "usuario", "modo", "color_ia", "color_mostrado",
              "origen_color", "decision", "color_final", "concordancia_ia", "concordancia_sugerencia", "motivo", "reglas", "correcciones",
              "motivos_filtrados", "consultas_chat", "chat_bloqueadas", "eventos", "integridad"]


@bp.get("/exportar.csv")
def exportar():
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CAMPOS_CSV, delimiter=";", extrasaction="ignore")
    w.writeheader()
    for r in _todos():
        w.writerow(r)
    nombre = "trazabilidad_triage_" + datetime.now().strftime("%Y%m%d_%H%M") + ".csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",   # BOM: Excel abre bien los acentos
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# ------------------------------------------------------------------ constancia
def _h(x):
    return html.escape(str(x if x is not None else ""))


def _hora(iso):
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return iso or ""


COLORES = {"ROJO": "#c62828", "NARANJA": "#ef6c00", "AMARILLO": "#f9a825", "VERDE": "#2e7d32", "AZUL": "#1565c0"}
NOMBRES_CAMPO = {"edad": "Edad", "sexo": "Sexo", "motivo_categoria": "Categoría", "motivo_consulta": "Motivo",
                 "dolor_localizacion": "Dónde le duele", "sintomas_asociados": "Síntomas",
                 "tiempo_evolucion_valor": "Desde hace", "tiempo_evolucion_unidad": "Unidad",
                 "ta_sistolica": "TA sistólica", "ta_diastolica": "TA diastólica",
                 "frecuencia_cardiaca": "Frec. cardíaca", "frecuencia_respiratoria": "Frec. respiratoria",
                 "saturacion_o2": "SpO₂", "temperatura": "Temperatura", "glucemia": "Glucemia",
                 "estado_conciencia": "Conciencia", "glasgow": "Glasgow", "dolor_intensidad": "Dolor (0-10)"}


def _chip(color):
    c = COLORES.get(str(color).upper())
    return (f'<span class="chip" style="background:{c}">{_h(color)}</span>' if c else _h(color or "—"))


def _lista(items):
    items = [i for i in (items or []) if i]
    return "<ul>" + "".join(f"<li>{_h(i)}</li>" for i in items) + "</ul>" if items else "<p class='q'>—</p>"


@bp.get("/constancia/<episodio>")
def constancia(episodio):
    con = _conectar()
    try:
        ep = con.execute("SELECT * FROM episodios WHERE codigo_episodio=?", (episodio,)).fetchone()
        if not ep:
            return Response("Episodio inexistente.", status=404)
        ev, integro = _eventos(con, episodio)
    finally:
        con.close()
    r = _resumen(ep, ev, integro)
    ult = lambda t: next((e["datos"] for e in reversed(ev) if e["tipo"] == t), {})   # noqa: E731
    relato = (ult("extraccion_ia") or ult("extraccion_sin_ia")).get("relato", "")
    revisados = ult("datos_revisados")
    sug = ult("sugerencia_ia")
    mostrada = ult("prioridad_mostrada")
    dec = ult("decision")
    chats = [e for e in ev if e["tipo"] == "chat"]
    discr = [e["datos"].get("texto", "") for e in ev if e["tipo"] == "discriminador"]

    datos = revisados.get("datos") or {}
    filas = "".join(f"<tr><td>{_h(NOMBRES_CAMPO.get(k, k))}</td><td>{_h(v)}</td></tr>"
                    for k, v in datos.items() if k in NOMBRES_CAMPO and v not in ("", None, False))
    banderas = [k for k in ("Sangrado evidente", "Convulsión activa", "Dificultad para respirar", "Mecanismo de trauma")
                if k in (revisados.get("banderas") or [])]
    correc = "".join(f"<tr><td>{_h(c.get('campo'))}</td><td>{_h(c.get('ia') or '—')}</td><td>{_h(c.get('final') or '—')}</td></tr>"
                     for c in (revisados.get("correcciones") or []))
    tl = "".join(f"<tr><td>{_h(_hora(e['cuando']))}</td><td>{_h(e['nombre'])}</td><td>{_h(e['usuario'])}</td>"
                 f"<td class='mono'>{'✔' if e['hash_ok'] else ('✘' if e['hash_ok'] is False else '·')}</td></tr>" for e in ev)
    chat_html = "".join(f"<div class='qa'><b>P:</b> {_h(c['datos'].get('pregunta'))}<br><b>R:</b> {_h(c['datos'].get('respuesta'))}"
                        f"{' <span class=tag>bloqueada</span>' if c['datos'].get('tipo_respuesta') == 'bloqueada' else ''}</div>"
                        for c in chats) or "<p class='q'>Sin consultas.</p>"
    dec_txt = {"aceptar": "Aceptó la sugerencia", "modificar": "Modificó la sugerencia",
               "rechazar": "Rechazó la sugerencia", "manual": "Clasificación manual (sin IA)"}.get(r["decision"], "Sin decisión registrada")
    ultimo_hash = next((e for e in reversed(ev) if e["hash_ok"] is not None), None)
    huella = ""
    if ultimo_hash:
        con = _conectar()
        try:
            f = con.execute("SELECT hash FROM eventos WHERE id=?", (ultimo_hash["id"],)).fetchone()
            huella = f["hash"] if f else ""
        finally:
            con.close()

    pagina = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Constancia de triage · {_h(r['codigo'])}</title>
<style>
 body{{font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;color:#1b1b1f;max-width:820px;margin:24px auto;padding:0 16px}}
 h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:15px;margin:22px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}}
 .sub{{color:#555;font-size:12px}} .aviso{{background:#fff8e1;border:1px solid #f0d58a;padding:8px 10px;border-radius:6px;font-size:12px;margin:12px 0}}
 table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border-bottom:1px solid #eee;padding:5px 6px;text-align:left;vertical-align:top}}
 th{{background:#f6f6f8}} .chip{{color:#fff;padding:2px 10px;border-radius:12px;font-weight:700;font-size:12px}}
 .grid{{display:grid;grid-template-columns:1fr 1fr;gap:4px 18px}} .q{{color:#777}} .mono{{font-family:Consolas,monospace;font-size:11px;word-break:break-all}}
 .qa{{border-left:3px solid #ddd;padding:4px 10px;margin:6px 0}} .tag{{background:#eee;border-radius:4px;padding:0 6px;font-size:11px}}
 .ok{{color:#2e7d32;font-weight:700}} .mal{{color:#c62828;font-weight:700}} .acc{{margin:12px 0}}
 @media print{{.acc{{display:none}} body{{margin:0}}}}
</style></head><body>
<div class="acc"><button onclick="window.print()">Imprimir / Guardar como PDF</button></div>
<h1>Constancia de triage asistido</h1>
<div class="sub">Hospital Regional Río Grande · Prototipo PP2 · Equipo 1</div>
<div class="aviso"><b>Datos ficticios · prototipo.</b> Herramienta de apoyo a la decisión: no diagnostica ni indica tratamientos.
La clasificación final es responsabilidad del profesional interviniente. Guía de ejemplo, no oficial.</div>

<h2>Episodio</h2>
<div class="grid">
 <div><b>Código:</b> {_h(r['codigo'])}</div><div><b>Registro:</b> <span class="mono">{_h(r['episodio'])}</span></div>
 <div><b>Inicio:</b> {_h(_hora(r['inicio']))}</div><div><b>Último evento:</b> {_h(_hora(r['fin']))}</div>
 <div><b>Profesional:</b> {_h(r['usuario'])}</div><div><b>Modo:</b> {_h(r['modo'] or '—')}</div>
</div>

<h2>Decisión</h2>
<div class="grid">
 <div><b>Prioridad final:</b> {_chip(r['color_final'])}</div><div><b>Decisión:</b> {_h(dec_txt)}</div>
 <div><b>Sugerida por el sistema:</b> {_chip(r['color_mostrado'])}</div><div><b>Sugerencia de MedGemma:</b> {_chip(r['color_ia'] or '—')}</div>
 <div><b>Origen del color sugerido:</b> {_h(r['origen_color'] or '—')}</div><div><b>Motivo del profesional:</b> {_h(r['motivo'] or '—')}</div>
</div>

<h2>Relato</h2><p>{_h(relato) or "<span class='q'>—</span>"}</p>

<h2>Datos registrados</h2>
<table><tr><th>Dato</th><th>Valor</th></tr>{filas or "<tr><td colspan=2 class='q'>Sin datos</td></tr>"}</table>
<p><b>Banderas rojas:</b> {_h(', '.join(banderas) or 'ninguna')}</p>

<h2>Correcciones del profesional a la IA</h2>
<table><tr><th>Dato</th><th>Valor de la IA</th><th>Valor final</th></tr>{correc or "<tr><td colspan=3 class='q'>Sin correcciones</td></tr>"}</table>

<h2>Fundamento de la prioridad</h2>
<p><b>Reglas de seguridad activadas:</b></p>{_lista(mostrada.get('reglas'))}
<p><b>Motivos mostrados:</b></p>{_lista(mostrada.get('motivos'))}
<p><b>Discriminadores confirmados por el profesional:</b></p>{_lista(discr)}
<p><b>Motivos de MedGemma descartados por los controles:</b></p>{_lista(sug.get('descartados'))}

<h2>Consultas al asistente</h2>{chat_html}

<h2>Línea de tiempo</h2>
<table><tr><th>Fecha y hora</th><th>Evento</th><th>Usuario</th><th>Íntegro</th></tr>{tl}</table>

<h2>Integridad del registro</h2>
<p>Verificación de la cadena de eventos: {'<span class="ok">ÍNTEGRO</span>' if integro else '<span class="mal">ALTERADO — un evento fue modificado después de registrarse</span>'}</p>
<p class="mono">Huella del último evento (SHA-256): {_h(huella)}</p>
<p class="sub">Emitida el {_h(datetime.now().strftime('%d/%m/%Y %H:%M'))} · {len(ev)} eventos registrados.</p>
</body></html>"""
    return Response(pagina, mimetype="text/html; charset=utf-8")
