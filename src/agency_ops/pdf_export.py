"""PDF export helpers for client-ready agency proposals."""

from __future__ import annotations

from io import BytesIO
import re
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


SECTION_TITLES = ("Project goal", "Scope", "Delivery timeline", "Investment", "Next step")


def _section(content: str, heading: str) -> str:
    match = re.search(rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)", content, flags=re.DOTALL)
    return match.group(1).strip() if match else "Not specified"


def _paragraph_text(value: str) -> str:
    return escape(value).replace("\n", "<br/>")


def build_proposal_pdf(project: dict[str, Any], proposal: dict[str, Any]) -> BytesIO:
    """Return a polished proposal PDF in memory for a saved proposal."""
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Proposal - {project['name']}",
        author="Agency Operations MCP",
    )
    styles = getSampleStyleSheet()
    eyebrow = ParagraphStyle(
        "Eyebrow",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#8A6A1E"),
        spaceAfter=6,
    )
    title = ParagraphStyle(
        "ProposalTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=25,
        leading=30,
        textColor=colors.HexColor("#182030"),
        spaceAfter=14,
        alignment=TA_LEFT,
    )
    heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#182030"),
        spaceBefore=14,
        spaceAfter=5,
    )
    body = ParagraphStyle(
        "ProposalBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#303948"),
        spaceAfter=6,
    )
    detail_label = ParagraphStyle(
        "DetailLabel",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#6D7480"),
    )
    detail_value = ParagraphStyle(
        "DetailValue",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#182030"),
    )

    content = proposal["content"]
    story = [
        Paragraph("AGENCY OPERATIONS / CLIENT PROPOSAL", eyebrow),
        Paragraph(escape(project["name"]), title),
    ]
    details = Table(
        [[
            [Paragraph("CLIENT", detail_label), Paragraph(escape(project["client_name"]), detail_value)],
            [Paragraph("PROPOSAL", detail_label), Paragraph("Prepared for review", detail_value)],
        ]],
        colWidths=[85 * mm, 85 * mm],
    )
    details.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F5F8")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9DEE7")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9DEE7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.extend([details, Spacer(1, 6 * mm)])
    for section in SECTION_TITLES:
        story.append(Paragraph(section, heading))
        story.append(Paragraph(_paragraph_text(_section(content, section)), body))

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9DEE7"))
        canvas.line(doc.leftMargin, 12 * mm, A4[0] - doc.rightMargin, 12 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6D7480"))
        canvas.drawString(doc.leftMargin, 7 * mm, "Prepared with Agency Operations MCP")
        canvas.drawRightString(A4[0] - doc.rightMargin, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    stream.seek(0)
    return stream
