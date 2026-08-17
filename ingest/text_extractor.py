from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ingest.document_text import MarkItDown, PdfReader, get_text_extraction_backends
from ingest.pdf_inspector_adapter import (
    StructuredPdfExtraction,
    canonical_full_text_projection,
    extract_structured_pdf,
    pdf_inspector_available,
)


@dataclass(frozen=True)
class FullTextExtractionResult:
    text: str = ""
    source: str = "none"
    char_count: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "failed"
    attempted_methods: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    structured_extraction: StructuredPdfExtraction | None = None
    provider: str = "none"
    provider_version: str = ""
    content_format: Literal["markdown", "plain_text"] = "plain_text"


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
    structured = extract_structured_pdf(pdf_path)
    if structured.status != "not_extracted":
        attempted_methods.append("pdf-inspector")
    if structured.status == "failed":
        errors.extend(structured.errors)
    structured_projection = canonical_full_text_projection(structured)
    if structured.status != "failed" and structured_projection:
        return _success(
            structured_projection,
            "pdf-inspector",
            errors,
            attempted_methods,
            warnings=structured.warnings,
            structured_extraction=structured,
            status=structured.status,
            provider=structured.provider,
            provider_version=structured.provider_version,
            content_format="markdown" if structured.markdown or any(page.markdown for page in structured.pages) else "plain_text",
        )

    if MarkItDown is not None:
        attempted_methods.append("markitdown")
        try:
            result = MarkItDown().convert(str(pdf_path))
            text = str(getattr(result, "text_content", "") or "")
        except Exception as exc:
            errors.append(f"markitdown: {exc}")
        if text.strip():
            return _success(
                text,
                "markitdown",
                errors,
                attempted_methods,
                warnings=structured.warnings,
                structured_extraction=structured,
                status="ocr_needed" if structured.status == "ocr_needed" else "success",
                provider="markitdown",
                content_format="markdown",
            )
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
            return _success(
                text,
                "pypdf",
                errors,
                attempted_methods,
                warnings=structured.warnings,
                structured_extraction=structured,
                status="ocr_needed" if structured.status == "ocr_needed" else "success",
                provider="pypdf",
            )
    else:
        errors.append("pypdf: unavailable")

    return FullTextExtractionResult(
        text=text,
        source="none",
        char_count=len(text),
        errors=(errors or ["No readable text extracted."]) if structured.status != "ocr_needed" else errors,
        status="ocr_needed" if structured.status == "ocr_needed" else "empty" if not text.strip() else "failed",
        attempted_methods=attempted_methods,
        warnings=structured.warnings,
        structured_extraction=structured,
        provider=structured.provider if structured.status != "not_extracted" else "none",
        provider_version=structured.provider_version,
    )


def extraction_diagnostics(pdf_path: Path) -> dict[str, object]:
    pdf_path = Path(pdf_path)
    exists = pdf_path.exists() and pdf_path.is_file()
    return {
        "pdf_path": str(pdf_path),
        "pdf_exists": exists,
        "pdf_size_mb": round(pdf_path.stat().st_size / (1024 * 1024), 6) if exists else 0.0,
        "pdf_inspector": pdf_inspector_available(),
        **get_text_extraction_backends(),
    }


def _success(
    text: str,
    source: str,
    errors: list[str],
    attempted_methods: list[str],
    *,
    warnings: list[str] | None = None,
    structured_extraction: StructuredPdfExtraction | None = None,
    status: str = "success",
    provider: str | None = None,
    provider_version: str = "",
    content_format: Literal["markdown", "plain_text"] = "plain_text",
) -> FullTextExtractionResult:
    return FullTextExtractionResult(
        text=text,
        source=source,
        char_count=len(text),
        errors=errors,
        status=status,
        attempted_methods=attempted_methods,
        warnings=list(warnings or []),
        structured_extraction=structured_extraction,
        provider=provider or source,
        provider_version=provider_version,
        content_format=content_format,
    )
