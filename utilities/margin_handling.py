from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls


def highlight_margin_error(section):
    sectPr = section._sectPr
    borders = parse_xml(r"""
        <w:pgBorders {0}>
            <w:top w:val="single" w:sz="4" w:space="24" w:color="FF0000"/>
            <w:left w:val="single" w:sz="4" w:space="24" w:color="FF0000"/>
            <w:bottom w:val="single" w:sz="4" w:space="24" w:color="FF0000"/>
            <w:right w:val="single" w:sz="4" w:space="24" w:color="FF0000"/>
        </w:pgBorders>
    """.format(nsdecls('w')))
    sectPr.append(borders)

def check_margins(document):
    errors = []
    standard_margin = 1.0
    for i, section in enumerate(document.sections):
        top = section.top_margin.inches
        bottom = section.bottom_margin.inches
        left = section.left_margin.inches
        right = section.right_margin.inches
        if any(m != standard_margin for m in [top, bottom, left, right]):
            highlight_margin_error(section)
            errors.append(f"\u274C Section {i+1}: Margins not set to 1 inch.")
    return errors


