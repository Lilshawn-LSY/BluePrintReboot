from storage.note_store import create_note_if_missing, load_note_text, save_note_text
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
    assert "# A Test Paper" in text
    assert "- Authors: Ada Lovelace" in text
    assert "- Year: 1843" in text
    assert "- Journal: Notes" in text
    assert "- DOI: 10.0000/example" in text
    assert "- Tags: computing, history" in text
    assert "## Key Claims" in text

    save_note_text(record, "updated note", notes_dir=notes_dir)
    assert load_note_text(record, notes_dir=notes_dir) == "updated note"
