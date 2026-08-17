from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ingest.text_extractor import extract_full_text_from_pdf
from services.managed_pdf import ManagedPdfState, resolve_indexed_pdf
from storage.atomic_text import atomic_write_text
from storage.extracted_text_store import (
    build_extraction_metadata,
    build_preserved_cache_failure_metadata,
    clear_extraction_cache,
    extraction_cache_status,
    load_cached_extracted_text,
    load_extraction_metadata,
    save_extracted_text,
    save_extraction_metadata,
)
from storage.index_store import read_index_snapshot, update_paper_metadata
from storage.paths import EXTRACTED_TEXT_DIR, INDEX_CSV
from storage.identities import require_safe_paper_id
from storage.workspace_lock import workspace_write_lock


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
    extraction_state: str = "not_extracted"
    cache_state: str = "not_extracted"
    classification: str = "unknown"
    ocr_needed_pages: list[int] = field(default_factory=list)


FullTextCacheState = Literal["not_extracted", "success", "cached", "stale", "failed", "ocr_needed"]
FullTextExtractionState = Literal["not_extracted", "success", "failed", "ocr_needed"]


class FullTextServiceUnavailable(Exception):
    """The bounded full-text service could not read or update cache state safely."""


class FullTextTransactionError(RuntimeError):
    """A multi-file extraction update failed and was rolled back."""


@dataclass(frozen=True)
class _FileSnapshot:
    exists: bool
    content: str = ""


@dataclass(frozen=True)
class FullTextStatus:
    paper_id: str
    state: FullTextCacheState
    extraction_state: FullTextExtractionState
    source: str
    provider: str
    provider_version: str
    content_format: Literal["markdown", "plain_text"]
    classification: str
    page_count: int
    char_count: int
    ocr_needed_pages: list[int]
    extracted_at: str
    has_content: bool
    is_stale: bool
    can_extract: bool
    previous_cache_preserved: bool
    message: str


@dataclass(frozen=True)
class FullTextDocument:
    status: FullTextStatus
    content: str


class FullTextService:
    """Single API-facing boundary over the existing full-text cache workflow."""

    def __init__(self, *, index_csv: Path = INDEX_CSV, cache_dir: Path = EXTRACTED_TEXT_DIR) -> None:
        self.index_csv = Path(index_csv)
        self.cache_dir = Path(cache_dir)

    def status(self, paper_id: str) -> FullTextStatus | None:
        record = self._record(paper_id)
        if record is None:
            return None
        try:
            resolved_pdf = _managed_pdf(record, self.index_csv)
            status = extraction_cache_status(
                paper_id,
                self.cache_dir,
                pdf_path=resolved_pdf.path,
            )
        except Exception:
            raise FullTextServiceUnavailable from None
        return _public_full_text_status(record, status, resolved_pdf.state)

    def document(self, paper_id: str) -> FullTextDocument | None:
        status = self.status(paper_id)
        if status is None:
            return None
        content = ""
        if status.has_content:
            try:
                content = load_cached_extracted_text(paper_id, self.cache_dir)
            except Exception:
                raise FullTextServiceUnavailable from None
        return FullTextDocument(status=status, content=content)

    def extract(self, paper_id: str, *, force: bool = False) -> FullTextDocument | None:
        record = self._record(paper_id)
        if record is None:
            return None
        metadata = load_extraction_metadata(paper_id, self.cache_dir)
        if metadata.get("metadata_corrupt"):
            raise FullTextServiceUnavailable
        try:
            extract_text_for_paper(
                record,
                force=force,
                cache_dir=self.cache_dir,
                index_csv=self.index_csv,
            )
        except Exception:
            raise FullTextServiceUnavailable from None
        return self.document(paper_id)

    def _record(self, paper_id: str) -> dict[str, str] | None:
        try:
            dataframe = read_index_snapshot(self.index_csv)
        except Exception:
            raise FullTextServiceUnavailable from None
        if "paper_id" not in dataframe:
            return None
        matches = dataframe[dataframe["paper_id"] == paper_id]
        if matches.empty:
            return None
        return {
            str(key): str(value)
            for key, value in matches.iloc[0].fillna("").to_dict().items()
        }


def extract_text_for_paper(
    record: dict[str, str],
    force: bool = False,
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    index_csv: Path = INDEX_CSV,
) -> FullTextWorkflowResult:
    paper_id = require_safe_paper_id(record.get("paper_id", ""))
    index_path = Path(index_csv)
    workspace_root = _workspace_root(index_path)
    with workspace_write_lock(workspace_root):
        current = _record_from_index(paper_id, index_path)
        if current is None:
            raise FullTextTransactionError("Paper disappeared before extraction could begin.")
        resolved_pdf = _managed_pdf(current, index_path)
        if resolved_pdf.state is not ManagedPdfState.available or resolved_pdf.path is None:
            raise FullTextTransactionError("The Paper does not reference an available managed PDF.")
        pdf_path = resolved_pdf.path
        return _extract_text_for_paper_locked(
            current,
            pdf_path=pdf_path,
            force=force,
            cache_dir=Path(cache_dir),
            index_csv=index_path,
        )


