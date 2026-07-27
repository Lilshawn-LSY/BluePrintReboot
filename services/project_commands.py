from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping
from uuid import uuid4

from services.project_read_model import project_links_revision, project_revision
from storage import project_link_store, project_store
from storage.atomic_text import atomic_write_text
from storage.index_store import read_index_snapshot
from storage.paths import INDEX_CSV, PROJECTS_DIR
from storage.workspace_lock import WorkspaceLockUnavailable, workspace_write_lock


MAX_PROJECT_NAME_LENGTH = 200
MAX_PROJECT_DESCRIPTION_LENGTH = 5_000
MAX_PROJECT_TAGS = 25
MAX_PROJECT_TAG_LENGTH = 100
PROJECT_UPDATE_FIELDS = frozenset({"name", "description", "status", "priority", "tags"})
COMMAND_PROJECT_STATUSES = frozenset({"active", "paused", "done"})


class ProjectCommandError(Exception):
    """Base class for controlled Project command failures."""


class ProjectCommandInvalid(ProjectCommandError):
    """The submitted command contains unsupported or invalid values."""


class ProjectCommandConflict(ProjectCommandError):
    """The caller's optimistic-concurrency baseline is stale."""


class ProjectArchivedConflict(ProjectCommandConflict):
    """The requested mutation is not supported for an archived Project."""


class ProjectCommandNotFound(ProjectCommandError):
    """A requested Project, Paper, or Paper link is unknown."""


class ProjectCommandUnavailable(ProjectCommandError):
    """The persistent command could not complete consistently."""


@dataclass(frozen=True)
class ProjectCommandState:
    project_id: str
    name: str
    description: str
    status: str
    priority: str
    tags: tuple[str, ...]
    created_at: str
    updated_at: str
    project_revision: str
    links_revision: str
    link_count: int
    linked_paper_count: int


@dataclass(frozen=True)
class PaperLinkCommandState:
    link_id: str
    project_id: str
    paper_id: str
    link_type: str
    created_at: str


@dataclass(frozen=True)
class ProjectCommandResult:
    status: Literal["created", "saved", "no_op", "archived", "already_archived"]
    project: ProjectCommandState


@dataclass(frozen=True)
class PaperLinkCommandResult:
    status: Literal["created", "unchanged", "removed"]
    project: ProjectCommandState
    link: PaperLinkCommandState


