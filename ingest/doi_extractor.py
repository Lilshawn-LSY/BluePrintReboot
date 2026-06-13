from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from ingest.doi import is_probable_doi, normalize_doi


DOI_CANDIDATE_PATTERN = re.compile(
    r"(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s\"'<>]+)",
    re.IGNORECASE,
)


def extract_doi_candidates_from_text(text: str) -> list[str]:
    return _unique_normalized(DOI_CANDIDATE_PATTERN.findall(text or ""))


def extract_doi_candidates_from_filename(filename: str) -> list[str]:
    text = Path(filename or "").stem.replace("_", "/")
    return extract_doi_candidates_from_text(text)


def extract_doi_candidates_from_pdf(pdf_path: Path, max_pages: int = 2) -> list[str]:
    debug = extract_text_from_pdf_with_debug(pdf_path, max_pages=max_pages)
    return extract_doi_candidates_from_text(debug["text"])


def extract_doi_candidates_for_record(record: Mapping[str, str]) -> list[str]:
    return extract_doi_candidates_for_record_with_debug(record)["candidates"]


def extract_doi_candidates_for_record_with_debug(record: Mapping[str, str], max_pages: int = 2) -> dict[str, Any]:
    filename_candidates = extract_doi_candidates_from_filename(record.get("filename", ""))
    pdf_path = Path(record.get("filepath", ""))
    pdf_debug = extract_text_from_pdf_with_debug(pdf_path, max_pages=max_pages)
    pdf_candidates = extract_doi_candidates_from_text(pdf_debug["text"])
    candidates = _unique_normalized(filename_candidates + pdf_candidates)
    return {
        "candidates": candidates,
        "pdf_path": str(pdf_path),
        "pdf_exists": pdf_path.exists() and pdf_path.is_file(),
        "pages_attempted": max_pages,
        "pages_read": pdf_debug["pages_read"],
        "extracted_char_count": len(pdf_debug["text"]),
        "errors": pdf_debug["errors"],
    }


def extract_text_from_pdf(pdf_path: Path, max_pages: int = 1) -> str:
    return extract_text_from_pdf_with_debug(pdf_path, max_pages=max_pages)["text"]


def extract_text_from_pdf_with_debug(pdf_path: Path, max_pages: int = 1) -> dict[str, Any]:
    pdf_path = Path(pdf_path)
    result = {
        "text": "",
        "pages_read": 0,
        "errors": [],
    }
    if not pdf_path.exists() or not pdf_path.is_file():
        result["errors"].append("PDF path does not exist or is not a file.")
        return result

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        text_parts: list[str] = []
        for page in reader.pages[:max_pages]:
            try:
                text_parts.append(page.extract_text() or "")
                result["pages_read"] += 1
            except Exception as exc:
                result["errors"].append(f"Page extraction failed: {exc}")
        result["text"] = "\n".join(text_parts)
    except Exception as exc:
        result["errors"].append(f"PDF extraction failed: {exc}")
    return result


def _unique_normalized(values: list[str]) -> list[str]:
    seen: set[str] = set()
    candidates: list[str] = []
    for value in values:
        normalized = normalize_doi(value)
        if is_probable_doi(normalized) and normalized not in seen:
            seen.add(normalized)
            candidates.append(normalized)
    return candidates
