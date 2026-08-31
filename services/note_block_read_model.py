from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Mapping, TypedDict

from storage.index_store import read_index_snapshot
from storage.note_block_store import list_note_blocks
from storage.paths import INDEX_CSV, NOTE_BLOCKS_DIR, PROJECTS_DIR
from storage.project_link_store import list_project_links
from storage.project_store import list_projects


NOTE_BLOCK_FIELDS = (
    "id",
    "paper_id",
    "block_type",
    "title",
    "text",
    "page",
    "figure",
    "quote",
    "tags",
    "created_at",
    "updated_at",
)
MAX_NOTE_BLOCKS_PER_PAPER = 1_000
MAX_NOTE_BLOCK_ID_LENGTH = 200
MAX_NOTE_BLOCK_TITLE_LENGTH = 1_000
MAX_NOTE_BLOCK_TEXT_LENGTH = 100_000
MAX_NOTE_BLOCK_PAGE_LENGTH = 100
MAX_NOTE_BLOCK_FIGURE_LENGTH = 500
MAX_NOTE_BLOCK_QUOTE_LENGTH = 100_000
MAX_NOTE_BLOCK_TAGS = 25
MAX_NOTE_BLOCK_TAG_LENGTH = 100
MAX_NOTE_BLOCK_TIMESTAMP_LENGTH = 100


class NoteBlockItem(TypedDict):
    id: str
    paper_id: str
    block_type: str
    title: str
    text: str
    page: str
    figure: str
    quote: str
    tags: list[str]
    created_at: str
    updated_at: str


class NoteBlockSourcePaper(TypedDict):
    paper_id: str
    title: str


class NoteBlockProjectLink(TypedDict):
    link_id: str
    project_id: str
    project_name: str
    project_status: str
    note_block_id: str
    link_type: str
    links_revision: str


class NoteBlockCollection(TypedDict):
    source_paper: NoteBlockSourcePaper
    items: list[NoteBlockItem]
    total: int
    note_blocks_revision: str
    project_links: list[NoteBlockProjectLink]
    project_links_state: Literal["available", "unavailable"]


def _canonical_revision(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_string(block: Mapping[str, Any], field: str, maximum: int) -> str:
    value = block[field]
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"Note Block {field} is invalid or out of bounds.")
    return value


def _public_block(block: Mapping[str, Any]) -> NoteBlockItem:
    tags = block["tags"]
    if not isinstance(tags, list) or len(tags) > MAX_NOTE_BLOCK_TAGS:
        raise ValueError("Note Block tags are invalid or out of bounds.")
    if any(not isinstance(tag, str) or len(tag) > MAX_NOTE_BLOCK_TAG_LENGTH for tag in tags):
        raise ValueError("Note Block tag is invalid or out of bounds.")
    return {
        "id": _bounded_string(block, "id", MAX_NOTE_BLOCK_ID_LENGTH),
        "paper_id": _bounded_string(block, "paper_id", MAX_NOTE_BLOCK_ID_LENGTH),
        "block_type": _bounded_string(block, "block_type", 20),
        "title": _bounded_string(block, "title", MAX_NOTE_BLOCK_TITLE_LENGTH),
        "text": _bounded_string(block, "text", MAX_NOTE_BLOCK_TEXT_LENGTH),
        "page": _bounded_string(block, "page", MAX_NOTE_BLOCK_PAGE_LENGTH),
        "figure": _bounded_string(block, "figure", MAX_NOTE_BLOCK_FIGURE_LENGTH),
        "quote": _bounded_string(block, "quote", MAX_NOTE_BLOCK_QUOTE_LENGTH),
        "tags": list(tags),
        "created_at": _bounded_string(block, "created_at", MAX_NOTE_BLOCK_TIMESTAMP_LENGTH),
        "updated_at": _bounded_string(block, "updated_at", MAX_NOTE_BLOCK_TIMESTAMP_LENGTH),
    }


