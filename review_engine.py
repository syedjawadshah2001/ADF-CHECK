"""Structured findings, with stable paragraph references and explicit explanations."""
import re
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from utilities.formatting import iter_paragraphs, effective_font, is_caption
from utilities.profiles import profile_value, expected_typography
from utilities.spacing_handling import _line_spacing_multiple
from utilities.apa_handling import extract_references_from_docx, validate_apa_reference
from utilities.pagenumber import is_page_number_field
from utilities.report import SECTION_TITLES


def paragraph_index(document):
    section = 'Document opening'
    rows = []
    for number, para in enumerate(iter_paragraphs(document), 1):
        if para.style.name.startswith('Heading') and para.text.strip():
            section = para.text.strip()
        rows.append({'id': f'P{number}', 'number': number, 'text': para.text,
                     'heading': section, 'style': para.style.name})
    return rows


def inspect_document(document, selected_profile=None):
    profile = profile_value(selected_profile)
    paragraphs = paragraph_index(document)
    findings = []

    def add(category, location, found, expected, explanation, group=None):
        findings.append({'id': f'F{len(findings)+1}', 'category': category, 'location': location,
                         'found': str(found), 'expected': str(expected), 'explanation': explanation,
                         'correction_group': group})

    for row, para in zip(paragraphs, iter_paragraphs(document)):
        if not para.text.strip():
            continue
        expected_font, expected_size = expected_typography(para, profile)
        fonts = sorted({effective_font(run, para, 'name', expected_font) for run in para.runs if run.text.strip()})
        sizes = sorted({effective_font(run, para, 'size', Pt(expected_size)).pt for run in para.runs if run.text.strip()})
        if any(font.casefold() != expected_font.casefold() for font in fonts):
            add('Font Style Errors', row['id'], ', '.join(fonts), expected_font,
                'The text typeface differs from the selected profile.', 'fonts')
        if any(abs(size-expected_size) > .01 for size in sizes):
            add('Font Size Errors', row['id'], ', '.join(map(str, sizes))+' pt', f'{expected_size:g} pt',
                'Use the profile size for this body paragraph, heading or caption.', 'sizes')
        if is_caption(para) and (any(f.casefold() != expected_font.casefold() for f in fonts) or any(abs(s-expected_size) > .01 for s in sizes)):
            add('Table & Figure Caption Errors', row['id'], f'{", ".join(fonts)}; {sizes} pt',
                f'{expected_font}, {expected_size:g} pt', 'Caption typography should match the profile. This can overlap with font findings.')
        spacing = _line_spacing_multiple(para)
        if spacing is not None and abs(spacing-profile.line_spacing) > .01:
            add('Line Spacing Errors', row['id'], f'{spacing:g} lines' if spacing else 'Fixed-point spacing',
                f'{profile.line_spacing:g} lines', 'Consistent line spacing improves readability.', 'spacing')
        if para.style.name.startswith('Heading') and para.style.name not in ('Heading 1', 'Heading 2'):
            add('Heading Style Errors', row['id'], para.style.name, 'Heading 1 or Heading 2',
                'Review the heading hierarchy manually; the app does not infer its academic meaning.')
        elif not para.style.name.startswith('Heading') and para.text.isupper():
            add('Heading Style Errors', row['id'], para.style.name, 'Review whether this is a heading',
                'An all-capitals paragraph may be a heading; this is a heuristic and can be a false positive.')

    seen = set()
    for number, section in enumerate(document.sections, 1):
        for side in ('top', 'bottom', 'left', 'right'):
            margin = getattr(section, side+'_margin')
            target = getattr(profile, 'margin_'+side)
            if margin is None or abs(margin.inches-target) > .001:
                add('Margin Errors', f'Section {number}', f'{side}: {margin.inches:g} in' if margin else f'{side}: unspecified',
                    f'{target:g} in', f'The {side} margin must match the selected profile.', 'margins')
        for kind in ('header', 'footer', 'first_page_header', 'first_page_footer', 'even_page_header', 'even_page_footer'):
            part = getattr(section, kind)
            if part.is_linked_to_previous or part._element in seen:
                continue
            seen.add(part._element)
            for para in iter_paragraphs(part):
                for run in para.runs:
                    font = effective_font(run, para, 'name', profile.header_font)
                    size = effective_font(run, para, 'size', Pt(profile.header_size)).pt
                    if font.casefold() != profile.header_font.casefold() or abs(size-profile.header_size) > .01:
                        add('Header & Footer Errors', f'Section {number} {kind}', f'{font}, {size:g} pt',
                            f'{profile.header_font}, {profile.header_size:g} pt', 'Headers and footers have their own typography rule.', 'headers')
                        break
        variants = [('default', section.header)]
        if section.different_first_page_header_footer:
            variants.append(('first page', section.first_page_header))
        if document.settings.odd_and_even_pages_header_footer:
            variants.append(('even page', section.even_page_header))
        for name, header in variants:
            fields = [p for p in header.paragraphs if is_page_number_field(p)]
            if not fields:
                add('Page Number Errors', f'Section {number} {name} header', 'No PAGE field', 'Right-aligned PAGE field',
                    'Insert a page-number field in Word; automatic correction does not invent one.')
            elif any(p.alignment != WD_ALIGN_PARAGRAPH.RIGHT for p in fields):
                add('Page Number Errors', f'Section {number} {name} header', 'Page field not right-aligned', 'Right aligned',
                    'Existing header page-number fields can be aligned automatically.', 'headers')

    references = extract_references_from_docx(document)
    for reference in references:
        if not validate_apa_reference(reference):
            row = next((r for r in paragraphs if r['text'].strip() == reference), None)
            add('Reference Errors', row['id'] if row else 'Reference list', reference[:500], 'Review APA reference format',
                'This reference did not match the supported APA patterns. Verify manually; no source lookup was performed.')
    flat = []
    for category in SECTION_TITLES:
        flat.append(category)
        flat.extend(f"Error: [{f['location']}] Found: {f['found']}. Expected: {f['expected']}. {f['explanation']}"
                    for f in findings if f['category'] == category)
    return {'findings': findings, 'paragraphs': paragraphs, 'errors': flat, 'profile': profile.model_dump()}


