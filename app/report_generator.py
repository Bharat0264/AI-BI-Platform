from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle


ACCENT = colors.HexColor("#0f766e")
INK = colors.HexColor("#101828")
MUTED = colors.HexColor("#667085")
SOFT = colors.HexColor("#ecfdf5")


def _clean_text(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _section(title, styles):
    return Paragraph(_clean_text(title), styles["SectionTitle"])


def _table(rows, widths=None):
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d0d5dd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            textColor=colors.white,
            fontSize=24,
            leading=28,
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["BodyText"],
            textColor=colors.HexColor("#ccfbf1"),
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            textColor=ACCENT,
            fontSize=14,
            leading=18,
            spaceBefore=14,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySoft",
            parent=styles["BodyText"],
            textColor=INK,
            fontSize=10,
            leading=15,
        )
    )
    return styles


def generate_pdf_report(report_text, metrics=None, insights=None, anomalies=None, forecast=None):
    reports_dir = Path(__file__).resolve().parents[1] / "outputs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    file_path = reports_dir / "AI_Business_Report.pdf"
    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    styles = _build_styles()
    story = []

    cover = Table(
        [
            [
                Paragraph("AI Business Intelligence Report", styles["ReportTitle"]),
            ],
            [
                Paragraph(
                    "Executive analytics, autonomous insights, risk signals, and forecast summary",
                    styles["ReportSubtitle"],
                )
            ],
        ],
        colWidths=[7.1 * inch],
    )
    cover.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
                ("BOX", (0, 0), (-1, -1), 0.5, ACCENT),
                ("TOPPADDING", (0, 0), (-1, -1), 24),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 24),
            ]
        )
    )
    story.append(cover)
    story.append(Spacer(1, 18))

    if metrics:
        rows = [["KPI", "Value"]]
        rows.extend([[key, value] for key, value in metrics.items()])
        story.append(_section("Executive KPI Snapshot", styles))
        story.append(_table(rows, widths=[3.2 * inch, 3.9 * inch]))

    if insights:
        rows = [["Signal", "Recommendation"]]
        rows.extend([[_clean_text(item["title"]), _clean_text(item["body"])] for item in insights])
        story.append(_section("Autonomous Business Signals", styles))
        story.append(_table(rows, widths=[2.1 * inch, 5.0 * inch]))

    if anomalies:
        rows = [["Anomaly", "Why it matters"]]
        rows.extend([[_clean_text(item["title"]), _clean_text(item["body"])] for item in anomalies])
        story.append(_section("Risk and Anomaly Detection", styles))
        story.append(_table(rows, widths=[2.1 * inch, 5.0 * inch]))

    if forecast is not None and not forecast.empty:
        rows = [["Month", "Prediction", "Lower", "Upper"]]
        for _, row in forecast.head(6).iterrows():
            rows.append(
                [
                    _clean_text(row["Forecast Month"]),
                    f"${row['Predicted Sales']:,.0f}",
                    f"${row['Lower Bound']:,.0f}",
                    f"${row['Upper Bound']:,.0f}",
                ]
            )
        story.append(_section("Six-Month Sales Forecast", styles))
        story.append(_table(rows, widths=[1.8 * inch, 1.8 * inch, 1.7 * inch, 1.8 * inch]))

    story.append(_section("AI Executive Narrative", styles))
    for block in str(report_text).split("\n\n"):
        if block.strip():
            story.append(Paragraph(_clean_text(block).replace("\n", "<br/>"), styles["BodySoft"]))
            story.append(Spacer(1, 8))

    doc.build(story)

    return str(file_path)
