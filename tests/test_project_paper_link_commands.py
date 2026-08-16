from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import dependencies
from api.main import INVALID_REQUEST_DETAIL, create_app
from services.project_commands import (
    ProjectArchivedConflict,
    ProjectCommandConflict,
    ProjectCommandNotFound,
    ProjectCommandService,
    ProjectCommandUnavailable,
)
from services.project_read_model import build_project_detail
from storage import project_link_store
from storage.project_link_store import (
    create_project_link,
    list_project_links,
    project_links_path,
)
from storage.project_store import projects_path


def _write_index(path: Path, paper_ids: tuple[str, ...] = ("paper-1", "paper-2")) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [{"paper_id": paper_id, "title": f"Title {paper_id}"} for paper_id in paper_ids]
    ).to_csv(path, index=False)


def _service(tmp_path: Path) -> ProjectCommandService:
    index_csv = tmp_path / "data" / "paper_index.csv"
    _write_index(index_csv)
    return ProjectCommandService(
        projects_dir=tmp_path / "projects",
        index_csv=index_csv,
    )


def _client(service: ProjectCommandService) -> TestClient:
    application = create_app()
    application.dependency_overrides[dependencies.get_project_command_service] = (
        lambda: service
    )
    return TestClient(application)


def _evidence(paths: list[Path]) -> dict[str, tuple[bytes, int]]:
    return {
        path.as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in paths
        if path.is_file()
    }


def test_add_paper_link_uses_server_identity_and_fixed_paper_target(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Link Project")

    result = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="key_reference",
        expected_links_revision=created.project.links_revision,
    )

    assert result.status == "created"
    UUID(result.link.link_id)
    assert result.link.project_id == created.project.project_id
    assert result.link.paper_id == "paper-1"
    assert result.link.link_type == "key_reference"
    assert result.project.link_count == result.project.linked_paper_count == 1
    assert result.project.linked_note_block_count == 0
    assert result.project.links_revision != created.project.links_revision
    stored = list_project_links(service.projects_dir)
    assert stored[0]["target_type"] == "paper"
    assert stored[0]["target_id"] == stored[0]["paper_id"] == "paper-1"
    assert stored[0]["note"] == ""


def test_links_revision_is_deterministic_and_visible_in_project_detail(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Revision")
    linked = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )

    detail_one = build_project_detail(
        created.project.project_id,
        projects_dir=service.projects_dir,
        index_csv=service.index_csv,
    )
    detail_two = build_project_detail(
        created.project.project_id,
        projects_dir=service.projects_dir,
        index_csv=service.index_csv,
    )

    assert detail_one is not None
    assert detail_two is not None
    assert detail_one["links_revision"] == linked.project.links_revision
    assert detail_two["links_revision"] == detail_one["links_revision"]
    assert detail_one["linked_paper_count"] == 1
    assert detail_one["linked_note_block_count"] == 0

    removed = service.remove_paper_link(
        created.project.project_id,
        linked.link.link_id,
        expected_links_revision=detail_one["links_revision"],
    )
    reloaded = build_project_detail(
        created.project.project_id,
        projects_dir=service.projects_dir,
        index_csv=service.index_csv,
    )

    assert removed.status == "removed"
    assert reloaded is not None
    assert reloaded["links"] == []
    assert reloaded["linked_paper_count"] == 0
    assert reloaded["link_count"] == 0


def test_duplicate_exact_add_returns_unchanged_without_duplicate_or_write(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Duplicate")
    first = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )
    path = project_links_path(service.projects_dir)
    before = _evidence([path])

    duplicate = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=first.project.links_revision,
    )

    assert duplicate.status == "unchanged"
    assert duplicate.link == first.link
    assert duplicate.project.links_revision == first.project.links_revision
    assert len(list_project_links(service.projects_dir)) == 1
    assert _evidence([path]) == before


def test_same_paper_with_different_allowed_link_type_is_distinct(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Two meanings")
    first = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )
    second = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="background",
        expected_links_revision=first.project.links_revision,
    )

    assert second.status == "created"
    assert second.link.link_id != first.link.link_id
    assert second.project.linked_paper_count == 2
    assert second.project.linked_note_block_count == 0


