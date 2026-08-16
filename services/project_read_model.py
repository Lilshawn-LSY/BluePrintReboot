from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, TypedDict

from services.library_read_model import build_paper_list_items
from services.note_block_read_model import normalized_note_blocks
from storage.note_block_store import list_note_blocks
from storage.paths import INDEX_CSV, NOTE_BLOCKS_DIR, PROJECTS_DIR
from storage.project_link_store import list_project_links
from storage.project_store import list_projects


class ProjectListItem(TypedDict):
    project_id: str
    name: str
    description: str
    status: str
    priority: str
    tags: list[str]
    created_at: str
    updated_at: str
    project_revision: str
    link_count: int
    linked_paper_count: int
    linked_note_block_count: int


class LinkedPaperSummary(TypedDict):
    paper_id: str
    title: str
    first_author: str
    year: str
    status: str
    priority: str
    tags: list[str]
    archived: bool


class LinkedNoteBlockSummary(TypedDict):
    block_id: str
    paper_id: str
    source_paper_title: str
    block_type: str
    title: str
    text_preview: str
    page: str
    figure: str
    tags: list[str]


class ProjectLinkTarget(TypedDict):
    link_id: str
    link_type: str
    target_type: str
    target_id: str
    target_state: str
    paper_id: str
    created_at: str
    paper: LinkedPaperSummary | None
    note_block: LinkedNoteBlockSummary | None


class ProjectDetail(ProjectListItem):
    links: list[ProjectLinkTarget]
    links_revision: str
    orphaned_link_count: int


