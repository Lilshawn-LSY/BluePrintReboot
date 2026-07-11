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


def test_note_creation_and_save_replace_from_same_directory() -> None:
    notes_dir = make_workspace("notes-atomic-success")
    record = {"paper_id": "paper-atomic", "title": "Atomic Note"}
    replacements = []

    def inspect_replace(source, target) -> None:
        assert source.parent.resolve() == target.parent.resolve() == notes_dir.resolve()
        assert source.exists()
        replacements.append((source, target))
        os.replace(source, target)

    note_path = create_note_if_missing(record, notes_dir=notes_dir, replace_file=inspect_replace)
    save_note_text(record, "saved atomically", notes_dir=notes_dir, replace_file=inspect_replace)

    assert note_path.read_text(encoding="utf-8") == "saved atomically"
    assert len(replacements) == 2
    assert sorted(path.name for path in notes_dir.iterdir()) == ["paper-atomic.md"]


def test_failed_note_replace_preserves_bytes_and_removes_temporary_file() -> None:
    notes_dir = make_workspace("notes-atomic-failure")
    record = {"paper_id": "paper-atomic", "title": "Atomic Note"}
    note_path = save_note_text(record, "old text \N{SNOWMAN}", notes_dir=notes_dir)
    previous_bytes = note_path.read_bytes()

    def fail_replace(_source, _target) -> None:
        raise OSError("simulated replace failure")

    with pytest.raises(OSError, match="simulated replace failure"):
        save_note_text(record, "new text", notes_dir=notes_dir, replace_file=fail_replace)

    assert note_path.read_bytes() == previous_bytes
    assert sorted(path.name for path in notes_dir.iterdir()) == ["paper-atomic.md"]


def test_create_note_if_missing_never_replaces_existing_note() -> None:
    notes_dir = make_workspace("notes-create-existing")
    record = {"paper_id": "paper-existing", "title": "Existing Note"}
    note_path = notes_dir / "paper-existing.md"
    note_path.write_bytes(b"existing note bytes")

    def unexpected_replace(_source, _target) -> None:
        raise AssertionError("replace must not be called for an existing note")

    result = create_note_if_missing(record, notes_dir=notes_dir, replace_file=unexpected_replace)

    assert result == note_path
    assert note_path.read_bytes() == b"existing note bytes"


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

    replace_calls = []

    def inspect_replace(source, target) -> None:
        replace_calls.append((source, target))
        os.replace(source, target)

    result = refresh_note_header(new_record, notes_dir=notes_dir, replace_file=inspect_replace)

    refreshed = load_note_text(new_record, notes_dir=notes_dir)
    assert result["changed"] is True
    assert "title: New Title" in refreshed
    assert "first_author: Grace Hopper" in refreshed
    assert "tags: new, metadata" in refreshed
    assert refreshed.split("## One-line Summary", 1)[1] == original.split("## One-line Summary", 1)[1]
    assert len(replace_calls) == 1
import os

import pytest