def _extract_text_for_paper_locked(
    record: dict[str, str],
    *,
    pdf_path: Path,
    force: bool,
    cache_dir: Path,
    index_csv: Path,
) -> FullTextWorkflowResult:
    paper_id = require_safe_paper_id(record.get("paper_id", ""))
    previous_status = extraction_cache_status(paper_id, cache_dir, pdf_path=pdf_path)
    previous_cache_is_reusable = bool(previous_status["has_reusable_extraction_cache"])

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
            extraction_state=str(previous_status["extraction_state"]),
            cache_state=str(previous_status["cache_state"]),
            classification=str(previous_status["classification"]),
            ocr_needed_pages=list(previous_status["ocr_needed_pages"]),
        )

    result = extract_full_text_from_pdf(pdf_path)
    extraction_succeeded = (
        (result.status == "success" and result.char_count > 0 and bool(result.text.strip()))
        or result.status == "ocr_needed"
    )

    if not extraction_succeeded and previous_cache_is_reusable:
        previous_metadata = load_extraction_metadata(paper_id, cache_dir)
        metadata = build_preserved_cache_failure_metadata(previous_metadata, pdf_path, result)
        _persist_extraction_transaction(
            paper_id,
            cache_dir=cache_dir,
            index_csv=index_csv,
            text=None,
            metadata=metadata,
            index_changes={
                "text_status": "recovery_failed",
                "text_source": str(previous_status["source"]),
                "text_char_count": str(previous_status["char_count"]),
                "text_extracted_at": str(previous_status["extracted_at"]),
            },
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
            extraction_state=result.status,
            cache_state="stale" if previous_status["is_stale"] else str(previous_status["cache_state"]),
            classification=str(previous_status["classification"]),
            ocr_needed_pages=list(previous_status["ocr_needed_pages"]),
        )

    metadata = build_extraction_metadata(paper_id, str(pdf_path), result, cache_dir)
    _persist_extraction_transaction(
        paper_id,
        cache_dir=cache_dir,
        index_csv=index_csv,
        text=result.text,
        metadata=metadata,
        index_changes={
            "text_status": result.status,
            "text_source": result.source,
            "text_char_count": str(result.char_count),
            "text_extracted_at": metadata["extracted_at"],
        },
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
        extraction_state=result.status,
        cache_state=(
            "ocr_needed"
            if result.status == "ocr_needed"
            else "success"
            if result.status == "success"
            else "failed"
        ),
        classification=(
            result.structured_extraction.classification
            if result.structured_extraction
            else "unknown"
        ),
        ocr_needed_pages=(
            list(result.structured_extraction.ocr_needed_pages)
            if result.structured_extraction
            else []
        ),
    )


def _workflow_error(result: Any) -> str:
    if result.status == "ocr_needed":
        return ""
    if result.status == "success" and result.text.strip():
        return ""
    if result.errors:
        return "; ".join(str(error) for error in result.errors)
    if not result.text.strip():
        return "No readable text was extracted."
    return "Full-text extraction failed."


def _public_full_text_status(
    record: dict[str, str],
    status: dict[str, Any],
    pdf_state: ManagedPdfState,
) -> FullTextStatus:
    raw_state = str(status.get("cache_state") or "not_extracted")
    state: FullTextCacheState = (
        raw_state
        if raw_state in {"not_extracted", "success", "cached", "stale", "failed", "ocr_needed"}
        else "failed"
    )  # type: ignore[assignment]
    content_format = str(status.get("content_format") or "plain_text")
    if content_format not in {"markdown", "plain_text"}:
        content_format = "plain_text"
    classification = str(status.get("classification") or "unknown")
    if classification not in {"text", "scanned", "image-based", "mixed", "unknown"}:
        classification = "unknown"
    ocr_needed_pages = sorted({
        page_number
        for value in list(status.get("ocr_needed_pages") or [])
        if (page_number := _positive_page_number(value)) is not None
    })
    can_extract = pdf_state is ManagedPdfState.available and not bool(status.get("metadata_corrupt", False))
    raw_extraction_state = str(status.get("extraction_state") or "not_extracted")
    extraction_state: FullTextExtractionState = (
        raw_extraction_state
        if raw_extraction_state in {"not_extracted", "success", "failed", "ocr_needed"}
        else "failed"
    )  # type: ignore[assignment]
    return FullTextStatus(
        paper_id=str(record.get("paper_id", "")),
        state=state,
        extraction_state=extraction_state,
        source=str(status.get("source") or ""),
        provider=str(status.get("provider") or status.get("source") or ""),
        provider_version=str(status.get("provider_version") or ""),
        content_format=content_format,  # type: ignore[arg-type]
        classification=classification,
        page_count=max(0, int(status.get("page_count") or 0)),
        char_count=max(0, int(status.get("char_count") or 0)),
        ocr_needed_pages=ocr_needed_pages,
        extracted_at=str(status.get("extracted_at") or ""),
        has_content=bool(status.get("has_reusable_text_cache", False)),
        is_stale=bool(status.get("is_stale", False)),
        can_extract=can_extract,
        previous_cache_preserved=bool(status.get("previous_cache_preserved", False)),
        message=_full_text_status_message(state, status, ocr_needed_pages),
    )


