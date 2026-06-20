from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingest.text_extractor import FullTextExtractionResult
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


def pdf_fingerprint(pdf_path: str | Path) -> dict[str, Any]:
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        return {
            "pdf_size_bytes": 0,
            "pdf_modified_at": "",
            "pdf_sha256": "",
        }
    stat = path.stat()
    return {
        "pdf_size_bytes": stat.st_size,
        "pdf_modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
        "pdf_sha256": _sha256_file(path),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_extracted_text(paper_id: str, text: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> Path:
    path = extracted_text_path(paper_id, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def save_extraction_metadata(
    paper_id: str,
    metadata: dict[str, Any],
    cache_dir: Path = EXTRACTED_TEXT_DIR,
) -> Path:
    path = extraction_metadata_path(paper_id, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


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
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "paper_id": paper_id,
            "status": "metadata_error",
            "errors": ["Extraction metadata JSON is invalid."],
        }


def extraction_cache_status(
    paper_id: str,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    pdf_path: str | Path | None = None,
) -> dict[str, Any]:
    text_path = extracted_text_path(paper_id, cache_dir)
    metadata_path = extraction_metadata_path(paper_id, cache_dir)
    metadata = load_extraction_metadata(paper_id, cache_dir)
    has_text_file = text_path.exists()
    has_reusable_text_cache = (
        has_text_file
        and metadata.get("status") == "success"
        and int(metadata.get("char_count") or 0) > 0
    )
    status = {
        "text_path": text_path,
        "metadata_path": metadata_path,
        "has_text_file": has_text_file,
        "has_reusable_text_cache": has_reusable_text_cache,
        "has_text": has_text_file,
        "has_metadata": metadata_path.exists(),
        "status": metadata.get("status", "not_extracted"),
        "source": metadata.get("source", ""),
        "char_count": metadata.get("char_count", 0),
        "extracted_at": metadata.get("extracted_at", ""),
        "errors": metadata.get("errors", []),
        "attempted_methods": metadata.get("attempted_methods", []),
    }
    if pdf_path is not None:
        current_pdf_sha256 = str(pdf_fingerprint(pdf_path)["pdf_sha256"])
        cached_pdf_sha256 = str(metadata.get("pdf_sha256") or "")
        status.update(
            {
                "is_stale": _hashes_show_stale(
                    has_reusable_text_cache,
                    current_pdf_sha256,
                    cached_pdf_sha256,
                ),
                "pdf_sha256": current_pdf_sha256,
                "cached_pdf_sha256": cached_pdf_sha256,
            }
        )
    return status


def is_extraction_cache_stale(
    paper_id: str,
    pdf_path: str | Path,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
) -> bool:
    if not has_reusable_extracted_text_cache(paper_id, cache_dir):
        return False

    current_pdf_sha256 = str(pdf_fingerprint(pdf_path)["pdf_sha256"])
    cached_pdf_sha256 = str(load_extraction_metadata(paper_id, cache_dir).get("pdf_sha256") or "")
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


def has_reusable_extracted_text_cache(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> bool:
    return bool(extraction_cache_status(paper_id, cache_dir)["has_reusable_text_cache"])


def clear_extraction_cache(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> None:
    for path in (extracted_text_path(paper_id, cache_dir), extraction_metadata_path(paper_id, cache_dir)):
        if path.exists():
            path.unlink()
