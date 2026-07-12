import json
from pathlib import Path

import pandas as pd

from services.library_read_model import (
    build_health_summary,
    build_library_status,
    build_paper_detail,
    build_paper_list_items,
    build_reader_snapshot,
)
from services.reading_note_template import render_reading_note_template
from tests.helpers import make_workspace


HEALTH_KEYS = {"overall_state", "blocking_issues", "warning_count", "corrupt_critical_state_count", "quarantine_count", "missing_pdf_count", "duplicate_review_count"}
STATUS_KEYS = {"active_count", "archived_count", "missing_count", "duplicate_count", "corrupt_count", "quarantine_count", "degraded", "workspace_warnings"}
LIST_KEYS = {"paper_id", "title", "first_author", "year", "status", "priority", "tags", "archived", "missing_pdf", "health"}


def _fixture(name: str):
    root = make_workspace(name)
    data = root / "data"
    papers = root / "papers"
    notes = root / "notes"
    blocks = data / "note_blocks"
    projects = data / "projects"
    extracted = data / "extracted_text"
    profiles = data / "paper_profiles"
    quarantine = data / "quarantine"
    exports = root / "exports"
    for path in (papers, notes, blocks, projects, extracted, profiles, quarantine, exports):
        path.mkdir(parents=True)
    (projects / "project_links.json").write_text("[]", encoding="utf-8")
    (projects / "projects.json").write_text("[]", encoding="utf-8")
    complete_pdf = papers / "complete.pdf"
    archived_pdf = papers / "archived.pdf"
    complete_pdf.write_bytes(b"complete pdf")
    archived_pdf.write_bytes(b"archived pdf")
    records = [
        {"paper_id": "complete", "filename": complete_pdf.name, "filepath": str(complete_pdf.resolve()), "title": "Complete Paper", "authors": "Alpha Author; Beta Author", "year": "2025", "doi": "10.1/example", "tags": "one, two", "status": "reading", "reading_priority": "high", "is_archived": "false"},
        {"paper_id": "doi-less", "filename": "missing.pdf", "filepath": str((papers / "missing.pdf").resolve()), "title": "DOI-less Paper", "authors": "", "year": "", "doi": "", "tags": "", "status": "unread", "reading_priority": "normal", "is_archived": "false"},
        {"paper_id": "archived", "filename": archived_pdf.name, "filepath": str(archived_pdf.resolve()), "title": "Archived Paper", "authors": "Archive Author", "year": "2020", "doi": "", "tags": "old", "status": "read", "reading_priority": "low", "is_archived": "true", "archived_at": "2026-01-01T00:00:00+00:00"},
    ]
    index = data / "paper_index.csv"
    pd.DataFrame(records).to_csv(index, index=False)
    (notes / "complete.md").write_text(render_reading_note_template(records[0]) + "Saved body\n", encoding="utf-8")
    (extracted / "complete.txt").write_text("cached", encoding="utf-8")
    (profiles / "complete.json").write_text("{}", encoding="utf-8")
    report = {
        "summary": {"issue_count": 2},
        "missing_pdfs": [{"paper_id": "doi-less"}],
        "duplicate_pdf_hashes": [{"indexed_records": [{"paper_id": "complete"}]}],
        "corrupt_json": [],
        "quarantined_caches": [],
        "ignored_duplicates": [],
        "duplicate_filenames": [], "duplicate_dois": [], "missing_metadata": [], "stale_extracted_text": [], "noncanonical_filepaths": [], "errors": [],
    }
    paths = {"index_csv": index, "workspace_root": root, "papers_dir": papers, "notes_dir": notes, "note_blocks_dir": blocks, "projects_dir": projects, "extracted_text_dir": extracted, "profile_dir": profiles, "paper_profiles_dir": profiles, "quarantine_dir": quarantine, "exports_dir": exports, "lifecycle_decisions_json": data / "lifecycle_decisions.json"}
    return root, paths, report


