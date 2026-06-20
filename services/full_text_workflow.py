from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingest.text_extractor import extract_full_text_from_pdf
from storage.extracted_text_store import (
    build_extraction_metadata,
    clear_extraction_cache,
    extraction_cache_status,
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


def extract_text_for_paper(
    record: dict[str, str],
    force: bool = False,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    index_csv: Path = INDEX_CSV,
) -> FullTextWorkflowResult:
    paper_id = record["paper_id"]
    pdf_path = Path(str(record.get("filepath", "")))
    if not force:
        status = extraction_cache_status(paper_id, cache_dir, pdf_path=pdf_path)
        if status["has_reusable_text_cache"] and not status["is_stale"]:
            return FullTextWorkflowResult(
                paper_id=paper_id,
                skipped=True,
                status=str(status["status"]),
                source=str(status["source"]),
                char_count=int(status["char_count"] or 0),
                extracted_at=str(status["extracted_at"]),
                errors=list(status["errors"]),
                attempted_methods=list(status["attempted_methods"]),
                metadata={},
            )

    result = extract_full_text_from_pdf(pdf_path)
    save_extracted_text(paper_id, result.text, cache_dir)
    metadata = build_extraction_metadata(paper_id, str(record.get("filepath", "")), result, cache_dir)
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
    )


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
