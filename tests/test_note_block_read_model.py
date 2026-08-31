from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from services import note_block_read_model
from services.note_block_read_model import (
    MAX_NOTE_BLOCKS_PER_PAPER,
    build_note_block_collection,
    normalized_note_blocks,
    note_blocks_revision,
)
from storage.atomic_json import CorruptJsonError
from storage.note_block_store import note_blocks_path, save_note_blocks
from storage.project_link_store import create_project_link
from storage.project_store import create_project


def _index(path: Path, paper_ids: tuple[str, ...] = ("paper-1",)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"paper_id": paper_id, "title": f"Title {paper_id}"} for paper_id in paper_ids]
    ).to_csv(path, index=False)


def _block(block_id: str, paper_id: str = "paper-1", text: str = "Text") -> dict[str, object]:
    return {
        "id": block_id,
        "paper_id": paper_id,
        "block_type": "claim",
        "title": f"Title {block_id}",
        "text": text,
        "page": "3",
        "figure": "Figure 1",
        "quote": "Quote",
        "tags": ["one", "two"],
        "created_at": "2026-08-02T00:00:00+00:00",
        "updated_at": "2026-08-02T00:00:00+00:00",
    }


def test_empty_collection_is_successful_and_revision_is_deterministic(tmp_path: Path) -> None:
    index_csv = tmp_path / "data" / "paper_index.csv"
    note_blocks_dir = tmp_path / "data" / "note_blocks"
    _index(index_csv)

    first = build_note_block_collection(
        "paper-1",
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=tmp_path / "data" / "projects",
    )
    second = build_note_block_collection(
        "paper-1",
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=tmp_path / "data" / "projects",
    )

    assert first == second
    assert first is not None
    assert first["items"] == []
    assert first["total"] == 0
    assert first["note_blocks_revision"] == note_blocks_revision("paper-1", [])
    assert not note_blocks_path("paper-1", note_blocks_dir).exists()


def test_collection_is_newest_first_and_excludes_private_fields(tmp_path: Path) -> None:
    index_csv = tmp_path / "data" / "paper_index.csv"
    note_blocks_dir = tmp_path / "data" / "note_blocks"
    _index(index_csv)
    first = {**_block("block-b"), "private_path": "C:/private/paper.pdf"}
    second = {**_block("block-a"), "created_at": "2026-08-03T00:00:00+00:00"}
    save_note_blocks("paper-1", [first, second], note_blocks_dir)

    collection = build_note_block_collection(
        "paper-1",
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=tmp_path / "data" / "projects",
    )

    assert collection is not None
    assert [block["id"] for block in collection["items"]] == ["block-a", "block-b"]
    assert all("private_path" not in block for block in collection["items"])
    assert collection["note_blocks_revision"] == note_blocks_revision(
        "paper-1",
        collection["items"],
    )


def test_corrupt_or_duplicate_collection_is_unavailable_without_mutation(tmp_path: Path) -> None:
    index_csv = tmp_path / "data" / "paper_index.csv"
    note_blocks_dir = tmp_path / "data" / "note_blocks"
    _index(index_csv)
    path = note_blocks_path("paper-1", note_blocks_dir)
    path.parent.mkdir(parents=True)
    path.write_text("{private broken JSON", encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(CorruptJsonError):
        build_note_block_collection(
            "paper-1",
            index_csv=index_csv,
            note_blocks_dir=note_blocks_dir,
            projects_dir=tmp_path / "data" / "projects",
        )
    assert path.read_bytes() == before

    path.write_text(json.dumps([_block("duplicate"), _block("duplicate")]), encoding="utf-8")
    with pytest.raises(ValueError, match="identities must be unique"):
        build_note_block_collection(
            "paper-1",
            index_csv=index_csv,
            note_blocks_dir=note_blocks_dir,
            projects_dir=tmp_path / "data" / "projects",
        )


def test_missing_paper_is_distinct_from_empty_collection(tmp_path: Path) -> None:
    index_csv = tmp_path / "data" / "paper_index.csv"
    _index(index_csv)

    assert build_note_block_collection(
        "missing",
        index_csv=index_csv,
        note_blocks_dir=tmp_path / "data" / "note_blocks",
        projects_dir=tmp_path / "data" / "projects",
    ) is None


def test_reader_collection_exposes_bounded_current_project_links(tmp_path: Path) -> None:
    index_csv = tmp_path / "data" / "paper_index.csv"
    note_blocks_dir = tmp_path / "data" / "note_blocks"
    projects_dir = tmp_path / "data" / "projects"
    _index(index_csv)
    save_note_blocks("paper-1", [_block("block-1")], note_blocks_dir)
    project = create_project("Project", base_dir=projects_dir)
    link = create_project_link(
        project["id"],
        "note_block",
        "block-1",
        paper_id="paper-1",
        link_type="related",
        note="private link note",
        base_dir=projects_dir,
    )

    collection = build_note_block_collection(
        "paper-1",
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
    )

    assert collection is not None
    assert collection["project_links_state"] == "available"
    assert collection["project_links"] == [
        {
            "link_id": link["id"],
            "project_id": project["id"],
            "project_name": "Project",
            "project_status": "active",
            "note_block_id": "block-1",
            "link_type": "related",
            "links_revision": collection["project_links"][0]["links_revision"],
        }
    ]
    assert "private" not in json.dumps(collection)


def test_revision_binds_complete_normalized_state_in_newest_first_order() -> None:
    first = _block("first")
    second = _block("second")
    baseline = note_blocks_revision("paper-1", [first, second])

    for field, value in {
        "id": "changed-id",
        "block_type": "idea",
        "title": "Changed",
        "text": "Changed text",
        "page": "99",
        "figure": "Changed figure",
        "quote": "Changed quote",
        "tags": ["changed"],
        "created_at": "2026-08-02T01:00:00+00:00",
        "updated_at": "2026-08-02T02:00:00+00:00",
    }.items():
        changed = [{**first, field: value}, second]
        assert note_blocks_revision("paper-1", changed) != baseline
    assert note_blocks_revision("paper-1", [second, first]) == baseline


def test_collection_count_is_bounded() -> None:
    blocks = [_block(f"block-{index}") for index in range(MAX_NOTE_BLOCKS_PER_PAPER + 1)]

    with pytest.raises(ValueError, match="supported bound"):
        normalized_note_blocks("paper-1", blocks)


def test_project_link_summary_failure_isolated_from_note_block_collection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    index_csv = tmp_path / "data" / "paper_index.csv"
    note_blocks_dir = tmp_path / "data" / "note_blocks"
    _index(index_csv)
    save_note_blocks("paper-1", [_block("block-1")], note_blocks_dir)

    def unavailable(_base_dir):
        raise OSError("C:/private/projects.json")

    monkeypatch.setattr(note_block_read_model, "list_projects", unavailable)
    collection = build_note_block_collection(
        "paper-1",
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=tmp_path / "data" / "projects",
    )

    assert collection is not None
    assert collection["items"][0]["id"] == "block-1"
    assert collection["project_links"] == []
    assert collection["project_links_state"] == "unavailable"
