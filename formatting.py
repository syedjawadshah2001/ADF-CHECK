"""Shared formatting rules for analysis and automatic correction."""
import re


def iter_paragraphs(container):
    yield from container.paragraphs
    for table in container.tables:
        seen = set()
        for row in table.rows:
            for cell in row.cells:
                if cell._tc not in seen:
                    seen.add(cell._tc)
                    yield from iter_paragraphs(cell)


def is_caption(para):
    return para.style.name == "Caption" or bool(re.match(r"^(table|figure)\s+\d+\b", para.text.strip(), re.I))


def effective_font(run, para, attribute, default):
    value = getattr(run.font, attribute)
    if value is not None:
        return value
    for style in (run.style, para.style):
        visited = set()
        while style is not None and style.style_id not in visited:
            visited.add(style.style_id)
            value = getattr(style.font, attribute)
            if value is not None:
                return value
            style = style.base_style
    return default
