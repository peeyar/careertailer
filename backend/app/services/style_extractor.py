import io
from dataclasses import dataclass, asdict
from typing import Optional
from collections import Counter
from docx import Document as DocxDocument


@dataclass
class ResumeStyle:
    body_font:   str = "Calibri"
    body_size:   int = 11
    header_font: str = "Calibri"
    header_size: int = 14


DEFAULT_STYLE = ResumeStyle()


# Map PDF font names → Word-compatible equivalents
_FONT_MAP = {
    "helveticaneue":       "Helvetica Neue",
    "helvetica":           "Arial",
    "arial":               "Arial",
    "timesnewroman":       "Times New Roman",
    "timesnewromanps":     "Times New Roman",
    "timesnewromanpsmt":   "Times New Roman",
    "garamond":            "Garamond",
    "georgia":             "Georgia",
    "trebuchetms":         "Trebuchet MS",
    "verdana":             "Verdana",
    "calibri":             "Calibri",
    "cambria":             "Cambria",
    "gillsans":            "Gill Sans MT",
    "futura":              "Century Gothic",  # closest common Word substitute
}

# PDF suffixes to strip before lookup
_PDF_SUFFIXES = ("psmt", "ps", "mt", "bold", "italic", "bolditalic", "oblique", "regular")


def _clean_font_name(name: str) -> str:
    """Normalize PDF font name to a Word-compatible name.
    Handles prefixes like 'ABCDEF+Calibri-Bold' and suffixes like 'TimesNewRomanPSMT'.
    """
    # Strip subset prefix (e.g. 'ABCDEF+')
    if '+' in name:
        name = name.split('+')[1]

    # Strip style suffix after '-' (e.g. 'Calibri-Bold' → 'Calibri')
    if '-' in name:
        name = name.split('-')[0]

    name = name.strip()

    # Try exact lookup (case-insensitive)
    lookup = name.lower().replace(" ", "")
    if lookup in _FONT_MAP:
        return _FONT_MAP[lookup]

    # Strip known PDF suffixes and retry (e.g. 'TimesNewRomanPSMT' → 'TimesNewRoman')
    for suffix in _PDF_SUFFIXES:
        if lookup.endswith(suffix):
            trimmed = lookup[: -len(suffix)]
            if trimmed in _FONT_MAP:
                return _FONT_MAP[trimmed]

    return name


def extract_from_docx(file_bytes: bytes) -> ResumeStyle:
    """Read paragraph styles from python-docx.
    Heading paragraphs → header font/size, Normal paragraphs → body font/size.
    Uses most common value across all runs. Falls back to DEFAULT_STYLE on any exception.
    """
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))

        body_fonts: list[str] = []
        body_sizes: list[int] = []
        header_fonts: list[str] = []
        header_sizes: list[int] = []

        for para in doc.paragraphs:
            style_name = (para.style.name or "").lower()
            is_heading = "heading" in style_name or para.style.font.bold

            for run in para.runs:
                font_name = run.font.name
                font_size = run.font.size

                if font_name:
                    if is_heading:
                        header_fonts.append(font_name)
                    else:
                        body_fonts.append(font_name)

                if font_size:
                    size_pt = int(font_size.pt) if hasattr(font_size, 'pt') else int(font_size / 12700)
                    if is_heading:
                        header_sizes.append(size_pt)
                    else:
                        body_sizes.append(size_pt)

        body_font   = Counter(body_fonts).most_common(1)[0][0]   if body_fonts   else DEFAULT_STYLE.body_font
        body_size   = Counter(body_sizes).most_common(1)[0][0]   if body_sizes   else DEFAULT_STYLE.body_size
        header_font = Counter(header_fonts).most_common(1)[0][0] if header_fonts else body_font
        header_size = Counter(header_sizes).most_common(1)[0][0] if header_sizes else DEFAULT_STYLE.header_size

        return ResumeStyle(
            body_font=body_font,
            body_size=body_size,
            header_font=header_font,
            header_size=header_size,
        )
    except Exception as e:
        print(f"⚠️  Style extract (docx) failed: {e}")
        return DEFAULT_STYLE


def extract_from_pdf(file_bytes: bytes) -> ResumeStyle:
    """Uses pdfplumber page.chars for per-character font metadata.
    Most common font/size → body; chars with size > body+1 → header candidates.
    Falls back to DEFAULT_STYLE on any exception.
    """
    try:
        import pdfplumber

        all_fonts: list[str] = []
        all_sizes: list[float] = []

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                for char in (page.chars or []):
                    font = char.get("fontname", "")
                    size = char.get("size", 0)
                    if font and size:
                        all_fonts.append(_clean_font_name(font))
                        all_sizes.append(round(size))

        if not all_fonts:
            return DEFAULT_STYLE

        body_font = Counter(all_fonts).most_common(1)[0][0]
        body_size = int(Counter(all_sizes).most_common(1)[0][0])

        # Header candidates: chars with font size noticeably larger than body
        header_size_threshold = body_size + 1
        header_chars = [
            (f, s) for f, s in zip(all_fonts, all_sizes)
            if s > header_size_threshold
        ]

        if header_chars:
            h_fonts, h_sizes = zip(*header_chars)
            header_font = Counter(h_fonts).most_common(1)[0][0]
            header_size = int(Counter(h_sizes).most_common(1)[0][0])
        else:
            header_font = body_font
            header_size = DEFAULT_STYLE.header_size

        return ResumeStyle(
            body_font=body_font,
            body_size=body_size,
            header_font=header_font,
            header_size=header_size,
        )
    except Exception as e:
        print(f"⚠️  Style extract (pdf) failed: {e}")
        return DEFAULT_STYLE


def extract(file_bytes: bytes, file_type: str) -> ResumeStyle:
    """Extract style from file bytes.
    file_type: 'pdf' | 'docx' | 'txt'
    """
    if file_type == 'docx':
        return extract_from_docx(file_bytes)
    if file_type == 'pdf':
        return extract_from_pdf(file_bytes)
    return DEFAULT_STYLE  # txt — no formatting to extract
