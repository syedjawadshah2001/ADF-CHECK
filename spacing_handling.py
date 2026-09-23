from collections import defaultdict
from utilities.formatting import iter_paragraphs
from typing import Optional
from docx.oxml.ns import qn
from utilities.utils import estimate_page_number


def _line_spacing_multiple(para) -> Optional[float]:
    """Resolve direct and inherited spacing; fixed point spacing is not 1.5 lines."""
    from docx.shared import Length
    value = para.paragraph_format.line_spacing
    style = para.style
    visited = set()
    while value is None and style is not None and style.style_id not in visited:
        visited.add(style.style_id)
        value = style.paragraph_format.line_spacing
        style = style.base_style
    if isinstance(value, Length):
        return 0.0
    return float(value) if value is not None else None


def check_line_spacing(document) -> list[str]:
    errors: dict[int, list[tuple[int, float]]] = defaultdict(list)
    standard = 1.5

    for i, para in enumerate(iter_paragraphs(document)):
        spacing = _line_spacing_multiple(para)
        if spacing is not None and abs(spacing - standard) > 0.01:
            page_num = estimate_page_number(i)
            errors[page_num].append((i + 1, spacing))

    total = sum(len(v) for v in errors.values())
    result = ["Line Spacing Errors", f"Total Line Spacing Errors: {total}"]

    for page_num, items in sorted(errors.items()):
        for para_num, found in sorted(items):
            result.append(
                f"Error: Incorrect line spacing (Expected: {standard}×, Found: {found:.2f}×)"
            )
            result.append(f"• Page {page_num}: Paragraph {para_num}")
        result.append("")

    return result
