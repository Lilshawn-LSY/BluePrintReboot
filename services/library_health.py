from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ingest.doi import normalize_doi
from storage.extracted_text_store import extraction_cache_status
from storage.index_store import INDEX_COLUMNS
from storage.paths import (
    EXTRACTED_TEXT_DIR,
    INDEX_CSV,
    NOTES_DIR,
    NOTE_BLOCKS_DIR,
    PAPERS_DIR,
    PROJECTS_DIR,
)


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


def _load_json_list(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name} could not be read: {exc}")
        return []
    if not isinstance(value, list):
        errors.append(f"{path.name} must contain a JSON list.")
        return []
    return [item for item in value if isinstance(item, dict)]


def _note_block_ids(note_blocks_dir: Path, errors: list[str]) -> dict[str, set[str]]:
    blocks_by_paper: dict[str, set[str]] = {}
    if not note_blocks_dir.exists():
        return blocks_by_paper
    for path in note_blocks_dir.glob("*.json"):
        blocks = _load_json_list(path, errors)
        blocks_by_paper[path.stem] = {str(block.get("id", "")) for block in blocks if block.get("id")}
    return blocks_by_paper


def run_library_health_check(
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
    notes_dir: Path = NOTES_DIR,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
    extracted_text_dir: Path = EXTRACTED_TEXT_DIR,
) -> dict[str, Any]:
    index_csv = Path(index_csv)
    papers_dir = _absolute(papers_dir)
    notes_dir = Path(notes_dir)
    note_blocks_dir = Path(note_blocks_dir)
    projects_dir = Path(projects_dir)
    extracted_text_dir = Path(extracted_text_dir)
    dataframe, errors = _read_index(index_csv)
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
        }
        if not resolved.exists() or not resolved.is_file():
            missing_pdfs.append(item)
        if not _is_within(resolved, papers_dir):
            noncanonical_filepaths.append(item)

    managed_pdfs = _pdf_files(papers_dir)
    unindexed_pdfs = [str(path) for path in managed_pdfs if _path_key(path) not in indexed_paths]

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

    orphan_notes = []
    if notes_dir.exists():
        orphan_notes = [str(path.resolve()) for path in notes_dir.glob("*.md") if path.stem not in paper_ids]
    orphan_note_blocks = []
    if note_blocks_dir.exists():
        orphan_note_blocks = [
            str(path.resolve()) for path in note_blocks_dir.glob("*.json") if path.stem not in paper_ids
        ]

    projects = _load_json_list(projects_dir / "projects.json", errors)
    project_links = _load_json_list(projects_dir / "project_links.json", errors)
    project_ids = {str(project.get("id", "")) for project in projects if project.get("id")}
    blocks_by_paper = _note_block_ids(note_blocks_dir, errors)
    orphan_project_links: list[dict[str, str]] = []
    for link in project_links:
        reasons: list[str] = []
        project_id = str(link.get("project_id", ""))
        paper_id = str(link.get("paper_id", ""))
        target_type = str(link.get("target_type", ""))
        target_id = str(link.get("target_id", ""))
        if project_id not in project_ids:
            reasons.append("project missing")
        if paper_id and paper_id not in paper_ids:
            reasons.append("paper missing")
        if target_type == "paper" and target_id not in paper_ids:
            reasons.append("target paper missing")
        if target_type == "note_block" and target_id not in blocks_by_paper.get(paper_id, set()):
            reasons.append("target note block missing")
        if reasons:
            orphan_project_links.append(
                {
                    "link_id": str(link.get("id", "")),
                    "project_id": project_id,
                    "paper_id": paper_id,
                    "reason": ", ".join(reasons),
                }
            )

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
        "duplicate_dois": duplicate_dois,
        "missing_metadata": missing_metadata,
        "orphan_notes": orphan_notes,
        "orphan_note_blocks": orphan_note_blocks,
        "orphan_project_links": orphan_project_links,
        "stale_extracted_text": stale_extracted_text,
        "noncanonical_filepaths": noncanonical_filepaths,
        "errors": errors,
    }
    issue_count = sum(len(items) for items in issue_sections.values())
    return {
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "healthy": issue_count == 0,
        "summary": {
            "index_rows": len(records),
            "managed_pdfs": len(managed_pdfs),
            "issue_count": issue_count,
        },
        **issue_sections,
    }