@dataclass(frozen=True)
class _FileSnapshot:
    exists: bool
    content: bytes
    accessed_ns: int
    modified_ns: int


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required_text(value: object, field_name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ProjectCommandInvalid(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ProjectCommandInvalid(f"{field_name} must not be empty.")
    if len(normalized) > maximum:
        raise ProjectCommandInvalid(f"{field_name} is too long.")
    return normalized


def _description(value: object) -> str:
    if not isinstance(value, str):
        raise ProjectCommandInvalid("description must be a string.")
    if len(value) > MAX_PROJECT_DESCRIPTION_LENGTH:
        raise ProjectCommandInvalid("description is too long.")
    return value


def _choice(value: object, field_name: str, allowed: frozenset[str] | tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ProjectCommandInvalid(f"{field_name} is unsupported.")
    return value


def _tags(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ProjectCommandInvalid("tags must be a list.")
    if len(value) > MAX_PROJECT_TAGS:
        raise ProjectCommandInvalid("tags contains too many values.")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        tag = _required_text(item, "tag", MAX_PROJECT_TAG_LENGTH)
        if tag not in seen:
            normalized.append(tag)
            seen.add(tag)
    return normalized


def _normalized_create(
    *,
    name: object,
    description: object,
    status: object,
    priority: object,
    tags: object,
) -> dict[str, Any]:
    return {
        "name": _required_text(name, "name", MAX_PROJECT_NAME_LENGTH),
        "description": _description(description),
        "status": _choice(status, "status", COMMAND_PROJECT_STATUSES),
        "priority": _choice(
            priority,
            "priority",
            project_store.ALLOWED_PROJECT_PRIORITIES,
        ),
        "tags": _tags(tags),
    }


def _normalized_updates(changes: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(changes, Mapping) or not changes:
        raise ProjectCommandInvalid("At least one Project change is required.")
    if set(changes) - PROJECT_UPDATE_FIELDS:
        raise ProjectCommandInvalid("The Project update contains an unsupported field.")
    normalized: dict[str, Any] = {}
    for field_name, value in changes.items():
        if field_name == "name":
            normalized[field_name] = _required_text(
                value,
                "name",
                MAX_PROJECT_NAME_LENGTH,
            )
        elif field_name == "description":
            normalized[field_name] = _description(value)
        elif field_name == "status":
            normalized[field_name] = _choice(
                value,
                "status",
                COMMAND_PROJECT_STATUSES,
            )
        elif field_name == "priority":
            normalized[field_name] = _choice(
                value,
                "priority",
                project_store.ALLOWED_PROJECT_PRIORITIES,
            )
        elif field_name == "tags":
            normalized[field_name] = _tags(value)
    return normalized


def _workspace_root(projects_dir: Path, index_csv: Path) -> Path:
    project_root = Path(projects_dir).resolve(strict=False).parent
    index_path = Path(index_csv).resolve(strict=False)
    index_root = (
        index_path.parent.parent
        if index_path.parent.name.casefold() == "data"
        else index_path.parent
    )
    try:
        return Path(os.path.commonpath((str(project_root), str(index_root))))
    except ValueError:
        return project_root


@contextmanager
def _persistent_command_lock(projects_dir: Path, index_csv: Path):
    try:
        with workspace_write_lock(_workspace_root(projects_dir, index_csv)):
            yield
    except WorkspaceLockUnavailable:
        raise ProjectCommandUnavailable from None


def _snapshot_file(path: Path) -> _FileSnapshot:
    target = Path(path)
    if not target.exists():
        return _FileSnapshot(False, b"", 0, 0)
    if not target.is_file():
        raise ProjectCommandUnavailable
    content = target.read_bytes()
    stat = target.stat()
    return _FileSnapshot(
        True,
        content,
        stat.st_atime_ns,
        stat.st_mtime_ns,
    )


def _restore_file(path: Path, snapshot: _FileSnapshot) -> None:
    target = Path(path)
    if not snapshot.exists:
        if target.exists():
            target.unlink()
        return
    current = target.read_bytes() if target.is_file() else None
    if current != snapshot.content:
        atomic_write_text(target, snapshot.content.decode("utf-8"))
    os.utime(
        target,
        ns=(snapshot.accessed_ns, snapshot.modified_ns),
    )


def _rollback(path: Path, snapshot: _FileSnapshot) -> None:
    try:
        _restore_file(path, snapshot)
    except Exception:
        raise ProjectCommandUnavailable from None


def _find_project(
    projects: list[dict[str, Any]],
    project_id: str,
) -> dict[str, Any]:
    project = next(
        (item for item in projects if str(item.get("id", "")) == project_id),
        None,
    )
    if project is None:
        raise ProjectCommandNotFound
    return project


def _project_state(
    project: Mapping[str, Any],
    links: list[Mapping[str, Any]],
) -> ProjectCommandState:
    project_id = str(project["id"])
    matching_links = [
        link
        for link in links
        if str(link.get("project_id", "")) == project_id
    ]
    return ProjectCommandState(
        project_id=project_id,
        name=str(project["name"]),
        description=str(project["description"]),
        status=str(project["status"]),
        priority=str(project["priority"]),
        tags=tuple(str(tag) for tag in project["tags"]),
        created_at=str(project["created_at"]),
        updated_at=str(project["updated_at"]),
        project_revision=project_revision(project),
        links_revision=project_links_revision(project_id, links),
        link_count=len(matching_links),
        linked_paper_count=sum(
            str(link.get("target_type", "")) == "paper"
            for link in matching_links
        ),
    )


def _paper_link_state(link: Mapping[str, Any]) -> PaperLinkCommandState:
    return PaperLinkCommandState(
        link_id=str(link["id"]),
        project_id=str(link["project_id"]),
        paper_id=str(link["paper_id"]),
        link_type=str(link["link_type"]),
        created_at=str(link["created_at"]),
    )


class ProjectCommandService:
    """Locked, optimistic, atomic command boundary for Projects and Paper links."""

    def __init__(
        self,
        *,
        projects_dir: Path = PROJECTS_DIR,
        index_csv: Path = INDEX_CSV,
    ) -> None:
        self.projects_dir = Path(projects_dir)
        self.index_csv = Path(index_csv)

    def _load(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            projects = project_store.list_projects(self.projects_dir)
            links = project_link_store.list_project_links(self.projects_dir)
        except Exception:
            raise ProjectCommandUnavailable from None
        return projects, links

    def _persist_projects(
        self,
        projects: list[dict[str, Any]],
        *,
        expected_project_id: str,
    ) -> list[dict[str, Any]]:
        path = project_store.projects_path(self.projects_dir)
        try:
            before = _snapshot_file(path)
        except Exception:
            raise ProjectCommandUnavailable from None
        try:
            project_store.save_projects(projects, self.projects_dir)
            persisted = project_store.list_projects(self.projects_dir)
            if persisted != projects:
                raise ProjectCommandUnavailable
            _find_project(persisted, expected_project_id)
            return persisted
        except Exception:
            _rollback(path, before)
            raise ProjectCommandUnavailable from None

    def _persist_links(
        self,
        links: list[dict[str, Any]],
        *,
        expected_link_id: str | None,
        removed_link_id: str | None = None,
    ) -> list[dict[str, Any]]:
        path = project_link_store.project_links_path(self.projects_dir)
        try:
            before = _snapshot_file(path)
        except Exception:
            raise ProjectCommandUnavailable from None
        try:
            project_link_store.save_project_links(links, self.projects_dir)
            persisted = project_link_store.list_project_links(self.projects_dir)
            if persisted != links:
                raise ProjectCommandUnavailable
            persisted_ids = {str(link.get("id", "")) for link in persisted}
            if expected_link_id is not None and expected_link_id not in persisted_ids:
                raise ProjectCommandUnavailable
            if removed_link_id is not None and removed_link_id in persisted_ids:
                raise ProjectCommandUnavailable
            return persisted
        except Exception:
            _rollback(path, before)
            raise ProjectCommandUnavailable from None

    def create_project(
        self,
        *,
        name: str,
        description: str = "",
        status: str = "active",
        priority: str = "normal",
        tags: list[str] | None = None,
    ) -> ProjectCommandResult:
        values = _normalized_create(
            name=name,
            description=description,
            status=status,
            priority=priority,
            tags=[] if tags is None else tags,
        )
        with _persistent_command_lock(self.projects_dir, self.index_csv):
            projects, links = self._load()
            timestamp = _utc_now_iso()
            project = {
                "id": str(uuid4()),
                **values,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            persisted = self._persist_projects(
                [*projects, project],
                expected_project_id=project["id"],
            )
            created = _find_project(persisted, project["id"])
            return ProjectCommandResult(
                status="created",
                project=_project_state(created, links),
            )

    def update_project(
        self,
        project_id: str,
        changes: Mapping[str, Any],
        expected_revision: str,
    ) -> ProjectCommandResult:
        updates = _normalized_updates(changes)
        with _persistent_command_lock(self.projects_dir, self.index_csv):
            projects, links = self._load()
            current = _find_project(projects, project_id)
            if project_revision(current) != expected_revision:
                raise ProjectCommandConflict
            if current["status"] == "archived":
                raise ProjectArchivedConflict
            if all(current.get(field) == value for field, value in updates.items()):
                return ProjectCommandResult(
                    status="no_op",
                    project=_project_state(current, links),
                )

            updated = {
                **current,
                **updates,
                "id": current["id"],
                "created_at": current["created_at"],
                "updated_at": _utc_now_iso(),
            }
            replacement = [
                updated if item["id"] == project_id else item
                for item in projects
            ]
            persisted = self._persist_projects(
                replacement,
                expected_project_id=project_id,
            )
            return ProjectCommandResult(
                status="saved",
                project=_project_state(_find_project(persisted, project_id), links),
            )

    def archive_project(
        self,
        project_id: str,
        expected_revision: str,
    ) -> ProjectCommandResult:
        with _persistent_command_lock(self.projects_dir, self.index_csv):
            projects, links = self._load()
            current = _find_project(projects, project_id)
            if project_revision(current) != expected_revision:
                raise ProjectCommandConflict
            if current["status"] == "archived":
                return ProjectCommandResult(
                    status="already_archived",
                    project=_project_state(current, links),
                )

            archived = {
                **current,
                "status": "archived",
                "id": current["id"],
                "created_at": current["created_at"],
                "updated_at": _utc_now_iso(),
            }
            replacement = [
                archived if item["id"] == project_id else item
                for item in projects
            ]
            persisted = self._persist_projects(
                replacement,
                expected_project_id=project_id,
            )
            return ProjectCommandResult(
                status="archived",
                project=_project_state(_find_project(persisted, project_id), links),
            )

    def add_paper_link(
        self,
        project_id: str,
        *,
        paper_id: str,
        link_type: str,
        expected_links_revision: str,
    ) -> PaperLinkCommandResult:
        safe_paper_id = _required_text(paper_id, "paper_id", 200)
        safe_link_type = _choice(
            link_type,
            "link_type",
            project_link_store.ALLOWED_LINK_TYPES,
        )
        with _persistent_command_lock(self.projects_dir, self.index_csv):
            projects, links = self._load()
            project = _find_project(projects, project_id)
            if project["status"] == "archived":
                raise ProjectArchivedConflict
            if project_links_revision(project_id, links) != expected_links_revision:
                raise ProjectCommandConflict
            try:
                paper_index = read_index_snapshot(self.index_csv)
            except Exception:
                raise ProjectCommandUnavailable from None
            if (
                "paper_id" not in paper_index
                or safe_paper_id not in set(paper_index["paper_id"].astype(str))
            ):
                raise ProjectCommandNotFound

            duplicate = next(
                (
                    link
                    for link in links
                    if str(link.get("project_id", "")) == project_id
                    and str(link.get("target_type", "")) == "paper"
                    and str(link.get("target_id", "")) == safe_paper_id
                    and str(link.get("link_type", "")) == safe_link_type
                ),
                None,
            )
            if duplicate is not None:
                return PaperLinkCommandResult(
                    status="unchanged",
                    project=_project_state(project, links),
                    link=_paper_link_state(duplicate),
                )

            link = {
                "id": str(uuid4()),
                "project_id": project_id,
                "target_type": "paper",
                "target_id": safe_paper_id,
                "paper_id": safe_paper_id,
                "link_type": safe_link_type,
                "note": "",
                "created_at": _utc_now_iso(),
            }
            persisted = self._persist_links(
                [*links, link],
                expected_link_id=link["id"],
            )
            created = next(
                item for item in persisted
                if str(item["id"]) == link["id"]
            )
            return PaperLinkCommandResult(
                status="created",
                project=_project_state(project, persisted),
                link=_paper_link_state(created),
            )

    def remove_paper_link(
        self,
        project_id: str,
        link_id: str,
        *,
        expected_links_revision: str,
    ) -> PaperLinkCommandResult:
        with _persistent_command_lock(self.projects_dir, self.index_csv):
            projects, links = self._load()
            project = _find_project(projects, project_id)
            if project_links_revision(project_id, links) != expected_links_revision:
                raise ProjectCommandConflict
            link = next(
                (
                    item
                    for item in links
                    if str(item.get("id", "")) == link_id
                    and str(item.get("project_id", "")) == project_id
                    and str(item.get("target_type", "")) == "paper"
                ),
                None,
            )
            if link is None:
                raise ProjectCommandNotFound

            persisted = self._persist_links(
                [item for item in links if str(item.get("id", "")) != link_id],
                expected_link_id=None,
                removed_link_id=link_id,
            )
            return PaperLinkCommandResult(
                status="removed",
                project=_project_state(project, persisted),
                link=_paper_link_state(link),
            )
