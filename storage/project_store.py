from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from storage.atomic_json import atomic_write_json
from storage.paths import PROJECTS_DIR


ALLOWED_PROJECT_STATUSES = ("active", "paused", "done", "archived")
ALLOWED_PROJECT_PRIORITIES = ("low", "normal", "high")


def projects_path(base_dir: Path = PROJECTS_DIR) -> Path:
    return Path(base_dir) / "projects.json"


def list_projects(base_dir: Path = PROJECTS_DIR) -> list[dict[str, Any]]:
    path = projects_path(base_dir)
    if not path.exists():
        return []
    try:
        stored_projects = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Projects file is invalid JSON: {path}") from exc
    if not isinstance(stored_projects, list):
        raise ValueError(f"Projects file must contain a list: {path}")
    return [_normalize_project(project) for project in stored_projects]


def save_projects(
    projects: Sequence[Mapping[str, Any]],
    base_dir: Path = PROJECTS_DIR,
) -> Path:
    normalized_projects = [_normalize_project(project) for project in projects]
    project_ids = [project["id"] for project in normalized_projects]
    if len(project_ids) != len(set(project_ids)):
        raise ValueError("Project IDs must be unique.")

    path = projects_path(base_dir)
    return atomic_write_json(path, normalized_projects, indent=2, ensure_ascii=False)


def create_project(
    name: str,
    description: str = "",
    status: str = "active",
    priority: str = "normal",
    tags: object | None = None,
    base_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    timestamp = _utc_now_iso()
    project = _normalize_project(
        {
            "id": str(uuid4()),
            "name": name,
            "description": description,
            "status": status,
            "priority": priority,
            "tags": normalize_project_tags(tags),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    projects = list_projects(base_dir)
    projects.append(project)
    save_projects(projects, base_dir)
    return project


def get_project(project_id: str, base_dir: Path = PROJECTS_DIR) -> dict[str, Any] | None:
    for project in list_projects(base_dir):
        if project["id"] == project_id:
            return project
    return None


def update_project(
    project_id: str,
    updates: Mapping[str, Any],
    base_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    projects = list_projects(base_dir)
    for index, project in enumerate(projects):
        if project["id"] != project_id:
            continue
        updated = {**project, **dict(updates)}
        updated["id"] = project["id"]
        updated["created_at"] = project["created_at"]
        updated["updated_at"] = _utc_now_iso()
        normalized = _normalize_project(updated)
        projects[index] = normalized
        save_projects(projects, base_dir)
        return normalized
    raise KeyError(f"Project not found: {project_id}")


def delete_project(project_id: str, base_dir: Path = PROJECTS_DIR) -> bool:
    projects = list_projects(base_dir)
    remaining = [project for project in projects if project["id"] != project_id]
    if len(remaining) == len(projects):
        return False
    save_projects(remaining, base_dir)
    return True


def normalize_project_tags(tags: object | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        values: Iterable[object] = tags.split(",")
    elif isinstance(tags, Iterable):
        values = tags
    else:
        values = [tags]

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = str(value).strip()
        if tag and tag not in seen:
            normalized.append(tag)
            seen.add(tag)
    return normalized


def _normalize_project(project: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(project, Mapping):
        raise ValueError("Each project must be an object.")

    normalized = dict(project)
    normalized["id"] = _required_non_empty_string(project.get("id"), "id")
    normalized["name"] = _required_non_empty_string(project.get("name"), "name").strip()
    normalized["description"] = _required_string(project.get("description", ""), "description")
    normalized["status"] = _validated_choice(project.get("status"), "status", ALLOWED_PROJECT_STATUSES)
    normalized["priority"] = _validated_choice(
        project.get("priority"),
        "priority",
        ALLOWED_PROJECT_PRIORITIES,
    )
    normalized["tags"] = normalize_project_tags(project.get("tags"))
    created_at_value = project["created_at"] if "created_at" in project else _utc_now_iso()
    created_at = _required_string(created_at_value, "created_at")
    normalized["created_at"] = created_at
    normalized["updated_at"] = _required_string(project.get("updated_at", created_at), "updated_at")
    return normalized


def _validated_choice(value: Any, field: str, allowed: tuple[str, ...]) -> str:
    selected = _required_string(value, field)
    if selected not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
    return selected


def _required_non_empty_string(value: Any, field: str) -> str:
    text = _required_string(value, field)
    if not text.strip():
        raise ValueError(f"{field} must not be empty.")
    return text


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    return value


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
