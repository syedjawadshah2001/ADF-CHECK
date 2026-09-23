"""Document analysis independent of the web interface."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from utilities.document import corrected_bytes
from utilities.review_engine import inspect_document, readiness
from utilities.formatting import iter_paragraphs
from utilities.report import generate_comprehensive_pdf
from utilities.ai_plagiarism import check_ai_plagiarism

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def analyze(data, include_ai=False, progress=None, selected_profile=None, generate_correction=True):
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Please upload a document smaller than 20 MB.")
    try:
        with ZipFile(BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("This document is too large after decompression.")
            if "word/document.xml" not in archive.namelist():
                raise ValueError("Please upload a valid Word document.")
    except BadZipFile as exc:
        raise ValueError("Please upload a valid Word .docx document.") from exc
    document = Document(BytesIO(data))
    review = inspect_document(document, selected_profile)
    text = "\n".join(p.text for p in document.paragraphs)
    ai = check_ai_plagiarism(text) if include_ai else None
    report_path = generate_comprehensive_pdf(review['errors'], ai, review['profile']['name'])
    if not report_path:
        raise ValueError("The report could not be generated. Please try again.")
    path = Path(report_path)
    try:
        pdf = path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
        path.parent.rmdir()
    bad_sizes = {f['location'] for f in review['findings'] if f['category'] == 'Font Size Errors'}
    for number, paragraph in enumerate(iter_paragraphs(document), 1):
        if f'P{number}' in bad_sizes:
            for run in paragraph.runs:
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW
    highlighted = BytesIO()
    document.save(highlighted)
    return {**review, "ai": ai, "pdf": pdf, "original": data,
            "highlighted": highlighted.getvalue(),
            "corrected": corrected_bytes(data, review['profile']) if generate_correction else None,
            "words": len(text.split()), "readiness": readiness(review)}
