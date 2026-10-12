"""Build the supplied St Elizabeth subject prospectus for EduGuide LS."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "references" / "st-elizabeth-college-subject-prospectus-supplied.pdf"

GREEN = colors.HexColor("#005c50")
TEAL = colors.HexColor("#0d8a78")
MINT = colors.HexColor("#e7f5ef")
INK = colors.HexColor("#18322d")
MUTED = colors.HexColor("#536a64")
LINE = colors.HexColor("#c7ded7")


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
  return Paragraph(escape(text).replace("\n", "<br/>"), style)


def footer(canvas, document) -> None:
  canvas.saveState()
  canvas.setStrokeColor(LINE)
  canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
  canvas.setFont("Helvetica", 8)
  canvas.setFillColor(MUTED)
  canvas.drawString(18 * mm, 9.5 * mm, "EduGuide LS source library | St Elizabeth College supplied prospectus")
  canvas.drawRightString(A4[0] - 18 * mm, 9.5 * mm, f"Page {document.page}")
  canvas.restoreState()


def requirement_block(title: str, statements: list[str], styles) -> KeepTogether:
  rows = [[paragraph(title, styles["programme_title"])]]
  for statement in statements:
    rows.append([paragraph(statement, styles["body"])])
  table = Table(rows, colWidths=[174 * mm], hAlign="LEFT")
  table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), MINT),
    ("TEXTCOLOR", (0, 0), (-1, 0), GREEN),
    ("BOX", (0, 0), (-1, -1), 0.7, LINE),
    ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
    ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
    ("TOPPADDING", (0, 0), (-1, -1), 3.3 * mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.3 * mm),
  ]))
  return KeepTogether([table, Spacer(1, 4.5 * mm)])


def build() -> None:
  OUTPUT.parent.mkdir(parents=True, exist_ok=True)
  styles = getSampleStyleSheet()
  styles.add(ParagraphStyle(
    name="cover_title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=28,
    leading=33, textColor=GREEN, alignment=TA_CENTER, spaceAfter=6 * mm,
  ))
  styles.add(ParagraphStyle(
    name="cover_subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=12,
    leading=17, textColor=MUTED, alignment=TA_CENTER,
  ))
  styles.add(ParagraphStyle(
    name="section_title", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=16,
    leading=20, textColor=GREEN, spaceBefore=3 * mm, spaceAfter=4 * mm,
  ))
  styles.add(ParagraphStyle(
    name="programme_title", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=11,
    leading=14, textColor=GREEN,
  ))
  styles.add(ParagraphStyle(
    name="body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.2,
    leading=14.4, textColor=INK,
  ))
  styles.add(ParagraphStyle(
    name="notice", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10.2,
    leading=14.4, textColor=INK,
  ))

  document = SimpleDocTemplate(
    str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
    topMargin=18 * mm, bottomMargin=22 * mm, title="St Elizabeth College Subject Prospectus",
    author="EduGuide LS source library",
  )
  story = [
    Spacer(1, 37 * mm),
    paragraph("St Elizabeth College", styles["cover_title"]),
    paragraph("Subject Prospectus and Entry Requirements", styles["cover_subtitle"]),
    Spacer(1, 11 * mm),
  ]
  source_notice = Table(
    [[paragraph(
      "Source status: this document was prepared from supplied college information. No publication date, fee schedule, or official application link was included in that material. Confirm current admissions, programme availability, fees, and funding terms directly with St Elizabeth College before applying.",
      styles["notice"],
    )]],
    colWidths=[174 * mm], hAlign="LEFT",
  )
  source_notice.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7df")),
    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#d9b85a")),
    ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
    ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
  ]))
  story.extend([source_notice, Spacer(1, 9 * mm)])

  story.append(paragraph("Consumer Science Department", styles["section_title"]))
  story.append(requirement_block("Two-year Certificate in Consumer Science", [
    "For holders of C.O.S.C/LGCSE with at least five (5) passes, including English Language and a related subject.",
  ], styles))
  story.append(requirement_block("Three-year Diploma in Consumer Science", [
    "Route I: For holders of C.O.S.C/LGCSE with two (2) credits and at least three (3) passes in related subjects, including English Language with a pass of D or better.",
    "Route II: For holders of C.O.S.C/LGCSE and a Certificate in Home Science Advanced or Consumer Science.",
  ], styles))

  story.append(paragraph("Commercial Department", styles["section_title"]))
  story.append(requirement_block("Two-year Certificate in Business Management", [
    "For holders of C.O.S.C/LGCSE with at least five (5) passes, including English Language, Mathematics, and a related commercial subject.",
  ], styles))
  story.append(requirement_block("Three-year Diploma in Business Management", [
    "Route I: For holders of C.O.S.C/LGCSE with two (2) credits and at least three (3) passes, including a pass of D or better in English Language, Mathematics, and a related commercial subject.",
    "Route II: For holders of a Certificate in Business Management from a recognized institute.",
  ], styles))
  story.append(requirement_block("Two-year Certificate in Office Administration", [
    "For holders of C.O.S.C/LGCSE with at least five (5) passes, including English Language and a related commercial subject.",
  ], styles))
  story.append(requirement_block("Three-year Diploma in Office Administration", [
    "Route I: For holders of C.O.S.C/LGCSE with two (2) credits and at least three (3) passes, including a pass of D or better in English Language and a related subject.",
    "Route II: For holders of a Certificate in Office Administration from a recognized institute.",
  ], styles))

  story.append(Spacer(1, 2 * mm))
  story.append(paragraph("Funding note", styles["section_title"]))
  funding_notice = Table(
    [[paragraph(
      "The supplied information states that the National Manpower Development Secretariat provides a loan bursary that is paid directly to the Institute's account. Eligibility, availability, and current terms must be verified with NMDS and the college.",
      styles["body"],
    )]],
    colWidths=[174 * mm], hAlign="LEFT",
  )
  funding_notice.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), MINT),
    ("BOX", (0, 0), (-1, -1), 0.8, LINE),
    ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
    ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
  ]))
  story.append(funding_notice)
  document.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
  build()