def _file_state(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_health_and_library_status_contracts_are_stable_and_json_serializable() -> None:
    _root, paths, report = _fixture("read-health")
    health = build_health_summary(report)
    status = build_library_status(index_csv=paths["index_csv"], health_report=report)
    assert set(health) == HEALTH_KEYS
    assert set(status) == STATUS_KEYS
    assert health["overall_state"] == "blocked"
    assert status["active_count"] == 2
    assert status["archived_count"] == 1
    json.dumps({"health": health, "status": status})


def test_paper_list_contract_covers_complete_doi_less_archived_and_missing() -> None:
    _root, paths, report = _fixture("read-list")
    items = build_paper_list_items(index_csv=paths["index_csv"], health_report=report)
    assert all(set(item) == LIST_KEYS for item in items)
    by_id = {item["paper_id"]: item for item in items}
    assert by_id["complete"]["first_author"] == "Alpha Author"
    assert by_id["complete"]["tags"] == ["one", "two"]
    assert by_id["doi-less"]["missing_pdf"] is True
    assert by_id["doi-less"]["year"] == ""
    assert by_id["archived"]["archived"] is True
    json.dumps(items)


def test_paper_detail_and_reader_snapshot_use_safe_relative_paths_and_defaults() -> None:
    root, paths, report = _fixture("read-detail")
    detail_kwargs = {key: paths[key] for key in ("workspace_root", "papers_dir", "notes_dir", "extracted_text_dir", "profile_dir", "projects_dir")}
    detail = build_paper_detail("complete", index_csv=paths["index_csv"], health_report=report, **detail_kwargs)
    missing = build_paper_detail("doi-less", index_csv=paths["index_csv"], health_report=report, **detail_kwargs)
    reader = build_reader_snapshot("complete", index_csv=paths["index_csv"], notes_dir=paths["notes_dir"], health_report=report, **{key: value for key, value in detail_kwargs.items() if key != "notes_dir"})
    absent_reader = build_reader_snapshot("doi-less", index_csv=paths["index_csv"], notes_dir=paths["notes_dir"], health_report=report, **{key: value for key, value in detail_kwargs.items() if key != "notes_dir"})
    assert detail and detail["relative_pdf_path"] == "papers/complete.pdf"
    assert detail["note_available"] is True
    assert detail["extracted_text_available"] is True
    assert detail["profile_available"] is True
    assert missing and missing["doi"] == "" and missing["note_available"] is False
    assert missing["extracted_text_available"] is False and missing["profile_available"] is False
    assert reader and reader["pdf_state"] == "available" and "Saved body" in reader["saved_note_content"]
    assert absent_reader and absent_reader["saved_note_available"] is False and absent_reader["unavailable_reason"]
    encoded = json.dumps({"detail": detail, "reader": reader, "missing": missing, "absent_reader": absent_reader})
    assert str(root.resolve()) not in encoded


def test_corrupt_degraded_contract_and_read_construction_do_not_mutate_files() -> None:
    root, paths, report = _fixture("read-no-write")
    report["corrupt_json"] = [{"storage_class": "critical user state"}, {"storage_class": "rebuildable cache"}]
    report["quarantined_caches"] = [{}]
    before = _file_state(root)
    health = build_health_summary(report)
    build_library_status(index_csv=paths["index_csv"], health_report=report)
    build_paper_list_items(index_csv=paths["index_csv"], health_report=report)
    build_paper_detail("complete", index_csv=paths["index_csv"], health_report=report, **{key: paths[key] for key in ("workspace_root", "papers_dir", "notes_dir", "extracted_text_dir", "profile_dir", "projects_dir")})
    build_reader_snapshot("complete", index_csv=paths["index_csv"], notes_dir=paths["notes_dir"], health_report=report, **{key: paths[key] for key in ("workspace_root", "papers_dir", "extracted_text_dir", "profile_dir", "projects_dir")})
    assert health["corrupt_critical_state_count"] == 1
    assert health["quarantine_count"] == 1
    assert _file_state(root) == before
