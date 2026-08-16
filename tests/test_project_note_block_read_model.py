from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from services.project_read_model import build_project_detail
from storage.note_block_store import note_blocks_path, save_note_blocks
from storage.project_link_store import create_project_link
from storage.project_store import create_project


def _block(block_id: str, paper_id: str, text: str = "Text") -> dict[str, object]:
    return {
        "id": block_id,
        "paper_id": paper_id,
        "block_type": "claim",
        "title": "Claim title",
        "text": text,
        "page": "8",
        "figure": "Figure 2",
        "quote": "private full quote",
        "tags": ["one", "two"],
        "created_at": "2026-08-02T00:00:00+00:00",
        "updated_at": "2026-08-02T00:00:00+00:00",
    }


def test_project_detail_resolves_available_orphaned_and_unavailable_note_blocks(
    tmp_path: Path,
) -> None:
    index_csv = tmp_path / "data" / "paper_index.csv"
    index_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {"paper_id": "paper-1", "title": "Source One"},
            {"paper_id": "paper-2", "title": "Source Two"},
        ]
    ).to_csv(index_csv, index=False)
    note_blocks_dir = tmp_path / "data" / "note_blocks"
    projects_dir = tmp_path / "data" / "projects"
    long_text = "private " * 100
    save_note_blocks("paper-1", [_block("available", "paper-1", long_text)], note_blocks_dir)
    corrupt = note_blocks_path("paper-2", note_blocks_dir)
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_text("{corrupt private JSON", encoding="utf-8")
    project = create_project("Project", base_dir=projects_dir)
    links = [
        create_project_link(project["id"], "note_block", "available", paper_id="paper-1", link_type="related", base_dir=projects_dir),
        create_project_link(project["id"], "note_block", "missing-block", paper_id="paper-1", link_type="background", base_dir=projects_dir),
        create_project_link(project["id"], "note_block", "missing-paper-block", paper_id="missing-paper", link_type="key_reference", base_dir=projects_dir),
        create_project_link(project["id"], "note_block", "unavailable", paper_id="paper-2", link_type="supports_project", base_dir=projects_dir),
    ]

    detail = build_project_detail(
        project["id"],
        projects_dir=projects_dir,
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
    )

    assert detail is not None
    by_id = {link["link_id"]: link for link in detail["links"]}
    assert by_id[links[0]["id"]]["target_state"] == "available"
    summary = by_id[links[0]["id"]]["note_block"]
    assert summary is not None
    assert summary["source_paper_title"] == "Source One"
    assert len(summary["text_preview"]) <= 280
    assert set(summary) == {
        "block_id", "paper_id", "source_paper_title", "block_type", "title",
        "text_preview", "page", "figure", "tags",
    }
    assert "quote" not in json.dumps(summary)
    assert by_id[links[1]["id"]]["target_state"] == "orphaned_note_block"
    assert by_id[links[1]["id"]]["target_id"] == "missing-block"
    assert by_id[links[2]["id"]]["target_state"] == "orphaned_paper"
    assert by_id[links[3]["id"]]["target_state"] == "unavailable"
    assert detail["linked_note_block_count"] == 4
    assert detail["orphaned_link_count"] == 2
    assert all(link["paper"] is None for link in detail["links"])
