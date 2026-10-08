from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem


def create_pdf(result, filename="informe_triage.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("INFORME DE TRIAJE", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"<b>Nivel de urgencia:</b> {result.level}", styles["Heading2"]),
        Spacer(1, 10),
        Paragraph("<b>Entrada recibida</b>", styles["Heading3"]),
        Paragraph(result.source_text or "(sin texto)", styles["BodyText"]),
        Spacer(1, 10),
        Paragraph("<b>Factores detectados</b>", styles["Heading3"]),
        ListFlowable(
            [ListItem(Paragraph(x, styles["BodyText"])) for x in (result.detected_factors or ["Ninguno"])],
            bulletType="bullet",
        ),
        Spacer(1, 10),
        Paragraph("<b>Reglas activadas</b>", styles["Heading3"]),
        ListFlowable(
            [ListItem(Paragraph(x, styles["BodyText"])) for x in (result.activated_rules or ["Ninguna"])],
            bulletType="bullet",
        ),
        Spacer(1, 10),
        Paragraph("<b>Explicación del resultado</b>", styles["Heading3"]),
        Paragraph(result.explanation, styles["BodyText"]),
        Spacer(1, 18),
        Paragraph(
            "<b>Advertencia:</b> este prototipo es educativo y no sustituye la evaluación "
            "de un profesional sanitario. Las reglas deben validarse clínicamente antes de "
            "cualquier uso real.",
            styles["BodyText"],
        ),
    ]
    doc.build(story)
    return filename
