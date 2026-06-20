import json

import pytest

from storage.note_block_store import (
    ALLOWED_BLOCK_TYPES,
    create_note_block,
    delete_note_block,
    get_note_block,
    list_note_blocks,
    note_blocks_path,
    update_note_block,
)
from tests.helpers import make_workspace


REQUIRED_BLOCK_FIELDS = {
    "id",
    "paper_id",
    "block_type",
    "title",
    "text",
    "page",
    "figure",
    "quote",
    "tags",
    "created_at",
    "updated_at",
}


def test_missing_note_block_file_returns_empty_list() -> None:
    base_dir = make_workspace("note-block-missing")

    assert list_note_blocks("paper-1", base_dir) == []
    assert not note_blocks_path("paper-1", base_dir).exists()


def test_create_note_block_writes_valid_schema() -> None:
    base_dir = make_workspace("note-block-create") / "note_blocks"

    block = create_note_block(
        "paper-1",
        "claim",
        title="Main claim",
        text="The treatment improved recovery.",
        page="4",
        figure="2A",
        quote="Recovery increased.",
        tags=["results", "clinical"],
        base_dir=base_dir,
    )

    assert REQUIRED_BLOCK_FIELDS <= set(block)
    assert block["id"]
    assert block["paper_id"] == "paper-1"
    assert block["block_type"] == "claim"
    assert block["page"] == "4"
    assert block["figure"] == "2A"
    assert block["quote"] == "Recovery increased."
    assert block["created_at"] == block["updated_at"]
    stored = json.loads(note_blocks_path("paper-1", base_dir).read_text(encoding="utf-8"))
    assert stored == [block]


def test_list_note_blocks_returns_created_blocks_in_order() -> None:
    base_dir = make_workspace("note-block-list")
    first = create_note_block("paper-1", "summary", text="First", base_dir=base_dir)
    second = create_note_block("paper-1", "question", text="Second", base_dir=base_dir)

    blocks = list_note_blocks("paper-1", base_dir)

    assert [block["id"] for block in blocks] == [first["id"], second["id"]]


def test_update_modifies_fields_preserves_created_at_and_unknown_fields(monkeypatch) -> None:
    base_dir = make_workspace("note-block-update")
    timestamps = iter(("2026-06-20T00:00:00+00:00", "2026-06-20T00:00:01+00:00"))
    monkeypatch.setattr("storage.note_block_store._utc_now_iso", lambda: next(timestamps))
    block = create_note_block("paper-1", "method", text="Original", base_dir=base_dir)

    updated = update_note_block(
        "paper-1",
        block["id"],
        {"text": "Updated", "page": "7", "future_field": {"kind": "preserved"}},
        base_dir=base_dir,
    )

    assert updated["text"] == "Updated"
    assert updated["page"] == "7"
    assert updated["created_at"] == block["created_at"]
    assert updated["updated_at"] != block["updated_at"]
    assert updated["future_field"] == {"kind": "preserved"}
    assert get_note_block("paper-1", block["id"], base_dir) == updated


def test_update_missing_block_raises_key_error() -> None:
    base_dir = make_workspace("note-block-update-missing")

    with pytest.raises(KeyError):
        update_note_block("paper-1", "missing", {"text": "No block"}, base_dir=base_dir)


def test_invalid_block_type_is_rejected() -> None:
    base_dir = make_workspace("note-block-invalid-type")

    with pytest.raises(ValueError, match="block_type"):
        create_note_block("paper-1", "citation", base_dir=base_dir)

    assert "claim" in ALLOWED_BLOCK_TYPES
    assert list_note_blocks("paper-1", base_dir) == []


def test_delete_note_block_removes_only_requested_block() -> None:
    base_dir = make_workspace("note-block-delete")
    first = create_note_block("paper-1", "evidence", text="Keep?", base_dir=base_dir)
    second = create_note_block("paper-1", "idea", text="Keep", base_dir=base_dir)

    assert delete_note_block("paper-1", first["id"], base_dir) is True
    assert list_note_blocks("paper-1", base_dir) == [second]
    assert delete_note_block("paper-1", "missing", base_dir) is False


def test_tags_are_normalized_to_unique_strings() -> None:
    base_dir = make_workspace("note-block-tags")

    block = create_note_block(
        "paper-1",
        "limitation",
        tags=["  sample-size  ", 42, "", "sample-size"],
        base_dir=base_dir,
    )
    comma_tags = create_note_block(
        "paper-1",
        "idea",
        tags="future work, validation, future work",
        base_dir=base_dir,
    )

    assert block["tags"] == ["sample-size", "42"]
    assert comma_tags["tags"] == ["future work", "validation"]
    assert all(isinstance(tag, str) for tag in block["tags"] + comma_tags["tags"])


def test_different_papers_use_different_files() -> None:
    base_dir = make_workspace("note-block-papers")
    first = create_note_block("paper-1", "summary", text="One", base_dir=base_dir)
    second = create_note_block("paper-2", "summary", text="Two", base_dir=base_dir)

    assert note_blocks_path("paper-1", base_dir) != note_blocks_path("paper-2", base_dir)
    assert list_note_blocks("paper-1", base_dir) == [first]
    assert list_note_blocks("paper-2", base_dir) == [second]
