"""Exportación del historial de casos para auditoría"""
"""
- Excel: CSV en UTF-8 con BOM, separador ';' y coma decimal (lo abre Excel en español).
- PDF: tabla resumida en A4 apaisado (reportlab).
"""
import csv
import io
from datetime import datetime, timedelta, timezone
import json
from xml.sax.saxutils import escape
from src.registro import COLUMNAS_EXPORTACION
COLUMNAS_PDF = [
    ("fecha_ingreso", "Ingreso", 2.4),
    ("codigo_episodio", "Episodio", 4.4),
    ("dni", "DNI del paciente", 4.2),
    ("motivo_categoria", "Categoría", 2.8),
    ("estado", "Estado", 2.0),
    ("color_final", "Color", 1.9),
    ("decision", "Decisión", 2.0),
    ("motivo_decision", "Motivo de la decisión", 5.0),
    ("profesional_decision", "Decidió", 2.3),
]

COLORES = {
    "ROJO": ("#D32F2F", "#FFFFFF"), "NARANJA": ("#F57C00", "#1A1D26"),
    "AMARILLO": ("#F9C80E", "#1A1D26"), "VERDE": ("#2E7D32", "#FFFFFF"),
    "AZUL": ("#1565C0", "#FFFFFF"),
}

# Presenta las fechas en UTC-03:00, sin depender de la configuración de la PC.
ZONA_INFORME = timezone(timedelta(hours=-3))

TIPOS_EVENTO = {
    "EPISODIO_CREADO": "Inicio de atención",
    "DATOS_INGRESO_REGISTRADOS": "Datos de ingreso revisados",
    "MEDICION_REGISTRADA": "Nueva medición",
    "MEDICION_CORREGIDA": "Corrección de medición",
    "ESTADO_CAMBIADO": "Cambio de estado",
    "DECISION_REGISTRADA": "Decisión profesional",
}

ESTADOS = {
    "en_ingreso": "En ingreso",
    "en_espera": "En espera",
    "finalizado": "Finalizado",
}

# Traduce los nombres internos y agrega las unidades de las mediciones.
CAMPOS = {
    "ta_sistolica": ("TA sistólica", "mmHg"),
    "ta_diastolica": ("TA diastólica", "mmHg"),
    "pam": ("Presión arterial media", "mmHg"),
    "frecuencia_cardiaca": ("Frecuencia cardíaca", "lat/min"),
    "frecuencia_respiratoria": ("Frecuencia respiratoria", "resp/min"),
    "saturacion_o2": ("Saturación de oxígeno", "%"),
    "temperatura": ("Temperatura", "°C"),
    "glucemia": ("Glucemia", "mg/dL"),
    "glasgow": ("Glasgow", "/15"),
    "dolor_intensidad": ("Intensidad del dolor", "/10"),
    "estado_conciencia": ("Estado de conciencia", ""),
    "edad": ("Edad", "años"),
    "sexo": ("Sexo", ""),
    "motivo_categoria": ("Categoría del motivo", ""),
    "motivo_consulta": ("Motivo de consulta", ""),
    "dolor_localizacion": ("Localización del dolor", ""),
    "dolor_caracteristicas": ("Características del dolor", ""),
    "sintomas_asociados": ("Síntomas asociados", ""),
    "alergias": ("Alergias", ""),
    "antecedentes_otros": ("Otros antecedentes", ""),
    "tiempo_evolucion_valor": ("Tiempo de evolución", ""),
    "tiempo_evolucion_unidad": ("Unidad del tiempo de evolución", ""),
    "br_sangrado": ("Sangrado", ""),
    "br_convulsion": ("Convulsión", ""),
    "br_disnea": ("Dificultad para respirar", ""),
    "br_trauma": ("Trauma", ""),
    "ant_diabetes": ("Antecedente de diabetes", ""),
    "ant_cardio": ("Antecedente cardiovascular", ""),
    "ant_resp": ("Antecedente respiratorio", ""),
    "ant_anticoag": ("Anticoagulación", ""),
    "ant_inmuno": ("Inmunosupresión", ""),
    "ant_embarazo": ("Embarazo", ""),
    "ant_medicacion": ("Medicación crítica", ""),
}


# Conserva el texto original si la fecha no puede interpretarse.
# No asigna una zona horaria inventada a fechas que no la tienen.
def _fecha_legible(valor):
    if not valor:
        return "No registrada"
    try:
        fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if fecha.utcoffset() is None:
            return f"{valor} (sin zona horaria)"
        return fecha.astimezone(ZONA_INFORME).strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        return str(valor)


# Presenta los valores sin True/False ni nombres propios de Python.
def _valor_legible(campo, valor):
    if valor is None or valor == "":
        return "Sin informar"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"

    texto = f"{valor:g}" if isinstance(valor, float) else str(valor)
    unidad = CAMPOS.get(campo, ("", ""))[1]
    return f"{texto} {unidad}".strip()


