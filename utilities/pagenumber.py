from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

def is_page_number_field(paragraph):
    # Checks if PAGE field exists via field codes
    if paragraph._element.xpath('.//w:fldSimple[contains(@w:instr, "PAGE")]'):
        return True
    if paragraph._element.xpath('.//w:instrText[contains(text(), "PAGE")]'):
        return True
    for run in paragraph.runs:
        if 'PAGE' in run.text.upper():
            return True
    return False

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