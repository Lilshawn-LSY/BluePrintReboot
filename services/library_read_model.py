from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, TypedDict

from services.library_health import run_library_health_check
from services.reading_note_template import reading_note_header_values
from storage.extracted_text_store import extracted_text_path
from storage.index_store import read_index_snapshot
from storage.paper_profile_store import paper_profile_path
from storage.paths import (
    EXTRACTED_TEXT_DIR,
    INDEX_CSV,
    NOTES_DIR,
    NOTE_BLOCKS_DIR,
    PAPERS_DIR,
    PAPER_PROFILES_DIR,
    PROJECTS_DIR,
    PROJECT_ROOT,
)
from storage.project_link_store import list_project_links


class HealthSummary(TypedDict):
    overall_state: str
    blocking_issues: int
    warning_count: int
    corrupt_critical_state_count: int
    quarantine_count: int
    missing_pdf_count: int
    duplicate_review_count: int


class LibraryStatus(TypedDict):
    active_count: int
    archived_count: int
    missing_count: int
    duplicate_count: int
    corrupt_count: int
    quarantine_count: int
    degraded: bool
    workspace_warnings: list[str]


class PaperListItem(TypedDict):
    paper_id: str
    title: str
    first_author: str
    year: str
    status: str
    priority: str
    tags: list[str]
    archived: bool
    missing_pdf: bool
    health: list[str]


class PaperDetail(PaperListItem):
    filename: str
    relative_pdf_path: str
    doi: str
    project_links: list[dict[str, str]]
    note_available: bool
    extracted_text_available: bool
    profile_available: bool
    lifecycle_state: str
    recoverable_warnings: list[str]


class ReaderSnapshot(TypedDict):
    paper: PaperDetail
    pdf_state: str
    saved_note_available: bool
    saved_note_content: str
    canonical_note_header: dict[str, str]
    saved_note_baseline: dict[str, Any]
    warnings: list[str]
    unavailable_reason: str


def _archived(record: Mapping[str, Any]) -> bool:
    return str(record.get("is_archived", "false")).lower() == "true"


def _first_author(record: Mapping[str, Any]) -> str:
    authors = str(record.get("authors", "") or "").strip()
    return authors.split(";")[0].split(",")[0].strip() if authors else ""


def _tags(value: object) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _safe_pdf(record: Mapping[str, Any], root: Path, papers_dir: Path) -> tuple[Path | None, str]:
    raw = str(record.get("filepath", "") or "").strip()
    candidate = Path(raw) if raw else papers_dir / str(record.get("filename", "") or "")
    if not candidate.is_absolute():
        candidate = root / candidate if candidate.parts and candidate.parts[0].lower() == "papers" else papers_dir / candidate
    resolved = candidate.resolve(strict=False)
    try:
        relative = resolved.relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return None, ""
    return resolved, relative


