from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from ingest.doi import normalize_doi
from storage.extracted_text_store import extraction_cache_status, pdf_fingerprint
from storage.index_store import INDEX_COLUMNS
from storage.atomic_json import (
    JsonStoreError,
    atomic_write_json,
    json_store_issue,
    read_json_file,
    require_json_list,
)
from storage.note_block_store import list_note_blocks, save_note_blocks
from storage.project_link_store import delete_project_link, list_project_links, save_project_links
from storage.paths import (
    EXTRACTED_TEXT_DIR,
    EXPORTS_DIR,
    INDEX_CSV,
    NOTES_DIR,
    NOTE_BLOCKS_DIR,
    PAPERS_DIR,
    PROJECTS_DIR,
)


ORPHAN_PRESERVE_ACTION = "Preserve for now; reattach manually later or export before deletion."
ORPHAN_PROJECT_LINK_ACTION = "Remove only this project link after confirmation."
ORPHAN_EXPORT_ACTION = "Export a recovery copy before reattaching or deleting orphan data."

ISSUE_GUIDANCE: dict[str, dict[str, str]] = {
    "missing_pdfs": {
        "severity": "error",
        "category": "file identity",
        "meaning": "The index points to a PDF path that is missing or unreadable.",
        "next_action": "Reconnect the record to the intended PDF under papers/ or remove only the index row after confirming related notes and links.",
    },
    "unindexed_pdfs": {
        "severity": "review",
        "category": "file identity",
        "meaning": "A PDF exists under papers/ but does not have a paper_index.csv row.",
        "next_action": "Run the local scan when you are ready to add it, or leave it untouched if it is intentionally staged.",
    },
    "duplicate_filenames": {
        "severity": "review",
        "category": "metadata",
        "meaning": "Multiple index rows use the same filename text.",
        "next_action": "Review the rows before moving files or running filename hygiene.",
    },
    "duplicate_pdf_hashes": {
        "severity": "warning",
        "category": "file identity",
        "meaning": "The same PDF content appears in more than one indexed or unindexed location.",
        "next_action": "Choose keep, reconnect, ignore, or confirmed index-row removal; the app does not auto-merge duplicates.",
    },
    "duplicate_dois": {
        "severity": "review",
        "category": "metadata",
        "meaning": "Multiple records normalize to the same DOI.",
        "next_action": "Review metadata and paper identity before editing or removing rows.",
    },
    "missing_metadata": {
        "severity": "review",
        "category": "metadata",
        "meaning": "Some records are missing title, author, or year fields.",
        "next_action": "Fill fields manually or use Metadata Assist before relying on filenames, tags, or release evidence.",
    },
    "orphan_notes": {
        "severity": "warning",
        "category": "user data",
        "meaning": "A Reading Note file no longer matches an indexed paper_id.",
        "next_action": "Preserve it, export it, or reattach it to an indexed paper before considering confirmed deletion.",
    },
    "orphan_note_blocks": {
        "severity": "warning",
        "category": "user data",
        "meaning": "A structured note-block JSON file no longer matches an indexed paper_id.",
        "next_action": "Export or reattach blocks before using confirmed deletion.",
    },
    "orphan_project_links": {
        "severity": "warning",
        "category": "project links",
        "meaning": "A project link points to a missing project, paper, or note block.",
        "next_action": "Export, reattach, or unlink the broken link; papers and notes remain untouched.",
    },
    "orphan_extracted_text": {
        "severity": "review",
        "category": "cache",
        "meaning": "Extracted-text cache files exist for paper_ids that are no longer indexed.",
        "next_action": "Preserve by default; delete only through an explicit cache cleanup decision.",
    },
    "stale_extracted_text": {
        "severity": "review",
        "category": "cache",
        "meaning": "A cached extracted-text file was built from a different PDF hash than the current PDF.",
        "next_action": "Rebuild extracted text when you next need full-text evidence for that paper.",
    },
    "noncanonical_filepaths": {
        "severity": "warning",
        "category": "file identity",
        "meaning": "An indexed PDF path is outside the managed papers/ directory.",
        "next_action": "Move or reconnect the PDF into papers/ before backup or restore work.",
    },
    "corrupt_json": {
        "severity": "error",
        "category": "storage",
        "meaning": "A local JSON store could not be parsed or has the wrong top-level shape.",
        "next_action": "Do not overwrite the file. Restore from backup or repair a copy manually, then rerun Health Check.",
    },
    "backup_snapshot_warnings": {
        "severity": "warning",
        "category": "backup",
        "meaning": "Backup snapshot coverage may be missing or stale.",
        "next_action": "Create a light or full backup snapshot before risky maintenance or moving computers.",
    },
    "errors": {
        "severity": "error",
        "category": "diagnostic",
        "meaning": "A health diagnostic could not read or inspect a local file.",
        "next_action": "Review the details, fix file access or corruption, and rerun Health Check before repair actions.",
    },
}


