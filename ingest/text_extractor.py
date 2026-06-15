from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ingest.document_text import MarkItDown, PdfReader, get_text_extraction_backends


@dataclass(frozen=True)
class FullTextExtractionResult:
    text: str = ""
    source: str = "none"
    char_count: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "failed"
    attempted_methods: list[str] = field(default_factory=list)


def extract_full_text_from_pdf(pdf_path: Path) -> FullTextExtractionResult:
    pdf_path = Path(pdf_path)
    errors: list[str] = []
    attempted_methods: list[str] = []
    if not pdf_path.exists() or not pdf_path.is_file():
        return FullTextExtractionResult(
            errors=[f"PDF file not found: {pdf_path}"],
            attempted_methods=attempted_methods,
        )

    text = ""
    if MarkItDown is not None:
        attempted_methods.append("markitdown")
        try:
            result = MarkItDown().convert(str(pdf_path))
            text = str(getattr(result, "text_content", "") or "")
        except Exception as exc:
            errors.append(f"markitdown: {exc}")
        if text.strip():
            return _success(text, "markitdown", errors, attempted_methods)
    else:
        errors.append("markitdown: unavailable")

    if PdfReader is not None:
        attempted_methods.append("pypdf")
        try:
            reader = PdfReader(str(pdf_path))
            parts = [(page.extract_text() or "") for page in reader.pages]
            text = "\n".join(parts)
        except Exception as exc:
            errors.append(f"pypdf: {exc}")
        if text.strip():
            return _success(text, "pypdf", errors, attempted_methods)
    else:
        errors.append("pypdf: unavailable")

    return FullTextExtractionResult(
        text=text,
        source="none",
        char_count=len(text),
        errors=errors or ["No readable text extracted."],
        status="empty" if not text.strip() else "failed",
        attempted_methods=attempted_methods,
    )


def extraction_diagnostics(pdf_path: Path) -> dict[str, object]:
    pdf_path = Path(pdf_path)
    exists = pdf_path.exists() and pdf_path.is_file()
    return {
        "pdf_path": str(pdf_path),
        "pdf_exists": exists,
        "pdf_size_mb": round(pdf_path.stat().st_size / (1024 * 1024), 6) if exists else 0.0,
        **get_text_extraction_backends(),
    }


def _success(
    text: str,
    source: str,
    errors: list[str],
    attempted_methods: list[str],
) -> FullTextExtractionResult:
    return FullTextExtractionResult(
        text=text,
        source=source,
        char_count=len(text),
        errors=errors,
        status="success",
        attempted_methods=attempted_methods,
    )
