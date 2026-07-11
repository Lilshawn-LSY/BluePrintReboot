from core.paper_text_profile import PaperTextProfile
from ui_streamlit.reader_workspace import (
    HTML_BASE64_FALLBACK_RENDERER,
    LARGE_PDF_SIZE_MB,
    NATIVE_STREAMLIT_RENDERER,
    STABLE_HTML_RENDERER,
    add_manual_tag,
    apply_pending_note_header_refresh,
    apply_pending_note_actions,
    append_markdown_snapshot,
    build_reader_tag_suggestion_record,
    citation_block,
    has_unsaved_note_changes,
    initial_pdf_render_status,
    insert_note_block,
    load_note_draft,
    mark_pdf_render_fallback,
    mark_pdf_render_native_attempt,
    mark_pdf_render_native_success,
    merge_selected_reader_tag_suggestions,
    native_pdf_support_status,
    note_baseline_key,
    note_draft_key,
    pending_note_block_append_key,
    pending_note_discard_reload_key,
    pending_note_header_refresh_key,
    pending_note_notice_key,
    pending_note_reload_key,
    pending_note_text_update_key,
    pdf_embed_html,
    pdf_external_open_reference,
    pdf_large_file_policy,
    pdf_path_status,
    preview_reader_tag_suggestions,
    preserve_reader_context,
    preserve_reader_context_for_paper_id,
    queue_note_header_refresh,
    queue_note_text_update,
    reader_profile_summary,
    reader_tag_suggestion_preview_key,
    save_note_draft,
    should_render_html_fallback,
)
from services.reading_note_template import refresh_reading_note_header
from services.tag_book import load_tag_book, suggestion_selection_id
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

    assert "# BluePrint Reading Note" in draft
    assert "paper_id: paper-1" in draft
    assert "title: Reader Paper" in draft
    assert "first_author: Curie Marie" in draft
    assert "## Key Claims" in draft
    assert session_state[note_draft_key(record)] == draft
    assert session_state[note_baseline_key(record)] == draft


def test_save_note_draft_writes_current_session_text() -> None:
    notes_dir = make_workspace("reader-note-save")
    record = {"paper_id": "paper-1", "title": "Reader Paper"}
    session_state = {note_draft_key(record): "draft text"}

    note_path = save_note_draft(record, session_state, notes_dir=notes_dir)

    assert note_path.read_text(encoding="utf-8") == "draft text"
    assert session_state[note_baseline_key(record)] == "draft text"
    assert session_state[f"reader_note_saved_at_{record['paper_id']}"]
    assert session_state["active_paper_id"] == "paper-1"
    assert session_state["current_page"] == "Paper Detail"


def test_preserve_reader_context_keeps_current_paper_active() -> None:
    session_state = {"active_paper_id": "old-paper", "current_page": "Library", "unrelated": "keep"}

    preserve_reader_context({"paper_id": "paper-1"}, session_state)

    assert session_state["active_paper_id"] == "paper-1"
    assert session_state["current_page"] == "Paper Detail"
    assert session_state["unrelated"] == "keep"


def test_non_note_reader_rerun_preserves_dirty_note_and_pending_state() -> None:
    record = {"paper_id": "paper-1"}
    session_state = {
        note_draft_key(record): "dirty draft",
        note_baseline_key(record): "saved baseline",
        pending_note_header_refresh_key(record): {"text": "header", "saved_to_file": False},
        pending_note_discard_reload_key(record): True,
    }
    note_state_before = dict(session_state)

    preserve_reader_context(record, session_state)

    assert {key: session_state[key] for key in note_state_before} == note_state_before
    assert session_state["active_paper_id"] == "paper-1"
    assert session_state["current_page"] == "Paper Detail"


def test_preserve_reader_context_for_paper_id_sets_paper_detail_page() -> None:
    session_state = {"current_page": "Project Workspace"}

    preserve_reader_context_for_paper_id("paper-2", session_state)

    assert session_state["active_paper_id"] == "paper-2"
    assert session_state["current_page"] == "Paper Detail"


def test_add_manual_tag_normalizes_and_avoids_duplicates() -> None:
    assert add_manual_tag("existing-tag, root-development", " Root   Development ") == (
        "existing-tag, root-development"
    )
    assert add_manual_tag("existing-tag", " New   Tag ") == "existing-tag, new-tag"
    assert add_manual_tag("existing-tag", "   ") == "existing-tag"


