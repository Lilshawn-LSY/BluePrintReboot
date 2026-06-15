from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None


def extract_pdf_text_with_pypdf(pdf_path: Path, max_pages: int = 3) -> str:
    reader = PdfReader(str(pdf_path))
    text_parts: list[str] = []
    for page_number, page in enumerate(reader.pages):
        if page_number >= max_pages:
            break
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def extract_pdf_text_with_markitdown(pdf_path: Path) -> str:
    if MarkItDown is None:
        return ""

    try:
        result = MarkItDown().convert(str(pdf_path))
    except Exception:
        return ""
    return str(getattr(result, "text_content", "") or "")
