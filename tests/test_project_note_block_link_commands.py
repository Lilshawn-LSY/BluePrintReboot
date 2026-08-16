from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from services import project_commands
from services.project_read_model import build_project_detail
from services.project_commands import (
    ProjectArchivedConflict,
    ProjectCommandConflict,
    ProjectCommandNotFound,
    ProjectCommandService,
    ProjectCommandUnavailable,
)
from storage.note_block_store import note_blocks_path, save_note_blocks
from storage import project_link_store
from storage.project_link_store import (
    create_project_link,
    list_project_links,
    project_links_path,
)
from storage.project_store import projects_path
from storage.workspace_lock import WorkspaceLockUnavailable


def _block(block_id: str, paper_id: str) -> dict[str, object]:
    return {
        "id": block_id,
        "paper_id": paper_id,
        "block_type": "evidence",
        "title": "Evidence",
        "text": "Text",
        "page": "1",
        "figure": "",
        "quote": "",
        "tags": [],
        "created_at": "2026-08-02T00:00:00+00:00",
        "updated_at": "2026-08-02T00:00:00+00:00",
    }


def _service(tmp_path: Path) -> ProjectCommandService:
    index_csv = tmp_path / "data" / "paper_index.csv"
    index_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {"paper_id": "paper-1", "title": "One"},
            {"paper_id": "paper-2", "title": "Two"},
        ]
    ).to_csv(index_csv, index=False)
    note_blocks_dir = tmp_path / "data" / "note_blocks"
    save_note_blocks("paper-1", [_block("block-1", "paper-1")], note_blocks_dir)
    save_note_blocks("paper-2", [_block("block-2", "paper-2")], note_blocks_dir)
    return ProjectCommandService(
        projects_dir=tmp_path / "data" / "projects",
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
    )


def test_add_duplicate_and_distinct_link_types_are_truthful(tmp_path: Path) -> None:
    service = _service(tmp_path)
    project = service.create_project(name="Project")
    first = service.add_note_block_link(
        project.project.project_id,
        paper_id="paper-1",
        note_block_id="block-1",
        link_type="related",
        expected_links_revision=project.project.links_revision,
    )
    duplicate = service.add_note_block_link(
        project.project.project_id,
        paper_id="paper-1",
        note_block_id="block-1",
        link_type="related",
        expected_links_revision=first.project.links_revision,
    )
    distinct = service.add_note_block_link(
        project.project.project_id,
        paper_id="paper-1",
        note_block_id="block-1",
        link_type="supports_project",
        expected_links_revision=duplicate.project.links_revision,
    )

    assert first.status == "created"
    assert duplicate.status == "unchanged"
    assert duplicate.link.link_id == first.link.link_id
    assert distinct.status == "created"
    assert len(list_project_links(service.projects_dir)) == 2
    assert distinct.project.link_count == 2
    assert distinct.project.linked_paper_count == 0
    assert distinct.project.linked_note_block_count == 2


def test_note_block_link_add_and_remove_survive_project_detail_reload(tmp_path: Path) -> None:
    service = _service(tmp_path)
    project = service.create_project(name="Project")
    linked = service.add_note_block_link(
        project.project.project_id,
        paper_id="paper-1",
        note_block_id="block-1",
        link_type="related",
        expected_links_revision=project.project.links_revision,
    )
    detail = build_project_detail(
        project.project.project_id,
        projects_dir=service.projects_dir,
        index_csv=service.index_csv,
        note_blocks_dir=service.note_blocks_dir,
    )

    assert detail is not None
    assert detail["linked_note_block_count"] == 1
    assert detail["links"][0]["note_block"]["block_id"] == "block-1"

    removed = service.remove_note_block_link(
        project.project.project_id,
        linked.link.link_id,
        expected_links_revision=detail["links_revision"],
    )
    reloaded = build_project_detail(
        project.project.project_id,
        projects_dir=service.projects_dir,
        index_csv=service.index_csv,
        note_blocks_dir=service.note_blocks_dir,
    )

    assert removed.status == "removed"
    assert reloaded is not None
    assert reloaded["links"] == []
    assert reloaded["linked_note_block_count"] == 0


def test_invalid_project_paper_block_mismatch_archived_and_stale_are_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    project = service.create_project(name="Project")

    for paper_id, block_id in (
        ("missing", "block-1"),
        ("paper-1", "missing"),
        ("paper-1", "block-2"),
    ):
        with pytest.raises(ProjectCommandNotFound):
            service.add_note_block_link(
                project.project.project_id,
                paper_id=paper_id,
                note_block_id=block_id,
                link_type="related",
                expected_links_revision=project.project.links_revision,
            )
    with pytest.raises(ProjectCommandNotFound):
        service.add_note_block_link(
            "missing",
            paper_id="paper-1",
            note_block_id="block-1",
            link_type="related",
            expected_links_revision=project.project.links_revision,
        )
    with pytest.raises(ProjectCommandConflict):
        service.add_note_block_link(
            project.project.project_id,
            paper_id="paper-1",
            note_block_id="block-1",
            link_type="related",
            expected_links_revision="0" * 64,
        )

    archived = service.archive_project(
        project.project.project_id,
        project.project.project_revision,
    )
    with pytest.raises(ProjectArchivedConflict):
        service.add_note_block_link(
            project.project.project_id,
            paper_id="paper-1",
            note_block_id="block-1",
            link_type="related",
            expected_links_revision=archived.project.links_revision,
        )
    assert list_project_links(service.projects_dir) == []


