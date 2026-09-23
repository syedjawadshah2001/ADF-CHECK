import docx
import re
from utilities.utils import sanitize_text


def validate_apa_reference(reference):
    reference = sanitize_text(reference)
    patterns = [
        r"^[A-Za-z]+,\s([A-Z]\.\s?)+\(\d{4}\)\.\s.+?\.\s[A-Za-z\s]+[.]$",  # General book format
        r"^[A-Za-z]+,\s([A-Z]\.\s?)+\(\d{4}\)\.\s.+?\.\shttps?:\/\/\S+$"   # Online source format
    ]
    for pattern in patterns:
        if re.match(pattern, reference):
            return True
    return False

def extract_references_from_docx(file_path):
    doc = docx.Document(file_path)
    references = []
    capture = False

    for para in doc.paragraphs:
        text = para.text.strip()
        if "References" in text:
            capture = True
            continue
        if capture and text:
            references.append(text)

    return references
