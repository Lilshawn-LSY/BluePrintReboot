from services.reading_note_template import render_reading_note_template
from storage.note_store import create_note_if_missing, load_note_text, refresh_note_header, save_note_text
from tests.helpers import make_workspace


def test_create_load_and_save_note() -> None:
    notes_dir = make_workspace("notes")
    record = {
        "paper_id": "paper-123",
        "title": "A Test Paper",
        "authors": "Ada Lovelace",
        "year": "1843",
        "journal": "Notes",
        "doi": "10.0000/example",
        "tags": "computing, history",
        "filename": "paper.pdf",
        "status": "unread",
    }

    note_path = create_note_if_missing(record, notes_dir=notes_dir)
    assert note_path.exists()
    assert note_path.name == "paper-123.md"

    text = load_note_text(record, notes_dir=notes_dir)
    assert "# BluePrint Reading Note" in text
    assert "paper_id: paper-123" in text
    assert "title: A Test Paper" in text
    assert "year: 1843" in text
    assert "first_author: Ada Lovelace" in text
    assert "doi: 10.0000/example" in text
    assert "tags: computing, history" in text
    assert "## Key Claims" in text
    assert "## Raw Notes" in text

    save_note_text(record, "updated note", notes_dir=notes_dir)
    assert load_note_text(record, notes_dir=notes_dir) == "updated note"


def test_refresh_note_header_updates_saved_header_and_preserves_body() -> None:
    notes_dir = make_workspace("notes-refresh-header")
    old_record = {
        "paper_id": "paper-123",
        "title": "Old Title",
        "authors": "Ada Lovelace",
        "year": "1843",
        "doi": "10.0000/old",
        "tags": "old",
        "filename": "paper.pdf",
    }
    new_record = {
        **old_record,
        "title": "New Title",
        "authors": "Grace Hopper; Ada Lovelace",
        "year": "1952",
        "doi": "10.0000/new",
        "tags": "new, metadata",
    }
    original = render_reading_note_template(old_record).replace("## Raw Notes\n\n", "## Raw Notes\n\nKeep this body.\n")
    save_note_text(old_record, original, notes_dir=notes_dir)

    result = refresh_note_header(new_record, notes_dir=notes_dir)

    refreshed = load_note_text(new_record, notes_dir=notes_dir)
    assert result["changed"] is True
    assert "title: New Title" in refreshed
    assert "first_author: Grace Hopper" in refreshed
    assert "tags: new, metadata" in refreshed
    assert refreshed.split("## One-line Summary", 1)[1] == original.split("## One-line Summary", 1)[1]
