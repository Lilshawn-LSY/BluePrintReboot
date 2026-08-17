from __future__ import annotations

from dataclasses import asdict, dataclass, field
from importlib import metadata as importlib_metadata
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

try:
    import pdf_inspector as _pdf_inspector
except ImportError:  # Optional dependency; compatibility extractors remain available.
    _pdf_inspector = None


DocumentClassification = Literal["text", "scanned", "image-based", "mixed", "unknown"]
PageExtractionState = Literal["success", "ocr_needed", "failed"]
StructuredExtractionState = Literal["not_extracted", "success", "ocr_needed", "failed"]


@dataclass(frozen=True)
class PositionedPdfText:
    page_number: int
    text: str
    x: float
    y: float
    width: float
    height: float
    font: str = ""
    font_size: float = 0.0
    is_bold: bool = False
    is_italic: bool = False
    item_type: str = "text"


@dataclass(frozen=True)
class StructuredPdfPage:
    page_number: int
    state: PageExtractionState
    text: str = ""
    markdown: str = ""
    positioned_text: list[PositionedPdfText] = field(default_factory=list)
    ocr_needed: bool = False
    ocr_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StructuredPdfExtraction:
    status: StructuredExtractionState
    classification: DocumentClassification = "unknown"
    classification_confidence: float | None = None
    page_count: int = 0
    pages: list[StructuredPdfPage] = field(default_factory=list)
    text: str = ""
    markdown: str = ""
    ocr_needed_pages: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    provider: str = "pdf-inspector"
    provider_version: str = ""
    source_pdf_sha256: str = ""
    source_pdf_size_bytes: int = 0
    source_pdf_modified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_full_text_projection(extraction: StructuredPdfExtraction) -> str:
    """Project structured pages into the one deterministic compatibility text."""

    page_content = [
        (page.markdown or page.text).strip()
        for page in sorted(extraction.pages, key=lambda page: page.page_number)
        if (page.markdown or page.text).strip()
    ]
    if page_content:
        return "\n\n".join(page_content)
    return (extraction.markdown or extraction.text).strip()


def pdf_inspector_available() -> bool:
    return _pdf_inspector is not None


def extract_structured_pdf(
    pdf_path: str | Path,
    *,
    inspector: ModuleType | Any | None = None,
) -> StructuredPdfExtraction:
    provider = _pdf_inspector if inspector is None else inspector
    provider_version = _provider_version(provider)
    if provider is None:
        return StructuredPdfExtraction(
            status="not_extracted",
            warnings=["pdf-inspector is unavailable; compatibility extraction remains enabled."],
            provider_version=provider_version,
        )

    path = str(Path(pdf_path))
    try:
        processed = provider.process_pdf(path)
    except Exception as exc:
        return StructuredPdfExtraction(
            status="failed",
            errors=[f"pdf-inspector: {exc}"],
            provider_version=provider_version,
        )

    classification = _normalize_classification(getattr(processed, "pdf_type", ""))
    page_count = max(0, _integer(getattr(processed, "page_count", 0)))
    confidence = _optional_confidence(getattr(processed, "confidence", None))
    warnings: list[str] = []
    ocr_needed_pages = _normalize_page_numbers(
        getattr(processed, "pages_needing_ocr", []),
        origin="one",
        page_count=page_count,
        warnings=warnings,
        field_name="process_pdf.pages_needing_ocr",
    )
    ocr_reasons = _normalize_ocr_reasons(
        getattr(processed, "ocr_reasons_by_page", []),
        page_count=page_count,
        warnings=warnings,
    )

    page_markdown: dict[int, str] = {}
    page_ocr_flags: set[int] = set(ocr_needed_pages)
    try:
        page_result = provider.extract_pages_markdown(path)
        for upstream_page in list(getattr(page_result, "pages", []) or []):
            page_number = _normalize_page_number(
                getattr(upstream_page, "page", None),
                origin="zero",
                page_count=page_count,
                warnings=warnings,
                field_name="extract_pages_markdown.pages[].page",
            )
            if page_number is None:
                continue
            page_markdown[page_number] = str(getattr(upstream_page, "markdown", "") or "")
            if bool(getattr(upstream_page, "needs_ocr", False)):
                page_ocr_flags.add(page_number)
            reason = str(getattr(upstream_page, "ocr_reason", "") or "").strip()
            if reason:
                ocr_reasons.setdefault(page_number, []).append(reason)
        page_ocr_flags.update(
            _normalize_page_numbers(
                getattr(page_result, "pages_needing_ocr", []),
                origin="one",
                page_count=page_count,
                warnings=warnings,
                field_name="extract_pages_markdown.pages_needing_ocr",
            )
        )
    except Exception as exc:
        warnings.append(f"pdf-inspector per-page Markdown unavailable: {exc}")

    positioned_by_page: dict[int, list[PositionedPdfText]] = {}
    try:
        for item in list(provider.extract_text_with_positions(path) or []):
            page_number = _normalize_page_number(
                getattr(item, "page", None),
                origin="one",
                page_count=page_count,
                warnings=warnings,
                field_name="extract_text_with_positions[].page",
            )
            if page_number is None:
                continue
            positioned_by_page.setdefault(page_number, []).append(
                PositionedPdfText(
                    page_number=page_number,
                    text=str(getattr(item, "text", "") or ""),
                    x=_float(getattr(item, "x", 0.0)),
                    y=_float(getattr(item, "y", 0.0)),
                    width=_float(getattr(item, "width", 0.0)),
                    height=_float(getattr(item, "height", 0.0)),
                    font=str(getattr(item, "font", "") or ""),
                    font_size=_float(getattr(item, "font_size", 0.0)),
                    is_bold=bool(getattr(item, "is_bold", False)),
                    is_italic=bool(getattr(item, "is_italic", False)),
                    item_type=str(getattr(item, "item_type", "text") or "text"),
                )
            )
    except Exception as exc:
        warnings.append(f"pdf-inspector positioned text unavailable: {exc}")

    pages: list[StructuredPdfPage] = []
    for page_number in range(1, page_count + 1):
        positioned_text = positioned_by_page.get(page_number, [])
        markdown = page_markdown.get(page_number, "")
        text = " ".join(item.text for item in positioned_text if item.text).strip()
        needs_ocr = page_number in page_ocr_flags
        pages.append(
            StructuredPdfPage(
                page_number=page_number,
                state="ocr_needed" if needs_ocr else "success",
                text=text,
                markdown=markdown,
                positioned_text=positioned_text,
                ocr_needed=needs_ocr,
                ocr_reasons=_dedupe(ocr_reasons.get(page_number, [])),
            )
        )

    markdown = str(getattr(processed, "markdown", "") or "").strip()
    if not markdown:
        markdown = "\n\n".join(page.markdown for page in pages if page.markdown).strip()
    text = canonical_full_text_projection(
        StructuredPdfExtraction(status="success", pages=pages, markdown=markdown)
    )
    normalized_ocr_pages = sorted(page_ocr_flags)
    status: StructuredExtractionState = "ocr_needed" if normalized_ocr_pages else "success"
    return StructuredPdfExtraction(
        status=status,
        classification=classification,
        classification_confidence=confidence,
        page_count=page_count,
        pages=pages,
        text=text,
        markdown=markdown,
        ocr_needed_pages=normalized_ocr_pages,
        warnings=_dedupe(warnings),
        provider_version=provider_version,
    )


