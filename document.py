"""Content-preserving ADF formatting automation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from utilities.formatting import iter_paragraphs, is_caption
from utilities.pagenumber import is_page_number_field
from utilities.profiles import profile_value, expected_typography, CORRECTION_GROUPS

def correct_document(doc, selected_profile=None, groups=None):
    """Match the existing checker's Arial/12pt standard without rewriting text."""
    profile = profile_value(selected_profile)
    groups = set(CORRECTION_GROUPS if groups is None else groups)
    if not groups.issubset(CORRECTION_GROUPS):
        raise ValueError("Unknown correction category")
    for para in iter_paragraphs(doc):
        if "spacing" in groups:
            para.paragraph_format.line_spacing = profile.line_spacing
        font, size = expected_typography(para, profile)
        for run in para.runs:
            if "fonts" in groups:
                run.font.name = font
            if "sizes" in groups:
                run.font.size = Pt(size)
    seen = set()
    for section in doc.sections:
        if "margins" in groups:
            for side in ("top", "bottom", "left", "right"):
                setattr(section, side+"_margin", Inches(getattr(profile, "margin_"+side)))
        if "headers" not in groups:
            continue
        for kind in ("header", "footer", "first_page_header", "first_page_footer", "even_page_header", "even_page_footer"):
            part = getattr(section, kind)
            if part.is_linked_to_previous or part._element in seen:
                continue
            seen.add(part._element)
            for para in iter_paragraphs(part):
                for run in para.runs:
                    run.font.name = profile.header_font
                    run.font.size = Pt(profile.header_size)
                if "header" in kind and is_page_number_field(para):
                    para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return doc

def corrected_bytes(data, selected_profile=None, groups=None):
    output = BytesIO()
    correct_document(Document(BytesIO(data)), selected_profile, groups).save(output)
    return output.getvalue()
