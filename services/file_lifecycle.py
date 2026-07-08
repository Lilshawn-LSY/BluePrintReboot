from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from ingest.scanner import pdf_sha256_with_metadata
from storage.index_store import INDEX_COLUMNS, load_index, save_index
from storage.paths import INDEX_CSV, PAPERS_DIR


class FileLifecycleRepairError(RuntimeError):
    def __init__(self, message: str, plan: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.plan = plan


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _absolute(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _path_key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _is_within(path: str | Path, directory: str | Path) -> bool:
    candidate = _path_key(path)
    parent = _path_key(directory)
    try:
        return os.path.commonpath((candidate, parent)) == parent
    except ValueError:
        return False


def _record_path(record: Mapping[str, object], papers_dir: Path) -> Path:
    filepath = _text(record.get("filepath", ""))
    filename = _text(record.get("filename", ""))
    if filepath:
        path = Path(filepath)
        return path if path.is_absolute() else Path(papers_dir) / path
    return Path(papers_dir) / filename


def _pdf_files(papers_dir: Path) -> list[Path]:
    if not papers_dir.exists():
        return []
    return sorted(
        (path.resolve() for path in papers_dir.rglob("*.pdf") if path.is_file()),
        key=lambda path: path.as_posix().lower(),
    )


def _read_index(index_csv: Path) -> pd.DataFrame:
    if not index_csv.exists():
        return pd.DataFrame(columns=INDEX_COLUMNS)
    dataframe = pd.read_csv(index_csv, dtype=str).fillna("")
    for column in INDEX_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""
    return dataframe


def _safe_pdf_hash_metadata(path: Path, metadata: Mapping[str, object] | None = None) -> dict[str, str]:
    try:
        return pdf_sha256_with_metadata(path, metadata)
    except OSError:
        return {"pdf_sha256": "", "pdf_size_bytes": "0", "pdf_modified_at": ""}


def _safe_pdf_sha256(path: Path, metadata: Mapping[str, object] | None = None) -> str:
    return _safe_pdf_hash_metadata(path, metadata)["pdf_sha256"]


def _single_record(dataframe: pd.DataFrame, paper_id: str) -> dict[str, Any]:
    matches = dataframe[dataframe["paper_id"] == str(paper_id)]
    if len(matches) != 1:
        raise FileLifecycleRepairError(f"Expected one index record for paper_id {paper_id!r}.")
    return matches.iloc[0].to_dict()


def _indexed_paths(dataframe: pd.DataFrame) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for record in dataframe.to_dict("records"):
        filepath = _text(record.get("filepath", ""))
        paper_id = _text(record.get("paper_id", ""))
        if filepath and paper_id:
            indexed[_path_key(filepath)] = paper_id
    return indexed


def _indexed_hash_counts(dataframe: pd.DataFrame, papers_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in dataframe.to_dict("records"):
        digest = _text(record.get("pdf_sha256", ""))
        record_path = _record_path(record, papers_dir)
        if record_path.exists() and record_path.is_file():
            digest = _safe_pdf_sha256(record_path, record)
        if digest:
            counts[digest] = counts.get(digest, 0) + 1
    return counts


def diagnose_file_lifecycle(
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
) -> dict[str, Any]:
    """Return read-only PDF lifecycle diagnostics for index and managed files."""
    index_csv = Path(index_csv)
    papers_dir = _absolute(papers_dir)
    dataframe = _read_index(index_csv)
    records = dataframe.to_dict("records")
    indexed_paths = {
        _path_key(_record_path(record, papers_dir)): str(record.get("paper_id", ""))
        for record in records
        if _text(record.get("paper_id", ""))
    }
    managed_pdfs = _pdf_files(papers_dir)
    unindexed_files: list[dict[str, str]] = []
    unindexed_by_hash: dict[str, list[dict[str, str]]] = {}
    for path in managed_pdfs:
        if _path_key(path) in indexed_paths:
            continue
        digest = _safe_pdf_sha256(path)
        item = {"filename": path.name, "filepath": str(path), "pdf_sha256": digest}
        unindexed_files.append(item)
        if digest:
            unindexed_by_hash.setdefault(digest, []).append(item)

    missing_rows: list[dict[str, str]] = []
    indexed_by_hash: dict[str, list[dict[str, str]]] = {}
    reconnect_candidates: list[dict[str, str]] = []
    for record in records:
        record_path = _record_path(record, papers_dir)
        digest = _text(record.get("pdf_sha256", ""))
        if record_path.exists() and record_path.is_file():
            digest = _safe_pdf_sha256(record_path, record)
        indexed_item = {
            "paper_id": _text(record.get("paper_id", "")),
            "filename": _text(record.get("filename", "")),
            "filepath": str(record_path.resolve(strict=False)),
            "pdf_sha256": digest,
        }
        if digest:
            indexed_by_hash.setdefault(digest, []).append(indexed_item)
        if not record_path.exists() or not record_path.is_file():
            missing_rows.append(indexed_item)
            for candidate in unindexed_by_hash.get(digest, []):
                reconnect_candidates.append(
                    {
                        "paper_id": indexed_item["paper_id"],
                        "missing_filepath": indexed_item["filepath"],
                        "candidate_filepath": candidate["filepath"],
                        "candidate_filename": candidate["filename"],
                        "pdf_sha256": digest,
                        "reason": "same_pdf_sha256",
                    }
                )

    same_hash_duplicates: list[dict[str, Any]] = []
    for digest in sorted(set(indexed_by_hash) | set(unindexed_by_hash)):
        indexed_items = indexed_by_hash.get(digest, [])
        unindexed_items = unindexed_by_hash.get(digest, [])
        if len(indexed_items) + len(unindexed_items) <= 1:
            continue
        same_hash_duplicates.append(
            {
                "pdf_sha256": digest,
                "indexed_records": indexed_items,
                "unindexed_files": unindexed_items,
                "indexed_record_count": len(indexed_items),
                "unindexed_file_count": len(unindexed_items),
            }
        )

    return {
        "missing_indexed_pdfs": missing_rows,
        "unindexed_pdfs": unindexed_files,
        "same_hash_duplicate_candidates": same_hash_duplicates,
        "likely_reconnect_candidates": reconnect_candidates,
    }


def build_duplicate_reconnect_plan(
    paper_id: str,
    target_pdf: str | Path,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
) -> dict[str, Any]:
    papers_dir = _absolute(papers_dir)
    dataframe = load_index(index_csv, papers_dir=papers_dir)
    record = _single_record(dataframe, paper_id)
    current_path = _record_path(record, papers_dir).resolve(strict=False)
    target_path = _absolute(target_pdf)
    current_hash = _text(record.get("pdf_sha256", ""))
    if current_path.exists() and current_path.is_file():
        current_hash = _safe_pdf_sha256(current_path, record)

    plan: dict[str, Any] = {
        "paper_id": str(paper_id),
        "current_filename": _text(record.get("filename", "")),
        "current_filepath": str(current_path),
        "current_pdf_sha256": current_hash,
        "target_filename": target_path.name,
        "target_path": str(target_path),
        "target_pdf_sha256": "",
        "target_pdf_size_bytes": "0",
        "target_pdf_modified_at": "",
        "status": "invalid",
        "message": "",
        "can_reconnect": False,
        "requires_hash_mismatch_confirmation": False,
        "updates": "filename, filepath, pdf_sha256, pdf_size_bytes, pdf_modified_at, updated_at",
        "preserves": "paper_id, notes, note blocks, project links, PDFs, extracted text",
    }
    if not _is_within(target_path, papers_dir):
        plan.update(status="outside_papers", message="Reconnect target must be inside papers/.")
        return plan
    if not target_path.exists() or not target_path.is_file() or target_path.suffix.lower() != ".pdf":
        plan.update(status="target_missing", message="Reconnect target must be an existing PDF file.")
        return plan

    indexed_paper_id = _indexed_paths(dataframe).get(_path_key(target_path), "")
    if indexed_paper_id and indexed_paper_id != str(paper_id):
        plan.update(
            status="already_indexed",
            message=(
                f"The selected PDF is already indexed as {indexed_paper_id}; "
                "remove a confirmed duplicate row instead of pointing two rows at one file."
            ),
            indexed_paper_id=indexed_paper_id,
        )
        return plan

    target_metadata = _safe_pdf_hash_metadata(target_path)
    target_hash = target_metadata["pdf_sha256"]
    if not target_hash:
        plan.update(status="target_unreadable", message="The selected PDF could not be hashed.")
        return plan
    requires_mismatch = bool(current_hash and target_hash != current_hash)
    status = "hash_mismatch" if requires_mismatch else "hash_match"
    message = (
        "SHA-256 differs from the selected paper row; explicit mismatch confirmation is required."
        if requires_mismatch
        else "Ready to reconnect this paper_id to the selected PDF."
    )
    if not current_hash:
        status = "hash_unknown"
        message = "The selected paper row has no stored SHA-256; verify the PDF manually before reconnecting."

    plan.update(
        target_pdf_sha256=target_hash,
        target_pdf_size_bytes=target_metadata["pdf_size_bytes"],
        target_pdf_modified_at=target_metadata["pdf_modified_at"],
        status=status,
        message=message,
        can_reconnect=True,
        requires_hash_mismatch_confirmation=requires_mismatch,
        indexed_paper_id=indexed_paper_id,
    )
    return plan


def reconnect_duplicate_pdf(
    paper_id: str,
    target_pdf: str | Path,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    confirm_hash_mismatch: bool = False,
) -> dict[str, Any]:
    plan = build_duplicate_reconnect_plan(
        paper_id,
        target_pdf,
        index_csv=index_csv,
        papers_dir=papers_dir,
    )
    if not plan["can_reconnect"]:
        raise FileLifecycleRepairError(f"Reconnect is blocked with status {plan['status']}.", plan)
    if plan["requires_hash_mismatch_confirmation"] and not confirm_hash_mismatch:
        raise FileLifecycleRepairError("Hash mismatch requires explicit confirmation.", plan)

    dataframe = load_index(index_csv, papers_dir=papers_dir)
    row_mask = dataframe["paper_id"] == str(paper_id)
    if row_mask.sum() != 1:
        raise FileLifecycleRepairError(f"Expected one index record for paper_id {paper_id!r}.", plan)
    dataframe.loc[row_mask, "filename"] = str(plan["target_filename"])
    dataframe.loc[row_mask, "filepath"] = str(plan["target_path"])
    dataframe.loc[row_mask, "pdf_sha256"] = str(plan["target_pdf_sha256"])
    dataframe.loc[row_mask, "pdf_size_bytes"] = str(plan.get("target_pdf_size_bytes", "0"))
    dataframe.loc[row_mask, "pdf_modified_at"] = str(plan.get("target_pdf_modified_at", ""))
    dataframe.loc[row_mask, "updated_at"] = _now_iso()
    save_index(dataframe, index_csv)

    result = dict(plan)
    result.update(
        status="reconnected",
        message="Duplicate lifecycle reconnect updated only file identity fields and preserved paper_id-linked data.",
        can_reconnect=False,
    )
    return result


def build_duplicate_remove_plan(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
) -> dict[str, Any]:
    papers_dir = _absolute(papers_dir)
    dataframe = load_index(index_csv, papers_dir=papers_dir)
    record = _single_record(dataframe, paper_id)
    record_path = _record_path(record, papers_dir)
    digest = _text(record.get("pdf_sha256", ""))
    if record_path.exists() and record_path.is_file():
        digest = _safe_pdf_sha256(record_path, record)
    counts = _indexed_hash_counts(dataframe, papers_dir)
    duplicate_count = counts.get(digest, 0) if digest else 0
    can_remove = duplicate_count > 1
    status = "ready" if can_remove else "not_duplicate_row"
    message = (
        "Ready to remove only this duplicate index row."
        if can_remove
        else "This row is not one of multiple indexed rows with the same PDF SHA-256."
    )
    return {
        "paper_id": str(paper_id),
        "filename": _text(record.get("filename", "")),
        "filepath": str(record_path.resolve(strict=False)),
        "pdf_sha256": digest,
        "same_hash_index_row_count": duplicate_count,
        "status": status,
        "message": message,
        "can_remove": can_remove,
        "removes": "paper_index_row_only",
        "preserves": "notes, note blocks, project links, PDFs, extracted text",
        "warning": "Orphan records may remain; review orphan repair after removing an index row.",
    }


def remove_duplicate_index_row(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    plan = build_duplicate_remove_plan(paper_id, index_csv=index_csv, papers_dir=papers_dir)
    if not plan["can_remove"]:
        raise FileLifecycleRepairError(f"Remove is blocked with status {plan['status']}.", plan)
    if not confirm:
        raise FileLifecycleRepairError("Duplicate index-row removal requires explicit confirmation.", plan)

    dataframe = load_index(index_csv, papers_dir=papers_dir)
    updated = dataframe[dataframe["paper_id"] != str(paper_id)].copy()
    save_index(updated, index_csv)
    result = dict(plan)
    result.update(
        status="removed_duplicate_index_row",
        message=(
            "Duplicate index row removed. Notes, note blocks, project links, PDFs, and extracted text "
            "were left untouched."
        ),
        can_remove=False,
    )
    return result