def _nombre_campo(campo):
    return CAMPOS.get(campo, (campo.replace("_", " ").capitalize(), ""))[0]


# Describe cada evento conservando los cambios y su motivo.
# Los identificadores y versiones siguen guardados en SQLite.
def _detalle_legible(evento):
    tipo = evento.get("tipo")
    detalle = evento.get("detalle") or {}
    valores = detalle.get("valores") or {}
    lineas = []

    if tipo == "EPISODIO_CREADO":
        lineas.append("Se inició la atención.")

    elif tipo in {"DATOS_INGRESO_REGISTRADOS", "MEDICION_REGISTRADA"}:
        for campo, valor in valores.items():
            lineas.append(
                f"{_nombre_campo(campo)}: {_valor_legible(campo, valor)}"
            )

    elif tipo == "MEDICION_CORREGIDA":
        anteriores = detalle.get("valores_anteriores") or {}

        # Incluye también campos retirados o agregados durante la corrección.
        for campo in dict.fromkeys([*anteriores, *valores]):
            antes = anteriores.get(campo)
            despues = valores.get(campo)
            if antes != despues:
                lineas.append(
                    f"{_nombre_campo(campo)}: "
                    f"{_valor_legible(campo, antes)} → "
                    f"{_valor_legible(campo, despues)}"
                )

        referencia = detalle.get("evento_corregido_id")
        if referencia is not None:
            lineas.append(f"Corrige el registro N.º {referencia}.")

    elif tipo == "ESTADO_CAMBIADO":
        antes = detalle.get("estado_anterior")
        despues = detalle.get("estado_nuevo")
        lineas.append(
            f"{ESTADOS.get(antes, antes or 'Sin estado previo')} → "
            f"{ESTADOS.get(despues, despues or 'Sin informar')}"
        )

    elif tipo == "DECISION_REGISTRADA":
        decision = detalle.get("decision") or "Sin informar"
        color = detalle.get("color_final") or "Sin color asignado"
        lineas.append(f"Decisión: {decision}. Color final: {color}.")

    else:
        # Evita ocultar información si aparece un tipo de evento nuevo.
        for campo, valor in detalle.items():
            lineas.append(f"{_nombre_campo(campo)}: {valor}")

    if detalle.get("motivo"):
        lineas.append(f"Motivo: {detalle['motivo']}")

    if detalle.get("origen_extraccion"):
        origen = {
            "ia": "IA local, con revisión profesional",
            "simulado": "Caso simulado",
            "manual": "Carga manual",
        }.get(detalle["origen_extraccion"], detalle["origen_extraccion"])
        lineas.append(f"Origen de los datos: {origen}")

    return lineas or ["Sin detalle adicional."]

def _celda(valor, campo):
    if campo == "dni" and (valor is None or valor == ""):
        return "No registrado"
    if valor is None:
        return ""
    if campo.startswith("fecha_") or campo in {"registrado_en", "medido_en"}:
        return _fecha_legible(valor)
    if isinstance(valor, float):
        return f"{valor:g}".replace(".", ",")  # Excel en español usa coma decimal
    texto = str(valor)
    # Evita que Excel interprete el texto como fórmula (inyección CSV).
    if texto[:1] in ("=", "+", "-", "@"):
        texto = "'" + texto
    return texto


# Exporta una fila por evento, repitiendo el resumen del episodio.
# Las columnas de resumen muestran el estado actual.
# Las columnas "Evento:" describen cada registro histórico.
def generar_csv(filas):
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
        # Incluye el DNI y conserva los códigos para vincular cada atención.
    columnas_resumen = [
        ("dni", "DNI del paciente"),
        *COLUMNAS_EXPORTACION,
    ]
    columnas_evento = [
        ("evento_id", "Evento: ID"),
        ("tipo", "Evento: tipo"),
        ("registrado_en", "Evento: fecha de registro"),
        ("profesional_usuario", "Evento: profesional"),
        ("medido_en", "Evento: fecha de medición"),
        ("evento_corregido_id", "Evento: registro corregido"),
        ("detalle", "Evento: detalle completo"),
    ]

    escritor.writerow(
        [titulo for _, titulo in columnas_resumen]
        + [titulo for _, titulo in columnas_evento]
    )

    for fila in filas:
        resumen = [
            _celda(fila.get(campo), campo)
            for campo, _ in columnas_resumen
        ]

        # Conserva también episodios que no tengan eventos disponibles.
        for evento in fila.get("historial") or [{}]:
            detalle = evento.get("detalle", {})
            datos_evento = {
                "evento_id": evento.get("evento_id"),
                "tipo": TIPOS_EVENTO.get(
                    evento.get("tipo"), evento.get("tipo", "")
                ),
                "registrado_en": evento.get("registrado_en"),
                "profesional_usuario": evento.get("profesional_usuario"),
                "medido_en": detalle.get("medido_en"),
                "detalle": "\n".join(_detalle_legible(evento)),
            }

            escritor.writerow(
                resumen
                + [
                    _celda(datos_evento.get(campo), campo)
                    for campo, _ in columnas_evento
                ]
            )

    # Excel reconoce los acentos mediante el BOM.
    return salida.getvalue().encode("utf-8-sig")


