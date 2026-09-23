from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

def is_page_number_field(paragraph):
    """Match PAGE fields, never plain text or NUMPAGES fields."""
    import re
    codes = paragraph._element.xpath('.//w:fldSimple/@w:instr')
    codes += [node.text or "" for node in paragraph._element.xpath('.//w:instrText')]
    return any(re.match(r"^\s*PAGE(?:\s|$)", code, re.I) for code in codes)

def check_page_number_format(doc_path):
    doc = Document(doc_path)

    for section in doc.sections:
        header = section.header
        for para in header.paragraphs:
            if is_page_number_field(para):
                if para.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
                    return "✔ Page number is in header and correctly top-right aligned"
                else:
                    return "❌ Page number is in header but not right-aligned"
    
    return "❌ No page number found in header"