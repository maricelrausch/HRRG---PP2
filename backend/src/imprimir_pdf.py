# Falta unir con boton y agregar un espacio de guardado, actualmente se guarda en memoria.

from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def generar_pdf_triage(paciente, resultado):
    # El PDF se genera en memoria, sin guardar un archivo permanente.
    archivo = BytesIO()

    documento = SimpleDocTemplate(
        archivo,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    estilos = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "TituloHospital",
        parent=estilos["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1769AA"),
    )

    contenido = []

    contenido.append(
        Paragraph("INFORME DE TRIAGE", titulo)
    )
    contenido.append(Spacer(1, 12))

    contenido.append(Paragraph(
        f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        estilos["Normal"],
    ))
    contenido.append(Spacer(1, 12))

    # Datos del paciente
    contenido.append(Paragraph(
        "1. Datos del paciente",
        estilos["Heading2"],
    ))

    campos = [
        ["Campo", "Valor"],
        ["Código de episodio", paciente.get("codigo_episodio", "No informado")],
        ["Edad", paciente.get("edad", "No informada")],
        ["Sexo", paciente.get("sexo", "No informado")],
        ["Motivo de consulta", paciente.get("motivo_consulta", "No informado")],
        ["Temperatura", paciente.get("temperatura", "No informada")],
        ["Frecuencia cardíaca", paciente.get("frec_cardiaca", "No informada")],
        ["Frecuencia respiratoria", paciente.get("frec_respiratoria", "No informada")],
        ["Presión arterial", (
            f"{paciente.get('tas', '—')}/"
            f"{paciente.get('tad', '—')} mmHg"
        )],
        ["Saturación", paciente.get("saturacion", "No informada")],
        ["Glasgow", paciente.get("glasgow", "No informado")],
        ["Dolor", paciente.get("dolor", "No informado")],
        ["Localización del dolor", paciente.get("localizacion_dolor", "No informada")],
    ]

    tabla = Table(campos, colWidths=[6 * cm, 10 * cm])

    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1769AA")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))

    contenido.append(tabla)
    contenido.append(Spacer(1, 18))

    # Resultado del triage
    contenido.append(Paragraph(
        "2. Resultado del triage",
        estilos["Heading2"],
    ))

    nivel = resultado.get("nivel", "No informado")
    codigo = resultado.get("codigo", "No informado")
    justificacion = resultado.get(
        "justificacion",
        "No se proporcionó una justificación."
    )

    contenido.append(Paragraph(
        f"<b>Nivel:</b> {nivel}",
        estilos["Normal"],
    ))
    contenido.append(Paragraph(
        f"<b>Código:</b> {codigo}",
        estilos["Normal"],
    ))
    contenido.append(Spacer(1, 8))

    contenido.append(Paragraph(
        "<b>Justificación del resultado</b>",
        estilos["Normal"],
    ))
    contenido.append(Paragraph(
        str(justificacion),
        estilos["BodyText"],
    ))

    contenido.append(Spacer(1, 18))

    contenido.append(Paragraph(
        "Documento generado por el sistema informático de triage. "
        "El resultado debe ser revisado y validado por el profesional "
        "responsable. Este informe no sustituye la evaluación clínica.",
        estilos["Italic"],
    ))

    documento.build(contenido)

    archivo.seek(0)
    return archivo