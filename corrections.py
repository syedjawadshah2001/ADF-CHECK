"""Server-side before/after previews and approval-bound correction tokens."""
import hashlib
import json
from io import BytesIO
from docx import Document
from utilities.document import corrected_bytes
from utilities.formatting import iter_paragraphs, effective_font
from utilities.profiles import profile_value, CORRECTION_GROUPS
from utilities.pagenumber import is_page_number_field
from utilities.spacing_handling import _line_spacing_multiple


def _snapshot(doc):
    state = {}
    def paragraph(para, location, header=False):
        text = para.text[:180] or '(Field or empty paragraph)'
        fonts = sorted({effective_font(r, para, 'name', 'Unspecified / theme font') for r in para.runs})
        sizes = sorted({str(value.pt) if value is not None else 'Inherited / unspecified'
                        for r in para.runs for value in [effective_font(r, para, 'size', None)]})
        state[(location, 'headers' if header else 'fonts', 'font')] = (', '.join(fonts), text)
        state[(location, 'headers' if header else 'sizes', 'size')] = (', '.join(sizes), text)
        if header:
            if is_page_number_field(para):
                state[(location, 'headers', 'alignment')] = (str(para.alignment), text)
        else:
            value = _line_spacing_multiple(para)
            state[(location, 'spacing', 'line spacing')] = (str(value) if value is not None else 'Inherited / unspecified', text)
    for index, para in enumerate(iter_paragraphs(doc), 1):
        paragraph(para, f'P{index}')
    for index, section in enumerate(doc.sections, 1):
        for side in ('top', 'bottom', 'left', 'right'):
            value = getattr(section, side+'_margin')
            state[(f'Section {index}', 'margins', side+' margin')] = (f'{value.inches:g} in' if value else 'Unspecified', '')
        for kind in ('header', 'footer', 'first_page_header', 'first_page_footer', 'even_page_header', 'even_page_footer'):
            part = getattr(section, kind)
            if not part.is_linked_to_previous:
                for number, para in enumerate(iter_paragraphs(part), 1):
                    paragraph(para, f'Section {index} {kind} paragraph {number}', True)
    return state


def preview(data, profile, groups):
    selected = sorted(set(groups))
    if not selected or not set(selected).issubset(CORRECTION_GROUPS):
        raise ValueError('Select at least one valid correction category.')
    profile = profile_value(profile).model_dump()
    before = _snapshot(Document(BytesIO(data)))
    corrected = corrected_bytes(data, profile, selected)
    after = _snapshot(Document(BytesIO(corrected)))
    changes = []
    for (location, group, field), (value, text) in before.items():
        new = after.get((location, group, field), (value, text))[0]
        if value != new:
            changes.append({'location': location, 'group': group, 'field': field, 'before': value, 'after': new, 'text': text})
    token = hashlib.sha256(data + json.dumps({'profile': profile, 'groups': selected}, sort_keys=True).encode()).hexdigest()
    return {'preview_id': token, 'groups': selected, 'total_changes': len(changes), 'changes': changes[:150],
            'counts': {g: sum(c['group']==g for c in changes) for g in selected},
            'note': 'Formatting-property preview, not a Word page rendering. Showing up to 150 changes. Text is preserved; review final page layout in Word.'}, corrected
