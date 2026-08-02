from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from api import dependencies
from api.main import INVALID_REQUEST_DETAIL, UNAVAILABLE_DETAIL, create_app
from api.routes import NOTE_BLOCK_COMMAND_UNAVAILABLE_DETAIL
from services.note_block_commands import (
    NoteBlockCommandService,
    NoteBlockCommandUnavailable,
)
from services.note_block_read_model import build_note_block_collection, note_blocks_revision
from services.project_commands import ProjectCommandService, ProjectCommandUnavailable
from storage.note_block_store import note_blocks_path


def _setup(tmp_path: Path) -> tuple[NoteBlockCommandService, TestClient]:
    index_csv = tmp_path / "data" / "paper_index.csv"
    index_csv.parent.mkdir(parents=True)
    pd.DataFrame([{"paper_id": "paper-1", "title": "Paper"}]).to_csv(index_csv, index=False)
    note_blocks_dir = tmp_path / "data" / "note_blocks"
    projects_dir = tmp_path / "data" / "projects"
    service = NoteBlockCommandService(note_blocks_dir=note_blocks_dir, index_csv=index_csv)
    application = create_app()
    application.dependency_overrides[dependencies.get_note_block_command_service] = lambda: service
    application.dependency_overrides[dependencies.get_note_block_collection] = lambda: build_note_block_collection(
        "paper-1",
        index_csv=index_csv,
        note_blocks_dir=note_blocks_dir,
        projects_dir=projects_dir,
    )
    return service, TestClient(application)


def _payload(revision: str) -> dict[str, object]:
    return {
        "block_type": "summary",
        "title": "Title",
        "text": "Text",
        "page": "1",
        "figure": "",
        "quote": "",
        "tags": ["one"],
        "expected_revision": revision,
    }


def _setup_project_links(
    tmp_path: Path,
) -> tuple[NoteBlockCommandService, ProjectCommandService, TestClient]:
    note_service, client = _setup(tmp_path)
    project_service = ProjectCommandService(
        projects_dir=tmp_path / "data" / "projects",
        index_csv=note_service.index_csv,
        note_blocks_dir=note_service.note_blocks_dir,
    )
    client.app.dependency_overrides[dependencies.get_project_command_service] = (
        lambda: project_service
    )
    return note_service, project_service, client


