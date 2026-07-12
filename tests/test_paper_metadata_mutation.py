from pathlib import Path

import pandas as pd

from services.paper_metadata_mutation import apply_paper_metadata_change
from services.reader_state_keys import (
    note_baseline_key,
    note_draft_key,
    pending_note_header_refresh_key,
    pending_note_save_result_key,
)
from services.reading_note_template import render_reading_note_template
from storage.index_store import load_index
from ui_streamlit.reader_workspace import apply_pending_note_actions, save_note_draft
from tests.helpers import make_workspace


def _workspace(name: str):
    root = make_workspace(name)
    index = root / "data" / "paper_index.csv"
    notes = root / "notes"
    papers = root / "papers"
    index.parent.mkdir(); notes.mkdir(); papers.mkdir()
    records = []
    for paper_id in ("paper-a", "paper-b"):
        pdf = papers / f"{paper_id}.pdf"
        pdf.write_bytes(b"pdf")
        record = {
            "paper_id": paper_id,
            "filename": pdf.name,
            "filepath": str(pdf.resolve()),
            "title": f"Title {paper_id}",
            "authors": "Author One; Author Two",
            "year": "2025",
            "doi": "",
            "tags": "existing",
            "status": "unread",
            "reading_priority": "normal",
            "note_path": str((notes / f"{paper_id}.md").resolve()),
        }
        records.append(record)
        (notes / f"{paper_id}.md").write_text(
            render_reading_note_template(record).replace("## Raw Notes\n", "## Raw Notes\n\nBody sentinel\n"),
            encoding="utf-8",
        )
    pd.DataFrame(records).to_csv(index, index=False)
    return root, index, notes


def _record(index: Path, paper_id: str) -> dict[str, str]:
    row = load_index(index)
    return {str(key): str(value) for key, value in row[row["paper_id"] == paper_id].iloc[0].to_dict().items()}


def test_manual_tag_updates_index_and_clean_note_without_changing_body() -> None:
    _root, index, notes = _workspace("metadata-manual-clean")
    note = notes / "paper-a.md"
    before_body = note.read_text(encoding="utf-8").split("## One-line Summary", 1)[1]

    result = apply_paper_metadata_change("paper-a", {"tags": "existing, manual"}, index_csv=index, notes_dir=notes)

    assert result.status == "applied"
    assert _record(index, "paper-a")["tags"] == "existing, manual"
    updated = note.read_text(encoding="utf-8")
    assert "tags: existing, manual" in updated
    assert updated.split("## One-line Summary", 1)[1] == before_body


def test_selected_suggested_tag_uses_same_clean_sync_contract() -> None:
    _root, index, notes = _workspace("metadata-suggested-clean")
    result = apply_paper_metadata_change("paper-a", {"tags": "existing, suggested"}, index_csv=index, notes_dir=notes)
    assert result.note_sync == "synced"
    assert "tags: existing, suggested" in (notes / "paper-a.md").read_text(encoding="utf-8")


def test_dirty_manual_tag_queues_header_and_never_writes_unsaved_body() -> None:
    _root, index, notes = _workspace("metadata-manual-dirty")
    note = notes / "paper-a.md"
    disk = note.read_text(encoding="utf-8")
    dirty = disk.replace("Body sentinel", "Unsaved private draft body")
    state = {note_draft_key("paper-a"): dirty, note_baseline_key("paper-a"): disk}

    result = apply_paper_metadata_change("paper-a", {"tags": "existing, manual"}, session_state=state, index_csv=index, notes_dir=notes)

    assert result.note_sync == "queued_dirty_draft"
    assert result.draft_dirty is True
    assert note.read_text(encoding="utf-8") == disk
    assert state[note_draft_key("paper-a")] == dirty
    pending = state[pending_note_header_refresh_key("paper-a")]
    assert "tags: existing, manual" in pending["text"]
    assert "Unsaved private draft body" in pending["text"]


def test_dirty_suggested_tag_preserves_paper_isolation() -> None:
    _root, index, notes = _workspace("metadata-isolation")
    disk_a = (notes / "paper-a.md").read_text(encoding="utf-8")
    disk_b = (notes / "paper-b.md").read_text(encoding="utf-8")
    state = {
        note_draft_key("paper-a"): disk_a.replace("Body sentinel", "Draft A"),
        note_baseline_key("paper-a"): disk_a,
        note_draft_key("paper-b"): disk_b.replace("Body sentinel", "Draft B"),
        note_baseline_key("paper-b"): disk_b,
        pending_note_header_refresh_key("paper-b"): {"text": "keep-b"},
    }
    before_b = dict(state)

    apply_paper_metadata_change("paper-a", {"tags": "existing, suggested"}, session_state=state, index_csv=index, notes_dir=notes)

    assert state[note_draft_key("paper-b")] == before_b[note_draft_key("paper-b")]
    assert state[note_baseline_key("paper-b")] == before_b[note_baseline_key("paper-b")]
    assert state[pending_note_header_refresh_key("paper-b")] == {"text": "keep-b"}
    assert (notes / "paper-b.md").read_text(encoding="utf-8") == disk_b
    assert _record(index, "paper-b")["tags"] == "existing"