def _canonical_revision(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def project_revision(project: Mapping[str, Any]) -> str:
    """Bind optimistic concurrency to the complete normalized Project record."""

    return _canonical_revision(dict(project))


def project_links_revision(
    project_id: str,
    links: list[Mapping[str, Any]],
) -> str:
    """Bind one Project's link commands to its complete stored link collection."""

    matching = [
        dict(link)
        for link in links
        if str(link.get("project_id", "")) == str(project_id)
    ]
    matching.sort(key=lambda link: (str(link.get("created_at", "")), str(link.get("id", ""))))
    return _canonical_revision(matching)


def _base_project(
    project: Mapping[str, Any],
    links: list[Mapping[str, Any]],
) -> ProjectListItem:
    paper_link_count = sum(link.get("target_type") == "paper" for link in links)
    note_block_link_count = sum(
        link.get("target_type") == "note_block" for link in links
    )
    return {
        "project_id": str(project["id"]),
        "name": str(project["name"]),
        "description": str(project["description"]),
        "status": str(project["status"]),
        "priority": str(project["priority"]),
        "tags": [str(tag) for tag in project["tags"]],
        "created_at": str(project["created_at"]),
        "updated_at": str(project["updated_at"]),
        "project_revision": project_revision(project),
        "link_count": len(links),
        "linked_paper_count": paper_link_count,
        "linked_note_block_count": note_block_link_count,
    }


def _load_projects_and_links(
    projects_dir: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_dir = Path(projects_dir) if projects_dir is not None else PROJECTS_DIR
    projects = list_projects(base_dir)
    links = list_project_links(base_dir)
    project_ids = [str(project["id"]) for project in projects]
    if len(project_ids) != len(set(project_ids)):
        raise ValueError("Project identities must be unique.")
    link_ids = [str(link["id"]) for link in links]
    if len(link_ids) != len(set(link_ids)):
        raise ValueError("Project link identities must be unique.")
    return projects, links


def build_project_list_items(
    *,
    projects_dir: Path | None = None,
) -> list[ProjectListItem]:
    projects, links = _load_projects_and_links(projects_dir)
    links_by_project: dict[str, list[Mapping[str, Any]]] = {}
    for link in links:
        links_by_project.setdefault(str(link["project_id"]), []).append(link)
    return [
        _base_project(project, links_by_project.get(str(project["id"]), []))
        for project in projects
    ]


def _linked_paper_summary(source: Mapping[str, Any]) -> LinkedPaperSummary:
    return {
        "paper_id": str(source["paper_id"]),
        "title": str(source.get("title", "")),
        "first_author": str(source.get("first_author", "")),
        "year": str(source.get("year", "")),
        "status": str(source.get("status", "")),
        "priority": str(source.get("priority", "")),
        "tags": [str(tag) for tag in source.get("tags", [])],
        "archived": bool(source.get("archived", False)),
    }


def _bounded_preview(value: object, maximum: int = 280) -> str:
    compact = " ".join(str(value or "").split())
    if len(compact) <= maximum:
        return compact
    return compact[: maximum - 3].rstrip() + "..."


def _linked_note_block_summary(
    block: Mapping[str, Any],
    paper: LinkedPaperSummary,
) -> LinkedNoteBlockSummary:
    return {
        "block_id": str(block["id"]),
        "paper_id": str(block["paper_id"]),
        "source_paper_title": paper["title"],
        "block_type": str(block["block_type"]),
        "title": str(block["title"]),
        "text_preview": _bounded_preview(block["text"]),
        "page": str(block["page"]),
        "figure": str(block["figure"]),
        "tags": [str(tag) for tag in block["tags"]],
    }


def build_project_detail(
    project_id: str,
    *,
    projects_dir: Path | None = None,
    index_csv: Path | None = None,
    note_blocks_dir: Path | None = None,
) -> ProjectDetail | None:
    projects, all_links = _load_projects_and_links(projects_dir)
    project = next(
        (candidate for candidate in projects if str(candidate["id"]) == project_id),
        None,
    )
    if project is None:
        return None

    links = [
        link for link in all_links
        if str(link["project_id"]) == project_id
    ]
    paper_context_links = [
        link for link in links
        if link["target_type"] in {"paper", "note_block"}
    ]
    papers_by_id: dict[str, LinkedPaperSummary] = {}
    if paper_context_links:
        paper_items = build_paper_list_items(
            index_csv=Path(index_csv) if index_csv is not None else INDEX_CSV,
            health_report={},
        )
        papers_by_id = {
            str(item["paper_id"]): _linked_paper_summary(item)
            for item in paper_items
            if str(item.get("paper_id", "")).strip()
        }

    targets: list[ProjectLinkTarget] = []
    orphaned_count = 0
    blocks_by_paper: dict[str, list[dict[str, Any]] | None] = {}
    effective_note_blocks_dir = (
        Path(note_blocks_dir) if note_blocks_dir is not None else NOTE_BLOCKS_DIR
    )
    for link in links:
        target_type = str(link["target_type"])
        paper_id = str(link.get("paper_id", "") or link["target_id"])
        paper = papers_by_id.get(paper_id) if paper_id else None
        note_block: LinkedNoteBlockSummary | None = None
        if target_type == "paper":
            target_state = "available" if paper is not None else "orphaned"
            orphaned_count += paper is None
        elif target_type == "note_block":
            if paper is None:
                target_state = "orphaned_paper"
                orphaned_count += 1
            else:
                if paper_id not in blocks_by_paper:
                    try:
                        blocks_by_paper[paper_id] = normalized_note_blocks(
                            paper_id,
                            list_note_blocks(paper_id, effective_note_blocks_dir),
                        )
                    except Exception:
                        blocks_by_paper[paper_id] = None
                blocks = blocks_by_paper[paper_id]
                if blocks is None:
                    target_state = "unavailable"
                else:
                    block = next(
                        (
                            candidate for candidate in blocks
                            if str(candidate["id"]) == str(link["target_id"])
                        ),
                        None,
                    )
                    if block is None:
                        target_state = "orphaned_note_block"
                        orphaned_count += 1
                    else:
                        target_state = "available"
                        note_block = _linked_note_block_summary(block, paper)
        else:
            target_state = "not_applicable"
        targets.append(
            {
                "link_id": str(link["id"]),
                "link_type": str(link["link_type"]),
                "target_type": target_type,
                "target_id": str(link["target_id"]),
                "target_state": target_state,
                "paper_id": paper_id,
                "created_at": str(link["created_at"]),
                "paper": paper if target_type == "paper" else None,
                "note_block": note_block,
            }
        )
    targets.sort(key=lambda link: (link["created_at"], link["link_id"]))
    return {
        **_base_project(project, links),
        "links": targets,
        "links_revision": project_links_revision(project_id, all_links),
        "orphaned_link_count": orphaned_count,
    }
