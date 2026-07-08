from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from storage.atomic_json import atomic_write_json, read_json_file, require_json_list
from storage.paths import PROJECTS_DIR


ALLOWED_TARGET_TYPES = ("paper", "note_block")
ALLOWED_LINK_TYPES = (
    "related",
    "background",
    "key_reference",
    "supports_project",
    "raises_question",
    "idea_for_project",
)


def project_links_path(base_dir: Path = PROJECTS_DIR) -> Path:
    return Path(base_dir) / "project_links.json"


def list_project_links(base_dir: Path = PROJECTS_DIR) -> list[dict[str, Any]]:
    path = project_links_path(base_dir)
    if not path.exists():
        return []
    stored_links = require_json_list(
        read_json_file(path, store_name="Project links file"),
        path,
        store_name="Project links file",
    )
    return [_normalize_project_link(link) for link in stored_links]


def save_project_links(
    links: Sequence[Mapping[str, Any]],
    base_dir: Path = PROJECTS_DIR,
) -> Path:
    normalized_links = [_normalize_project_link(link) for link in links]
    link_ids = [link["id"] for link in normalized_links]
    if len(link_ids) != len(set(link_ids)):
        raise ValueError("Project link IDs must be unique.")
    link_keys = [_duplicate_key(link) for link in normalized_links]
    if len(link_keys) != len(set(link_keys)):
        raise ValueError("Duplicate project links are not allowed.")

    path = project_links_path(base_dir)
    return atomic_write_json(path, normalized_links, indent=2, ensure_ascii=False)


def create_project_link(
    project_id: str,
    target_type: str,
    target_id: str,
    paper_id: str = "",
    link_type: str = "related",
    note: str = "",
    base_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    effective_paper_id = target_id if target_type == "paper" and not paper_id else paper_id
    candidate = _normalize_project_link(
        {
            "id": str(uuid4()),
            "project_id": project_id,
            "target_type": target_type,
            "target_id": target_id,
            "paper_id": effective_paper_id,
            "link_type": link_type,
            "note": note,
            "created_at": _utc_now_iso(),
        }
    )
    links = list_project_links(base_dir)
    candidate_key = _duplicate_key(candidate)
    for link in links:
        if _duplicate_key(link) == candidate_key:
            return link
    links.append(candidate)
    save_project_links(links, base_dir)
    return candidate


def update_project_link(
    link_id: str,
    updates: Mapping[str, Any],
    base_dir: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    links = list_project_links(base_dir)
    for index, link in enumerate(links):
        if link["id"] != link_id:
            continue
        updated = {**link, **dict(updates)}
        for protected_field in (
            "id",
            "project_id",
            "target_type",
            "target_id",
            "paper_id",
            "created_at",
        ):
            updated[protected_field] = link[protected_field]
        normalized = _normalize_project_link(updated)
        links[index] = normalized
        save_project_links(links, base_dir)
        return normalized
    raise KeyError(f"Project link not found: {link_id}")


def delete_project_link(link_id: str, base_dir: Path = PROJECTS_DIR) -> bool:
    links = list_project_links(base_dir)
    remaining = [link for link in links if link["id"] != link_id]
    if len(remaining) == len(links):
        return False
    save_project_links(remaining, base_dir)
    return True


def list_links_for_project(project_id: str, base_dir: Path = PROJECTS_DIR) -> list[dict[str, Any]]:
    return [link for link in list_project_links(base_dir) if link["project_id"] == project_id]


def list_links_for_target(
    target_type: str,
    target_id: str,
    base_dir: Path = PROJECTS_DIR,
) -> list[dict[str, Any]]:
    _validated_choice(target_type, "target_type", ALLOWED_TARGET_TYPES)
    return [
        link
        for link in list_project_links(base_dir)
        if link["target_type"] == target_type and link["target_id"] == target_id
    ]


def list_links_for_paper(paper_id: str, base_dir: Path = PROJECTS_DIR) -> list[dict[str, Any]]:
    return [link for link in list_project_links(base_dir) if link["paper_id"] == paper_id]


def delete_links_for_project(project_id: str, base_dir: Path = PROJECTS_DIR) -> int:
    links = list_project_links(base_dir)
    remaining = [link for link in links if link["project_id"] != project_id]
    deleted_count = len(links) - len(remaining)
    if deleted_count:
        save_project_links(remaining, base_dir)
    return deleted_count


def _normalize_project_link(link: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(link, Mapping):
        raise ValueError("Each project link must be an object.")

    normalized = dict(link)
    normalized["id"] = _required_non_empty_string(link.get("id"), "id")
    normalized["project_id"] = _required_non_empty_string(link.get("project_id"), "project_id")
    normalized["target_type"] = _validated_choice(
        link.get("target_type"),
        "target_type",
        ALLOWED_TARGET_TYPES,
    )
    normalized["target_id"] = _required_non_empty_string(link.get("target_id"), "target_id")
    normalized["paper_id"] = _required_string(link.get("paper_id", ""), "paper_id")
    normalized["link_type"] = _validated_choice(
        link.get("link_type"),
        "link_type",
        ALLOWED_LINK_TYPES,
    )
    normalized["note"] = _required_string(link.get("note", ""), "note")
    created_at_value = link["created_at"] if "created_at" in link else _utc_now_iso()
    normalized["created_at"] = _required_string(created_at_value, "created_at")
    return normalized


def _duplicate_key(link: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(link["project_id"]),
        str(link["target_type"]),
        str(link["target_id"]),
        str(link["link_type"]),
    )


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
