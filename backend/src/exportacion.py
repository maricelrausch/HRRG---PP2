"""Exportación del historial de casos para auditoría (Barby, 23/10 · a revisar por Maricel).

- Excel: CSV en UTF-8 con BOM, separador ';' y coma decimal (lo abre Excel en español).
- PDF: tabla resumida en A4 apaisado (reportlab).
Ninguno de los dos incluye el DNI: el paciente va con su código interno.
"""
import csv
import io
from datetime import datetime

from src.registro import COLUMNAS_EXPORTACION

# Columnas del PDF (resumen: el detalle completo va en el Excel).
COLUMNAS_PDF = [
    ("fecha_ingreso", "Ingreso", 2.4),
    ("codigo_episodio", "Episodio", 4.4),
    ("codigo_paciente", "Paciente (código)", 4.2),
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


def _celda(valor, campo):
    if valor is None:
        return ""
    if campo.startswith("fecha_"):
        try:
            return datetime.fromisoformat(valor).astimezone().strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return valor
    if isinstance(valor, float):
        return f"{valor:g}".replace(".", ",")  # Excel en español usa coma decimal
    texto = str(valor)
    # Evita que Excel interprete el texto como fórmula (inyección CSV).
    if texto[:1] in ("=", "+", "-", "@"):
        texto = "'" + texto
    return texto


def generar_csv(filas):
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    escritor.writerow([titulo for _, titulo in COLUMNAS_EXPORTACION])
    for fila in filas:
        escritor.writerow([_celda(fila.get(campo), campo) for campo, _ in COLUMNAS_EXPORTACION])
    return ("﻿" + salida.getvalue()).encode("utf-8")  # BOM: Excel reconoce los acentos


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

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    partes = [
        Paragraph("Historial de casos · Triage asistido HRRG", estilos["Title"]),
        Paragraph(
            f"Exportado por <b>{usuario}</b> el {ahora} · {filtros_texto} · {len(filas)} episodios · "
            "<b>Sin DNI</b> (el paciente figura con su código interno) · Datos ficticios del prototipo.",
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

    def pie(canvas, documento):
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(landscape(A4)[0] - 1 * cm, 0.6 * cm, f"Página {documento.page}")

    doc.build(partes, onFirstPage=pie, onLaterPages=pie)
    return archivo.getvalue()
