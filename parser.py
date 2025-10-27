import logging
import os
import re
import shutil
from typing import Dict, List, Optional

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - library optional at runtime
    fitz = None

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
except ImportError:  # pragma: no cover - library optional at runtime
    pdfminer_extract_text = None

try:
    from pdf2image import convert_from_path
    import pytesseract
except ImportError:  # pragma: no cover - OCR is an optional fallback
    convert_from_path = None
    pytesseract = None

try:
    import docx
except ImportError:  # pragma: no cover - library optional at runtime
    docx = None

PDF_TEXT_MIN_LENGTH = 80  # Heuristic threshold to trigger fallbacks
WINDOWS_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
WINDOWS_POPPLER_CANDIDATES = [
    r"C:\Program Files\poppler\Library\bin",
    r"C:\Program Files\poppler-24.02.0\Library\bin",
    r"C:\Program Files\poppler-24.07.0\Library\bin",
    r"C:\poppler\Library\bin",
    r"C:\poppler\bin",
]

_configured_poppler_path: Optional[str] = None
logger = logging.getLogger(__name__)

PDF_BACKENDS_AVAILABLE = bool(fitz) or bool(pdfminer_extract_text) or (
    convert_from_path is not None and pytesseract is not None
)


def _configure_ocr_backends() -> None:
    """Best-effort configuration for OCR toolchain on Windows installs."""
    global _configured_poppler_path

    if pytesseract:
        env_tesseract_cmd = os.getenv("TESSERACT_CMD")
        if env_tesseract_cmd and os.path.exists(env_tesseract_cmd):
            pytesseract.pytesseract.tesseract_cmd = env_tesseract_cmd
        else:
            existing_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "")
            if not shutil.which(existing_cmd):
                for candidate in WINDOWS_TESSERACT_CANDIDATES:
                    if os.path.exists(candidate):
                        pytesseract.pytesseract.tesseract_cmd = candidate
                        break

    poppler_env = os.getenv("POPPLER_PATH")
    potential_paths = []
    if poppler_env:
        potential_paths.append(poppler_env)
    potential_paths.extend(WINDOWS_POPPLER_CANDIDATES)
    for candidate in potential_paths:
        if candidate and os.path.isdir(candidate):
            _configured_poppler_path = candidate
            break


if convert_from_path and pytesseract:
    _configure_ocr_backends()