def test_get_create_update_routes_are_typed_and_revisioned(tmp_path: Path) -> None:
    service, client = _setup(tmp_path)
    empty = client.get("/papers/paper-1/note-blocks")
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    created = client.post(
        "/papers/paper-1/note-blocks",
        json=_payload(note_blocks_revision("paper-1", [])),
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["status"] == "created"
    assert set(created_body["block"]) == {
        "id", "paper_id", "block_type", "title", "text", "page", "figure",
        "quote", "tags", "created_at", "updated_at",
    }

    updated = client.patch(
        f"/papers/paper-1/note-blocks/{created_body['block']['id']}",
        json={
            "changes": {"text": "Updated"},
            "expected_revision": created_body["note_blocks_revision"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["block"]["text"] == "Updated"
    assert len(service._load("paper-1")) == 1


def test_strict_requests_reject_server_owned_unknown_and_malformed_values(tmp_path: Path) -> None:
    _service, client = _setup(tmp_path)
    revision = note_blocks_revision("paper-1", [])
    for extra in (
        {"id": "client-owned"},
        {"paper_id": "client-owned"},
        {"created_at": "client-owned"},
        {"updated_at": "client-owned"},
        {"private_field": "client-owned"},
    ):
        response = client.post(
            "/papers/paper-1/note-blocks",
            json={**_payload(revision), **extra},
        )
        assert response.status_code == 422
        assert response.json() == {"detail": INVALID_REQUEST_DETAIL}
    assert client.post(
        "/papers/paper-1/note-blocks",
        content="not-json",
        headers={"Content-Type": "application/json"},
    ).json() == {"detail": INVALID_REQUEST_DETAIL}


def test_api_errors_are_generic_and_do_not_echo_private_values(tmp_path: Path, monkeypatch) -> None:
    service, client = _setup(tmp_path)

    def unavailable(*_args, **_kwargs):
        raise NoteBlockCommandUnavailable("C:/private/paper.json raw exception")

    monkeypatch.setattr(service, "create_note_block", unavailable)
    response = client.post(
        "/papers/paper-1/note-blocks",
        json=_payload(note_blocks_revision("paper-1", [])),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": NOTE_BLOCK_COMMAND_UNAVAILABLE_DETAIL}
    assert "private" not in response.text


def test_note_block_command_statuses_and_methods_are_private_safe(tmp_path: Path) -> None:
    _service, client = _setup(tmp_path)
    revision = note_blocks_revision("paper-1", [])

    stale = client.post("/papers/paper-1/note-blocks", json=_payload("0" * 64))
    missing = client.post("/papers/missing/note-blocks", json=_payload(revision))
    invalid = client.post(
        "/papers/paper-1/note-blocks",
        json={**_payload(revision), "block_type": "private-invalid"},
    )
    non_json = client.post(
        "/papers/paper-1/note-blocks",
        content="private body",
        headers={"Content-Type": "text/plain"},
    )

    assert stale.status_code == 409
    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert non_json.status_code == 422
    assert all("private" not in response.text for response in (stale, missing, invalid, non_json))
    assert client.put("/papers/paper-1/note-blocks", json=_payload(revision)).status_code == 405
    assert client.get("/papers/paper-1/note-blocks/extra/path").status_code == 404


def test_project_note_block_link_api_add_duplicate_and_unlink(tmp_path: Path) -> None:
    note_service, project_service, client = _setup_project_links(tmp_path)
    block = note_service.create_note_block(
        "paper-1",
        {key: value for key, value in _payload(note_blocks_revision("paper-1", [])).items() if key != "expected_revision"},
        note_blocks_revision("paper-1", []),
    )
    project = project_service.create_project(name="Project")
    payload = {
        "paper_id": "paper-1",
        "note_block_id": block.block["id"],
        "link_type": "related",
        "expected_links_revision": project.project.links_revision,
    }
    created = client.post(
        f"/projects/{project.project.project_id}/note-block-links",
        json=payload,
    )
    assert created.status_code == 200
    assert created.json()["status"] == "created"
    duplicate = client.post(
        f"/projects/{project.project.project_id}/note-block-links",
        json={
            **payload,
            "expected_links_revision": created.json()["project"]["links_revision"],
        },
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "unchanged"
    note_path = note_blocks_path("paper-1", note_service.note_blocks_dir)
    note_before = note_path.read_bytes()
    removed = client.request(
        "DELETE",
        f"/projects/{project.project.project_id}/note-block-links/{created.json()['link']['link_id']}",
        json={"expected_links_revision": duplicate.json()["project"]["links_revision"]},
    )
    assert removed.status_code == 200
    assert removed.json()["status"] == "removed"
    assert note_path.read_bytes() == note_before


def test_project_note_block_link_api_errors_are_generic(tmp_path: Path, monkeypatch) -> None:
    _note_service, project_service, client = _setup_project_links(tmp_path)
    project = project_service.create_project(name="Project")
    path = f"/projects/{project.project.project_id}/note-block-links"
    missing = client.post(
        path,
        json={
            "paper_id": "paper-1",
            "note_block_id": "missing-private-block",
            "link_type": "related",
            "expected_links_revision": project.project.links_revision,
        },
    )
    invalid = client.post(
        path,
        json={
            "paper_id": "paper-1",
            "note_block_id": "block",
            "link_type": "related",
            "expected_links_revision": project.project.links_revision,
            "private_path": "C:/private",
        },
    )

    def unavailable(*_args, **_kwargs):
        raise ProjectCommandUnavailable("C:/private/project_links.json")

    monkeypatch.setattr(project_service, "add_note_block_link", unavailable)
    unavailable_response = client.post(
        path,
        json={
            "paper_id": "paper-1",
            "note_block_id": "block",
            "link_type": "related",
            "expected_links_revision": project.project.links_revision,
        },
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert unavailable_response.status_code == 503
    assert all("C:/private" not in response.text for response in (missing, invalid, unavailable_response))


def test_note_block_read_distinguishes_missing_and_private_safe_unavailable(
    monkeypatch,
) -> None:
    client = TestClient(create_app())
    monkeypatch.setattr(
        dependencies.note_block_read_model,
        "build_note_block_collection",
        lambda _paper_id: None,
    )
    missing = client.get("/papers/missing/note-blocks")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Paper not found."}

    def unavailable(_paper_id):
        raise OSError("C:/private/note_blocks/paper.json")

    monkeypatch.setattr(
        dependencies.note_block_read_model,
        "build_note_block_collection",
        unavailable,
    )
    response = client.get("/papers/paper-1/note-blocks")
    assert response.status_code == 503
    assert response.json() == {"detail": UNAVAILABLE_DETAIL}
    assert "private" not in response.text
