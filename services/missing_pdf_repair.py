from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from ingest.scanner import compute_pdf_sha256
from storage.index_store import load_index, save_index
from storage.paths import INDEX_CSV, PAPERS_DIR


ARCHIVE_DEFERRED_MESSAGE = (
    "Archive is deferred because paper status currently supports unread, reading, and read only."
)


class MissingPDFRepairError(RuntimeError):
    def __init__(self, message: str, plan: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.plan = plan


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
        return path if path.is_absolute() else papers_dir / path
    return papers_dir / filename


def _pdf_files(papers_dir: Path) -> list[Path]:
    if not papers_dir.exists():
        return []
    return sorted(
        (path.resolve() for path in papers_dir.rglob("*.pdf") if path.is_file()),
        key=lambda path: path.as_posix().lower(),
    )


def _indexed_paths(dataframe: pd.DataFrame) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for record in dataframe.to_dict("records"):
        filepath = _text(record.get("filepath", ""))
        paper_id = _text(record.get("paper_id", ""))
        if filepath and paper_id:
            indexed[_path_key(filepath)] = paper_id
    return indexed


def _single_record(dataframe: pd.DataFrame, paper_id: str) -> dict[str, Any]:
    matches = dataframe[dataframe["paper_id"] == str(paper_id)]
    if len(matches) != 1:
        raise MissingPDFRepairError(f"Expected one index record for paper_id {paper_id!r}.")
    return matches.iloc[0].to_dict()


def _candidate_for_pdf(
    record: Mapping[str, object],
    pdf_path: Path,
    indexed_by_path: Mapping[str, str],
) -> dict[str, Any]:
    paper_id = _text(record.get("paper_id", ""))
    expected_hash = _text(record.get("pdf_sha256", ""))
    resolved = _absolute(pdf_path)
    try:
        selected_hash = compute_pdf_sha256(resolved)
    except OSError as exc:
        return {
            "path": str(resolved),
            "filename": resolved.name,
            "pdf_sha256": "",
            "expected_pdf_sha256": expected_hash,
            "status": "unreadable",
            "message": f"Could not read PDF hash: {exc}",
            "can_reconnect": False,
            "requires_hash_mismatch_confirmation": False,
            "indexed_paper_id": "",
        }

    indexed_paper_id = indexed_by_path.get(_path_key(resolved), "")
    if indexed_paper_id and indexed_paper_id != paper_id:
        return {
            "path": str(resolved),
            "filename": resolved.name,
            "pdf_sha256": selected_hash,
            "expected_pdf_sha256": expected_hash,
            "status": "already_indexed",
            "message": f"This PDF is already indexed as {indexed_paper_id}; duplicate repair is deferred.",
            "can_reconnect": False,
            "requires_hash_mismatch_confirmation": False,
            "indexed_paper_id": indexed_paper_id,
        }

    if expected_hash and selected_hash == expected_hash:
        status = "hash_match"
        message = "SHA-256 matches the missing index record."
        requires_confirmation = False
    elif expected_hash:
        status = "hash_mismatch"
        message = "SHA-256 differs from the missing index record; explicit mismatch confirmation is required."
        requires_confirmation = True
    else:
        status = "hash_unknown"
        message = "The missing index record has no stored SHA-256; verify the PDF manually before reconnecting."
        requires_confirmation = False

    return {
        "path": str(resolved),
        "filename": resolved.name,
        "pdf_sha256": selected_hash,
        "expected_pdf_sha256": expected_hash,
        "status": status,
        "message": message,
        "can_reconnect": True,
        "requires_hash_mismatch_confirmation": requires_confirmation,
        "indexed_paper_id": indexed_paper_id,
    }


def list_reconnect_candidates(
    record: Mapping[str, object],
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
) -> list[dict[str, Any]]:
    papers_dir = _absolute(papers_dir)
    dataframe = load_index(index_csv, papers_dir=papers_dir)
    indexed_by_path = _indexed_paths(dataframe)
    candidates = [
        _candidate_for_pdf(record, pdf_path, indexed_by_path)
        for pdf_path in _pdf_files(papers_dir)
    ]
    rank = {
        "hash_match": 0,
        "hash_unknown": 1,
        "hash_mismatch": 2,
        "already_indexed": 3,
        "unreadable": 4,
    }
    return sorted(candidates, key=lambda item: (rank.get(str(item["status"]), 99), str(item["filename"]).lower()))


def build_reconnect_plan(
    paper_id: str,
    target_pdf: str | Path,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
) -> dict[str, Any]:
    papers_dir = _absolute(papers_dir)
    dataframe = load_index(index_csv, papers_dir=papers_dir)
    record = _single_record(dataframe, paper_id)
    current_path = _absolute(_record_path(record, papers_dir))
    target_path = _absolute(target_pdf)
    base_plan: dict[str, Any] = {
        "paper_id": str(paper_id),
        "current_filename": _text(record.get("filename", "")),
        "current_filepath": str(current_path),
        "current_pdf_sha256": _text(record.get("pdf_sha256", "")),
        "target_path": str(target_path),
        "target_filename": target_path.name,
        "target_pdf_sha256": "",
        "status": "invalid",
        "message": "",
        "can_reconnect": False,
        "requires_hash_mismatch_confirmation": False,
    }

    if current_path.exists() and current_path.is_file():
        base_plan.update(
            status="current_pdf_present",
            message="The indexed PDF is not missing; missing-PDF repair is not needed.",
        )
        return base_plan
    if not _is_within(target_path, papers_dir):
        base_plan.update(
            status="outside_papers",
            message="Reconnect target must be inside the managed papers directory.",
        )
        return base_plan
    if not target_path.exists() or not target_path.is_file() or target_path.suffix.lower() != ".pdf":
        base_plan.update(
            status="target_missing",
            message="Reconnect target must be an existing PDF file.",
        )
        return base_plan

    candidate = _candidate_for_pdf(record, target_path, _indexed_paths(dataframe))
    base_plan.update(
        target_pdf_sha256=candidate["pdf_sha256"],
        status=candidate["status"],
        message=candidate["message"],
        can_reconnect=candidate["can_reconnect"],
        requires_hash_mismatch_confirmation=candidate["requires_hash_mismatch_confirmation"],
        indexed_paper_id=candidate["indexed_paper_id"],
    )
    return base_plan


def reconnect_missing_pdf(
    paper_id: str,
    target_pdf: str | Path,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    confirm_hash_mismatch: bool = False,
) -> dict[str, Any]:
    plan = build_reconnect_plan(paper_id, target_pdf, index_csv=index_csv, papers_dir=papers_dir)
    if not plan["can_reconnect"]:
        raise MissingPDFRepairError(f"Reconnect is blocked with status {plan['status']}.", plan)
    if plan["requires_hash_mismatch_confirmation"] and not confirm_hash_mismatch:
        raise MissingPDFRepairError("Hash mismatch requires explicit confirmation.", plan)

    dataframe = load_index(index_csv, papers_dir=papers_dir)
    row_mask = dataframe["paper_id"] == str(paper_id)
    if row_mask.sum() != 1:
        raise MissingPDFRepairError(f"Expected one index record for paper_id {paper_id!r}.", plan)
    dataframe.loc[row_mask, "filename"] = str(plan["target_filename"])
    dataframe.loc[row_mask, "filepath"] = str(plan["target_path"])
    dataframe.loc[row_mask, "pdf_sha256"] = str(plan["target_pdf_sha256"])
    save_index(dataframe, index_csv)

    result = dict(plan)
    result.update(
        status="reconnected",
        message="Missing PDF record reconnected without changing paper_id.",
    )
    return result


def remove_missing_pdf_from_index(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    dataframe = load_index(index_csv, papers_dir=papers_dir)
    record = _single_record(dataframe, paper_id)
    current_path = _absolute(_record_path(record, _absolute(papers_dir)))
    plan = {
        "paper_id": str(paper_id),
        "filename": _text(record.get("filename", "")),
        "filepath": str(current_path),
        "status": "ready",
        "message": "Ready to remove only the index row.",
        "can_remove": True,
    }
    if current_path.exists() and current_path.is_file():
        plan.update(
            status="current_pdf_present",
            message="The indexed PDF still exists; this missing-PDF remove action is blocked.",
            can_remove=False,
        )
        raise MissingPDFRepairError("Remove from index is blocked because the PDF exists.", plan)
    if not confirm:
        raise MissingPDFRepairError("Remove from index requires explicit confirmation.", plan)

    updated = dataframe[dataframe["paper_id"] != str(paper_id)].copy()
    save_index(updated, index_csv)
    result = dict(plan)
    result.update(
        status="removed_from_index",
        message="Index row removed. Notes, note blocks, project links, PDFs, and caches were left untouched.",
    )
    return result
