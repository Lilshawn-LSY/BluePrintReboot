from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from storage.extracted_text_store import pdf_fingerprint
from storage.index_store import update_index_from_scan
from storage.paths import INDEX_CSV, NOTES_DIR, PAPERS_DIR


ONLINE_ONLY_MESSAGE = (
    "File is not locally available or cannot be read. Open it in Google Drive for desktop "
    "or make it available offline, then try again."
)


class PDFInboxError(RuntimeError):
    def __init__(self, message: str, plan: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.plan = plan


def _absolute(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _same_path(left: str | Path, right: str | Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _is_within(path: str | Path, directory: str | Path) -> bool:
    candidate = os.path.normcase(os.path.abspath(path))
    parent = os.path.normcase(os.path.abspath(directory))
    try:
        return os.path.commonpath((candidate, parent)) == parent
    except ValueError:
        return False


def _path_error(inbox_dir: str | Path | None, papers_dir: Path) -> tuple[str, str]:
    if inbox_dir is None or not str(inbox_dir).strip():
        return "invalid_path", "Configure an inbox folder before scanning."
    inbox_path = _absolute(inbox_dir)
    if _is_within(inbox_path, papers_dir):
        return "invalid_path", "The inbox must be outside papers/. papers/ is the only managed PDF directory."
    if not inbox_path.exists():
        return "source_missing", "The configured inbox folder does not exist."
    if not inbox_path.is_dir():
        return "invalid_path", "The configured inbox path is not a folder."
    return "", ""


def _managed_hashes(papers_dir: Path) -> set[str]:
    hashes: set[str] = set()
    if not papers_dir.exists():
        return hashes
    for pdf_path in papers_dir.rglob("*.pdf"):
        try:
            digest = str(pdf_fingerprint(pdf_path).get("pdf_sha256") or "")
        except OSError:
            continue
        if digest:
            hashes.add(digest)
    return hashes


def _source_details(source_path: Path) -> tuple[dict[str, Any], str]:
    try:
        stat = source_path.stat()
        with source_path.open("rb") as source:
            header = source.read(4096)
        if stat.st_size <= 0 or b"%PDF-" not in header:
            return {}, "The PDF appears empty or incomplete."
        fingerprint = pdf_fingerprint(source_path)
    except (OSError, PermissionError):
        return {}, ONLINE_ONLY_MESSAGE
    if not fingerprint.get("pdf_sha256"):
        return {}, ONLINE_ONLY_MESSAGE
    return {
        "size_bytes": stat.st_size,
        "modified_time": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "sha256": str(fingerprint["pdf_sha256"]),
    }, ""


def _available_suffix_suggestion(target_path: Path) -> str:
    for suffix in range(2, 10_000):
        candidate = target_path.with_name(f"{target_path.stem}_{suffix}{target_path.suffix}")
        if not candidate.exists():
            return candidate.name
    return ""


def _candidate_record(source_path: Path, papers_dir: Path, managed_hashes: set[str]) -> dict[str, Any]:
    source_path = _absolute(source_path)
    target_path = _absolute(papers_dir / source_path.name)
    record: dict[str, Any] = {
        "filename": source_path.name,
        "source_path": str(source_path),
        "target_path": str(target_path),
        "size_bytes": 0,
        "modified_time": "",
        "sha256": "",
        "status": "new",
        "message": "Ready to preview for import.",
        "can_import": True,
    }
    if not source_path.exists() or not source_path.is_file():
        record.update(
            status="source_missing",
            message="The inbox PDF no longer exists.",
            can_import=False,
        )
        return record

    details, error = _source_details(source_path)
    if error:
        record.update(status="unreadable", message=error, can_import=False)
        return record
    record.update(details)

    if target_path.exists():
        try:
            target_hash = str(pdf_fingerprint(target_path).get("pdf_sha256") or "")
        except OSError:
            target_hash = ""
        if target_hash and target_hash == record["sha256"]:
            record.update(
                status="already_imported",
                message="The same PDF is already present in papers/.",
                can_import=False,
            )
        else:
            suggestion = _available_suffix_suggestion(target_path)
            message = "A different PDF with this filename already exists in papers/."
            if suggestion:
                message += f" An available filename is {suggestion}, but import will not rename automatically."
            record.update(status="filename_collision", message=message, can_import=False)
        return record

    if record["sha256"] in managed_hashes:
        record.update(
            status="already_imported",
            message="The same PDF content is already present in papers/ under another filename.",
            can_import=False,
        )
    return record


def scan_pdf_inbox(
    inbox_dir: str | Path | None,
    papers_dir: Path = PAPERS_DIR,
) -> dict[str, Any]:
    papers_dir = _absolute(papers_dir)
    error_status, error_message = _path_error(inbox_dir, papers_dir)
    inbox_path = _absolute(inbox_dir) if inbox_dir is not None and str(inbox_dir).strip() else None
    if error_status:
        return {
            "inbox_path": str(inbox_path or ""),
            "status": error_status,
            "message": error_message,
            "candidates": [],
        }

    assert inbox_path is not None
    try:
        entries = sorted(inbox_path.iterdir(), key=lambda path: path.name.lower())
    except (OSError, PermissionError):
        return {
            "inbox_path": str(inbox_path),
            "status": "unreadable",
            "message": "The configured inbox folder cannot be read.",
            "candidates": [],
        }

    managed_hashes = _managed_hashes(papers_dir)
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        if entry.suffix.lower() != ".pdf":
            continue
        try:
            is_file = entry.is_file()
        except OSError:
            is_file = True
        if is_file:
            candidates.append(_candidate_record(entry, papers_dir, managed_hashes))
    return {
        "inbox_path": str(inbox_path),
        "status": "ok",
        "message": f"Found {len(candidates)} PDF import candidate(s).",
        "candidates": candidates,
    }


def build_inbox_import_plan(
    source_path: str | Path,
    inbox_dir: str | Path | None,
    papers_dir: Path = PAPERS_DIR,
) -> dict[str, Any]:
    papers_dir = _absolute(papers_dir)
    error_status, error_message = _path_error(inbox_dir, papers_dir)
    source = _absolute(source_path)
    if error_status:
        return {
            "filename": source.name,
            "source_path": str(source),
            "target_path": str(_absolute(papers_dir / source.name)),
            "size_bytes": 0,
            "modified_time": "",
            "sha256": "",
            "status": error_status,
            "message": error_message,
            "can_import": False,
        }

    assert inbox_dir is not None
    inbox_path = _absolute(inbox_dir)
    if not _same_path(source.parent, inbox_path) or source.suffix.lower() != ".pdf":
        return {
            "filename": source.name,
            "source_path": str(source),
            "target_path": str(_absolute(papers_dir / source.name)),
            "size_bytes": 0,
            "modified_time": "",
            "sha256": "",
            "status": "invalid_path",
            "message": "The selected file is not a direct PDF child of the configured inbox.",
            "can_import": False,
        }
    return _candidate_record(source, papers_dir, _managed_hashes(papers_dir))


def _copy_exclusive(source: Path, target: Path) -> None:
    created_target = False
    try:
        with source.open("rb") as source_file:
            with target.open("xb") as target_file:
                created_target = True
                shutil.copyfileobj(source_file, target_file, length=1024 * 1024)
                target_file.flush()
                os.fsync(target_file.fileno())
        shutil.copystat(source, target)
    except Exception:
        if created_target and target.exists():
            target.unlink()
        raise


def import_pdf_from_inbox(
    source_path: str | Path,
    inbox_dir: str | Path | None,
    papers_dir: Path = PAPERS_DIR,
    index_csv: Path = INDEX_CSV,
    notes_dir: Path = NOTES_DIR,
    *,
    index_updater: Callable[..., pd.DataFrame] | None = None,
) -> dict[str, Any]:
    papers_dir = _absolute(papers_dir)
    plan = build_inbox_import_plan(source_path, inbox_dir, papers_dir)
    if not plan["can_import"]:
        raise PDFInboxError(f"Import is blocked with status {plan['status']}: {plan['message']}", plan)

    source = Path(str(plan["source_path"]))
    target = Path(str(plan["target_path"]))
    if not source.exists() or not source.is_file():
        stale_plan = build_inbox_import_plan(source, inbox_dir, papers_dir)
        raise PDFInboxError("The source PDF disappeared before import.", stale_plan)
    if target.exists():
        stale_plan = build_inbox_import_plan(source, inbox_dir, papers_dir)
        raise PDFInboxError("The target filename now exists; no file was overwritten.", stale_plan)

    details, source_error = _source_details(source)
    if source_error:
        stale_plan = dict(plan)
        stale_plan.update(status="unreadable", message=source_error, can_import=False)
        raise PDFInboxError(source_error, stale_plan)
    if target.exists():
        stale_plan = build_inbox_import_plan(source, inbox_dir, papers_dir)
        raise PDFInboxError("The target filename now exists; no file was overwritten.", stale_plan)

    papers_dir.mkdir(parents=True, exist_ok=True)
    copy_completed = False
    try:
        _copy_exclusive(source, target)
        copy_completed = True
        copied_hash = str(pdf_fingerprint(target).get("pdf_sha256") or "")
        if not copied_hash or copied_hash != details["sha256"]:
            raise OSError("Copied PDF verification failed.")
    except FileExistsError as exc:
        stale_plan = build_inbox_import_plan(source, inbox_dir, papers_dir)
        raise PDFInboxError(
            "The target filename appeared before copy; no file was overwritten.",
            stale_plan,
        ) from exc
    except FileNotFoundError as exc:
        stale_plan = build_inbox_import_plan(source, inbox_dir, papers_dir)
        raise PDFInboxError("The source PDF disappeared before copy.", stale_plan) from exc
    except PermissionError as exc:
        stale_plan = dict(plan)
        stale_plan.update(status="unreadable", message=ONLINE_ONLY_MESSAGE, can_import=False)
        raise PDFInboxError(ONLINE_ONLY_MESSAGE, stale_plan) from exc
    except Exception as exc:
        if copy_completed and target.exists():
            target.unlink()
        raise PDFInboxError(f"Could not copy the inbox PDF: {exc}", plan) from exc

    updater = index_updater or update_index_from_scan
    try:
        dataframe = updater(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir)
    except Exception as exc:
        result = dict(plan)
        result.update(copied=True, indexed=False, target_path=str(target))
        raise PDFInboxError(
            "The PDF was copied into papers/, but the library index update failed. Run Scan papers to retry.",
            result,
        ) from exc

    paper_id = ""
    target_resolved = str(target.resolve(strict=False))
    for record in dataframe.to_dict("records"):
        if _same_path(str(record.get("filepath", "")), target_resolved):
            paper_id = str(record.get("paper_id", ""))
            break
    result = dict(plan)
    result.update(
        status="imported",
        message="PDF copied into papers/ and the library index was updated.",
        can_import=False,
        copied=True,
        indexed=True,
        paper_id=paper_id,
        target_path=target_resolved,
    )
    return result
