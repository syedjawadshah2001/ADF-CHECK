from collections import defaultdict
from utilities.utils import estimate_page_number , format_errors

# --- Validate line spacing ---
def check_line_spacing(document):  # ✅ Corrected: Function is properly separated
    errors = defaultdict(list)
    standard_spacing = 1.5

    for i, para in enumerate(document.paragraphs):
        spacing = para.paragraph_format.line_spacing
        if spacing and spacing != standard_spacing:
            page_num = estimate_page_number(i)
            errors[page_num].append(i + 1)  # Store paragraph number

    formatted_errors = ["Line Spacing Errors", f"Total Line Spacing Errors: {sum(len(paras) for paras in errors.values())}"]

    for page_num, paragraphs in sorted(errors.items()):
        formatted_errors.append(f"Error: Incorrect line spacing (Expected: {standard_spacing})")
        formatted_errors.append(f"• Page {page_num}: Paragraphs {', '.join(map(str, sorted(set(paragraphs))))}")
        formatted_errors.append("")  # Add a blank line for readability

    return formatted_errors