from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Paragraph
from reportlab.platypus import Spacer

from reportlab.lib.styles import getSampleStyleSheet


def generate_pdf_report(report_text):

    file_path = "../outputs/reports/AI_Business_Report.pdf"

    doc = SimpleDocTemplate(file_path)

    styles = getSampleStyleSheet()

    story = []

    title = Paragraph(
        "AI Business Intelligence Report",
        styles['Title']
    )

    story.append(title)

    story.append(Spacer(1, 20))

    report_paragraph = Paragraph(
        report_text.replace("\n", "<br/>"),
        styles['BodyText']
    )

    story.append(report_paragraph)

    doc.build(story)

    return file_path