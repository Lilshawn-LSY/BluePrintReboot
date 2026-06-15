from ui_streamlit.reader_workspace import (
    add_manual_tag,
    citation_block,
    insert_note_block,
    load_note_draft,
    note_draft_key,
    pdf_embed_html,
    pdf_path_status,
    save_note_draft,
)
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