def test_reader_tag_suggestions_are_previewed_without_mutating_record() -> None:
    record = {
        "paper_id": "paper-1",
        "title": "Arabidopsis root development protocol",
        "tags": "existing-tag",
    }

    suggestions = preview_reader_tag_suggestions(record)

    assert suggestions[:3] == ["arabidopsis", "root-development", "protocol"]
    assert record["tags"] == "existing-tag"
    assert reader_tag_suggestion_preview_key(record) == "reader_tag_suggestion_preview_paper-1"


def test_reader_tag_suggestion_record_uses_profile_cache(monkeypatch) -> None:
    profile = PaperTextProfile(
        paper_id="paper-profile",
        title="Synthetic biology profile",
        abstract="Profile abstract mentions single-cell RNA sequencing.",
        keywords=["spatial transcriptomics"],
        note_sections={"Methods": "The profile method uses a pipeline."},
        confidence={"title": "high", "abstract": "high", "keywords": "high", "note_sections": "high"},
        generated_at="2026-07-06T00:00:00+00:00",
    )
    monkeypatch.setattr("ui_streamlit.reader_workspace.load_profile", lambda paper_id: profile)
    record = {"paper_id": "paper-profile", "title": "Saved title", "tags": ""}

    built = build_reader_tag_suggestion_record(record)
    summary = reader_profile_summary(profile)

    assert built["title"] == "Synthetic biology profile"
    assert built["abstract"] == "Profile abstract mentions single-cell RNA sequencing."
    assert built["keywords"] == ["spatial transcriptomics"]
    assert built["note_methods"] == "The profile method uses a pipeline."
    assert "extracted_text_preview" not in built
    assert summary["available"] is True
    assert summary["note_sections"] == ["Methods"]


def test_reader_selected_known_suggestion_adds_canonical_tag() -> None:
    suggestion = {
        "display": "Lateral Root",
        "canonical": "lateral-root",
        "category": "tissue_or_cell_type",
        "kind": "known_canonical",
    }

    updated = merge_selected_reader_tag_suggestions(
        "existing-tag",
        [suggestion],
        [suggestion_selection_id(suggestion)],
    )

    assert updated == "existing-tag, lateral-root"


def test_reader_candidate_suggestion_adds_paper_local_tag_only() -> None:
    suggestion = {
        "display": "CRISPR screen",
        "canonical": "crispr-screen",
        "category": "method",
        "kind": "new_candidate",
    }

    assert merge_selected_reader_tag_suggestions("", [suggestion], []) == ""
    updated = merge_selected_reader_tag_suggestions("", [suggestion], [suggestion_selection_id(suggestion)])

    assert updated == "crispr-screen"
    assert "crispr-screen" not in load_tag_book()["tags"]


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


def test_queued_note_text_update_applies_before_pending_append_and_clears_key() -> None:
    notes_dir = make_workspace("reader-pending-text-update")
    record = {"paper_id": "paper-1", "title": "Reader Paper"}
    append_key = pending_note_block_append_key(record)
    session_state = {
        note_draft_key(record): "Existing draft",
        append_key: "### Evidence: Result\n\nBlock text\n",
    }
    queue_note_text_update(record, session_state, "Queued draft", notice="Draft updated.")

    draft = apply_pending_note_actions(record, session_state, notes_dir=notes_dir)

    assert draft == "Queued draft\n\n### Evidence: Result\n\nBlock text\n"
    assert session_state[note_draft_key(record)] == draft
    assert pending_note_text_update_key(record) not in session_state
    assert append_key not in session_state
    assert session_state[pending_note_notice_key(record)] == "Draft updated."


def test_pending_reload_is_skipped_when_unsaved_draft_exists() -> None:
    notes_dir = make_workspace("reader-pending-reload")
    record = {"paper_id": "paper-1", "title": "Reader Paper"}
    save_note_text(record, "Saved note", notes_dir=notes_dir)
    reload_key = pending_note_reload_key(record)
    append_key = pending_note_block_append_key(record)
    session_state = {
        note_draft_key(record): "Unsaved draft",
        note_baseline_key(record): "Saved note",
        reload_key: True,
        append_key: "### Claim: Snapshot\n",
    }

    draft = apply_pending_note_actions(record, session_state, notes_dir=notes_dir)

    assert draft == "Unsaved draft\n\n### Claim: Snapshot\n"
    assert reload_key not in session_state
    assert append_key not in session_state
    assert session_state[pending_note_notice_key(record)] == "Reload needs confirmation; unsaved changes kept."
    assert session_state[pending_note_discard_reload_key(record)] is True


