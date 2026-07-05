from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from storage.atomic_json import atomic_write_json
from storage.paths import NOTE_BLOCKS_DIR


ALLOWED_BLOCK_TYPES = (
    "summary",
    "claim",
    "method",
    "evidence",
    "question",
    "idea",
    "limitation",
)


def note_blocks_path(paper_id: str, base_dir: Path = NOTE_BLOCKS_DIR) -> Path:
    return Path(base_dir) / f"{paper_id}.json"


def list_note_blocks(paper_id: str, base_dir: Path = NOTE_BLOCKS_DIR) -> list[dict[str, Any]]:
    path = note_blocks_path(paper_id, base_dir)
    if not path.exists():
        return []
    try:
        stored_blocks = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Note block file is invalid JSON: {path}") from exc
    if not isinstance(stored_blocks, list):
        raise ValueError(f"Note block file must contain a list: {path}")
    return [_normalize_block(paper_id, block) for block in stored_blocks]


def save_note_blocks(
    paper_id: str,
    blocks: Sequence[Mapping[str, Any]],
    base_dir: Path = NOTE_BLOCKS_DIR,
) -> Path:
    normalized_blocks = [_normalize_block(paper_id, block) for block in blocks]
    block_ids = [block["id"] for block in normalized_blocks]
    if len(block_ids) != len(set(block_ids)):
        raise ValueError("Note block IDs must be unique within a paper.")

    path = note_blocks_path(paper_id, base_dir)
    return atomic_write_json(path, normalized_blocks, indent=2, ensure_ascii=False)


def create_note_block(
    paper_id: str,
    block_type: str,
    title: str = "",
    text: str = "",
    page: str = "",
    figure: str = "",
    quote: str = "",
    tags: object | None = None,
    base_dir: Path = NOTE_BLOCKS_DIR,
) -> dict[str, Any]:
    timestamp = _utc_now_iso()
    block = _normalize_block(
        paper_id,
        {
            "id": str(uuid4()),
            "paper_id": paper_id,
            "block_type": block_type,
            "title": title,
            "text": text,
            "page": page,
            "figure": figure,
            "quote": quote,
            "tags": normalize_note_block_tags(tags),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    blocks = list_note_blocks(paper_id, base_dir)
    blocks.append(block)
    save_note_blocks(paper_id, blocks, base_dir)
    return block


def get_note_block(
    paper_id: str,
    block_id: str,
    base_dir: Path = NOTE_BLOCKS_DIR,
) -> dict[str, Any] | None:
    for block in list_note_blocks(paper_id, base_dir):
        if block["id"] == block_id:
            return block
    return None


def update_note_block(
    paper_id: str,
    block_id: str,
    updates: Mapping[str, Any],
    base_dir: Path = NOTE_BLOCKS_DIR,
) -> dict[str, Any]:
    blocks = list_note_blocks(paper_id, base_dir)
    for index, block in enumerate(blocks):
        if block["id"] != block_id:
            continue
        updated = {**block, **dict(updates)}
        updated["id"] = block["id"]
        updated["paper_id"] = block["paper_id"]
        updated["created_at"] = block["created_at"]
        updated["updated_at"] = _utc_now_iso()
        normalized = _normalize_block(paper_id, updated)
        blocks[index] = normalized
        save_note_blocks(paper_id, blocks, base_dir)
        return normalized
    raise KeyError(f"Note block not found: {block_id}")


def delete_note_block(
    paper_id: str,
    block_id: str,
    base_dir: Path = NOTE_BLOCKS_DIR,
) -> bool:
    blocks = list_note_blocks(paper_id, base_dir)
    remaining = [block for block in blocks if block["id"] != block_id]
    if len(remaining) == len(blocks):
        return False
    save_note_blocks(paper_id, remaining, base_dir)
    return True


def normalize_note_block_tags(tags: object | None) -> list[str]:
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


def render_note_block_as_markdown(block: Mapping[str, Any]) -> str:
    block_type = _validated_block_type(block.get("block_type"))
    title = _required_string(block.get("title", ""), "title").strip()
    text = _required_string(block.get("text", ""), "text").strip()
    page = _required_string(block.get("page", ""), "page").strip()
    figure = _required_string(block.get("figure", ""), "figure").strip()
    quote = _required_string(block.get("quote", ""), "quote").strip()
    tags = normalize_note_block_tags(block.get("tags"))

    type_label = block_type.replace("_", " ").title()
    heading = f"### {type_label}: {title}" if title else f"### {type_label}"
    details = []
    if page:
        details.append(f"* Page: {page}")
    if figure:
        details.append(f"* Figure: {figure}")
    if tags:
        details.append(f"* Tags: {', '.join(tags)}")

    sections = [heading]
    if details:
        sections.append("\n".join(details))
    if quote:
        sections.append("\n".join(f"> {line}" for line in quote.splitlines()))
    if text:
        sections.append(text)
    return "\n\n".join(sections) + "\n"


def _normalize_block(paper_id: str, block: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(block, Mapping):
        raise ValueError("Each note block must be an object.")

    normalized = dict(block)
    normalized["id"] = _required_non_empty_string(block.get("id"), "id")
    stored_paper_id = _required_non_empty_string(block.get("paper_id", paper_id), "paper_id")
    if stored_paper_id != paper_id:
        raise ValueError("Note block paper_id must match its storage file.")
    normalized["paper_id"] = stored_paper_id
    normalized["block_type"] = _validated_block_type(block.get("block_type"))
    normalized["title"] = _required_string(block.get("title", ""), "title")
    normalized["text"] = _required_string(block.get("text", ""), "text")
    normalized["page"] = _required_string(block.get("page", ""), "page")
    normalized["figure"] = _required_string(block.get("figure", ""), "figure")
    normalized["quote"] = _required_string(block.get("quote", ""), "quote")
    normalized["tags"] = normalize_note_block_tags(block.get("tags"))
    created_at_value = block["created_at"] if "created_at" in block else _utc_now_iso()
    created_at = _required_string(created_at_value, "created_at")
    normalized["created_at"] = created_at
    normalized["updated_at"] = _required_string(block.get("updated_at", created_at), "updated_at")
    return normalized


def _validated_block_type(value: Any) -> str:
    block_type = _required_string(value, "block_type")
    if block_type not in ALLOWED_BLOCK_TYPES:
        allowed = ", ".join(ALLOWED_BLOCK_TYPES)
        raise ValueError(f"block_type must be one of: {allowed}")
    return block_type


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
