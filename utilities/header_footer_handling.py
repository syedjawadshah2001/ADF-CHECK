from collections import defaultdict
from utilities.utils import estimate_page_number , format_errors

def check_header_footer_styles(doc):
    errors = defaultdict(lambda: defaultdict(list))
    standard_font = "Arial"
    standard_size = 9  # Using points directly for clarity

    # Check Headers and Footers
    sections = doc.sections
    for section_idx, section in enumerate(sections):
        # Process headers
        for header in [section.header, section.even_page_header, section.first_page_header]:
            if header and header.is_linked_to_previous is False:
                for i, para in enumerate(header.paragraphs):
                    check_text_style(para, errors, f"Header (Section {section_idx + 1})", i, standard_font, standard_size)

        # Process footers
        for footer in [section.footer, section.even_page_footer, section.first_page_footer]:
            if footer and footer.is_linked_to_previous is False:
                for i, para in enumerate(footer.paragraphs):
                    check_text_style(para, errors, f"Footer (Section {section_idx + 1})", i, standard_font, standard_size)

    return format_header_footer_errors(errors, "Header & Footer Errors")

def check_text_style(para, errors, section_type, paragraph_index, standard_font, standard_size):
    """Checks font style and size for a given paragraph."""
    for run in para.runs:
        run_font = run.font.name if run.font and run.font.name else None
        run_size = run.font.size.pt if run.font and run.font.size else None

        # Check font style
        if run_font and run_font.lower() != standard_font.lower():
            errors[section_type]["Font Style"].append(paragraph_index + 1)

        # Check font size
        if run_size and run_size != standard_size:
            errors[section_type]["Font Size"].append(paragraph_index + 1)


def format_header_footer_errors(errors, title):
    """Formats the errors for display."""
    formatted_errors = [title]
    total_errors = sum(len(paras) for section in errors.values() for paras in section.values())
    formatted_errors.append(f"Total Errors: {total_errors}\n")

    for section, section_errors in sorted(errors.items()):
        for error_type, paragraphs in sorted(section_errors.items()):
            expected = "Arial, 9pt" if error_type == "Font Style" else "9pt"
            formatted_errors.append(f"Error: Incorrect {error_type} (Expected: {expected})")
            formatted_errors.append(f"• {section}: Paragraphs {', '.join(map(str, sorted(set(paragraphs))))}\n")
    
    return formatted_errors
