import json

import pytest

from storage.project_store import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    projects_path,
    save_projects,
    update_project,
)
from tests.helpers import make_workspace


PROJECT_FIELDS = {
    "id",
    "name",
    "description",
    "status",
    "priority",
    "tags",
    "created_at",
    "updated_at",
}


def test_missing_projects_file_returns_empty_list() -> None:
    base_dir = make_workspace("projects-missing")

    assert list_projects(base_dir) == []
    assert not projects_path(base_dir).exists()


def test_create_project_writes_valid_schema() -> None:
    base_dir = make_workspace("projects-create") / "projects"

    project = create_project(
        "Root Development",
        description="Collect evidence about root development.",
        status="active",
        priority="high",
        tags=["roots", "development"],
        base_dir=base_dir,
    )

    assert PROJECT_FIELDS <= set(project)
    assert project["id"]
    assert project["name"] == "Root Development"
    assert project["created_at"] == project["updated_at"]
    assert json.loads(projects_path(base_dir).read_text(encoding="utf-8")) == [project]


def test_update_project_preserves_identity_and_updates_fields(monkeypatch) -> None:
    base_dir = make_workspace("projects-update")
    timestamps = iter(("2026-06-20T00:00:00+00:00", "2026-06-20T00:00:01+00:00"))
    monkeypatch.setattr("storage.project_store._utc_now_iso", lambda: next(timestamps))
    project = create_project("Original", base_dir=base_dir)

    updated = update_project(
        project["id"],
        {
            "id": "replacement",
            "created_at": "replacement",
            "name": "Updated",
            "description": "Updated description",
            "status": "paused",
            "priority": "high",
            "tags": " biology, evidence, biology ",
        },
        base_dir=base_dir,
    )

    assert updated["id"] == project["id"]
    assert updated["created_at"] == project["created_at"]
    assert updated["updated_at"] != project["updated_at"]
    assert updated["name"] == "Updated"
    assert updated["description"] == "Updated description"
    assert updated["status"] == "paused"
    assert updated["priority"] == "high"
    assert updated["tags"] == ["biology", "evidence"]
    assert get_project(project["id"], base_dir) == updated


@pytest.mark.parametrize(
    ("field", "value"),
    (("status", "unknown"), ("priority", "urgent")),
)
def test_invalid_project_choices_are_rejected(field, value) -> None:
    base_dir = make_workspace(f"projects-invalid-{field}")
    kwargs = {field: value, "base_dir": base_dir}

    with pytest.raises(ValueError, match=field):
        create_project("Project", **kwargs)


def test_empty_project_name_is_rejected() -> None:
    base_dir = make_workspace("projects-empty-name")

    with pytest.raises(ValueError, match="name"):
        create_project("   ", base_dir=base_dir)


def test_update_missing_project_does_not_create_project() -> None:
    base_dir = make_workspace("projects-update-missing")

    with pytest.raises(KeyError):
        update_project("missing", {"name": "No project"}, base_dir=base_dir)

    assert list_projects(base_dir) == []


def test_delete_project_is_safe_and_removes_project() -> None:
    base_dir = make_workspace("projects-delete")
    project = create_project("Delete me", base_dir=base_dir)

    assert delete_project(project["id"], base_dir) is True
    assert list_projects(base_dir) == []
    assert delete_project("missing", base_dir) is False


def test_project_tags_are_normalized_to_strings() -> None:
    base_dir = make_workspace("projects-tags")

    project = create_project(
        "Tagged",
        tags=[" roots ", 42, "", "roots"],
        base_dir=base_dir,
    )

    assert project["tags"] == ["roots", "42"]


def test_save_projects_serialization_failure_preserves_existing_file() -> None:
    base_dir = make_workspace("projects-atomic-serialization")
    project = create_project("Existing", base_dir=base_dir)
    path = projects_path(base_dir)
    before = path.read_bytes()

    with pytest.raises(TypeError):
        save_projects([{**project, "future_field": object()}], base_dir=base_dir)

    assert path.read_bytes() == before
    assert list_projects(base_dir) == [project]


def test_save_projects_replace_failure_preserves_existing_file_and_cleans_temp(monkeypatch) -> None:
    base_dir = make_workspace("projects-atomic-replace")
    project = create_project("Existing", base_dir=base_dir)
    path = projects_path(base_dir)
    before = path.read_bytes()

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr("storage.atomic_json.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        save_projects([{**project, "name": "Updated"}], base_dir=base_dir)

    assert path.read_bytes() == before
    assert list_projects(base_dir) == [project]
    assert sorted(item.name for item in base_dir.iterdir()) == ["projects.json"]