def _normalize_classification(value: object) -> DocumentClassification:
    normalized = str(getattr(value, "value", value) or "").strip().lower().replace("-", "_")
    return {
        "text": "text",
        "text_based": "text",
        "scanned": "scanned",
        "image": "image-based",
        "image_based": "image-based",
        "mixed": "mixed",
    }.get(normalized, "unknown")  # type: ignore[return-value]


def _normalize_page_number(
    value: object,
    *,
    origin: Literal["zero", "one"],
    page_count: int,
    warnings: list[str],
    field_name: str,
) -> int | None:
    try:
        upstream_number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        warnings.append(f"Ignored invalid {field_name} value: {value!r}.")
        return None
    page_number = upstream_number + 1 if origin == "zero" else upstream_number
    if page_number < 1 or (page_count > 0 and page_number > page_count):
        warnings.append(f"Ignored out-of-range {field_name} value: {value!r}.")
        return None
    return page_number


def _normalize_page_numbers(
    values: object,
    *,
    origin: Literal["zero", "one"],
    page_count: int,
    warnings: list[str],
    field_name: str,
) -> list[int]:
    normalized: list[int] = []
    for value in list(values or []):  # type: ignore[call-overload]
        page_number = _normalize_page_number(
            value,
            origin=origin,
            page_count=page_count,
            warnings=warnings,
            field_name=field_name,
        )
        if page_number is not None and page_number not in normalized:
            normalized.append(page_number)
    return sorted(normalized)


def _normalize_ocr_reasons(
    values: object,
    *,
    page_count: int,
    warnings: list[str],
) -> dict[int, list[str]]:
    reasons_by_page: dict[int, list[str]] = {}
    for item in list(values or []):  # type: ignore[call-overload]
        page_number = _normalize_page_number(
            getattr(item, "page", None),
            origin="one",
            page_count=page_count,
            warnings=warnings,
            field_name="process_pdf.ocr_reasons_by_page[].page",
        )
        if page_number is None:
            continue
        reasons_by_page[page_number] = [str(reason) for reason in list(getattr(item, "reasons", []) or [])]
    return reasons_by_page


def _provider_version(provider: object | None) -> str:
    if provider is not None:
        version = str(getattr(provider, "__version__", "") or "").strip()
        if version:
            return version
    try:
        return importlib_metadata.version("pdf-inspector")
    except importlib_metadata.PackageNotFoundError:
        return ""


def _optional_confidence(value: object) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, _float(value)))


def _integer(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
