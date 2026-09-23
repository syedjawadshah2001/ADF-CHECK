"""Printable ADF reports with consistent counts and resilient pagination."""
import logging
import math
import re
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

SECTION_TITLES = [
    "Font Size Errors", "Font Style Errors", "Table & Figure Caption Errors",
    "Heading Style Errors", "Line Spacing Errors", "Header & Footer Errors",
    "Margin Errors", "Reference Errors", "Page Number Errors",
]
INK = colors.HexColor("#163641")
TEAL = colors.HexColor("#087e83")
MUTED = colors.HexColor("#526b75")
LIGHT = colors.HexColor("#eff6f6")
WIDTH = 500


def _font_setup():
    # ReportLab ships these fonts: no system font or network dependency.
    root = Path(reportlab.__file__).parent / "fonts"
    for name, filename in (("ADF", "Vera.ttf"), ("ADF-Bold", "VeraBd.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(root / filename)))
    pdfmetrics.registerFontFamily("ADF", normal="ADF", bold="ADF-Bold", italic="ADF", boldItalic="ADF-Bold")


def _build_styles():
    _font_setup()
    base = dict(fontName="ADF", fontSize=9, leading=13, textColor=INK, splitLongWords=True)
    return {
        "body": ParagraphStyle("body", **base, spaceAfter=6),
        "cell": ParagraphStyle("cell", **base),
        "headcell": ParagraphStyle("headcell", fontName="ADF-Bold", fontSize=9, leading=13, textColor=colors.white),
        "title": ParagraphStyle("title", fontName="ADF-Bold", fontSize=25, leading=31, textColor=INK, spaceAfter=10),
        "section": ParagraphStyle("section", fontName="ADF-Bold", fontSize=13, leading=18, textColor=TEAL, spaceBefore=14, spaceAfter=9, keepWithNext=True),
        "muted": ParagraphStyle("muted", **{**base, "fontSize":8, "leading":12, "textColor":MUTED}, spaceAfter=10),
    }


def _parse_sections(all_errors: list[str]) -> dict[str, list[str]]:
    sections = {title: [] for title in SECTION_TITLES}
    current = None
    for entry in all_errors:
        clean = str(entry).strip()
        if clean in sections:
            current = clean
        elif clean and current:
            sections[current].append(clean)
    return sections


def count_issues(lines):
    """Count finding groups, consistently with the app (not affected runs)."""
    return sum(line.strip().startswith("\u274c") or "Error:" in line for line in lines)


def _printable(text):
    # Replace decorative status glyphs that otherwise become missing-glyph boxes.
    replacements = {"\u274c":"", "\u2714":"", "\u2705":"", "\u26a0":"", "\ufe0f":"",
                    "\u2022":"-", "\u2013":"-", "\u2014":"-", "\u2011":"-"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text).strip()


def _paragraph(text, style):
    return Paragraph(escape(_printable(str(text))).replace("\n", "<br/>"), style)


def _table(rows, widths, styles, caption=None):
    data = [[_paragraph(cell, styles["headcell"] if i == 0 else styles["cell"])
             for cell in row] for i, row in enumerate(rows)]
    header = 0
    if caption:
        data.insert(0, [_paragraph(caption, styles["section"])] + [""] * (len(widths)-1))
        header = 1
    table = Table(data, colWidths=widths, repeatRows=header+1, splitByRow=1, splitInRow=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,header), (-1,header), INK),
        ("ROWBACKGROUNDS", (0,header+1), (-1,-1), [colors.white, LIGHT]),
        ("LINEBELOW", (0,header), (-1,header), 1, TEAL),
        ("LINEBELOW", (0,header+1), (-1,-1), .4, colors.HexColor("#dce7e9")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    if caption:
        table.setStyle(TableStyle([("SPAN", (0,0), (-1,0)),
                                   ("LEFTPADDING", (0,0), (-1,0), 0),
                                   ("TOPPADDING", (0,0), (-1,0), 14)]))
    return table


def _section_table(contents, styles, caption=None):
    rows = [["Type", "Finding / location"]]
    for line in contents:
        # Validator totals count runs/occurrences, not the grouped rows in this report.
        if line.strip().startswith("Total"):
            continue
        if count_issues([line]):
            kind = "Review"
        elif line.startswith(("\u2714", "\u2705", "OK:")):
            kind = "OK"
        elif line.startswith(("\u2022", "-")):
            kind = "Location"
        else:
            kind = "Info"
        # Keep the first fragment short enough to share a page with its heading.
        # An enormous first row otherwise pushes the heading onto a new page.
        fragments = textwrap.wrap(line, width=1000, break_long_words=True,
                                  break_on_hyphens=False) or [line]
        for index, fragment in enumerate(fragments):
            rows.append([kind if index == 0 else "Continued", fragment])
    if len(rows) == 1:
        rows.append(["OK", "No findings returned by this automated check."])
    return _table(rows, [72, WIDTH-72], styles, caption)


def _page_chrome(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#dce7e9"))
    canvas.line(56, 751, 556, 751)
    canvas.setFont("ADF-Bold", 8)
    canvas.setFillColor(TEAL)
    canvas.drawString(56, 763, "ADF CHECK  /  DOCUMENT REVIEW")
    canvas.setFont("ADF", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(56, 30, "Automated formatting review | Manual review remains necessary")
    canvas.drawRightString(556, 30, f"Page {doc.page}")
    canvas.restoreState()


def _ai_note(result):
    if result is None:
        return "AI content estimate: not requested."
    if "error" in result:
        return "AI content estimate: unavailable. Formatting results are unaffected."
    try:
        real = float(result.get("real_probability", result.get("human")))
        fake = float(result.get("fake_probability", result.get("ai")))
        if not all(math.isfinite(n) and 0 <= n <= 1 for n in (real, fake)):
            raise ValueError("Invalid probability")
    except (ValueError, TypeError):
        return "AI content estimate: unavailable (invalid service response)."
    return (f"Optional AI estimate: human-written {real:.1%}; AI-generated {fake:.1%}. "
            "This estimate covers only the submitted excerpt and is not a plagiarism check or proof of authorship.")


def generate_comprehensive_pdf(all_errors: list, plagiarism_result: Optional[dict] = None, profile_name: Optional[str] = None) -> Optional[str]:
    """Return a unique report path. The caller owns successful output cleanup."""
    folder = None
    path = None
    try:
        folder = Path(tempfile.mkdtemp(prefix="adf-report-"))
        path = folder / "ADF_Validation_Report.pdf"
        styles = _build_styles()
        sections = _parse_sections(all_errors)
        included = {str(line).strip() for line in all_errors} & set(SECTION_TITLES)
        counts = {title: count_issues(lines) for title, lines in sections.items()}
        total = sum(counts.values())
        doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=56, rightMargin=56,
                                topMargin=62, bottomMargin=52, title="ADF Document Review", author="ADF Check")
        story = [_paragraph("Document formatting review", styles["title"]),
                 _paragraph(f"Generated {datetime.now().astimezone().strftime('%d %b %Y, %H:%M %Z')}", styles["muted"])]
        if profile_name:
            story.append(_paragraph(f"Formatting profile: {profile_name} (user-selected rules)", styles["muted"]))
        if total:
            verdict = f"Review needed: {total} issue group(s) across {sum(n > 0 for n in counts.values())} categories."
        elif len(included) < len(SECTION_TITLES):
            verdict = "Incomplete review: no issues reported in the supplied categories."
        else:
            verdict = "No issues detected by the automated checks."
        story += [_paragraph(verdict, styles["body"]),
                  _paragraph("Summary of findings", styles["section"])]
        rows = [["Check category", "Issue groups", "Result"]]
        for title in SECTION_TITLES:
            status = "Not supplied" if title not in included else ("Review" if counts[title] else "No findings")
            rows.append([title.removesuffix(" Errors"), str(counts[title]) if title in included else "-", status])
        rows.append(["TOTAL ISSUE GROUPS", str(total), f"{len(included)} / 9 supplied"])
        story.append(_table(rows, [280, 95, 125], styles))
        story += [Spacer(1,12), _paragraph("How to read this report", styles["section"]),
                  _paragraph("Counts represent reported issue groups, not individual affected runs or paragraphs. "
                             "Page locations in findings are estimates based on paragraph count. "
                             "APA references use pattern checks; no findings does not confirm that a reference list exists or is complete.", styles["muted"]),
                  _paragraph(_ai_note(plagiarism_result), styles["muted"])]
        details = [(title, lines) for title, lines in sections.items()
                   if any(not line.startswith("Total") for line in lines)]
        if details:
            story.append(PageBreak())
            story.append(_paragraph("Detailed findings", styles["title"]))
            for title, lines in details:
                caption = f"{title.removesuffix(' Errors')} | {counts[title]} issue group(s)"
                story.append(_section_table(lines, styles, caption))
                story.append(Spacer(1,8))
        doc.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome)
        return str(path)
    except Exception:
        logging.getLogger(__name__).exception("PDF report generation failed")
        if path is not None:
            path.unlink(missing_ok=True)
        if folder is not None:
            folder.rmdir()
        return None
