import docx
import re
from utilities.utils import sanitize_text

# ---------------------------------------------------------------------------
# APA 7th edition reference patterns
# ---------------------------------------------------------------------------
# Author block: one or more "Last, F. M." entries joined by ", " and "& "
_AUTHOR = r"[A-Za-zÀ-ɏ'\-]+"          # last name (supports accented chars)
_INIT   = r"[A-Z]\.(?:\s?[A-Z]\.)?"              # one or two initials, e.g. "A." or "A. B."
_ONE_AUTHOR = rf"{_AUTHOR},\s{_INIT}"
_AUTHORS = (
    rf"(?:{_ONE_AUTHOR}"                          # first author
    rf"(?:,\s{_ONE_AUTHOR})*"                     # additional authors
    rf"(?:,?\s&\s{_ONE_AUTHOR})?"                 # final author after "&"
    rf")"
)
_YEAR       = r"\(\d{{4}}[a-z]?\)"               # (2023) or (2023a)
_YEAR_ND    = r"\(n\.d\.\)"                       # (n.d.)
_YEAR_DATE  = r"\(\d{{4}},\s[A-Za-z]+(?:\s\d{{1,2}})?\)"  # (2023, March 5)
_ANY_YEAR   = rf"(?:{_YEAR}|{_YEAR_ND}|{_YEAR_DATE})"
_TITLE      = r".+?"                              # any title text (non-greedy)
_URL        = r"https?://\S+"

APA_PATTERNS = [
    # ── Journal article ──────────────────────────────────────────────────
    # Author, A. A. (Year). Title. Journal Name, vol(issue), pp–pp.
    # Author, A. A. (Year). Title. Journal Name, vol(issue), pp–pp. https://doi.org/...
    rf"^{_AUTHORS}\s{_ANY_YEAR}\.\s{_TITLE}\.\s[A-Z][^,]+,\s\d+(?:\(\d+\))?,\s\d+[–\-]\d+\.?(?:\s{_URL})?$",

    # ── Book ─────────────────────────────────────────────────────────────
    # Author, A. A. (Year). Title of book. Publisher.
    rf"^{_AUTHORS}\s{_ANY_YEAR}\.\s{_TITLE}\.\s[A-Za-z][^.]+\.$",

    # ── Book chapter ─────────────────────────────────────────────────────
    # Author, A. A. (Year). Chapter title. In E. Editor (Ed.), Book title (pp. x–y). Publisher.
    rf"^{_AUTHORS}\s{_ANY_YEAR}\.\s{_TITLE}\.\sIn\s.+?\(Ed[s]?\.\),\s{_TITLE}\s\(pp\.\s\d+[–\-]\d+\)\.\s.+\.$",

    # ── Online / URL source ───────────────────────────────────────────────
    # Author, A. A. (Year). Title. Site Name. https://...
    rf"^{_AUTHORS}\s{_ANY_YEAR}\.\s{_TITLE}\.\s.+?\.\s{_URL}$",

    # ── Online with date ─────────────────────────────────────────────────
    # Author, A. A. (2023, March 5). Title. Site Name. https://...
    rf"^{_AUTHORS}\s{_YEAR_DATE}\.\s{_TITLE}\.\s.+?\.\s{_URL}$",

    # ── No date ──────────────────────────────────────────────────────────
    # Author, A. A. (n.d.). Title. Publisher.
    rf"^{_AUTHORS}\s{_YEAR_ND}\.\s{_TITLE}\.\s[A-Za-z][^.]+\.$",
]

# Pre-compile for performance
_COMPILED = [re.compile(p) for p in APA_PATTERNS]


def validate_apa_reference(reference: str) -> bool:
    reference = sanitize_text(reference)
    if len(reference) < 15:
        return False
    for pattern in _COMPILED:
        if pattern.match(reference):
            return True
    return False


def extract_references_from_docx(file_path) -> list[str]:
    doc = file_path if hasattr(file_path, "paragraphs") else docx.Document(file_path)
    references = []
    capture = False

    for para in doc.paragraphs:
        text = para.text.strip()
        # Start capturing after a heading that contains "References" or "Bibliography"
        if re.fullmatch(r"(?:References|Bibliography)\s*:?", text, re.IGNORECASE):
            capture = True
            continue
        if capture and text:
            # Stop at the next major heading (all-caps short line or Heading style)
            if para.style.name.startswith("Heading") and text.lower() not in ("references", "bibliography"):
                break
            references.append(text)

    return references