def test_paper_link_add_and_remove_routes_return_refreshed_revisions(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="API links")
    client = _client(service)

    added_response = client.post(
        f"/projects/{created.project.project_id}/paper-links",
        json={
            "paper_id": "paper-1",
            "link_type": "supports_project",
            "expected_links_revision": created.project.links_revision,
        },
    )
    assert added_response.status_code == 200
    added = added_response.json()
    assert added["status"] == "created"
    assert added["link"]["paper_id"] == "paper-1"
    assert added["project"]["linked_paper_count"] == 1
    assert added["project"]["linked_note_block_count"] == 0

    removed_response = client.request(
        "DELETE",
        (
            f"/projects/{created.project.project_id}/paper-links/"
            f"{added['link']['link_id']}"
        ),
        json={
            "expected_links_revision": added["project"]["links_revision"],
        },
    )
    assert removed_response.status_code == 200
    removed = removed_response.json()
    assert removed["status"] == "removed"
    assert removed["project"]["linked_paper_count"] == 0
    assert removed["project"]["linked_note_block_count"] == 0


def test_paper_link_route_not_found_and_stale_conflicts_are_controlled(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="API link conflicts")
    client = _client(service)

    missing = client.post(
        f"/projects/{created.project.project_id}/paper-links",
        json={
            "paper_id": "missing",
            "link_type": "related",
            "expected_links_revision": created.project.links_revision,
        },
    )
    assert missing.status_code == 404
    assert "paper link" in missing.json()["detail"].casefold()

    linked = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )
    stale = client.post(
        f"/projects/{created.project.project_id}/paper-links",
        json={
            "paper_id": "paper-2",
            "link_type": "related",
            "expected_links_revision": created.project.links_revision,
        },
    )
    assert stale.status_code == 409
    assert len(list_project_links(service.projects_dir)) == linked.project.link_count


def test_add_rejects_unknown_project_paper_and_archived_project(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Validation")

    with pytest.raises(ProjectCommandNotFound):
        service.add_paper_link(
            "unknown-project",
            paper_id="paper-1",
            link_type="related",
            expected_links_revision=created.project.links_revision,
        )
    with pytest.raises(ProjectCommandNotFound):
        service.add_paper_link(
            created.project.project_id,
            paper_id="unknown-paper",
            link_type="related",
            expected_links_revision=created.project.links_revision,
        )
    archived = service.archive_project(
        created.project.project_id,
        created.project.project_revision,
    )
    with pytest.raises(ProjectArchivedConflict):
        service.add_paper_link(
            created.project.project_id,
            paper_id="paper-1",
            link_type="related",
            expected_links_revision=archived.project.links_revision,
        )
    assert list_project_links(service.projects_dir) == []


def test_stale_add_conflict_has_zero_mutation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Stale add")
    current = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )
    path = project_links_path(service.projects_dir)
    before = _evidence([path])

    with pytest.raises(ProjectCommandConflict):
        service.add_paper_link(
            created.project.project_id,
            paper_id="paper-2",
            link_type="related",
            expected_links_revision=created.project.links_revision,
        )

    assert _evidence([path]) == before
    assert current.project.link_count == 1


def test_remove_paper_link_changes_only_link_storage(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Unlink only")
    linked = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )
    pdf = tmp_path / "papers" / "paper-1.pdf"
    note = tmp_path / "notes" / "paper-1.md"
    pdf.parent.mkdir(parents=True)
    note.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4 private paper bytes")
    note.write_text("# private note", encoding="utf-8")
    protected = [
        service.index_csv,
        pdf,
        note,
        projects_path(service.projects_dir),
    ]
    before = _evidence(protected)

    removed = service.remove_paper_link(
        created.project.project_id,
        linked.link.link_id,
        expected_links_revision=linked.project.links_revision,
    )

    assert removed.status == "removed"
    assert removed.link == linked.link
    assert removed.project.link_count == removed.project.linked_paper_count == 0
    assert removed.project.linked_note_block_count == 0
    assert list_project_links(service.projects_dir) == []
    assert _evidence(protected) == before


