from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from ingest.doi import extract_doi_from_text, normalize_doi
from ingest.document_text import extract_pdf_text_with_markitdown, extract_pdf_text_with_pypdf
from storage.paths import NOTES_DIR, PAPERS_DIR


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_stem(stem: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return cleaned or "paper"


def make_paper_id(pdf_path: Path, papers_dir: Path = PAPERS_DIR) -> str:
    relative_path = pdf_path.relative_to(papers_dir).as_posix().lower()
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:10]
    return f"{_safe_stem(pdf_path.stem)}-{digest}"


def compute_pdf_sha256(pdf_path: Path) -> str:
    digest = hashlib.sha256()
    with Path(pdf_path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


PDF_HASH_METADATA_FIELDS = ("pdf_sha256", "pdf_size_bytes", "pdf_modified_at")


def pdf_hash_metadata_key(pdf_path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(pdf_path))


def pdf_file_signature(pdf_path: str | Path) -> dict[str, str]:
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        return {
            "pdf_size_bytes": "0",
            "pdf_modified_at": "",
        }
    stat = path.stat()
    return {
        "pdf_size_bytes": str(stat.st_size),
        "pdf_modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def pdf_hash_metadata_matches_file(pdf_path: str | Path, metadata: Mapping[str, object] | None) -> bool:
    if not metadata:
        return False
    digest = str(metadata.get("pdf_sha256", "") or "").strip()
    if not digest:
        return False
    signature = pdf_file_signature(pdf_path)
    if signature["pdf_modified_at"] == "":
        return False
    return (
        _metadata_size(metadata.get("pdf_size_bytes")) == signature["pdf_size_bytes"]
        and str(metadata.get("pdf_modified_at", "") or "").strip() == signature["pdf_modified_at"]
    )


def pdf_sha256_with_metadata(
    pdf_path: str | Path,
    metadata: Mapping[str, object] | None = None,
    *,
    compute_hash_func=None,
) -> dict[str, str]:
    signature = pdf_file_signature(pdf_path)
    if signature["pdf_modified_at"] == "":
        return {
            "pdf_sha256": "",
            **signature,
        }
    if pdf_hash_metadata_matches_file(pdf_path, metadata):
        return {
            "pdf_sha256": str((metadata or {}).get("pdf_sha256", "") or "").strip(),
            **signature,
        }
    compute_hash = compute_hash_func or compute_pdf_sha256
    return {
        "pdf_sha256": compute_hash(Path(pdf_path)),
        **signature,
    }


def _metadata_size(value: object) -> str:
    try:
        return str(int(value or 0))
    except (TypeError, ValueError):
        return ""


@dataclass(frozen=True)
class DoiExtractionResult:
    doi: str = ""
    source: str = "none"


def extract_doi_metadata_from_pdf(pdf_path: Path, max_pages: int = 3) -> DoiExtractionResult:
    try:
        pypdf_text = extract_pdf_text_with_pypdf(pdf_path, max_pages=max_pages)
    except Exception:
        pypdf_text = ""

    pypdf_doi = normalize_doi(extract_doi_from_text(pypdf_text))
    if pypdf_doi:
        return DoiExtractionResult(doi=pypdf_doi, source="pypdf")

    markitdown_text = extract_pdf_text_with_markitdown(pdf_path)
    markitdown_doi = normalize_doi(extract_doi_from_text(markitdown_text))
    if markitdown_doi:
        return DoiExtractionResult(doi=markitdown_doi, source="markitdown")

    return DoiExtractionResult()


def extract_doi_from_pdf(pdf_path: Path, max_pages: int = 3) -> str:
    return extract_doi_metadata_from_pdf(pdf_path, max_pages=max_pages).doi


def scan_papers(
    papers_dir: Path = PAPERS_DIR,
    notes_dir: Path = NOTES_DIR,
    *,
    hash_metadata_by_path: Mapping[str, Mapping[str, object]] | None = None,
) -> list[dict[str, str]]:
    papers_dir = Path(papers_dir)
    notes_dir = Path(notes_dir)
    if not papers_dir.exists():
        return []

    scanned_at = _now_iso()
    records: list[dict[str, str]] = []
    for pdf_path in sorted(papers_dir.rglob("*.pdf"), key=lambda path: path.as_posix().lower()):
        paper_id = make_paper_id(pdf_path, papers_dir)
        hash_metadata = pdf_sha256_with_metadata(
            pdf_path,
            (hash_metadata_by_path or {}).get(pdf_hash_metadata_key(pdf_path)),
        )
        records.append(
            {
                "paper_id": paper_id,
                "filename": pdf_path.name,
                "filepath": str(pdf_path.resolve()),
                "pdf_sha256": hash_metadata["pdf_sha256"],
                "pdf_size_bytes": hash_metadata["pdf_size_bytes"],
                "pdf_modified_at": hash_metadata["pdf_modified_at"],
                "title": pdf_path.stem,
                "authors": "",
                "year": "",
                "journal": "",
                "doi": "",
                "abstract": "",
                "keywords": "",
                "tags": "",
                "status": "unread",
                "reading_priority": "normal",
                "doi_source": "",
                "extraction_source": "",
                "extraction_checked_at": "",
                "metadata_source": "",
                "metadata_confidence": "",
                "metadata_checked_at": "",
                "note_path": str((notes_dir / f"{paper_id}.md").resolve()),
                "added_at": scanned_at,
                "updated_at": scanned_at,
            }
        )
    return records
