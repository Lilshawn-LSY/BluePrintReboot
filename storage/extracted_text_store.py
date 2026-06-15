from __future__ import annotations

import json
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
    return {
        "paper_id": paper_id,
        "pdf_path": str(pdf_path),
        "text_path": str(text_path),
        "source": result.source,
        "extracted_at": utc_now_iso(),
        "char_count": result.char_count,
        "status": result.status,
        "errors": result.errors,
        "attempted_methods": result.attempted_methods,
    }


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


def extraction_cache_status(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> dict[str, Any]:
    text_path = extracted_text_path(paper_id, cache_dir)
    metadata_path = extraction_metadata_path(paper_id, cache_dir)
    metadata = load_extraction_metadata(paper_id, cache_dir)
    return {
        "text_path": text_path,
        "metadata_path": metadata_path,
        "has_text": text_path.exists(),
        "has_metadata": metadata_path.exists(),
        "status": metadata.get("status", "not_extracted"),
        "source": metadata.get("source", ""),
        "char_count": metadata.get("char_count", 0),
        "extracted_at": metadata.get("extracted_at", ""),
        "errors": metadata.get("errors", []),
        "attempted_methods": metadata.get("attempted_methods", []),
    }


def clear_extraction_cache(paper_id: str, cache_dir: Path = EXTRACTED_TEXT_DIR) -> None:
    for path in (extracted_text_path(paper_id, cache_dir), extraction_metadata_path(paper_id, cache_dir)):
        if path.exists():
            path.unlink()