def test_pending_reload_updates_clean_draft() -> None:
    notes_dir = make_workspace("reader-pending-reload-clean")
    record = {"paper_id": "paper-1", "title": "Reader Paper"}
    save_note_text(record, "Saved note", notes_dir=notes_dir)
    reload_key = pending_note_reload_key(record)
    session_state = {
        note_draft_key(record): "Old saved note",
        note_baseline_key(record): "Old saved note",
        reload_key: True,
    }

    draft = apply_pending_note_actions(record, session_state, notes_dir=notes_dir)

    assert draft == "Saved note"
    assert session_state[note_baseline_key(record)] == "Saved note"
    assert session_state[pending_note_notice_key(record)] == "Note reloaded."
    assert reload_key not in session_state


def test_metadata_header_refresh_waits_when_draft_has_unsaved_changes() -> None:
    notes_dir = make_workspace("reader-header-refresh-unsaved")
    old_record = {
        "paper_id": "paper-1",
        "title": "Old Title",
        "authors": "Old Author",
        "year": "2024",
        "tags": "old-tag",
    }
    updated_record = {**old_record, "title": "New Title", "tags": "new-tag"}
    session_state = {}
    baseline = load_note_draft(old_record, session_state, notes_dir=notes_dir)
    unsaved = baseline.rstrip() + "\n\nUser note\n"
    session_state[note_draft_key(old_record)] = unsaved
    refreshed = refresh_reading_note_header(unsaved, updated_record)
    queue_note_header_refresh(
        updated_record,
        session_state,
        str(refreshed["text"]),
        notice="Header refresh available; unsaved changes kept.",
    )

    draft = apply_pending_note_actions(updated_record, session_state, notes_dir=notes_dir)

    assert draft == unsaved
    assert session_state[pending_note_header_refresh_key(updated_record)]
    assert session_state[pending_note_notice_key(updated_record)] == "Header refresh available; unsaved changes kept."
    assert has_unsaved_note_changes(updated_record, session_state) is True


def test_explicit_header_refresh_preserves_unsaved_body_and_keeps_draft_dirty() -> None:
    notes_dir = make_workspace("reader-header-refresh-apply")
    old_record = {"paper_id": "paper-1", "title": "Old Title", "authors": "Old Author", "year": "2024"}
    updated_record = {**old_record, "title": "New Title", "authors": "New Author"}
    session_state = {}
    baseline = load_note_draft(old_record, session_state, notes_dir=notes_dir)
    unsaved = baseline.rstrip() + "\n\nUser note\n"
    session_state[note_draft_key(old_record)] = unsaved
    refreshed = refresh_reading_note_header(unsaved, updated_record)
    queue_note_header_refresh(updated_record, session_state, str(refreshed["text"]))
    session_state[note_draft_key(old_record)] = unsaved.rstrip() + "\nLater note\n"

    applied = apply_pending_note_header_refresh(updated_record, session_state)

    assert applied is True
    draft = session_state[note_draft_key(updated_record)]
    assert "title: New Title" in draft
    assert "first_author: New Author" in draft
    assert "User note" in draft
    assert "Later note" in draft
    assert pending_note_header_refresh_key(updated_record) not in session_state
    assert session_state[note_baseline_key(updated_record)] == baseline
    assert has_unsaved_note_changes(updated_record, session_state) is True


def test_clean_draft_header_refresh_updates_baseline_after_metadata_change() -> None:
    notes_dir = make_workspace("reader-header-refresh-clean")
    old_record = {"paper_id": "paper-1", "title": "Old Title", "authors": "Old Author", "year": "2024"}
    updated_record = {**old_record, "title": "New Title"}
    session_state = {}
    baseline = load_note_draft(old_record, session_state, notes_dir=notes_dir)
    refreshed = refresh_reading_note_header(baseline, updated_record)
    queue_note_header_refresh(
        updated_record,
        session_state,
        str(refreshed["text"]),
        notice="Header refreshed.",
        saved_to_file=True,
    )

    draft = apply_pending_note_actions(updated_record, session_state, notes_dir=notes_dir)

    assert "title: New Title" in draft
    assert pending_note_header_refresh_key(updated_record) not in session_state
    assert session_state[note_baseline_key(updated_record)] == draft
    assert session_state[pending_note_notice_key(updated_record)] == "Header refreshed."
    assert has_unsaved_note_changes(updated_record, session_state) is False


