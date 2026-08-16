from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import dependencies
from api.main import INVALID_REQUEST_DETAIL, create_app
from services.library_read_model import (
    build_paper_detail,
    build_paper_list_items,
    build_reader_snapshot,
)
from services.paper_metadata_mutation import paper_tags_revision
from services.reader_commands import (
    ReaderCommandConflict,
    ReaderCommandNotFound,
    ReaderCommandService,
    ReaderCommandUnavailable,
)
from services.reading_note_template import render_reading_note_template
from storage.index_store import INDEX_COLUMNS, read_index_snapshot, save_index


def _workspace(tmp_path: Path) -> tuple[ReaderCommandService, Path, Path, dict[str, str]]:
    index_csv = tmp_path / "data" / "paper_index.csv"
    notes_dir = tmp_path / "notes"
    papers_dir = tmp_path / "papers"
    projects_dir = tmp_path / "projects"
    notes_dir.mkdir(parents=True)
    papers_dir.mkdir()
    projects_dir.mkdir()
    pdf_path = papers_dir / "paper-1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    record = {column: "" for column in INDEX_COLUMNS}
    record.update(
        {
            "paper_id": "paper-1",
            "filename": pdf_path.name,
            "filepath": str(pdf_path.resolve()),
            "title": "Tag command paper",
            "authors": "Author One; Author Two",
            "year": "2026",
            "tags": "Legacy Label, unrelated_legacy",
            "status": "reading",
            "reading_priority": "normal",
            "is_archived": "false",
            "note_path": str((notes_dir / "paper-1.md").resolve()),
        }
    )
    save_index(pd.DataFrame([record]), index_csv)
    note = render_reading_note_template(record).replace(
        "## Raw Notes\n",
        "## Raw Notes\n\nExact tag-command body  \nSecond body line\n",
    )
    (notes_dir / "paper-1.md").write_text(note, encoding="utf-8", newline="")
    return ReaderCommandService(index_csv=index_csv, notes_dir=notes_dir), index_csv, notes_dir, record


def _record(index_csv: Path) -> dict[str, str]:
    row = read_index_snapshot(index_csv)
    return {
        str(key): str(value)
        for key, value in row[row["paper_id"] == "paper-1"].iloc[0].fillna("").to_dict().items()
    }


def _client(service: ReaderCommandService) -> TestClient:
    app = create_app()
    app.dependency_overrides[dependencies.get_reader_command_service] = lambda: service
    return TestClient(app)


def test_paper_tag_commands_normalize_one_value_preserve_legacy_tags_and_share_reads(tmp_path: Path) -> None:
    service, index_csv, notes_dir, record = _workspace(tmp_path)
    note_path = notes_dir / "paper-1.md"
    body_before = note_path.read_text(encoding="utf-8").split("## One-line Summary", 1)[1]

    added = service.add_paper_tag("paper-1", " New Tag! ", paper_tags_revision(record))

    assert added.status == "saved"
    assert added.tags == ("Legacy Label", "unrelated_legacy", "new-tag")
    assert _record(index_csv)["tags"] == "Legacy Label, unrelated_legacy, new-tag"
    assert "tags: Legacy Label, unrelated_legacy, new-tag" in added.reading_note.content
    assert added.reading_note.content.split("## One-line Summary", 1)[1] == body_before

    persisted_before_duplicate = (index_csv.read_bytes(), note_path.read_bytes())
    duplicate = service.add_paper_tag("paper-1", "new tag", added.tags_revision)
    assert duplicate.status == "no_op"
    assert duplicate.tags == added.tags
    assert (index_csv.read_bytes(), note_path.read_bytes()) == persisted_before_duplicate

    removed = service.remove_paper_tag("paper-1", "unrelated legacy", duplicate.tags_revision)
    assert removed.status == "saved"
    assert removed.tags == ("Legacy Label", "new-tag")
    assert _record(index_csv)["tags"] == "Legacy Label, new-tag"

    persisted_before_absent_remove = (index_csv.read_bytes(), note_path.read_bytes())
    absent = service.remove_paper_tag("paper-1", "not stored", removed.tags_revision)
    assert absent.status == "no_op"
    assert absent.tags == removed.tags
    assert (index_csv.read_bytes(), note_path.read_bytes()) == persisted_before_absent_remove

    health_report = {"missing_pdfs": [], "duplicate_pdf_hashes": []}
    paper_list = build_paper_list_items(index_csv=index_csv, health_report=health_report)
    detail = build_paper_detail(
        "paper-1",
        index_csv=index_csv,
        workspace_root=tmp_path,
        papers_dir=tmp_path / "papers",
        notes_dir=notes_dir,
        projects_dir=tmp_path / "projects",
        health_report=health_report,
    )
    reader = build_reader_snapshot(
        "paper-1",
        index_csv=index_csv,
        notes_dir=notes_dir,
        workspace_root=tmp_path,
        papers_dir=tmp_path / "papers",
        projects_dir=tmp_path / "projects",
        health_report=health_report,
    )
    assert paper_list[0]["tags"] == ["Legacy Label", "new-tag"]
    assert detail and detail["tags"] == ["Legacy Label", "new-tag"]
    assert reader and reader["paper"]["tags"] == ["Legacy Label", "new-tag"]
    assert reader and reader["canonical_note_header"]["tags"] == "Legacy Label, new-tag"


