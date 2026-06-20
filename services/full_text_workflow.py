from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingest.text_extractor import extract_full_text_from_pdf
from storage.extracted_text_store import (
    build_extraction_metadata,
    build_preserved_cache_failure_metadata,
    clear_extraction_cache,
    extraction_cache_status,
    load_extraction_metadata,
    save_extracted_text,
    save_extraction_metadata,
)
from storage.index_store import update_paper_metadata
from storage.paths import EXTRACTED_TEXT_DIR, INDEX_CSV


@dataclass(frozen=True)
class FullTextWorkflowResult:
    paper_id: str
    skipped: bool
    status: str
    source: str
    char_count: int
    extracted_at: str
    errors: list[str]
    attempted_methods: list[str]
    metadata: dict[str, Any]
    previous_cache_preserved: bool = False
    recovery_failed: bool = False
    error: str = ""


def extract_text_for_paper(
    record: dict[str, str],
    force: bool = False,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    index_csv: Path = INDEX_CSV,
) -> FullTextWorkflowResult:
    paper_id = record["paper_id"]
    pdf_path = Path(str(record.get("filepath", "")))
    previous_status = extraction_cache_status(paper_id, cache_dir, pdf_path=pdf_path)
    previous_cache_is_reusable = bool(previous_status["has_reusable_text_cache"])

    if not force and previous_cache_is_reusable and not previous_status["is_stale"]:
        return FullTextWorkflowResult(
            paper_id=paper_id,
            skipped=True,
            status=str(previous_status["status"]),
            source=str(previous_status["source"]),
            char_count=int(previous_status["char_count"] or 0),
            extracted_at=str(previous_status["extracted_at"]),
            errors=list(previous_status["errors"]),
            attempted_methods=list(previous_status["attempted_methods"]),
            metadata={},
            previous_cache_preserved=bool(previous_status["previous_cache_preserved"]),
            recovery_failed=bool(previous_status["recovery_failed"]),
            error=str(previous_status["error"]),
        )

    result = extract_full_text_from_pdf(pdf_path)
    extraction_succeeded = (
        result.status == "success"
        and result.char_count > 0
        and bool(result.text.strip())
    )

    if not extraction_succeeded and previous_cache_is_reusable:
        previous_metadata = load_extraction_metadata(paper_id, cache_dir)
        metadata = build_preserved_cache_failure_metadata(previous_metadata, pdf_path, result)
        save_extraction_metadata(paper_id, metadata, cache_dir)
        update_paper_metadata(
            paper_id,
            {
                "text_status": "recovery_failed",
                "text_source": previous_status["source"],
                "text_char_count": str(previous_status["char_count"]),
                "text_extracted_at": previous_status["extracted_at"],
            },
            index_csv=index_csv,
        )
        return FullTextWorkflowResult(
            paper_id=paper_id,
            skipped=False,
            status=result.status,
            source=result.source,
            char_count=result.char_count,
            extracted_at=str(metadata["recovery_attempted_at"]),
            errors=result.errors,
            attempted_methods=result.attempted_methods,
            metadata=metadata,
            previous_cache_preserved=True,
            recovery_failed=True,
            error=str(metadata["recovery_error"]),
        )

    save_extracted_text(paper_id, result.text, cache_dir)
    metadata = build_extraction_metadata(paper_id, str(pdf_path), result, cache_dir)
    save_extraction_metadata(paper_id, metadata, cache_dir)
    update_paper_metadata(
        paper_id,
        {
            "text_status": result.status,
            "text_source": result.source,
            "text_char_count": str(result.char_count),
            "text_extracted_at": metadata["extracted_at"],
        },
        index_csv=index_csv,
    )
    return FullTextWorkflowResult(
        paper_id=paper_id,
        skipped=False,
        status=result.status,
        source=result.source,
        char_count=result.char_count,
        extracted_at=str(metadata["extracted_at"]),
        errors=result.errors,
        attempted_methods=result.attempted_methods,
        metadata=metadata,
        error=_workflow_error(result),
    )


def _workflow_error(result: Any) -> str:
    if result.status == "success" and result.text.strip():
        return ""
    if result.errors:
        return "; ".join(str(error) for error in result.errors)
    if not result.text.strip():
        return "No readable text was extracted."
    return "Full-text extraction failed."


def clear_text_cache_for_paper(
    record: dict[str, str],
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    index_csv: Path = INDEX_CSV,
) -> None:
    paper_id = record["paper_id"]
    clear_extraction_cache(paper_id, cache_dir)
    update_paper_metadata(
        paper_id,
        {
            "text_status": "",
            "text_source": "",
            "text_char_count": "",
            "text_extracted_at": "",
        },
        index_csv=index_csv,
    )
