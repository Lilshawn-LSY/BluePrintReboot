import json

import pytest

from storage.note_block_store import (
    ALLOWED_BLOCK_TYPES,
    create_note_block,
    delete_note_block,
    get_note_block,
    list_note_blocks,
    note_blocks_path,
    render_note_block_as_markdown,
    save_note_blocks,
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
        {
            "id": "replacement-id",
            "paper_id": "paper-2",
            "created_at": "replacement-created-at",
            "block_type": "evidence",
            "title": "Updated title",
            "text": "Updated text",
            "page": "7",
            "figure": "3B",
            "quote": "Updated quote",
            "tags": " results, validation, results ",
            "future_field": {"kind": "preserved"},
        },
        base_dir=base_dir,
    )

    assert updated["id"] == block["id"]
    assert updated["paper_id"] == block["paper_id"]
    assert updated["block_type"] == "evidence"
    assert updated["title"] == "Updated title"
    assert updated["text"] == "Updated text"
    assert updated["page"] == "7"
    assert updated["figure"] == "3B"
    assert updated["quote"] == "Updated quote"
    assert updated["tags"] == ["results", "validation"]
    assert updated["created_at"] == block["created_at"]
    assert updated["updated_at"] != block["updated_at"]
    assert updated["future_field"] == {"kind": "preserved"}
    assert get_note_block("paper-1", block["id"], base_dir) == updated


def test_update_missing_block_raises_key_error() -> None:
    base_dir = make_workspace("note-block-update-missing")

    with pytest.raises(KeyError):
        update_note_block("paper-1", "missing", {"text": "No block"}, base_dir=base_dir)

    assert list_note_blocks("paper-1", base_dir) == []
    assert not note_blocks_path("paper-1", base_dir).exists()


def test_update_rejects_invalid_block_type_without_changing_block() -> None:
    base_dir = make_workspace("note-block-update-invalid-type")
    block = create_note_block("paper-1", "claim", text="Original", base_dir=base_dir)

    with pytest.raises(ValueError, match="block_type"):
        update_note_block(
            "paper-1",
            block["id"],
            {"block_type": "citation", "text": "Should not be saved"},
            base_dir=base_dir,
        )

    assert get_note_block("paper-1", block["id"], base_dir) == block


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


def test_render_note_block_as_markdown_returns_stable_readable_snippet() -> None:
    snippet = render_note_block_as_markdown(
        {
            "block_type": "evidence",
            "title": "Ck induces growth of RAM length",
            "text": "Root apical meristem length increased after treatment.",
            "page": "3",
            "figure": "1a",
            "quote": "RAM length increased significantly.",
            "tags": ["Cytokinin", " RAM ", "Cytokinin"],
        }
    )

    assert snippet == (
        "### Evidence: Ck induces growth of RAM length\n\n"
        "* Page: 3\n"
        "* Figure: 1a\n"
        "* Tags: Cytokinin, RAM\n\n"
        "> RAM length increased significantly.\n\n"
        "Root apical meristem length increased after treatment.\n"
    )


def test_render_note_block_as_markdown_omits_empty_metadata() -> None:
    snippet = render_note_block_as_markdown(
        {
            "block_type": "idea",
            "title": "",
            "text": "Test this in a larger cohort.",
            "page": "",
            "figure": "",
            "quote": "",
            "tags": [],
        }
    )

    assert snippet == "### Idea\n\nTest this in a larger cohort.\n"
    assert "* Page:" not in snippet
    assert "* Figure:" not in snippet
    assert "* Tags:" not in snippet


def test_save_note_blocks_replace_failure_preserves_existing_file_and_cleans_temp(monkeypatch) -> None:
    base_dir = make_workspace("note-block-atomic-replace")
    block = create_note_block("paper-1", "summary", text="Existing", base_dir=base_dir)
    path = note_blocks_path("paper-1", base_dir)
    before = path.read_bytes()

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr("storage.atomic_json.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        save_note_blocks("paper-1", [{**block, "text": "Updated"}], base_dir=base_dir)

    assert path.read_bytes() == before
    assert list_note_blocks("paper-1", base_dir) == [block]
    assert sorted(item.name for item in base_dir.iterdir()) == ["paper-1.json"]