def readiness(review):
    """Evidence-based task plan, never an academic pass/fail score."""
    tasks = []
    profile = review['profile']
    rows = review['paragraphs']
    aliases = {'References': ('references', 'bibliography'), 'Methodology': ('methodology', 'methods', 'research methodology'),
               'Results': ('results', 'findings', 'results and discussion'), 'Conclusion': ('conclusion', 'conclusions'),
               'Literature review': ('literature review', 'review of literature')}
    for name in dict.fromkeys(profile['required_sections']):
        def matches(row):
            text = re.sub(r'^(?:chapter\s+)?[\divx]+[\s.:\-]+', '', row['text'].strip(), flags=re.I).strip().casefold().rstrip(':')
            return text in aliases.get(name, (name.casefold(),))
        evidence = next((r for r in rows if matches(r)), None)
        tasks.append({'id': f'section:{name}', 'title': f'{name} section', 'status': 'detected' if evidence else 'needs_review',
                      'kind': 'structure', 'location': evidence['id'] if evidence else None,
                      'detail': 'A matching heading was detected; content quality still needs review.' if evidence else 'No matching heading found. Check the document manually.'})
    grouped = {}
    for finding in review['findings']:
        grouped.setdefault(finding['category'], []).append(finding)
    for name, findings in grouped.items():
        tasks.append({'id': f'format:{name}', 'title': name.replace(' Errors', ''), 'status': 'needs_review', 'kind': 'formatting',
                      'location': findings[0]['location'], 'detail': f'{len(findings)} finding(s). Review the evidence and preview available corrections.'})
    tasks.append({'id': 'manual:academic', 'title': 'Academic and citation review', 'status': 'manual_required', 'kind': 'manual',
                  'location': None, 'detail': 'Confirm references, originality, accuracy, department approval and final page layout yourself.'})
    return {'status': 'needs_review' if grouped or any(t['status']=='needs_review' for t in tasks) else 'manual_review_remaining',
            'tasks': tasks, 'steps': ['Profile selected', 'Formatting checked', 'Structure screened', 'Corrections require approval', 'Final human review'],
            'note': 'Local rule-based workflow. Detected sections do not prove completeness, and acknowledgements do not remove findings.'}