def test_save_after_dirty_metadata_refresh_converges_header_and_latest_body() -> None:
    _root, index, notes = _workspace("metadata-save-after-dirty")
    record = _record(index, "paper-a")
    disk = (notes / "paper-a.md").read_text(encoding="utf-8")
    state = {note_draft_key("paper-a"): disk.replace("Body sentinel", "Latest unsaved body"), note_baseline_key("paper-a"): disk}
    result = apply_paper_metadata_change("paper-a", {"tags": "existing, latest"}, session_state=state, index_csv=index, notes_dir=notes)
    updated_record = result.updated_record

    save_note_draft(updated_record, state, notes_dir=notes)

    saved = (notes / "paper-a.md").read_text(encoding="utf-8")
    assert "tags: existing, latest" in saved
    assert "Latest unsaved body" in saved
    assert state[note_draft_key("paper-a")] != state[note_baseline_key("paper-a")]
    assert pending_note_save_result_key("paper-a") in state

    apply_pending_note_actions(updated_record, state, notes_dir=notes)

    assert state[note_draft_key("paper-a")] == state[note_baseline_key("paper-a")]
    assert "tags: existing, latest" in state[note_draft_key("paper-a")]
    assert "Latest unsaved body" in state[note_draft_key("paper-a")]
    assert pending_note_header_refresh_key("paper-a") not in state
    assert pending_note_save_result_key("paper-a") not in state


def test_normalized_duplicate_tag_is_structured_no_op(monkeypatch) -> None:
    _root, index, notes = _workspace("metadata-tag-noop")
    monkeypatch.setattr("services.paper_metadata_mutation.save_index", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no write expected")))
    result = apply_paper_metadata_change("paper-a", {"tags": " existing, existing "}, index_csv=index, notes_dir=notes)
    assert result.status == "no_op"
    assert result.changed_fields == ()


def test_unchanged_doi_does_not_rewrite_provenance(monkeypatch) -> None:
    _root, index, notes = _workspace("metadata-doi-noop")
    from services.paper_metadata_mutation import save_index as real_save
    dataframe = load_index(index)
    dataframe.loc[dataframe["paper_id"] == "paper-a", "doi"] = "10.1000/example"
    dataframe.loc[dataframe["paper_id"] == "paper-a", "doi_source"] = "crossref"
    real_save(dataframe, index)
    result = apply_paper_metadata_change("paper-a", {"doi": "https://doi.org/10.1000/EXAMPLE"}, index_csv=index, notes_dir=notes)
    assert result.status == "no_op"
    assert _record(index, "paper-a")["doi_source"] == "crossref"


def test_index_failure_does_not_report_note_success(monkeypatch) -> None:
    _root, index, notes = _workspace("metadata-index-failure")
    before = (notes / "paper-a.md").read_bytes()
    monkeypatch.setattr("services.paper_metadata_mutation.save_index", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("index failed")))
    result = apply_paper_metadata_change("paper-a", {"tags": "changed"}, index_csv=index, notes_dir=notes)
    assert result.status == "index_write_failed"
    assert result.index_updated is False
    assert result.note_sync == "not_required"
    assert (notes / "paper-a.md").read_bytes() == before


def test_note_failure_reports_partial_success(monkeypatch) -> None:
    _root, index, notes = _workspace("metadata-note-failure")
    monkeypatch.setattr("services.paper_metadata_mutation.refresh_note_header", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("note failed")))
    result = apply_paper_metadata_change("paper-a", {"tags": "changed"}, index_csv=index, notes_dir=notes)
    assert result.status == "partial_failure"
    assert result.index_updated is True
    assert result.note_sync == "failed"
    assert _record(index, "paper-a")["tags"] == "changed"


def test_streamlit_metadata_flows_use_shared_service_boundary() -> None:
    app_source = Path("ui_streamlit/app.py").read_text(encoding="utf-8")
    reader_source = Path("ui_streamlit/reader_workspace.py").read_text(encoding="utf-8")
    assert "apply_paper_metadata_change" in app_source
    assert "apply_paper_metadata_change" in reader_source
    for direct_call in ("update_paper_metadata(", "accept_crossref_metadata(", "apply_metadata_candidate_to_index("):
        assert direct_call not in app_source
        assert direct_call not in reader_source
