from ui_streamlit.reader_workspace import (
    NATIVE_STREAMLIT_RENDERER,
    STABLE_HTML_RENDERER,
    add_manual_tag,
    apply_pending_note_actions,
    append_markdown_snapshot,
    citation_block,
    initial_pdf_render_status,
    insert_note_block,
    load_note_draft,
    mark_pdf_render_fallback,
    mark_pdf_render_native_attempt,
    native_pdf_support_status,
    note_draft_key,
    pending_note_block_append_key,
    pending_note_reload_key,
    pdf_embed_html,
    pdf_path_status,
    save_note_draft,
)
from storage.note_store import save_note_text
from tests.helpers import make_workspace


def test_load_note_draft_uses_default_template_when_missing() -> None:
    notes_dir = make_workspace("reader-note-template")
    record = {
        "paper_id": "paper-1",
        "title": "Reader Paper",
        "authors": "Curie Marie",
        "year": "1911",
        "journal": "Local Journal",
        "doi": "10.1000/test",
        "tags": "physics",
        "filename": "reader.pdf",
        "status": "reading",
    }
    session_state = {}

    draft = load_note_draft(record, session_state, notes_dir=notes_dir)

    assert "# Reader Paper" in draft
    assert "## Key Claims" in draft
    assert session_state[note_draft_key(record)] == draft


def test_save_note_draft_writes_current_session_text() -> None:
    notes_dir = make_workspace("reader-note-save")
    record = {"paper_id": "paper-1", "title": "Reader Paper"}
    session_state = {note_draft_key(record): "draft text"}

    note_path = save_note_draft(record, session_state, notes_dir=notes_dir)

    assert note_path.read_text(encoding="utf-8") == "draft text"
    assert session_state[f"reader_note_saved_at_{record['paper_id']}"]


def test_add_manual_tag_normalizes_and_avoids_duplicates() -> None:
    assert add_manual_tag("existing-tag, root-development", " Root   Development ") == (
        "existing-tag, root-development"
    )
    assert add_manual_tag("existing-tag", " New   Tag ") == "existing-tag, new-tag"
    assert add_manual_tag("existing-tag", "   ") == "existing-tag"


def test_insert_note_block_appends_without_erasing_existing_text() -> None:
    updated = insert_note_block("Existing note", "key_claim")

    assert updated.startswith("Existing note")
    assert "## Key Claim" in updated
    assert "- Claim:" in updated


def test_append_markdown_snapshot_preserves_existing_draft() -> None:
    updated = append_markdown_snapshot("Existing freeform note\n", "### Evidence: Result\n\nBlock text\n")

    assert updated == "Existing freeform note\n\n### Evidence: Result\n\nBlock text\n"


def test_apply_pending_note_append_updates_draft_and_clears_pending_key() -> None:
    notes_dir = make_workspace("reader-pending-append")
    record = {"paper_id": "paper-1", "title": "Reader Paper"}
    pending_key = pending_note_block_append_key(record)
    session_state = {
        note_draft_key(record): "Existing draft",
        pending_key: "### Evidence: Result\n\nBlock text\n",
    }

    draft = apply_pending_note_actions(record, session_state, notes_dir=notes_dir)

    assert draft == "Existing draft\n\n### Evidence: Result\n\nBlock text\n"
    assert session_state[note_draft_key(record)] == draft
    assert pending_key not in session_state


def test_apply_pending_reload_happens_before_pending_append() -> None:
    notes_dir = make_workspace("reader-pending-reload")
    record = {"paper_id": "paper-1", "title": "Reader Paper"}
    save_note_text(record, "Saved note", notes_dir=notes_dir)
    reload_key = pending_note_reload_key(record)
    append_key = pending_note_block_append_key(record)
    session_state = {
        note_draft_key(record): "Unsaved draft",
        reload_key: True,
        append_key: "### Claim: Snapshot\n",
    }

    draft = apply_pending_note_actions(record, session_state, notes_dir=notes_dir)

    assert draft == "Saved note\n\n### Claim: Snapshot\n"
    assert reload_key not in session_state
    assert append_key not in session_state


def test_citation_block_uses_available_metadata() -> None:
    block = citation_block(
        {
            "title": "A Paper",
            "authors": "Curie Marie; Einstein Albert",
            "year": "1911",
            "journal": "Science",
            "doi": "10.1000/example",
        }
    )

    assert "Curie Marie (1911). A Paper." in block
    assert "Science." in block
    assert "DOI: 10.1000/example." in block


def test_pdf_path_status_reports_missing_pdf() -> None:
    status = pdf_path_status({"filepath": "does-not-exist.pdf"})

    assert status["exists"] is False
    assert status["size_mb"] == 0.0
    assert "PDF file not found" in status["message"]


def test_pdf_path_status_includes_file_size_when_pdf_exists() -> None:
    workspace = make_workspace("reader-pdf-status")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ncontent")

    status = pdf_path_status({"filepath": str(pdf_path)})

    assert status["exists"] is True
    assert status["size_mb"] > 0
    assert status["message"] == ""


def test_pdf_embed_html_returns_non_empty_object_for_valid_pdf() -> None:
    workspace = make_workspace("reader-pdf-embed")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ncontent")

    html = pdf_embed_html(pdf_path)

    assert html
    assert "<object" in html
    assert "application/pdf" in html


def test_initial_pdf_render_status_defaults_to_stable_html_viewer() -> None:
    status = initial_pdf_render_status(
        native_status={"available": True, "error": ""},
    )

    assert status["selected_renderer"] == STABLE_HTML_RENDERER
    assert status["native_available"] is True
    assert status["attempted_methods"] == []
    assert status["final_method"] == ""
    assert status["native_render_error"] == ""


def test_mark_pdf_render_fallback_records_error_and_final_method() -> None:
    status = mark_pdf_render_fallback(
        mark_pdf_render_native_attempt(
            initial_pdf_render_status(
                selected_renderer=NATIVE_STREAMLIT_RENDERER,
                native_status={"available": True, "error": ""},
            )
        ),
        RuntimeError("streamlit-pdf missing"),
    )

    assert status["attempted_methods"] == ["st.pdf", "html-object"]
    assert status["final_method"] == "html-object"
    assert status["native_render_error"] == "streamlit-pdf missing"


def test_mark_pdf_render_fallback_without_native_starts_with_html_object() -> None:
    status = mark_pdf_render_fallback(
        initial_pdf_render_status(native_status={"available": False, "error": "missing"})
    )

    assert status["native_available"] is False
    assert status["native_availability_error"] == "missing"
    assert status["attempted_methods"] == ["html-object"]
    assert status["final_method"] == "html-object"


def test_native_pdf_support_status_handles_import_failure(monkeypatch) -> None:
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "streamlit_pdf":
            raise ImportError("no streamlit_pdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    status = native_pdf_support_status()

    assert status["available"] is False
    assert "no streamlit_pdf" in status["error"]


def test_native_renderer_is_not_attempted_by_default() -> None:
    status = mark_pdf_render_fallback(initial_pdf_render_status(native_status={"available": True, "error": ""}))

    assert status["selected_renderer"] == STABLE_HTML_RENDERER
    assert status["attempted_methods"] == ["html-object"]
    assert "st.pdf" not in status["attempted_methods"]