def _positive_page_number(value: object) -> int | None:
    try:
        page_number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return page_number if page_number >= 1 else None


def _full_text_status_message(
    state: FullTextCacheState,
    status: dict[str, Any],
    ocr_needed_pages: list[int],
) -> str:
    if bool(status.get("recovery_failed", False)):
        return "Re-extraction failed. The previous valid cached full text remains available."
    if state == "not_extracted":
        return "Full text has not been extracted."
    if state == "stale":
        return "The managed PDF changed after this full-text cache was created."
    if state == "failed":
        return "Full-text extraction failed. Retry explicitly after checking the managed PDF."
    if state == "ocr_needed":
        if ocr_needed_pages:
            pages = ", ".join(str(page) for page in ocr_needed_pages)
            return f"Local text extraction completed; OCR is still needed for page(s) {pages}."
        return "Local text extraction completed; OCR is still needed for this PDF."
    if state == "success":
        return "Full text was extracted successfully."
    return "Reusable full text is available from the local cache."


def clear_text_cache_for_paper(
    record: dict[str, str],
    cache_dir: Path = EXTRACTED_TEXT_DIR,
    index_csv: Path = INDEX_CSV,
) -> None:
    paper_id = require_safe_paper_id(record.get("paper_id", ""))
    with workspace_write_lock(_workspace_root(Path(index_csv))):
        snapshots = _transaction_snapshots(paper_id, Path(cache_dir), Path(index_csv))
        try:
            clear_extraction_cache(paper_id, cache_dir)
            changes = {
                "text_status": "",
                "text_source": "",
                "text_char_count": "",
                "text_extracted_at": "",
            }
            update_paper_metadata(paper_id, changes, index_csv=index_csv)
            _verify_index_changes(paper_id, changes, Path(index_csv))
        except Exception as exc:
            _restore_transaction_snapshots(snapshots)
            raise FullTextTransactionError("Full-text cache clear failed and was rolled back.") from exc


def _workspace_root(index_csv: Path) -> Path:
    path = Path(index_csv).resolve(strict=False)
    return path.parent.parent if path.parent.name.casefold() == "data" else path.parent


def _papers_dir(index_csv: Path) -> Path:
    return _workspace_root(index_csv) / "papers"


def _managed_pdf(record: dict[str, str], index_csv: Path):
    return resolve_indexed_pdf(record, papers_dir=_papers_dir(index_csv))


def _record_from_index(paper_id: str, index_csv: Path) -> dict[str, str] | None:
    dataframe = read_index_snapshot(index_csv)
    matches = dataframe[dataframe["paper_id"] == paper_id]
    if matches.empty:
        return None
    return {str(key): str(value) for key, value in matches.iloc[0].fillna("").to_dict().items()}


def _snapshot_text(path: Path) -> _FileSnapshot:
    if not path.is_file():
        return _FileSnapshot(False)
    return _FileSnapshot(True, path.read_text(encoding="utf-8"))


def _transaction_snapshots(
    paper_id: str,
    cache_dir: Path,
    index_csv: Path,
) -> dict[Path, _FileSnapshot]:
    from storage.extracted_text_store import extracted_text_path, extraction_metadata_path

    paths = (
        extracted_text_path(paper_id, cache_dir),
        extraction_metadata_path(paper_id, cache_dir),
        index_csv,
    )
    return {path: _snapshot_text(path) for path in paths}


def _restore_transaction_snapshots(snapshots: dict[Path, _FileSnapshot]) -> None:
    failures = 0
    for path, snapshot in snapshots.items():
        try:
            if snapshot.exists:
                atomic_write_text(path, snapshot.content)
            elif path.exists():
                path.unlink()
        except Exception:
            failures += 1
    if failures:
        raise FullTextTransactionError("Full-text rollback could not restore every previous file.")


def _verify_index_changes(paper_id: str, changes: dict[str, str], index_csv: Path) -> None:
    persisted = _record_from_index(paper_id, index_csv)
    if persisted is None or any(persisted.get(key, "") != str(value) for key, value in changes.items()):
        raise FullTextTransactionError("paper_index.csv did not persist the extraction state.")


def _persist_extraction_transaction(
    paper_id: str,
    *,
    cache_dir: Path,
    index_csv: Path,
    text: str | None,
    metadata: dict[str, Any],
    index_changes: dict[str, str],
) -> None:
    snapshots = _transaction_snapshots(paper_id, cache_dir, index_csv)
    try:
        if text is not None:
            save_extracted_text(paper_id, text, cache_dir)
        save_extraction_metadata(paper_id, metadata, cache_dir)
        update_paper_metadata(paper_id, index_changes, index_csv=index_csv)
        _verify_index_changes(paper_id, index_changes, index_csv)
    except Exception as exc:
        try:
            _restore_transaction_snapshots(snapshots)
        except FullTextTransactionError as rollback_error:
            raise rollback_error from exc
        raise FullTextTransactionError("Full-text persistence failed and was rolled back.") from exc
