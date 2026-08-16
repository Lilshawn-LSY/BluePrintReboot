from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from api import dependencies
from api.main import INVALID_REQUEST_DETAIL, create_app
from api.routes import PROJECT_COMMAND_UNAVAILABLE_DETAIL
from services import project_commands
from services.project_read_model import build_project_detail, build_project_list_items
from services.project_commands import (
    ProjectArchivedConflict,
    ProjectCommandConflict,
    ProjectCommandService,
    ProjectCommandUnavailable,
)
from storage import project_store
from storage.project_link_store import create_project_link, list_project_links
from storage.project_store import list_projects, projects_path
from storage.workspace_lock import WorkspaceLockUnavailable


def _service(tmp_path: Path) -> ProjectCommandService:
    return ProjectCommandService(
        projects_dir=tmp_path / "projects",
        index_csv=tmp_path / "data" / "paper_index.csv",
    )


def _client(service: ProjectCommandService) -> TestClient:
    application = create_app()
    application.dependency_overrides[dependencies.get_project_command_service] = (
        lambda: service
    )
    return TestClient(application)


def _file_evidence(path: Path) -> tuple[bytes, int]:
    return path.read_bytes(), path.stat().st_mtime_ns


def test_create_project_generates_identity_defaults_and_strict_result(tmp_path: Path) -> None:
    service = _service(tmp_path)

    response = _client(service).post("/projects", json={"name": "  Evidence map  "})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    project = body["project"]
    UUID(project["project_id"])
    assert project["name"] == "Evidence map"
    assert project["description"] == ""
    assert project["status"] == "active"
    assert project["priority"] == "normal"
    assert project["tags"] == []
    assert project["created_at"] == project["updated_at"]
    assert len(project["project_revision"]) == 64
    assert len(project["links_revision"]) == 64
    assert project["link_count"] == project["linked_paper_count"] == 0
    assert project["linked_note_block_count"] == 0
    assert set(list_projects(service.projects_dir)[0]) >= {
        "id",
        "created_at",
        "updated_at",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "x" * 201},
        {"name": "Valid", "status": "archived"},
        {"name": "Valid", "priority": "urgent"},
        {"name": "Valid", "tags": [""]},
        {"name": "Valid", "id": "client-controlled"},
        {"name": "Valid", "created_at": "client-controlled"},
        {"name": "Valid", "future_field": "unsupported"},
    ],
)
def test_create_validation_and_unknown_fields_are_generic_422(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    service = _service(tmp_path)

    response = _client(service).post("/projects", json=payload)

    assert response.status_code == 422
    assert response.json() == {"detail": INVALID_REQUEST_DETAIL}
    assert not projects_path(service.projects_dir).exists()


def test_update_is_allowlisted_revisioned_and_preserves_immutable_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    timestamps = iter(
        (
            "2026-07-27T00:00:00+00:00",
            "2026-07-27T00:00:01+00:00",
        )
    )
    monkeypatch.setattr(project_commands, "_utc_now_iso", lambda: next(timestamps))
    service = _service(tmp_path)
    created = service.create_project(name="Original")

    result = service.update_project(
        created.project.project_id,
        {
            "name": "Updated",
            "description": "Bounded description",
            "status": "paused",
            "priority": "high",
            "tags": ["methods", "methods", "evidence"],
        },
        created.project.project_revision,
    )

    assert result.status == "saved"
    assert result.project.name == "Updated"
    assert result.project.status == "paused"
    assert result.project.tags == ("methods", "evidence")
    assert result.project.created_at == created.project.created_at
    assert result.project.updated_at != created.project.updated_at
    assert result.project.project_id == created.project.project_id
    assert result.project.project_revision != created.project.project_revision


def test_metadata_update_survives_project_list_and_detail_reload(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Workspace metadata")

    updated = service.update_project(
        created.project.project_id,
        {"status": "paused", "priority": "high"},
        created.project.project_revision,
    )
    listing = build_project_list_items(projects_dir=service.projects_dir)
    detail = build_project_detail(
        created.project.project_id,
        projects_dir=service.projects_dir,
        index_csv=service.index_csv,
    )

    assert updated.status == "saved"
    assert [(item["status"], item["priority"]) for item in listing] == [("paused", "high")]
    assert detail is not None
    assert detail["status"] == "paused"
    assert detail["priority"] == "high"


def test_update_and_archive_routes_return_refreshed_strict_state(tmp_path: Path) -> None:
    service = _service(tmp_path)
    client = _client(service)
    created = client.post("/projects", json={"name": "API Project"}).json()["project"]

    updated_response = client.patch(
        f"/projects/{created['project_id']}",
        json={
            "changes": {
                "name": "API Updated",
                "description": "  intentionally spaced  ",
                "status": "done",
            },
            "expected_revision": created["project_revision"],
        },
    )
    assert updated_response.status_code == 200
    updated = updated_response.json()
    assert updated["status"] == "saved"
    assert updated["project"]["name"] == "API Updated"
    assert updated["project"]["description"] == "  intentionally spaced  "
    assert updated["project"]["status"] == "done"

    archived_response = client.post(
        f"/projects/{created['project_id']}/archive",
        json={"expected_revision": updated["project"]["project_revision"]},
    )
    assert archived_response.status_code == 200
    assert archived_response.json()["status"] == "archived"
    assert archived_response.json()["project"]["status"] == "archived"


def test_stale_and_archived_route_conflicts_are_controlled(tmp_path: Path) -> None:
    service = _service(tmp_path)
    client = _client(service)
    created = service.create_project(name="API conflict")
    current = service.update_project(
        created.project.project_id,
        {"priority": "high"},
        created.project.project_revision,
    )

    stale = client.patch(
        f"/projects/{created.project.project_id}",
        json={
            "changes": {"name": "Stale"},
            "expected_revision": created.project.project_revision,
        },
    )
    assert stale.status_code == 409
    assert "Reload" in stale.json()["detail"]

    archived = service.archive_project(
        created.project.project_id,
        current.project.project_revision,
    )
    blocked = client.patch(
        f"/projects/{created.project.project_id}",
        json={
            "changes": {"name": "Blocked"},
            "expected_revision": archived.project.project_revision,
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Archived Projects do not allow this command."


def test_update_rejects_immutable_and_archived_fields_without_mutation(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Original")
    path = projects_path(service.projects_dir)
    before = _file_evidence(path)

    for changes in (
        {"id": "replacement"},
        {"created_at": "replacement"},
        {"updated_at": "replacement"},
        {"status": "archived"},
        {"future": "field"},
    ):
        with pytest.raises(project_commands.ProjectCommandInvalid):
            service.update_project(
                created.project.project_id,
                changes,
                created.project.project_revision,
            )

    assert _file_evidence(path) == before


def test_no_op_is_deterministic_and_does_not_advance_timestamp_or_revision(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Stable", tags=["one"])
    path = projects_path(service.projects_dir)
    before = _file_evidence(path)

    result = service.update_project(
        created.project.project_id,
        {"name": "Stable", "tags": ["one"]},
        created.project.project_revision,
    )

    assert result.status == "no_op"
    assert result.project == created.project
    assert _file_evidence(path) == before


def test_stale_update_conflict_preserves_exact_bytes_and_mtime(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Original")
    saved = service.update_project(
        created.project.project_id,
        {"name": "Current"},
        created.project.project_revision,
    )
    path = projects_path(service.projects_dir)
    before = _file_evidence(path)

    with pytest.raises(ProjectCommandConflict):
        service.update_project(
            created.project.project_id,
            {"name": "Stale overwrite"},
            created.project.project_revision,
        )

    assert _file_evidence(path) == before
    assert list_projects(service.projects_dir)[0]["name"] == saved.project.name


def test_archive_is_one_way_idempotent_with_current_revision_and_preserves_links(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Archive safely")
    link = create_project_link(
        created.project.project_id,
        "paper",
        "orphan-paper",
        base_dir=service.projects_dir,
    )
    current_revision = project_commands.project_revision(
        list_projects(service.projects_dir)[0]
    )

    archived = service.archive_project(
        created.project.project_id,
        current_revision,
    )
    links_after = list_project_links(service.projects_dir)
    repeated = service.archive_project(
        created.project.project_id,
        archived.project.project_revision,
    )

    assert archived.status == "archived"
    assert archived.project.status == "archived"
    assert repeated.status == "already_archived"
    assert repeated.project == archived.project
    assert links_after == [link] == list_project_links(service.projects_dir)
    with pytest.raises(ProjectArchivedConflict):
        service.update_project(
            created.project.project_id,
            {"name": "Blocked"},
            archived.project.project_revision,
        )


def test_archive_with_stale_revision_is_conflict_and_zero_mutation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Archive conflict")
    current = service.update_project(
        created.project.project_id,
        {"priority": "high"},
        created.project.project_revision,
    )
    path = projects_path(service.projects_dir)
    before = _file_evidence(path)

    with pytest.raises(ProjectCommandConflict):
        service.archive_project(
            created.project.project_id,
            created.project.project_revision,
        )

    assert _file_evidence(path) == before
    assert current.project.status == "active"


def test_lock_contention_is_controlled_and_preserves_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Locked")
    path = projects_path(service.projects_dir)
    before = _file_evidence(path)

    @contextmanager
    def unavailable_lock(_root):
        raise WorkspaceLockUnavailable
        yield

    monkeypatch.setattr(project_commands, "workspace_write_lock", unavailable_lock)

    with pytest.raises(ProjectCommandUnavailable):
        service.update_project(
            created.project.project_id,
            {"name": "Must not save"},
            created.project.project_revision,
        )

    assert _file_evidence(path) == before


@pytest.mark.parametrize(
    "failure",
    ["serialization", "replace", "after_write", "verification_mismatch"],
)
def test_project_persistence_failures_restore_exact_bytes_and_mtime(
    tmp_path: Path,
    monkeypatch,
    failure: str,
) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Original")
    path = projects_path(service.projects_dir)
    before = _file_evidence(path)

    if failure == "serialization":
        monkeypatch.setattr(
            project_store,
            "save_projects",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                TypeError("private serialization detail")
            ),
        )
    elif failure == "replace":
        monkeypatch.setattr(
            "storage.atomic_text.os.replace",
            lambda *_args: (_ for _ in ()).throw(
                OSError("private replacement detail")
            ),
        )
    elif failure == "after_write":
        def write_then_fail(_projects, base_dir):
            projects_path(base_dir).write_text(
                '[{"private":"corrupt intermediate"}]',
                encoding="utf-8",
            )
            raise OSError("private post-write detail")

        monkeypatch.setattr(project_store, "save_projects", write_then_fail)
    else:
        original_save = project_store.save_projects

        def persist_different_valid_state(projects, base_dir):
            mismatched = [dict(project) for project in projects]
            mismatched[0]["description"] = "unexpected persisted value"
            return original_save(mismatched, base_dir)

        monkeypatch.setattr(
            project_store,
            "save_projects",
            persist_different_valid_state,
        )

    with pytest.raises(ProjectCommandUnavailable):
        service.update_project(
            created.project.project_id,
            {"name": "Never persisted"},
            created.project.project_revision,
        )

    assert _file_evidence(path) == before
    assert list_projects(service.projects_dir)[0]["name"] == "Original"


def test_command_failure_response_leaks_no_private_diagnostics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = _service(tmp_path)
    private_error = f"private failure at {tmp_path / 'projects' / 'projects.json'}"
    monkeypatch.setattr(
        service,
        "create_project",
        lambda **_kwargs: (_ for _ in ()).throw(
            ProjectCommandUnavailable(private_error)
        ),
    )

    response = _client(service).post("/projects", json={"name": "Safe request"})

    assert response.status_code == 503
    assert response.json() == {"detail": PROJECT_COMMAND_UNAVAILABLE_DETAIL}
    assert private_error not in response.text
    assert str(tmp_path) not in response.text