def test_saved_header_refresh_does_not_mark_a_later_dirty_draft_clean() -> None:
    notes_dir = make_workspace("reader-saved-header-refresh-later-edit")
    old_record = {"paper_id": "paper-1", "title": "Old Title", "authors": "Old Author"}
    updated_record = {**old_record, "title": "New Title"}
    session_state = {}
    baseline = load_note_draft(old_record, session_state, notes_dir=notes_dir)
    saved_refresh = str(refresh_reading_note_header(baseline, updated_record)["text"])
    queue_note_header_refresh(
        updated_record,
        session_state,
        saved_refresh,
        saved_to_file=True,
    )
    session_state[note_draft_key(updated_record)] = baseline.rstrip() + "\n\nLatest unsaved body\n"

    assert apply_pending_note_header_refresh(updated_record, session_state) is True

    draft = session_state[note_draft_key(updated_record)]
    assert "title: New Title" in draft
    assert "Latest unsaved body" in draft
    assert session_state[note_baseline_key(updated_record)] == saved_refresh
    assert has_unsaved_note_changes(updated_record, session_state) is True


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


def test_initial_pdf_render_status_defaults_to_native_viewer() -> None:
    status = initial_pdf_render_status(
        native_status={"available": True, "error": ""},
    )

    assert status["selected_renderer"] == NATIVE_STREAMLIT_RENDERER
    assert status["native_available"] is True
    assert status["attempted_methods"] == []
    assert status["final_method"] == ""
    assert status["native_render_error"] == ""


def test_pdf_renderer_options_keep_html_fallback_non_default() -> None:
    assert STABLE_HTML_RENDERER == HTML_BASE64_FALLBACK_RENDERER
    status = mark_pdf_render_native_success(
        initial_pdf_render_status(native_status={"available": True, "error": ""})
    )

    assert status["selected_renderer"] == NATIVE_STREAMLIT_RENDERER
    assert status["attempted_methods"] == ["st.pdf"]
    assert status["final_method"] == "st.pdf"


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
        initial_pdf_render_status(
            selected_renderer=HTML_BASE64_FALLBACK_RENDERER,
            native_status={"available": False, "error": "missing"},
        )
    )

    assert status["native_available"] is False
    assert status["native_availability_error"] == "missing"
    assert status["selected_renderer"] == HTML_BASE64_FALLBACK_RENDERER
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


def test_native_renderer_is_attempted_by_default() -> None:
    status = mark_pdf_render_native_attempt(initial_pdf_render_status(native_status={"available": True, "error": ""}))

    assert status["selected_renderer"] == NATIVE_STREAMLIT_RENDERER
    assert status["attempted_methods"] == ["st.pdf"]


def test_large_pdf_policy_blocks_automatic_html_base64_rendering() -> None:
    status = {"exists": True, "size_mb": LARGE_PDF_SIZE_MB + 1}

    policy = pdf_large_file_policy(status)

    assert policy["is_large"] is True
    assert policy["allow_automatic_html_fallback"] is False
    assert should_render_html_fallback(HTML_BASE64_FALLBACK_RENDERER, status) is False
    assert should_render_html_fallback(
        HTML_BASE64_FALLBACK_RENDERER,
        status,
        confirmed_large_render=True,
    ) is True


def test_small_pdf_policy_allows_html_only_after_explicit_fallback_selection() -> None:
    status = {"exists": True, "size_mb": 1.0}

    policy = pdf_large_file_policy(status)

    assert policy["is_large"] is False
    assert policy["allow_automatic_html_fallback"] is True
    assert should_render_html_fallback(NATIVE_STREAMLIT_RENDERER, status) is False
    assert should_render_html_fallback(HTML_BASE64_FALLBACK_RENDERER, status) is True


def test_pdf_external_open_reference_returns_path_and_file_uri() -> None:
    workspace = make_workspace("reader-external-open-reference")
    pdf_path = workspace / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ncontent")

    reference = pdf_external_open_reference(pdf_path)

    assert reference["path"].endswith("paper.pdf")
    assert reference["file_uri"].startswith("file:///")
