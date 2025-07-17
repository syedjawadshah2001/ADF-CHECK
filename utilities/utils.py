import re

# --- Estimate Page Numbers Based on Paragraphs ---
def estimate_page_number(paragraph_index, paragraphs_per_page=40):
    return (paragraph_index // paragraphs_per_page) + 1



# --- Sanitize Reference Text ---
def sanitize_text(text):
    text = text.replace('\u200b', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    return text.strip()

# --- Validate APA References ---


def format_errors(errors, title):
    """Formats the errors for display."""
    formatted_errors = [title]
    total_errors = sum(len(issues) for issues in errors.values())
    formatted_errors.append(f"Total Errors: {total_errors}\n")

    for error_type, locations in sorted(errors.items()):
        formatted_errors.append(f"Error: {error_type}")
        formatted_errors.append(f"• Locations: {', '.join(map(str, locations))}\n")

    return formatted_errors