def normalized_note_blocks(
    paper_id: str,
    blocks: list[Mapping[str, Any]],
) -> list[NoteBlockItem]:
    if len(blocks) > MAX_NOTE_BLOCKS_PER_PAPER:
        raise ValueError("Note Block collection exceeds its supported bound.")
    public = [_public_block(block) for block in blocks]
    identities = [block["id"] for block in public]
    if len(identities) != len(set(identities)):
        raise ValueError("Note Block identities must be unique within one Paper.")
    if any(block["paper_id"] != paper_id for block in public):
        raise ValueError("Note Block Paper identity does not match its collection.")
    return public


def newest_first_note_blocks(
    paper_id: str,
    blocks: list[Mapping[str, Any]],
) -> list[NoteBlockItem]:
    """Return the deterministic Reader presentation and command order.

    Creation time is the Note Block ordering invariant.  ``updated_at`` is
    deliberately excluded: editing a historical observation must not promote
    it above more recent observations.  Block ID is only a deterministic
    tie-breaker for legacy records that share a creation timestamp.
    """

    return sorted(
        normalized_note_blocks(paper_id, blocks),
        key=lambda block: (block["created_at"], block["id"]),
        reverse=True,
    )


def note_blocks_revision(
    paper_id: str,
    blocks: list[Mapping[str, Any]],
) -> str:
    """Bind optimistic concurrency to the complete normalized newest-first collection."""

    return _canonical_revision(newest_first_note_blocks(paper_id, blocks))


def _project_links_revision(
    project_id: str,
    links: list[Mapping[str, Any]],
) -> str:
    matching = [
        dict(link)
        for link in links
        if str(link.get("project_id", "")) == project_id
    ]
    matching.sort(key=lambda link: (str(link.get("created_at", "")), str(link.get("id", ""))))
    return _canonical_revision(matching)


def _paper_record(paper_id: str, index_csv: Path) -> dict[str, Any] | None:
    dataframe = read_index_snapshot(index_csv)
    matches = dataframe[dataframe["paper_id"].astype(str) == paper_id]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


def _project_links(
    paper_id: str,
    block_ids: set[str],
    projects_dir: Path,
) -> tuple[list[NoteBlockProjectLink], Literal["available", "unavailable"]]:
    try:
        projects = list_projects(projects_dir)
        links = list_project_links(projects_dir)
    except Exception:
        return [], "unavailable"

    projects_by_id = {str(project["id"]): project for project in projects}
    result: list[NoteBlockProjectLink] = []
    for link in links:
        if (
            str(link.get("target_type", "")) != "note_block"
            or str(link.get("paper_id", "")) != paper_id
            or str(link.get("target_id", "")) not in block_ids
        ):
            continue
        project_id = str(link["project_id"])
        project = projects_by_id.get(project_id)
        result.append(
            {
                "link_id": str(link["id"]),
                "project_id": project_id,
                "project_name": str(project.get("name", "")) if project else "",
                "project_status": str(project.get("status", "unavailable")) if project else "unavailable",
                "note_block_id": str(link["target_id"]),
                "link_type": str(link["link_type"]),
                "links_revision": _project_links_revision(project_id, links),
            }
        )
    result.sort(
        key=lambda item: (
            item["note_block_id"],
            item["project_name"].casefold(),
            item["project_id"],
            item["link_type"],
            item["link_id"],
        )
    )
    return result, "available"


def build_note_block_collection(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    note_blocks_dir: Path = NOTE_BLOCKS_DIR,
    projects_dir: Path = PROJECTS_DIR,
) -> NoteBlockCollection | None:
    record = _paper_record(paper_id, Path(index_csv))
    if record is None:
        return None

    blocks = newest_first_note_blocks(
        paper_id,
        list_note_blocks(paper_id, Path(note_blocks_dir)),
    )
    project_links, project_links_state = _project_links(
        paper_id,
        {block["id"] for block in blocks},
        Path(projects_dir),
    )
    return {
        "source_paper": {
            "paper_id": paper_id,
            "title": str(record.get("title", "") or record.get("filename", "") or ""),
        },
        "items": blocks,
        "total": len(blocks),
        "note_blocks_revision": note_blocks_revision(paper_id, blocks),
        "project_links": project_links,
        "project_links_state": project_links_state,
    }