def generar_pdf(filas, filtros_texto, usuario):
    # Import diferido: si falta reportlab, solo falla el PDF (el Excel sigue andando).
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    archivo = io.BytesIO()
    doc = SimpleDocTemplate(
        archivo, pagesize=landscape(A4),
        leftMargin=1 * cm, rightMargin=1 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
        title="Historial de casos · Triage HRRG",
    )
    estilos = getSampleStyleSheet()
    chico = estilos["BodyText"].clone("chico", fontSize=7.5, leading=9)
    encabezado = estilos["BodyText"].clone("enc", fontSize=8, leading=10, fontName="Helvetica-Bold")

        # Identifica explícitamente la zona horaria del informe.
    ahora = datetime.now(ZONA_INFORME).strftime("%d/%m/%Y %H:%M") + " (UTC-03:00)"
    partes = [
        Paragraph("Historial de casos · Triage asistido HRRG", estilos["Title"]),
        Paragraph(
            f"Exportado por <b>{usuario}</b> el {ahora} · {filtros_texto} · {len(filas)} episodios · "
                        "<b>Informe identificado por DNI</b> · Datos ficticios del prototipo.",
            chico,
        ),
        Spacer(1, 0.3 * cm),
    ]

    datos = [[Paragraph(t, encabezado) for _, t, _ in COLUMNAS_PDF]]
    estilo_tabla = [
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B0B4BE")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EAF0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    col_color = [c for c, _, _ in COLUMNAS_PDF].index("color_final")
    for i, fila in enumerate(filas, start=1):
        datos.append([
            Paragraph(_celda(fila.get(c), c).lstrip("'").replace("&", "&amp;").replace("<", "&lt;"), chico)
            for c, _, _ in COLUMNAS_PDF
        ])
        fondo, tinta = COLORES.get(fila.get("color_final") or "", (None, None))
        if fondo:
            estilo_tabla.append(("BACKGROUND", (col_color, i), (col_color, i), colors.HexColor(fondo)))
            estilo_tabla.append(("TEXTCOLOR", (col_color, i), (col_color, i), colors.HexColor(tinta)))

    tabla = Table(datos, colWidths=[a * cm for _, _, a in COLUMNAS_PDF], repeatRows=1)
    tabla.setStyle(TableStyle(estilo_tabla))
    partes.append(tabla)
        # Presenta la evolución con títulos claros y fechas uniformes.
    for fila in filas:
        partes.append(Spacer(1, 0.5 * cm))
        partes.append(Paragraph(
            "Historial de la atención "
            + escape(str(fila.get("codigo_episodio", ""))),
            estilos["Heading2"],
        ))

                # Identifica al paciente también al comienzo de su historial.
        partes.append(Paragraph(
            "DNI del paciente: " + escape(_celda(fila.get("dni"), "dni")),
            chico,
        ))

        historial = fila.get("historial") or []
        if not historial:
            partes.append(Paragraph("Sin eventos disponibles.", chico))
            continue

        for evento in historial:
            detalle = evento.get("detalle") or {}
            tipo = TIPOS_EVENTO.get(
                evento.get("tipo"), evento.get("tipo", "Evento")
            )

            # Mantiene una referencia breve para vincular las correcciones.
            titulo = f"{tipo} · Registro N.º {evento.get('evento_id', '')}"
            partes.append(Paragraph(escape(titulo), estilos["Heading3"]))

            registro = _fecha_legible(evento.get("registrado_en"))
            profesional = evento.get("profesional_usuario") or "No registrado"
            partes.append(Paragraph(
                escape(f"Registrado: {registro} · Profesional: {profesional}"),
                chico,
            ))

            # Distingue cuándo se tomó el dato de cuándo se registró o corrigió.
            if detalle.get("medido_en"):
                partes.append(Paragraph(
                    escape("Fecha de la toma: "
                           + _fecha_legible(detalle["medido_en"])),
                    chico,
                ))

            for linea in _detalle_legible(evento):
                partes.append(Paragraph(escape(linea), chico))

            partes.append(Spacer(1, 0.2 * cm))
    def pie(canvas, documento):
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(landscape(A4)[0] - 1 * cm, 0.6 * cm, f"Página {documento.page}")

    doc.build(partes, onFirstPage=pie, onLaterPages=pie)
    return archivo.getvalue()