def test_unlink_is_exact_and_preserves_project_paper_and_note_block(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first_project = service.create_project(name="One")
    second_project = service.create_project(name="Two")
    linked = service.add_note_block_link(
        first_project.project.project_id,
        paper_id="paper-1",
        note_block_id="block-1",
        link_type="related",
        expected_links_revision=first_project.project.links_revision,
    )
    paper_link = create_project_link(
        first_project.project.project_id,
        "paper",
        "paper-1",
        base_dir=service.projects_dir,
    )
    note_path = note_blocks_path("paper-1", service.note_blocks_dir)
    project_path = projects_path(service.projects_dir)
    index_before = service.index_csv.read_bytes()
    note_before = note_path.read_bytes()
    project_before = project_path.read_bytes()

    for project_id, link_id in (
        (second_project.project.project_id, linked.link.link_id),
        (first_project.project.project_id, paper_link["id"]),
        (first_project.project.project_id, "missing"),
    ):
        current_links = list_project_links(service.projects_dir)
        from services.project_read_model import project_links_revision
        with pytest.raises(ProjectCommandNotFound):
            service.remove_note_block_link(
                project_id,
                link_id,
                expected_links_revision=project_links_revision(project_id, current_links),
            )

    from services.project_read_model import project_links_revision
    removed = service.remove_note_block_link(
        first_project.project.project_id,
        linked.link.link_id,
        expected_links_revision=project_links_revision(
            first_project.project.project_id,
            list_project_links(service.projects_dir),
        ),
    )

    assert removed.status == "removed"
    assert service.index_csv.read_bytes() == index_before
    assert note_path.read_bytes() == note_before
    assert project_path.read_bytes() == project_before
    assert [link["id"] for link in list_project_links(service.projects_dir)] == [paper_link["id"]]


def test_stale_unlink_and_archived_unlink_have_zero_mutation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    project = service.create_project(name="Project")
    linked = service.add_note_block_link(
        project.project.project_id,
        paper_id="paper-1",
        note_block_id="block-1",
        link_type="related",
        expected_links_revision=project.project.links_revision,
    )
    path = project_links_path(service.projects_dir)
    before = (path.read_bytes(), path.stat().st_mtime_ns)

    with pytest.raises(ProjectCommandConflict):
        service.remove_note_block_link(
            project.project.project_id,
            linked.link.link_id,
            expected_links_revision="0" * 64,
        )
    archived = service.archive_project(
        project.project.project_id,
        linked.project.project_revision,
    )
    with pytest.raises(ProjectArchivedConflict):
        service.remove_note_block_link(
            project.project.project_id,
            linked.link.link_id,
            expected_links_revision=archived.project.links_revision,
        )

    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_link_command_reloads_after_lock_and_detects_concurrent_revision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    project = service.create_project(name="Project")

    @contextmanager
    def concurrent_write(_root):
        create_project_link(
            project.project.project_id,
            "paper",
            "paper-2",
            base_dir=service.projects_dir,
        )
        yield

    monkeypatch.setattr(project_commands, "workspace_write_lock", concurrent_write)
    with pytest.raises(ProjectCommandConflict):
        service.add_note_block_link(
            project.project.project_id,
            paper_id="paper-1",
            note_block_id="block-1",
            link_type="related",
            expected_links_revision=project.project.links_revision,
        )

    assert [link["target_type"] for link in list_project_links(service.projects_dir)] == ["paper"]


def test_link_lock_failure_is_private_safe_and_non_mutating(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    project = service.create_project(name="Project")

    @contextmanager
    def unavailable(_root):
        raise WorkspaceLockUnavailable("C:/private/workspace")
        yield

    monkeypatch.setattr(project_commands, "workspace_write_lock", unavailable)
    with pytest.raises(ProjectCommandUnavailable) as error:
        service.add_note_block_link(
            project.project.project_id,
            paper_id="paper-1",
            note_block_id="block-1",
            link_type="related",
            expected_links_revision=project.project.links_revision,
        )

    assert str(error.value) == ""
    assert list_project_links(service.projects_dir) == []


def test_link_persistence_failure_restores_exact_bytes_and_timestamp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    project = service.create_project(name="Project")
    existing = create_project_link(
        project.project.project_id,
        "paper",
        "paper-2",
        base_dir=service.projects_dir,
    )
    path = project_links_path(service.projects_dir)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    from services.project_read_model import project_links_revision

    def write_then_fail(links, base_dir):
        path.write_text('[{"private":"intermediate"}]', encoding="utf-8")
        raise OSError("C:/private/project_links.json")

    monkeypatch.setattr(project_link_store, "save_project_links", write_then_fail)
    with pytest.raises(ProjectCommandUnavailable) as error:
        service.add_note_block_link(
            project.project.project_id,
            paper_id="paper-1",
            note_block_id="block-1",
            link_type="related",
            expected_links_revision=project_links_revision(
                project.project.project_id,
                [existing],
            ),
        )

    assert str(error.value) == ""
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