class OrphanRepairError(RuntimeError):
    def __init__(self, message: str, plan: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.plan = plan


class OrphanProjectLinkRepairError(RuntimeError):
    def __init__(self, message: str, plan: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.plan = plan


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


def _read_index(index_csv: Path) -> tuple[pd.DataFrame, list[str]]:
    if not index_csv.exists():
        return pd.DataFrame(columns=INDEX_COLUMNS), ["paper_index.csv does not exist."]
    try:
        dataframe = pd.read_csv(index_csv, dtype=str).fillna("")
    except Exception as exc:
        return pd.DataFrame(columns=INDEX_COLUMNS), [f"paper_index.csv could not be read: {exc}"]
    for column in INDEX_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""
    return dataframe, []


def _pdf_files(papers_dir: Path) -> list[Path]:
    if not papers_dir.exists():
        return []
    return sorted(
        (path.resolve() for path in papers_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.as_posix().lower(),
    )


def _remember_json_issue(
    issues: dict[str, dict[str, str]],
    error: JsonStoreError,
    *,
    severity: str = "error",
) -> None:
    record = json_store_issue(error, severity=severity)
    record["classification"] = "corrupt json" if error.__class__.__name__ == "CorruptJsonError" else "invalid json store"
    issues.setdefault(record["path"], record)


def _load_json_list(
    path: Path,
    errors: list[str],
    corrupt_json: dict[str, dict[str, str]] | None = None,
    *,
    store_name: str = "JSON file",
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = require_json_list(
            read_json_file(path, store_name=store_name),
            path,
            store_name=store_name,
        )
    except JsonStoreError as exc:
        if corrupt_json is not None:
            _remember_json_issue(corrupt_json, exc)
        errors.append(f"{path.name} could not be read: {exc}")
        return []
    return [item for item in value if isinstance(item, dict)]


def _health_json_files(
    *,
    index_csv: Path,
    note_blocks_dir: Path,
    projects_dir: Path,
    extracted_text_dir: Path,
) -> list[Path]:
    data_dir = Path(index_csv).parent
    config_dir = data_dir.parent / "config"
    candidates: list[Path] = [
        projects_dir / "projects.json",
        projects_dir / "project_links.json",
        data_dir / "note_imports.json",
        config_dir / "tag_rules.json",
        config_dir / "canonical_tags.json",
        config_dir / "settings.json",
        data_dir / "settings.json",
    ]
    for directory in (
        note_blocks_dir,
        extracted_text_dir,
        data_dir / "paper_profiles",
        config_dir / "tag_book",
    ):
        if directory.exists() and directory.is_dir():
            candidates.extend(sorted(directory.glob("*.json"), key=lambda item: item.as_posix().lower()))
    unique: dict[str, Path] = {}
    for path in candidates:
        if path.exists() and path.is_file():
            unique[_path_key(path)] = path
    return sorted(unique.values(), key=lambda item: item.as_posix().lower())


def _scan_corrupt_json(
    paths: list[Path],
    issues: dict[str, dict[str, str]],
) -> None:
    for path in paths:
        try:
            read_json_file(path, store_name="App-owned JSON file")
        except JsonStoreError as exc:
            _remember_json_issue(issues, exc)


def _backup_snapshot_warnings(exports_dir: Path) -> list[dict[str, str]]:
    if not exports_dir.exists() or not exports_dir.is_dir():
        return [
            {
                "severity": "warning",
                "category": "backup",
                "path": str(exports_dir.resolve(strict=False)),
                "issue": "No exports directory was found for backup snapshots.",
                "suggested_action": "Create a backup snapshot before maintenance or moving this library.",
            }
        ]
    snapshots = sorted(exports_dir.glob("blueprint_snapshot_*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not snapshots:
        return [
            {
                "severity": "warning",
                "category": "backup",
                "path": str(exports_dir.resolve(strict=False)),
                "issue": "No backup snapshots were found in exports/.",
                "suggested_action": "Create a light or full backup snapshot before risky maintenance or moving computers.",
            }
        ]
    latest = snapshots[0]
    return [
        {
            "severity": "info",
            "category": "backup",
            "path": str(latest.resolve(strict=False)),
            "issue": "Latest backup snapshot found.",
            "suggested_action": "Verify this snapshot is recent enough before moving or repairing library data.",
        }
    ]


def _active_issue_guidance(issue_sections: dict[str, list[Any]]) -> dict[str, dict[str, str]]:
    return {
        key: ISSUE_GUIDANCE[key]
        for key, items in issue_sections.items()
        if items and key in ISSUE_GUIDANCE
    }


def _atomic_write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return path


def _export_path(exports_dir: Path, prefix: str, identifier: str) -> Path:
    safe_identifier = "".join(character if character.isalnum() or character in ("-", "_") else "-" for character in identifier)
    safe_identifier = safe_identifier.strip("-_") or "orphan"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(exports_dir) / f"{prefix}_{safe_identifier}_{timestamp}.json"


def _pdf_sha256(path: Path, errors: list[str]) -> str:
    try:
        return str(pdf_fingerprint(path).get("pdf_sha256") or "")
    except OSError as exc:
        errors.append(f"PDF hash check failed for {path}: {exc}")
        return ""


def _file_modified_at(path: Path, errors: list[str]) -> str:
    try:
        timestamp = path.stat().st_mtime
    except OSError as exc:
        errors.append(f"File stat failed for {path}: {exc}")
        return ""
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat()


def _file_size(path: Path, errors: list[str]) -> int:
    try:
        return path.stat().st_size
    except OSError as exc:
        errors.append(f"File stat failed for {path}: {exc}")
        return 0


def _text_preview(value: object, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _note_path_for_record(record: dict[str, Any], notes_dir: Path) -> Path | None:
    note_path = str(record.get("note_path", "")).strip()
    if note_path:
        return _absolute(note_path)
    paper_id = str(record.get("paper_id", "")).strip()
    if not paper_id:
        return None
    return _absolute(notes_dir / f"{paper_id}.md")


def _note_block_summary(block: dict[str, Any]) -> dict[str, str]:
    text = str(block.get("text", "") or "").strip() or str(block.get("quote", "") or "").strip()
    return {
        "block_id": str(block.get("id", "")),
        "block_type": str(block.get("block_type", "")),
        "title": str(block.get("title", "")),
        "text_preview": _text_preview(text),
        "created_at": str(block.get("created_at", "")),
        "updated_at": str(block.get("updated_at", "")),
    }


def _note_blocks_by_paper(
    note_blocks_dir: Path,
    errors: list[str],
    corrupt_json: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, set[str]], dict[str, int], dict[str, list[dict[str, str]]]]:
    block_ids_by_paper: dict[str, set[str]] = {}
    block_counts_by_paper: dict[str, int] = {}
    block_details_by_paper: dict[str, list[dict[str, str]]] = {}
    if not note_blocks_dir.exists():
        return block_ids_by_paper, block_counts_by_paper, block_details_by_paper
    for path in note_blocks_dir.glob("*.json"):
        blocks = _load_json_list(path, errors, corrupt_json, store_name="Note block file")
        block_ids_by_paper[path.stem] = {str(block.get("id", "")) for block in blocks if block.get("id")}
        block_counts_by_paper[path.stem] = len(blocks)
        block_details_by_paper[path.stem] = [_note_block_summary(block) for block in blocks]
    return block_ids_by_paper, block_counts_by_paper, block_details_by_paper


def _project_link_counts(project_links: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for link in project_links:
        paper_id = str(link.get("paper_id", "")).strip()
        if paper_id:
            counts[paper_id] = counts.get(paper_id, 0) + 1
    return counts


def _duplicate_pdf_hash_classification(indexed_count: int, unindexed_count: int) -> str:
    if indexed_count and unindexed_count:
        return "indexed + unindexed duplicate"
    if indexed_count > 1:
        return "indexed duplicate"
    return "multiple unindexed duplicate"


def _orphan_note_records(notes_dir: Path, paper_ids: set[str], errors: list[str]) -> list[dict[str, Any]]:
    if not notes_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(notes_dir.glob("*.md"), key=lambda item: item.as_posix().lower()):
        if path.stem in paper_ids:
            continue
        resolved = path.resolve()
        records.append(
            {
                "classification": "orphan note file",
                "paper_id": path.stem,
                "filename": path.name,
                "filepath": str(resolved),
                "size_bytes": _file_size(resolved, errors),
                "modified_at": _file_modified_at(resolved, errors),
                "review_action": ORPHAN_PRESERVE_ACTION,
            }
        )
    return records


def _orphan_note_block_records(
    note_blocks_dir: Path,
    paper_ids: set[str],
    note_block_counts: dict[str, int],
    note_block_details: dict[str, list[dict[str, str]]],
    errors: list[str],
) -> list[dict[str, Any]]:
    if not note_blocks_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(note_blocks_dir.glob("*.json"), key=lambda item: item.as_posix().lower()):
        if path.stem in paper_ids:
            continue
        resolved = path.resolve()
        blocks = note_block_details.get(path.stem, [])
        records.append(
            {
                "classification": "orphan note block file",
                "paper_id": path.stem,
                "filename": path.name,
                "filepath": str(resolved),
                "block_count": note_block_counts.get(path.stem, 0),
                "block_ids": ", ".join(block["block_id"] for block in blocks if block.get("block_id")),
                "modified_at": _file_modified_at(resolved, errors),
                "review_action": ORPHAN_PRESERVE_ACTION,
                "blocks": blocks,
            }
        )
    return records


def _project_names(projects: list[dict[str, Any]]) -> dict[str, str]:
    return {str(project.get("id", "")): str(project.get("name", "")) for project in projects if project.get("id")}


def _orphan_project_link_reasons(
    link: dict[str, Any],
    *,
    paper_ids: set[str],
    project_ids: set[str],
    blocks_by_paper: dict[str, set[str]],
) -> list[str]:
    reasons: list[str] = []
    project_id = str(link.get("project_id", "")).strip()
    paper_id = str(link.get("paper_id", "")).strip()
    target_type = str(link.get("target_type", "")).strip()
    target_id = str(link.get("target_id", "")).strip()
    if project_id not in project_ids:
        reasons.append("missing project")
    if target_type == "paper":
        if target_id not in paper_ids:
            reasons.append("missing target paper")
    else:
        if not paper_id or paper_id not in paper_ids:
            reasons.append("missing paper context")
    if target_type == "note_block" and target_id not in blocks_by_paper.get(paper_id, set()):
        reasons.append("missing target note block")
    return reasons


def _orphan_project_link_records(
    project_links: list[dict[str, Any]],
    *,
    paper_ids: set[str],
    project_ids: set[str],
    project_names: dict[str, str],
    blocks_by_paper: dict[str, set[str]],
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for link in project_links:
        reasons = _orphan_project_link_reasons(
            link,
            paper_ids=paper_ids,
            project_ids=project_ids,
            blocks_by_paper=blocks_by_paper,
        )
        if not reasons:
            continue
        project_id = str(link.get("project_id", ""))
        records.append(
            {
                "classification": "orphan project link",
                "link_id": str(link.get("id", "")),
                "project_id": project_id,
                "project_name": project_names.get(project_id, ""),
                "target_type": str(link.get("target_type", "")),
                "target_id": str(link.get("target_id", "")),
                "paper_id": str(link.get("paper_id", "")),
                "link_type": str(link.get("link_type", "")),
                "note": str(link.get("note", "")),
                "created_at": str(link.get("created_at", "")),
                "reason": ", ".join(reasons),
                "review_action": ORPHAN_PROJECT_LINK_ACTION,
            }
        )
    return records


def _orphan_extracted_text_records(
    extracted_text_dir: Path,
    paper_ids: set[str],
    errors: list[str],
) -> list[dict[str, Any]]:
    if not extracted_text_dir.exists():
        return []
    stems = {
        path.stem
        for path in extracted_text_dir.glob("*")
        if path.is_file() and path.suffix.lower() in (".txt", ".json")
    }
    records: list[dict[str, Any]] = []
    for paper_id in sorted(stem for stem in stems if stem not in paper_ids):
        text_path = extracted_text_dir / f"{paper_id}.txt"
        metadata_path = extracted_text_dir / f"{paper_id}.json"
        size_bytes = 0
        if text_path.exists():
            size_bytes += _file_size(text_path, errors)
        if metadata_path.exists():
            size_bytes += _file_size(metadata_path, errors)
        records.append(
            {
                "classification": "orphan extracted-text cache",
                "paper_id": paper_id,
                "text_path": str(text_path.resolve(strict=False)),
                "metadata_path": str(metadata_path.resolve(strict=False)),
                "has_text_file": text_path.exists(),
                "has_metadata_file": metadata_path.exists(),
                "size_bytes": size_bytes,
                "review_action": "Preserve by default; delete only after explicit cache cleanup confirmation.",
            }
        )
    return records


def _duplicate_pdf_hashes(
    records: list[dict[str, Any]],
    managed_pdfs: list[Path],
    indexed_paths: set[str],
    errors: list[str],
    *,
    notes_dir: Path,
    note_block_counts: dict[str, int],
    project_link_counts: dict[str, int],
) -> list[dict[str, Any]]:
    items_by_hash: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        filepath = str(record.get("filepath", "")).strip()
        resolved = _absolute(filepath) if filepath else None
        digest = str(record.get("pdf_sha256", "")).strip()
        if not digest and resolved is not None and resolved.exists() and resolved.is_file():
            digest = _pdf_sha256(resolved, errors)
        if not digest:
            continue
        paper_id = str(record.get("paper_id", ""))
        note_path = _note_path_for_record(record, notes_dir)
        group = items_by_hash.setdefault(digest, {"indexed_records": [], "unindexed_files": []})
        group["indexed_records"].append(
            {
                "paper_id": paper_id,
                "title": str(record.get("title", "")),
                "filename": str(record.get("filename", "")),
                "filepath": str(resolved or ""),
                "status": str(record.get("status", "")),
                "note_path": str(note_path or ""),
                "note_file_count": 1 if note_path is not None and note_path.exists() else 0,
                "note_block_count": note_block_counts.get(paper_id, 0),
                "project_link_count": project_link_counts.get(paper_id, 0),
            }
        )

    for path in managed_pdfs:
        if _path_key(path) in indexed_paths:
            continue
        digest = _pdf_sha256(path, errors)
        if not digest:
            continue
        group = items_by_hash.setdefault(digest, {"indexed_records": [], "unindexed_files": []})
        group["unindexed_files"].append(
            {
                "filename": path.name,
                "filepath": str(path),
                "review_action": "Do not add to index yet; handle later.",
            }
        )

    duplicates: list[dict[str, Any]] = []
    for digest, grouped_items in items_by_hash.items():
        indexed_records = grouped_items["indexed_records"]
        unindexed_files = grouped_items["unindexed_files"]
        indexed_count = len(indexed_records)
        unindexed_count = len(unindexed_files)
        if indexed_count + unindexed_count <= 1:
            continue
        duplicates.append(
            {
                "pdf_sha256": digest,
                "classification": _duplicate_pdf_hash_classification(indexed_count, unindexed_count),
                "indexed_record_count": indexed_count,
                "unindexed_file_count": unindexed_count,
                "indexed_records": indexed_records,
                "unindexed_files": unindexed_files,
            }
        )
    return sorted(
        duplicates,
        key=lambda item: (
            str(item["classification"]),
            str(item["pdf_sha256"]),
        ),
    )


def run_library_health_check(
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    notes_dir: Path = NOTES_DIR,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
    extracted_text_dir: Path = EXTRACTED_TEXT_DIR,
    exports_dir: Path | None = None,
) -> dict[str, Any]:
    index_csv = Path(index_csv)
    papers_dir = _absolute(papers_dir)
    notes_dir = Path(notes_dir)
    note_blocks_dir = Path(note_blocks_dir)
    projects_dir = Path(projects_dir)
    extracted_text_dir = Path(extracted_text_dir)
    exports_dir = Path(exports_dir) if exports_dir is not None else index_csv.parent.parent / "exports"
    dataframe, errors = _read_index(index_csv)
    corrupt_json_by_path: dict[str, dict[str, str]] = {}
    records = dataframe.to_dict("records")
    paper_ids = {str(record.get("paper_id", "")) for record in records if record.get("paper_id")}

    missing_pdfs: list[dict[str, str]] = []
    noncanonical_filepaths: list[dict[str, str]] = []
    indexed_paths: set[str] = set()
    for record in records:
        filepath = str(record.get("filepath", "")).strip()
        resolved = _absolute(filepath) if filepath else _absolute(papers_dir / str(record.get("filename", "")))
        indexed_paths.add(_path_key(resolved))
        item = {
            "paper_id": str(record.get("paper_id", "")),
            "filename": str(record.get("filename", "")),
            "filepath": str(resolved),
            "pdf_sha256": str(record.get("pdf_sha256", "")),
        }
        if not resolved.exists() or not resolved.is_file():
            missing_pdfs.append(item)
        if not _is_within(resolved, papers_dir):
            noncanonical_filepaths.append(item)

    managed_pdfs = _pdf_files(papers_dir)
    projects = _load_json_list(
        projects_dir / "projects.json",
        errors,
        corrupt_json_by_path,
        store_name="Projects file",
    )
    project_links = _load_json_list(
        projects_dir / "project_links.json",
        errors,
        corrupt_json_by_path,
        store_name="Project links file",
    )
    blocks_by_paper, note_block_counts, note_block_details = _note_blocks_by_paper(
        note_blocks_dir,
        errors,
        corrupt_json_by_path,
    )
    project_link_counts = _project_link_counts(project_links)
    unindexed_pdfs = [str(path) for path in managed_pdfs if _path_key(path) not in indexed_paths]
    duplicate_pdf_hashes = _duplicate_pdf_hashes(
        records,
        managed_pdfs,
        indexed_paths,
        errors,
        notes_dir=notes_dir,
        note_block_counts=note_block_counts,
        project_link_counts=project_link_counts,
    )

    filenames: dict[str, list[dict[str, str]]] = {}
    dois: dict[str, list[dict[str, str]]] = {}
    missing_metadata: list[dict[str, Any]] = []
    for record in records:
        paper_id = str(record.get("paper_id", ""))
        filename = str(record.get("filename", "")).strip()
        if filename:
            filenames.setdefault(filename.casefold(), []).append({"paper_id": paper_id, "filename": filename})
        doi = normalize_doi(str(record.get("doi", "")))
        if doi:
            dois.setdefault(doi, []).append({"paper_id": paper_id, "doi": doi})
        missing_fields = [field for field in ("title", "year", "authors") if not str(record.get(field, "")).strip()]
        if missing_fields:
            missing_metadata.append(
                {
                    "paper_id": paper_id,
                    "filename": filename,
                    "missing_fields": ", ".join(missing_fields),
                }
            )
    duplicate_filenames = [
        {"filename": items[0]["filename"], "count": len(items), "paper_ids": ", ".join(item["paper_id"] for item in items)}
        for items in filenames.values()
        if len(items) > 1
    ]
    duplicate_dois = [
        {"doi": doi, "count": len(items), "paper_ids": ", ".join(item["paper_id"] for item in items)}
        for doi, items in dois.items()
        if len(items) > 1
    ]

    project_ids = {str(project.get("id", "")) for project in projects if project.get("id")}
    project_names = _project_names(projects)
    orphan_notes = _orphan_note_records(notes_dir, paper_ids, errors)
    orphan_note_blocks = _orphan_note_block_records(
        note_blocks_dir,
        paper_ids,
        note_block_counts,
        note_block_details,
        errors,
    )
    orphan_project_links = _orphan_project_link_records(
        project_links,
        paper_ids=paper_ids,
        project_ids=project_ids,
        project_names=project_names,
        blocks_by_paper=blocks_by_paper,
    )
    orphan_extracted_text = _orphan_extracted_text_records(extracted_text_dir, paper_ids, errors)
    _scan_corrupt_json(
        _health_json_files(
            index_csv=index_csv,
            note_blocks_dir=note_blocks_dir,
            projects_dir=projects_dir,
            extracted_text_dir=extracted_text_dir,
        ),
        corrupt_json_by_path,
    )
    corrupt_json = sorted(corrupt_json_by_path.values(), key=lambda item: item["path"])
    backup_snapshot_warnings = _backup_snapshot_warnings(exports_dir)

    stale_extracted_text: list[dict[str, str]] = []
    for record in records:
        filepath = str(record.get("filepath", "")).strip()
        paper_id = str(record.get("paper_id", ""))
        if not filepath or not paper_id or not Path(filepath).is_file():
            continue
        try:
            cache_status = extraction_cache_status(paper_id, extracted_text_dir, pdf_path=filepath)
        except OSError as exc:
            errors.append(f"Extracted-text cache check failed for {paper_id}: {exc}")
            continue
        if cache_status["is_stale"]:
            stale_extracted_text.append(
                {
                    "paper_id": paper_id,
                    "filename": str(record.get("filename", "")),
                    "current_sha256": str(cache_status["pdf_sha256"]),
                    "cached_sha256": str(cache_status["cached_pdf_sha256"]),
                }
            )

    issue_sections = {
        "missing_pdfs": missing_pdfs,
        "unindexed_pdfs": unindexed_pdfs,
        "duplicate_filenames": duplicate_filenames,
        "duplicate_pdf_hashes": duplicate_pdf_hashes,
        "duplicate_dois": duplicate_dois,
        "missing_metadata": missing_metadata,
        "orphan_notes": orphan_notes,
        "orphan_note_blocks": orphan_note_blocks,
        "orphan_project_links": orphan_project_links,
        "orphan_extracted_text": orphan_extracted_text,
        "stale_extracted_text": stale_extracted_text,
        "noncanonical_filepaths": noncanonical_filepaths,
        "corrupt_json": corrupt_json,
        "backup_snapshot_warnings": backup_snapshot_warnings,
        "errors": errors,
    }
    issue_count = sum(
        len(items)
        for key, items in issue_sections.items()
        if key != "backup_snapshot_warnings" or any(item.get("severity") != "info" for item in items)
    )
    return {
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "healthy": issue_count == 0,
        "summary": {
            "index_rows": len(records),
            "managed_pdfs": len(managed_pdfs),
            "issue_count": issue_count,
        },
        "issue_guidance": _active_issue_guidance(issue_sections),
        **issue_sections,
    }


def build_orphan_project_link_removal_plan(
    link_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    index_csv = Path(index_csv)
    note_blocks_dir = Path(note_blocks_dir)
    projects_dir = Path(projects_dir)
    dataframe, errors = _read_index(index_csv)
    projects = _load_json_list(projects_dir / "projects.json", errors)
    project_links = _load_json_list(projects_dir / "project_links.json", errors)
    blocks_by_paper, _note_block_counts, _note_block_details = _note_blocks_by_paper(note_blocks_dir, errors)
    paper_ids = {str(record.get("paper_id", "")) for record in dataframe.to_dict("records") if record.get("paper_id")}
    project_ids = {str(project.get("id", "")) for project in projects if project.get("id")}
    project_names = _project_names(projects)

    plan: dict[str, Any] = {
        "link_id": str(link_id),
        "status": "not_found",
        "message": "Project link was not found.",
        "can_remove": False,
        "removes": "project_link_only",
        "errors": errors,
    }
    if errors:
        plan.update(
            status="diagnostic_error",
            message="Project link removal is blocked until health diagnostics can verify orphan status.",
        )
        return plan

    orphan_links = _orphan_project_link_records(
        project_links,
        paper_ids=paper_ids,
        project_ids=project_ids,
        project_names=project_names,
        blocks_by_paper=blocks_by_paper,
    )
    for orphan_link in orphan_links:
        if orphan_link["link_id"] == str(link_id):
            plan.update(
                orphan_link,
                status="ready",
                message="Ready to remove only this orphan project link.",
                can_remove=True,
            )
            return plan
    if any(str(link.get("id", "")) == str(link_id) for link in project_links):
        plan.update(
            status="not_orphan",
            message="Project link exists but is no longer orphaned.",
        )
    return plan


def remove_orphan_project_link(
    link_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    plan = build_orphan_project_link_removal_plan(
        link_id,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
    )
    if not plan["can_remove"]:
        raise OrphanProjectLinkRepairError(f"Remove is blocked with status {plan['status']}.", plan)
    if not confirm:
        raise OrphanProjectLinkRepairError("Orphan project link removal requires explicit confirmation.", plan)
    if not delete_project_link(str(link_id), projects_dir):
        raise OrphanProjectLinkRepairError("Project link was not found during removal.", plan)

    result = dict(plan)
    result.update(
        status="removed_project_link",
        message="Orphan project link removed. Papers, PDFs, notes, note blocks, and index rows were left untouched.",
        can_remove=False,
    )
    return result


def _indexed_paper_ids(index_csv: Path) -> tuple[set[str], list[str]]:
    dataframe, errors = _read_index(Path(index_csv))
    paper_ids = {str(record.get("paper_id", "")) for record in dataframe.to_dict("records") if record.get("paper_id")}
    return paper_ids, errors


def _note_path_for_paper_id(paper_id: str, notes_dir: Path) -> Path:
    return Path(notes_dir) / f"{paper_id}.md"


def _note_blocks_path_for_paper_id(paper_id: str, note_blocks_dir: Path) -> Path:
    return Path(note_blocks_dir) / f"{paper_id}.json"


def build_orphan_note_repair_plan(
    orphan_paper_id: str,
    target_paper_id: str = "",
    *,
    index_csv: Path = INDEX_CSV,
    notes_dir: Path = NOTES_DIR,
) -> dict[str, Any]:
    paper_ids, errors = _indexed_paper_ids(index_csv)
    orphan_paper_id = str(orphan_paper_id)
    target_paper_id = str(target_paper_id)
    note_path = _note_path_for_paper_id(orphan_paper_id, Path(notes_dir))
    target_path = _note_path_for_paper_id(target_paper_id, Path(notes_dir)) if target_paper_id else None
    plan: dict[str, Any] = {
        "orphan_paper_id": orphan_paper_id,
        "target_paper_id": target_paper_id,
        "source_path": str(note_path.resolve(strict=False)),
        "target_path": str(target_path.resolve(strict=False)) if target_path else "",
        "status": "invalid",
        "message": "",
        "can_reattach": False,
        "can_delete": False,
        "errors": errors,
    }
    if errors:
        plan.update(status="diagnostic_error", message="Index diagnostics must be clean before orphan note repair.")
        return plan
    if orphan_paper_id in paper_ids:
        plan.update(status="not_orphan", message="This note belongs to an indexed paper.")
        return plan
    if not note_path.exists() or not note_path.is_file():
        plan.update(status="missing_source", message="Orphan note file was not found.")
        return plan
    if target_paper_id and target_paper_id not in paper_ids:
        plan.update(status="target_missing", message="Target paper_id is not in the index.", can_delete=True)
        return plan
    plan.update(
        status="ready",
        message="Ready to reattach, export, or delete this orphan note with confirmation.",
        can_reattach=bool(target_paper_id),
        can_delete=True,
    )
    return plan


def export_orphan_note(
    orphan_paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    notes_dir: Path = NOTES_DIR,
    exports_dir: Path = EXPORTS_DIR,
) -> dict[str, Any]:
    plan = build_orphan_note_repair_plan(orphan_paper_id, index_csv=index_csv, notes_dir=notes_dir)
    if plan["status"] != "ready":
        raise OrphanRepairError(f"Export is blocked with status {plan['status']}.", plan)
    note_path = Path(str(plan["source_path"]))
    export_path = _export_path(Path(exports_dir), "orphan_note", orphan_paper_id)
    payload = {
        "kind": "orphan_note",
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "orphan_paper_id": str(orphan_paper_id),
        "source_path": str(note_path),
        "note_text": note_path.read_text(encoding="utf-8"),
    }
    atomic_write_json(export_path, payload, indent=2, ensure_ascii=False)
    result = dict(plan)
    result.update(status="exported", message="Orphan note exported without changing library data.", export_path=str(export_path))
    return result


def reattach_orphan_note(
    orphan_paper_id: str,
    target_paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    notes_dir: Path = NOTES_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    plan = build_orphan_note_repair_plan(
        orphan_paper_id,
        target_paper_id,
        index_csv=index_csv,
        notes_dir=notes_dir,
    )
    if not plan["can_reattach"]:
        raise OrphanRepairError(f"Reattach is blocked with status {plan['status']}.", plan)
    if not confirm:
        raise OrphanRepairError("Orphan note reattach requires explicit confirmation.", plan)

    source_path = Path(str(plan["source_path"]))
    target_path = Path(str(plan["target_path"]))
    orphan_text = source_path.read_text(encoding="utf-8")
    if target_path.exists():
        existing = target_path.read_text(encoding="utf-8").rstrip()
        marker = f"\n\n---\n\n## Reattached orphan note: {orphan_paper_id}\n\n"
        target_text = existing + marker + orphan_text.strip() + "\n"
    else:
        target_text = orphan_text
    _atomic_write_text(target_path, target_text)
    source_path.unlink()

    result = dict(plan)
    result.update(
        status="reattached_note",
        message="Orphan note content reattached to the selected paper. The original orphan file was removed.",
    )
    return result


def delete_orphan_note(
    orphan_paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    notes_dir: Path = NOTES_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    plan = build_orphan_note_repair_plan(orphan_paper_id, index_csv=index_csv, notes_dir=notes_dir)
    if not plan["can_delete"]:
        raise OrphanRepairError(f"Delete is blocked with status {plan['status']}.", plan)
    if not confirm:
        raise OrphanRepairError("Orphan note delete requires explicit confirmation.", plan)
    Path(str(plan["source_path"])).unlink()
    result = dict(plan)
    result.update(status="deleted_note", message="Orphan note file deleted after explicit confirmation.")
    return result


def build_orphan_note_block_repair_plan(
    orphan_paper_id: str,
    target_paper_id: str = "",
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
) -> dict[str, Any]:
    paper_ids, errors = _indexed_paper_ids(index_csv)
    orphan_paper_id = str(orphan_paper_id)
    target_paper_id = str(target_paper_id)
    source_path = _note_blocks_path_for_paper_id(orphan_paper_id, Path(note_blocks_dir))
    target_path = _note_blocks_path_for_paper_id(target_paper_id, Path(note_blocks_dir)) if target_paper_id else None
    plan: dict[str, Any] = {
        "orphan_paper_id": orphan_paper_id,
        "target_paper_id": target_paper_id,
        "source_path": str(source_path.resolve(strict=False)),
        "target_path": str(target_path.resolve(strict=False)) if target_path else "",
        "status": "invalid",
        "message": "",
        "can_reattach": False,
        "can_delete": False,
        "errors": errors,
    }
    if errors:
        plan.update(status="diagnostic_error", message="Index diagnostics must be clean before orphan block repair.")
        return plan
    if orphan_paper_id in paper_ids:
        plan.update(status="not_orphan", message="This note-block file belongs to an indexed paper.")
        return plan
    if not source_path.exists() or not source_path.is_file():
        plan.update(status="missing_source", message="Orphan note-block file was not found.")
        return plan
    if target_paper_id and target_paper_id not in paper_ids:
        plan.update(status="target_missing", message="Target paper_id is not in the index.", can_delete=True)
        return plan
    plan.update(
        status="ready",
        message="Ready to reattach, export, or delete this orphan note-block file with confirmation.",
        can_reattach=bool(target_paper_id),
        can_delete=True,
    )
    return plan


def export_orphan_note_blocks(
    orphan_paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    exports_dir: Path = EXPORTS_DIR,
) -> dict[str, Any]:
    plan = build_orphan_note_block_repair_plan(
        orphan_paper_id,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
    )
    if plan["status"] != "ready":
        raise OrphanRepairError(f"Export is blocked with status {plan['status']}.", plan)
    source_path = Path(str(plan["source_path"]))
    export_path = _export_path(Path(exports_dir), "orphan_note_blocks", orphan_paper_id)
    payload = {
        "kind": "orphan_note_blocks",
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "orphan_paper_id": str(orphan_paper_id),
        "source_path": str(source_path),
        "blocks": json.loads(source_path.read_text(encoding="utf-8")),
    }
    atomic_write_json(export_path, payload, indent=2, ensure_ascii=False)
    result = dict(plan)
    result.update(status="exported", message="Orphan note blocks exported without changing library data.", export_path=str(export_path))
    return result


def reattach_orphan_note_blocks(
    orphan_paper_id: str,
    target_paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    plan = build_orphan_note_block_repair_plan(
        orphan_paper_id,
        target_paper_id,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
    )
    if not plan["can_reattach"]:
        raise OrphanRepairError(f"Reattach is blocked with status {plan['status']}.", plan)
    if not confirm:
        raise OrphanRepairError("Orphan note-block reattach requires explicit confirmation.", plan)

    orphan_blocks = list_note_blocks(str(orphan_paper_id), Path(note_blocks_dir))
    target_blocks = list_note_blocks(str(target_paper_id), Path(note_blocks_dir))
    existing_ids = {str(block["id"]) for block in target_blocks}
    reattached_blocks: list[dict[str, Any]] = []
    for block in orphan_blocks:
        updated = dict(block)
        original_block_id = str(updated["id"])
        if original_block_id in existing_ids:
            updated["id"] = str(uuid4())
            updated["reattached_from_block_id"] = original_block_id
        updated["paper_id"] = str(target_paper_id)
        updated["reattached_from_paper_id"] = str(orphan_paper_id)
        existing_ids.add(str(updated["id"]))
        reattached_blocks.append(updated)

    save_note_blocks(str(target_paper_id), [*target_blocks, *reattached_blocks], Path(note_blocks_dir))
    Path(str(plan["source_path"])).unlink()
    result = dict(plan)
    result.update(
        status="reattached_note_blocks",
        message="Orphan note blocks reattached to the selected paper. The original orphan file was removed.",
        reattached_block_count=len(reattached_blocks),
    )
    return result


def delete_orphan_note_blocks(
    orphan_paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    plan = build_orphan_note_block_repair_plan(
        orphan_paper_id,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
    )
    if not plan["can_delete"]:
        raise OrphanRepairError(f"Delete is blocked with status {plan['status']}.", plan)
    if not confirm:
        raise OrphanRepairError("Orphan note-block delete requires explicit confirmation.", plan)
    Path(str(plan["source_path"])).unlink()
    result = dict(plan)
    result.update(status="deleted_note_blocks", message="Orphan note-block file deleted after explicit confirmation.")
    return result


def export_orphan_project_link(
    link_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
    exports_dir: Path = EXPORTS_DIR,
) -> dict[str, Any]:
    plan = build_orphan_project_link_removal_plan(
        link_id,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
    )
    if plan["status"] != "ready":
        raise OrphanProjectLinkRepairError(f"Export is blocked with status {plan['status']}.", plan)
    export_path = _export_path(Path(exports_dir), "orphan_project_link", link_id)
    payload = {
        "kind": "orphan_project_link",
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "link": {key: value for key, value in plan.items() if key not in {"errors", "can_remove"}},
    }
    atomic_write_json(export_path, payload, indent=2, ensure_ascii=False)
    result = dict(plan)
    result.update(status="exported", message="Orphan project link exported without changing library data.", export_path=str(export_path))
    return result


def build_orphan_project_link_reattach_plan(
    link_id: str,
    target_paper_id: str,
    *,
    target_block_id: str = "",
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    removal_plan = build_orphan_project_link_removal_plan(
        link_id,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
    )
    plan = dict(removal_plan)
    plan.update(
        target_paper_id=str(target_paper_id),
        target_block_id=str(target_block_id),
        can_reattach=False,
    )
    if removal_plan["status"] != "ready":
        plan.update(message=f"Reattach is blocked with status {removal_plan['status']}.")
        return plan

    paper_ids, errors = _indexed_paper_ids(index_csv)
    if errors:
        plan.update(status="diagnostic_error", message="Index diagnostics must be clean before link reattach.")
        return plan
    if str(target_paper_id) not in paper_ids:
        plan.update(status="target_missing", message="Target paper_id is not in the index.")
        return plan
    if plan.get("target_type") == "note_block":
        if not target_block_id:
            plan.update(status="target_block_required", message="A target note-block id is required.")
            return plan
        block_ids = {str(block["id"]) for block in list_note_blocks(str(target_paper_id), Path(note_blocks_dir))}
        if str(target_block_id) not in block_ids:
            plan.update(status="target_block_missing", message="Target note-block id was not found.")
            return plan
    plan.update(status="ready", message="Ready to reattach this orphan project link.", can_reattach=True)
    return plan


def reattach_orphan_project_link(
    link_id: str,
    target_paper_id: str,
    *,
    target_block_id: str = "",
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    plan = build_orphan_project_link_reattach_plan(
        link_id,
        target_paper_id,
        target_block_id=target_block_id,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
    )
    if not plan["can_reattach"]:
        raise OrphanProjectLinkRepairError(f"Reattach is blocked with status {plan['status']}.", plan)
    if not confirm:
        raise OrphanProjectLinkRepairError("Orphan project link reattach requires explicit confirmation.", plan)

    links = list_project_links(Path(projects_dir))
    updated_links: list[dict[str, Any]] = []
    found = False
    for link in links:
        if str(link["id"]) != str(link_id):
            updated_links.append(link)
            continue
        found = True
        updated = dict(link)
        updated["paper_id"] = str(target_paper_id)
        if updated["target_type"] == "paper":
            updated["target_id"] = str(target_paper_id)
        elif updated["target_type"] == "note_block":
            updated["target_id"] = str(target_block_id)
        updated_links.append(updated)
    if not found:
        raise OrphanProjectLinkRepairError("Project link was not found during reattach.", plan)
    save_project_links(updated_links, Path(projects_dir))
    result = dict(plan)
    result.update(status="reattached_project_link", message="Orphan project link reattached to the selected paper.")
    return result


def unlink_orphan_project_link(
    link_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
    confirm: bool = False,
) -> dict[str, Any]:
    return remove_orphan_project_link(
        link_id,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
        confirm=confirm,
    )