def _corrupt_records(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [item for item in report.get("corrupt_json", []) if isinstance(item, Mapping)]


def build_health_summary(report: Mapping[str, Any] | None = None, **health_kwargs: Any) -> HealthSummary:
    source = dict(report) if report is not None else run_library_health_check(**health_kwargs)
    corrupt = _corrupt_records(source)
    critical = sum(item.get("storage_class") == "critical user state" for item in corrupt)
    missing = len(source.get("missing_pdfs", []))
    duplicates = len(source.get("duplicate_pdf_hashes", []))
    quarantine = len(source.get("quarantined_caches", []))
    warnings = sum(
        len(source.get(key, []))
        for key in ("duplicate_filenames", "duplicate_dois", "missing_metadata", "stale_extracted_text", "noncanonical_filepaths", "errors")
    )
    blocking = critical + missing
    has_issues = bool(source.get("healthy") is False or source.get("summary", {}).get("issue_count", 0) or corrupt or missing or duplicates or quarantine or warnings)
    return {
        "overall_state": "healthy" if not has_issues else ("blocked" if blocking else "degraded"),
        "blocking_issues": blocking,
        "warning_count": warnings,
        "corrupt_critical_state_count": critical,
        "quarantine_count": quarantine,
        "missing_pdf_count": missing,
        "duplicate_review_count": duplicates,
    }


def build_library_status(
    *,
    index_csv: Path = INDEX_CSV,
    health_report: Mapping[str, Any] | None = None,
    **health_kwargs: Any,
) -> LibraryStatus:
    dataframe = read_index_snapshot(index_csv)
    records = dataframe.to_dict("records")
    report = dict(health_report) if health_report is not None else run_library_health_check(index_csv=index_csv, **health_kwargs)
    health = build_health_summary(report)
    archived_count = sum(_archived(record) for record in records)
    workspace_warnings: list[str] = []
    if health["missing_pdf_count"]:
        workspace_warnings.append("Some indexed PDFs are missing.")
    if health["corrupt_critical_state_count"]:
        workspace_warnings.append("Critical app-owned state requires manual recovery.")
    if health["duplicate_review_count"]:
        workspace_warnings.append("Duplicate PDF candidates require review.")
    return {
        "active_count": len(records) - archived_count,
        "archived_count": archived_count,
        "missing_count": health["missing_pdf_count"],
        "duplicate_count": health["duplicate_review_count"],
        "corrupt_count": len(_corrupt_records(report)),
        "quarantine_count": health["quarantine_count"],
        "degraded": health["overall_state"] != "healthy",
        "workspace_warnings": workspace_warnings,
    }


def _paper_health(paper_id: str, report: Mapping[str, Any]) -> tuple[bool, list[str]]:
    missing = any(str(item.get("paper_id", "")) == paper_id for item in report.get("missing_pdfs", []) if isinstance(item, Mapping))
    duplicate = any(
        any(str(record.get("paper_id", "")) == paper_id for record in group.get("indexed_records", []) if isinstance(record, Mapping))
        for group in report.get("duplicate_pdf_hashes", [])
        if isinstance(group, Mapping)
    )
    health: list[str] = []
    if missing:
        health.append("missing_pdf")
    if duplicate:
        health.append("duplicate_candidate")
    return missing, health


def build_paper_list_items(
    *,
    index_csv: Path = INDEX_CSV,
    health_report: Mapping[str, Any] | None = None,
    **health_kwargs: Any,
) -> list[PaperListItem]:
    report = dict(health_report) if health_report is not None else run_library_health_check(index_csv=index_csv, **health_kwargs)
    items: list[PaperListItem] = []
    for record in read_index_snapshot(index_csv).to_dict("records"):
        paper_id = str(record.get("paper_id", ""))
        missing, health = _paper_health(paper_id, report)
        items.append({
            "paper_id": paper_id,
            "title": str(record.get("title", "") or record.get("filename", "") or ""),
            "first_author": _first_author(record),
            "year": str(record.get("year", "") or ""),
            "status": str(record.get("status", "unread") or "unread"),
            "priority": str(record.get("reading_priority", "normal") or "normal"),
            "tags": _tags(record.get("tags", "")),
            "archived": _archived(record),
            "missing_pdf": missing,
            "health": health,
        })
    return sorted(items, key=lambda item: (item["title"].casefold(), item["paper_id"]))


def build_paper_detail(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    workspace_root: Path = PROJECT_ROOT,
    papers_dir: Path = PAPERS_DIR,
    notes_dir: Path = NOTES_DIR,
    extracted_text_dir: Path = EXTRACTED_TEXT_DIR,
    profile_dir: Path = PAPER_PROFILES_DIR,
    projects_dir: Path = PROJECTS_DIR,
    health_report: Mapping[str, Any] | None = None,
    **health_kwargs: Any,
) -> PaperDetail | None:
    dataframe = read_index_snapshot(index_csv)
    matches = dataframe[dataframe["paper_id"] == paper_id]
    if matches.empty:
        return None
    record = matches.iloc[0].to_dict()
    report = dict(health_report) if health_report is not None else run_library_health_check(index_csv=index_csv, papers_dir=papers_dir, notes_dir=notes_dir, projects_dir=projects_dir, extracted_text_dir=extracted_text_dir, **health_kwargs)
    missing, health = _paper_health(paper_id, report)
    pdf_path, relative_pdf_path = _safe_pdf(record, Path(workspace_root), Path(papers_dir))
    note_path = Path(notes_dir) / f"{paper_id}.md"
    try:
        links = list_project_links(Path(projects_dir))
    except Exception:
        links = []
        health = [*health, "project_links_unavailable"]
    public_links = [
        {"project_id": str(link.get("project_id", "")), "link_type": str(link.get("link_type", "")), "target_type": str(link.get("target_type", ""))}
        for link in links
        if str(link.get("paper_id", "")) == paper_id
    ]
    base: PaperListItem = {
        "paper_id": paper_id,
        "title": str(record.get("title", "") or record.get("filename", "") or ""),
        "first_author": _first_author(record),
        "year": str(record.get("year", "") or ""),
        "status": str(record.get("status", "unread") or "unread"),
        "priority": str(record.get("reading_priority", "normal") or "normal"),
        "tags": _tags(record.get("tags", "")),
        "archived": _archived(record),
        "missing_pdf": missing or pdf_path is None or not pdf_path.is_file(),
        "health": health,
    }
    return {
        **base,
        "filename": str(record.get("filename", "") or ""),
        "relative_pdf_path": relative_pdf_path,
        "doi": str(record.get("doi", "") or ""),
        "project_links": public_links,
        "note_available": note_path.is_file(),
        "extracted_text_available": extracted_text_path(paper_id, Path(extracted_text_dir)).is_file(),
        "profile_available": paper_profile_path(paper_id, Path(profile_dir)).is_file(),
        "lifecycle_state": "archived" if _archived(record) else "active",
        "recoverable_warnings": list(health),
    }


def build_reader_snapshot(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    notes_dir: Path = NOTES_DIR,
    **detail_kwargs: Any,
) -> ReaderSnapshot | None:
    detail = build_paper_detail(paper_id, index_csv=index_csv, notes_dir=notes_dir, **detail_kwargs)
    if detail is None:
        return None
    dataframe = read_index_snapshot(index_csv)
    record = dataframe[dataframe["paper_id"] == paper_id].iloc[0].to_dict()
    note_path = Path(notes_dir) / f"{paper_id}.md"
    note_read_warning = ""
    if note_path.is_file():
        try:
            saved_note = note_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            saved_note = ""
            note_read_warning = "saved_note_unavailable"
    else:
        saved_note = ""
    baseline = {
        "sha256": hashlib.sha256(saved_note.encode("utf-8")).hexdigest() if saved_note else "",
        "size_bytes": len(saved_note.encode("utf-8")),
    }
    warnings = list(detail["recoverable_warnings"])
    if note_read_warning:
        warnings.append(note_read_warning)
    unavailable_reason = "PDF file is missing." if detail["missing_pdf"] else ""
    return {
        "paper": detail,
        "pdf_state": "missing" if detail["missing_pdf"] else "available",
        "saved_note_available": bool(saved_note),
        "saved_note_content": saved_note,
        "canonical_note_header": reading_note_header_values(record),
        "saved_note_baseline": baseline,
        "warnings": warnings,
        "unavailable_reason": unavailable_reason,
    }


def paper_lifecycle_summary(record: Mapping[str, Any], *, pdf_exists: bool) -> dict[str, Any]:
    archived = _archived(record)
    return {"paper_id": str(record.get("paper_id", "")), "lifecycle_state": "archived" if archived else "active", "is_archived": archived, "archived_at": str(record.get("archived_at", "")), "pdf_state": "available" if pdf_exists else "missing", "readable": bool(pdf_exists)}


def library_health_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = build_health_summary(report)
    return {"duplicate_candidate_count": summary["duplicate_review_count"], "ignored_duplicate_count": len(report.get("ignored_duplicates", [])), "corrupt_critical_state_count": summary["corrupt_critical_state_count"], "corrupt_rebuildable_cache_count": sum(item.get("storage_class") == "rebuildable cache" for item in _corrupt_records(report)), "quarantined_cache_count": summary["quarantine_count"], "library_state": "healthy" if summary["overall_state"] == "healthy" else "degraded but readable"}