def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF, DOCX, or TXT files with graceful fallbacks."""
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            text = _extract_pdf_text(file_path)
        elif ext == ".docx":
            text = _extract_docx_text(file_path)
        elif ext == ".txt":
            text = _extract_txt_text(file_path)
        else:
            return f"Error: Unsupported file type for {file_path}"
    except ImportError as exc:
        return f"Error: {exc}"

    normalized = _normalize_text(text)

    if ext == ".pdf":
        if normalized:
            return normalized
        return (
            "Error: Unable to extract text from PDF. Install PyMuPDF or pdfminer.six "
            "and ensure OCR dependencies (Tesseract + Poppler) are configured."
        )

    return normalized


def _extract_pdf_text(file_path: str) -> str:
    """Attempt PyMuPDF, fall back to pdfminer, then OCR if needed."""
    if not PDF_BACKENDS_AVAILABLE:
        return (
            "Error: No PDF extraction backend available. Install PyMuPDF or pdfminer.six "
            "and configure OCR (pdf2image + pytesseract)."
        )

    text = ""

    if fitz:
        try:
            with fitz.open(file_path) as doc:
                text_chunks = [page.get_text("text", sort=True) for page in doc]
            text = "\n".join(text_chunks)
        except Exception:
            text = ""

    if len(text.strip()) < PDF_TEXT_MIN_LENGTH and fitz:
        try:
            with fitz.open(file_path) as doc:
                block_chunks: List[str] = []
                for page in doc:
                    blocks = page.get_text("blocks")
                    for block in blocks:
                        block_text = block[4]
                        if block_text:
                            block_chunks.append(block_text.strip())
                alt_text = "\n".join(block_chunks)
            if len(alt_text.strip()) > len(text.strip()):
                text = alt_text
        except Exception:
            pass

    if len(text.strip()) < PDF_TEXT_MIN_LENGTH and pdfminer_extract_text:
        try:
            text = pdfminer_extract_text(file_path) or text
        except Exception:
            pass

    if len(text.strip()) < PDF_TEXT_MIN_LENGTH and convert_from_path and pytesseract:
        try:
            text = _extract_pdf_via_ocr(file_path)
        except Exception:
            pass
        else:
            if text.strip():
                logger.info("OCR fallback succeeded for %s", file_path)
            else:
                logger.warning("OCR fallback yielded empty text for %s", file_path)
    elif len(text.strip()) < PDF_TEXT_MIN_LENGTH:
        logger.warning(
            "PDF text extraction produced < %s characters for %s",
            PDF_TEXT_MIN_LENGTH,
            file_path,
        )

    return text


def _extract_pdf_via_ocr(file_path: str) -> str:
    """Last-resort OCR extraction for image-based PDFs."""
    if not convert_from_path or not pytesseract:
        return ""

    kwargs = {}
    if _configured_poppler_path:
        kwargs["poppler_path"] = _configured_poppler_path

    images = convert_from_path(file_path, dpi=300, **kwargs)
    ocr_chunks = []
    for image in images:
        ocr_chunks.append(pytesseract.image_to_string(image))
    return "\n".join(ocr_chunks)


def _extract_docx_text(file_path: str) -> str:
    if not docx:
        raise ImportError("python-docx is required to read .docx files.")
    doc = docx.Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs)


def _extract_txt_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def _normalize_text(text: str) -> str:
    """Normalize whitespace and replace common unicode bullets/dashes."""
    if not text:
        return ""

    char_replacements = {
        "\u2022": "-",
        "\u2023": "-",
        "\u25e6": "-",
        "\u2043": "-",
        "\u2212": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2010": "-",
        "\u2012": "-",
        "\u2015": "-",
        "\uf0b7": "-",
        "\uf0d8": "-",
        "\uf0d9": "-",
        "\uf0da": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\u00ad": "-",
        "\u00b7": "-",
        "\u00a0": " ",
        "\u2024": ".",
    }
    string_replacements = {
        "â€“": "-",
        "â€”": "-",
        "â€•": "-",
    }

    translation_table = str.maketrans(char_replacements)
    cleaned = text.translate(translation_table)
    for source, target in string_replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = re.sub(r"\r\n?", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def parse_jd_sections(jd_text: str) -> Dict[str, str]:
    """Split a standardized JD into section blocks keyed by heading."""
    if not jd_text:
        return {}

    normalized = _normalize_text(jd_text)
    lines = normalized.splitlines()
    sections: Dict[str, str] = {}
    current_heading = "Overview"
    buffer: List[str] = []

    heading_pattern = re.compile(r"^[A-Z][A-Z\s/&-]{2,}$")
    known_headings = {
        "ROLE SUMMARY",
        "KEY RESPONSIBILITIES",
        "PRIMARY RESPONSIBILITIES",
        "POSITION OVERVIEW",
        "QUALIFICATIONS",
        "REQUIREMENTS",
        "SKILLS",
        "TOOLS & TECHNOLOGIES",
        "TECH STACK",
        "ABOUT THE COMPANY",
        "COMPENSATION & BENEFITS",
        "LOCATION",
    }

    def flush_buffer(title: str) -> None:
        content = "\n".join(buffer).strip()
        if content:
            sections[title] = content
        buffer.clear()

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if heading_pattern.match(upper) or upper in known_headings:
            flush_buffer(current_heading)
            current_heading = upper
            continue
        buffer.append(stripped)

    flush_buffer(current_heading)
    return sections