def test_paper_tag_command_conflict_does_not_lose_newer_update(tmp_path: Path) -> None:
    service, index_csv, notes_dir, record = _workspace(tmp_path)
    stale_revision = paper_tags_revision(record)
    first = service.add_paper_tag("paper-1", "current", stale_revision)
    before = (index_csv.read_bytes(), (notes_dir / "paper-1.md").read_bytes())

    with pytest.raises(ReaderCommandConflict):
        service.remove_paper_tag("paper-1", "Legacy Label", stale_revision)

    assert first.tags == ("Legacy Label", "unrelated_legacy", "current")
    assert (index_csv.read_bytes(), (notes_dir / "paper-1.md").read_bytes()) == before


def test_paper_tag_header_sync_failure_rolls_back_index_and_note(tmp_path: Path, monkeypatch) -> None:
    service, index_csv, notes_dir, record = _workspace(tmp_path)
    note_path = notes_dir / "paper-1.md"
    before = (index_csv.read_bytes(), note_path.read_bytes())

    def corrupt_then_fail(*_args, **_kwargs):
        note_path.write_text("partial tag synchronization", encoding="utf-8")
        raise OSError("private storage failure")

    monkeypatch.setattr("services.paper_metadata_mutation.refresh_note_header", corrupt_then_fail)

    with pytest.raises(ReaderCommandUnavailable):
        service.add_paper_tag("paper-1", "will rollback", paper_tags_revision(record))

    assert (index_csv.read_bytes(), note_path.read_bytes()) == before


def test_paper_tag_index_failure_does_not_touch_the_reading_note(tmp_path: Path, monkeypatch) -> None:
    service, index_csv, notes_dir, record = _workspace(tmp_path)
    note_path = notes_dir / "paper-1.md"
    before = (index_csv.read_bytes(), note_path.read_bytes())
    monkeypatch.setattr(
        "services.paper_metadata_mutation.save_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("private index failure")),
    )

    with pytest.raises(ReaderCommandUnavailable):
        service.add_paper_tag("paper-1", "will not persist", paper_tags_revision(record))

    assert (index_csv.read_bytes(), note_path.read_bytes()) == before


def test_paper_tag_api_is_bounded_and_returns_controlled_states(tmp_path: Path) -> None:
    service, index_csv, notes_dir, record = _workspace(tmp_path)
    client = _client(service)
    response = client.post(
        "/papers/paper-1/tags",
        json={"tag": "API Tag", "expected_revision": paper_tags_revision(record)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["tags"] == ["Legacy Label", "unrelated_legacy", "api-tag"]
    assert set(body) == {
        "status",
        "tags",
        "tags_revision",
        "note_header_status",
        "canonical_note_header",
        "canonical_note_header_text",
        "reading_note",
    }
    before = (index_csv.read_bytes(), (notes_dir / "paper-1.md").read_bytes())
    stale = client.request(
        "DELETE",
        "/papers/paper-1/tags",
        json={"tag": "Legacy Label", "expected_revision": paper_tags_revision(record)},
    )
    assert stale.status_code == 409
    assert "Legacy Label" not in stale.text
    assert (index_csv.read_bytes(), (notes_dir / "paper-1.md").read_bytes()) == before

    invalid = client.post(
        "/papers/paper-1/tags",
        json={"tag": "   ", "expected_revision": "a" * 64},
    )
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": INVALID_REQUEST_DETAIL}

    missing = client.post(
        "/papers/missing/tags",
        json={"tag": "tag", "expected_revision": "a" * 64},
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Paper not found."}
    with pytest.raises(ReaderCommandNotFound):
        service.add_paper_tag("missing", "tag", "a" * 64)
