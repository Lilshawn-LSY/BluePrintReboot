from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ingest.scanner import pdf_sha256_with_metadata
from ingest.text_extractor import FullTextExtractionResult
from storage.atomic_json import JsonStoreError, atomic_write_json, read_json_file
from storage.paths import EXTRACTED_TEXT_DIR


def extracted_text_path(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> Path:
    return Path(cache_dir) / f"{paper_id}.txt"


def extraction_metadata_path(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> Path:
    return Path(cache_dir) / f"{paper_id}.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_extraction_metadata(
    paper_id: str,
    pdf_path: str,
    result: FullTextExtractionResult,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
) -> dict[str, Any]:
    text_path = extracted_text_path(paper_id, cache_dir)
    fingerprint = pdf_fingerprint(pdf_path)
    return {
        "paper_id": paper_id,
        "pdf_path": str(pdf_path),
        "text_path": str(text_path),
        **fingerprint,
        "source": result.source,
        "extracted_at": utc_now_iso(),
        "char_count": result.char_count,
        "status": result.status,
        "errors": result.errors,
        "attempted_methods": result.attempted_methods,
    }


def build_preserved_cache_failure_metadata(
    metadata: dict[str, Any],
    pdf_path: str | Path,
    result: FullTextExtractionResult,
) -> dict[str, Any]:
    preserved_metadata = dict(metadata)
    preserved_metadata.update(
        {
            "previous_cache_preserved": True,
            "recovery_failed": True,
            "recovery_status": result.status,
            "recovery_source": result.source,
            "recovery_char_count": result.char_count,
            "recovery_attempted_at": utc_now_iso(),
            "recovery_attempted_methods": result.attempted_methods,
            "recovery_errors": result.errors,
            "recovery_error": _extraction_result_error(result),
            "recovery_pdf_sha256": pdf_fingerprint(pdf_path, metadata)["pdf_sha256"],
        }
    )
    return preserved_metadata


def pdf_fingerprint(pdf_path: str | Path, cached_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        return {
            "pdf_size_bytes": 0,
            "pdf_modified_at": "",
            "pdf_sha256": "",
        }
    fingerprint = pdf_sha256_with_metadata(path, cached_metadata)
    return {
        "pdf_size_bytes": int(fingerprint["pdf_size_bytes"] or 0),
        "pdf_modified_at": fingerprint["pdf_modified_at"],
        "pdf_sha256": fingerprint["pdf_sha256"],
    }


def _atomic_write_text(
    path: str | Path,
    text: str,
    *,
    replace_file: Callable[[str | Path, str | Path], None] | None = None,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    replace = replace_file or os.replace
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=target.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        replace(temporary_path, target)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return target


def save_extracted_text(
    paper_id: str,
    text: str,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    *,
    replace_file: Callable[[str | Path, str | Path], None] | None = None,
) -> Path:
    path = extracted_text_path(paper_id, cache_dir)
    return _atomic_write_text(path, text, replace_file=replace_file)


def save_extraction_metadata(
    paper_id: str,
    metadata: dict[str, Any],
    cache_dir: Path = EXTRACTED_TEXT_DIR,
) -> Path:
    path = extraction_metadata_path(paper_id, cache_dir)
    return atomic_write_json(path, metadata, indent=2, ensure_ascii=False)


def load_cached_extracted_text(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> str:
    path = extracted_text_path(paper_id, cache_dir)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_extraction_metadata(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> dict[str, Any]:
    path = extraction_metadata_path(paper_id, cache_dir)
    if not path.exists():
        return {}
    try:
        value = read_json_file(path, store_name="Extraction metadata")
    except JsonStoreError as exc:
        return {
            "paper_id": paper_id,
            "status": "metadata_error",
            "metadata_corrupt": True,
            "metadata_path": str(path.resolve(strict=False)),
            "metadata_issue": exc.summary,
            "metadata_suggested_action": exc.suggested_action,
            "errors": [exc.summary],
        }
    if not isinstance(value, dict):
        return {
            "paper_id": paper_id,
            "status": "metadata_error",
            "metadata_corrupt": True,
            "metadata_path": str(path.resolve(strict=False)),
            "metadata_issue": "Extraction metadata must contain a JSON object",
            "metadata_suggested_action": "Do not overwrite this file. Rebuild the extracted-text cache only after preserving or removing the invalid metadata file.",
            "errors": ["Extraction metadata must contain a JSON object."],
        }
    return value


def extraction_cache_status(
    paper_id: str,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    pdf_path: str | Path | None = None,
) -> dict[str, Any]:
    text_path = extracted_text_path(paper_id, cache_dir)
    metadata_path = extraction_metadata_path(paper_id, cache_dir)
    metadata = load_extraction_metadata(paper_id, cache_dir)
    has_text_file = text_path.exists()
    has_metadata_file = metadata_path.exists()
    char_count = _safe_int(metadata.get("char_count"))
    has_reusable_text_cache = (
        has_text_file
        and metadata.get("status") == "success"
        and char_count > 0
    )

    cached_pdf_sha256 = str(metadata.get("pdf_sha256") or "")
    current_pdf_sha256 = ""
    is_stale = False
    if pdf_path is not None:
        current_pdf_sha256 = str(pdf_fingerprint(pdf_path, metadata)["pdf_sha256"])
        is_stale = _hashes_show_stale(
            has_reusable_text_cache,
            current_pdf_sha256,
            cached_pdf_sha256,
        )

    recovery_failed = bool(metadata.get("recovery_failed", False))
    errors = metadata.get("recovery_errors" if recovery_failed else "errors", [])
    if not isinstance(errors, list):
        errors = [str(errors)] if errors else []
    error = str(metadata.get("recovery_error") or metadata.get("error") or "")
    if not error and errors:
        error = str(errors[0])

    return {
        "text_path": text_path,
        "metadata_path": metadata_path,
        "has_text_file": has_text_file,
        "has_metadata_file": has_metadata_file,
        "has_reusable_text_cache": has_reusable_text_cache,
        "is_stale": is_stale,
        "pdf_sha256": current_pdf_sha256,
        "cached_pdf_sha256": cached_pdf_sha256,
        "status": metadata.get("status", "not_extracted"),
        "char_count": char_count,
        "error": error,
        "source": metadata.get("source", ""),
        "has_text": has_text_file,
        "has_metadata": has_metadata_file,
        "extracted_at": metadata.get("extracted_at", ""),
        "errors": errors,
        "attempted_methods": metadata.get(
            "recovery_attempted_methods" if recovery_failed else "attempted_methods",
            [],
        ),
        "previous_cache_preserved": bool(metadata.get("previous_cache_preserved", False)),
        "recovery_failed": recovery_failed,
        "recovery_status": metadata.get("recovery_status", ""),
        "recovery_attempted_at": metadata.get("recovery_attempted_at", ""),
    }


def is_extraction_cache_stale(
    paper_id: str,
    pdf_path: str | Path,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
) -> bool:
    if not has_reusable_extracted_text_cache(paper_id, cache_dir):
        return False

    metadata = load_extraction_metadata(paper_id, cache_dir)
    current_pdf_sha256 = str(pdf_fingerprint(pdf_path, metadata)["pdf_sha256"])
    cached_pdf_sha256 = str(metadata.get("pdf_sha256") or "")
    return _hashes_show_stale(True, current_pdf_sha256, cached_pdf_sha256)


def _hashes_show_stale(
    has_reusable_text_cache: bool,
    current_pdf_sha256: str,
    cached_pdf_sha256: str,
) -> bool:
    return bool(
        has_reusable_text_cache
        and current_pdf_sha256
        and cached_pdf_sha256
        and current_pdf_sha256 != cached_pdf_sha256
    )


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _extraction_result_error(result: FullTextExtractionResult) -> str:
    if result.errors:
        return "; ".join(str(error) for error in result.errors)
    if not result.text.strip():
        return "No readable text was extracted."
    return "Full-text extraction failed."


def has_reusable_extracted_text_cache(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> bool:
    return bool(extraction_cache_status(paper_id, cache_dir)["has_reusable_text_cache"])


def clear_extraction_cache(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> None:
    for path in (extracted_text_path(paper_id, cache_dir), extraction_metadata_path(paper_id, cache_dir)):
        if path.exists():
            path.unlink()