def test_remove_existing_orphaned_paper_link_is_allowed(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Orphan cleanup")
    orphan = create_project_link(
        created.project.project_id,
        "paper",
        "paper-no-longer-indexed",
        base_dir=service.projects_dir,
    )
    detail = build_project_detail(
        created.project.project_id,
        projects_dir=service.projects_dir,
        index_csv=service.index_csv,
    )
    assert detail is not None

    removed = service.remove_paper_link(
        created.project.project_id,
        orphan["id"],
        expected_links_revision=detail["links_revision"],
    )

    assert removed.status == "removed"
    assert removed.link.paper_id == "paper-no-longer-indexed"
    assert list_project_links(service.projects_dir) == []


def test_archived_project_rejects_paper_unlink_without_mutation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Archived links")
    linked = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )
    archived = service.archive_project(
        created.project.project_id,
        created.project.project_revision,
    )
    path = project_links_path(service.projects_dir)
    before = _evidence([path])

    with pytest.raises(ProjectArchivedConflict):
        service.remove_paper_link(
            created.project.project_id,
            linked.link.link_id,
            expected_links_revision=archived.project.links_revision,
        )

    response = _client(service).request(
        "DELETE",
        f"/projects/{created.project.project_id}/paper-links/{linked.link.link_id}",
        json={"expected_links_revision": archived.project.links_revision},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Archived Projects do not allow this command."
    assert _evidence([path]) == before


def test_remove_rejects_unknown_cross_project_and_note_block_links(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    first = service.create_project(name="First")
    second = service.create_project(name="Second")
    paper_link = create_project_link(
        second.project.project_id,
        "paper",
        "paper-1",
        base_dir=service.projects_dir,
    )
    note_block_link = create_project_link(
        first.project.project_id,
        "note_block",
        "block-1",
        paper_id="paper-1",
        base_dir=service.projects_dir,
    )
    detail = build_project_detail(
        first.project.project_id,
        projects_dir=service.projects_dir,
        index_csv=service.index_csv,
    )
    assert detail is not None
    before = list_project_links(service.projects_dir)

    for link_id in ("unknown", paper_link["id"], note_block_link["id"]):
        with pytest.raises(ProjectCommandNotFound):
            service.remove_paper_link(
                first.project.project_id,
                link_id,
                expected_links_revision=detail["links_revision"],
            )

    assert list_project_links(service.projects_dir) == before


def test_stale_remove_conflict_preserves_link_bytes_and_mtime(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Stale remove")
    first = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )
    current = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-2",
        link_type="related",
        expected_links_revision=first.project.links_revision,
    )
    path = project_links_path(service.projects_dir)
    before = _evidence([path])

    with pytest.raises(ProjectCommandConflict):
        service.remove_paper_link(
            created.project.project_id,
            first.link.link_id,
            expected_links_revision=first.project.links_revision,
        )

    assert current.project.link_count == 2
    assert _evidence([path]) == before


def test_injected_link_write_failure_restores_original_bytes_and_mtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Rollback links")
    linked = service.add_paper_link(
        created.project.project_id,
        paper_id="paper-1",
        link_type="related",
        expected_links_revision=created.project.links_revision,
    )
    path = project_links_path(service.projects_dir)
    before = _evidence([path])

    def write_then_fail(_links, base_dir):
        project_links_path(base_dir).write_text(
            '[{"private":"intermediate"}]',
            encoding="utf-8",
        )
        raise OSError("private link write failure")

    monkeypatch.setattr(project_link_store, "save_project_links", write_then_fail)

    with pytest.raises(ProjectCommandUnavailable):
        service.remove_paper_link(
            created.project.project_id,
            linked.link.link_id,
            expected_links_revision=linked.project.links_revision,
        )

    assert _evidence([path]) == before
    assert len(list_project_links(service.projects_dir)) == 1


def test_link_verification_mismatch_removes_new_file_and_fails_safely(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Verify links")
    path = project_links_path(service.projects_dir)
    assert not path.exists()
    original_save = project_link_store.save_project_links

    def persist_different_valid_state(links, base_dir):
        mismatched = [dict(link) for link in links]
        mismatched[-1]["note"] = "unexpected persisted value"
        return original_save(mismatched, base_dir)

    monkeypatch.setattr(
        project_link_store,
        "save_project_links",
        persist_different_valid_state,
    )

    with pytest.raises(ProjectCommandUnavailable):
        service.add_paper_link(
            created.project.project_id,
            paper_id="paper-1",
            link_type="related",
            expected_links_revision=created.project.links_revision,
        )

    assert not path.exists()
    assert list_project_links(service.projects_dir) == []


@pytest.mark.parametrize(
    "method,path,payload",
    [
        (
            "post",
            "/projects/project/paper-links",
            {
                "paper_id": "paper-1",
                "link_type": "related",
                "expected_links_revision": "0" * 64,
                "target_type": "note_block",
            },
        ),
        (
            "delete",
            "/projects/project/paper-links/link",
            {
                "expected_links_revision": "0" * 64,
                "target_type": "note_block",
            },
        ),
    ],
)
def test_paper_routes_reject_any_note_block_or_arbitrary_target_fields(
    tmp_path: Path,
    method: str,
    path: str,
    payload: dict[str, object],
) -> None:
    response = _client(_service(tmp_path)).request(
        method.upper(),
        path,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": INVALID_REQUEST_DETAIL}
    assert "note_block" not in response.text
