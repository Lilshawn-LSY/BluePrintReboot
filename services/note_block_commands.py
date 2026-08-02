from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping
from uuid import uuid4

from services.note_block_read_model import (
    MAX_NOTE_BLOCKS_PER_PAPER,
    MAX_NOTE_BLOCK_FIGURE_LENGTH,
    MAX_NOTE_BLOCK_PAGE_LENGTH,
    MAX_NOTE_BLOCK_QUOTE_LENGTH,
    MAX_NOTE_BLOCK_TAG_LENGTH,
    MAX_NOTE_BLOCK_TAGS,
    MAX_NOTE_BLOCK_TEXT_LENGTH,
    MAX_NOTE_BLOCK_TITLE_LENGTH,
    NoteBlockItem,
    normalized_note_blocks,
    note_blocks_revision,
)
from storage import note_block_store
from storage.atomic_text import atomic_write_text
from storage.index_store import read_index_snapshot
from storage.paths import INDEX_CSV, NOTE_BLOCKS_DIR
from storage.workspace_lock import WorkspaceLockUnavailable, workspace_write_lock


NOTE_BLOCK_CONTENT_FIELDS = (
    "block_type",
    "title",
    "text",
    "page",
    "figure",
    "quote",
    "tags",
)
NOTE_BLOCK_CONTENT_FIELD_SET = frozenset(NOTE_BLOCK_CONTENT_FIELDS)


class NoteBlockCommandError(Exception):
    """Base class for controlled structured Note Block command failures."""


class NoteBlockCommandInvalid(NoteBlockCommandError):
    """The submitted Note Block values are unsupported or out of bounds."""


class NoteBlockCommandConflict(NoteBlockCommandError):
    """The caller's complete Note Block collection revision is stale."""


class NoteBlockCommandNotFound(NoteBlockCommandError):
    """The requested Paper or Note Block identity is unknown."""


class NoteBlockCommandUnavailable(NoteBlockCommandError):
    """The persistent Note Block command could not complete consistently."""


@dataclass(frozen=True)
class NoteBlockCommandResult:
    status: Literal["created", "saved", "no_op"]
    block: NoteBlockItem
    note_blocks_revision: str
    total: int


@dataclass(frozen=True)
class _FileSnapshot:
    exists: bool
    content: bytes
    accessed_ns: int
    modified_ns: int


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_root(note_blocks_dir: Path, index_csv: Path) -> Path:
    blocks_root = Path(note_blocks_dir).resolve(strict=False).parent
    index_path = Path(index_csv).resolve(strict=False)
    index_root = (
        index_path.parent.parent
        if index_path.parent.name.casefold() == "data"
        else index_path.parent
    )
    try:
        return Path(os.path.commonpath((str(blocks_root), str(index_root))))
    except ValueError:
        return blocks_root


@contextmanager
def _persistent_command_lock(note_blocks_dir: Path, index_csv: Path):
    try:
        with workspace_write_lock(_workspace_root(note_blocks_dir, index_csv)):
            yield
    except WorkspaceLockUnavailable:
        raise NoteBlockCommandUnavailable from None


def _snapshot_file(path: Path) -> _FileSnapshot:
    target = Path(path)
    if not target.exists():
        return _FileSnapshot(False, b"", 0, 0)
    if not target.is_file():
        raise NoteBlockCommandUnavailable
    content = target.read_bytes()
    stat = target.stat()
    return _FileSnapshot(True, content, stat.st_atime_ns, stat.st_mtime_ns)


def _restore_file(path: Path, snapshot: _FileSnapshot) -> None:
    target = Path(path)
    if not snapshot.exists:
        if target.exists():
            target.unlink()
        return
    current = target.read_bytes() if target.is_file() else None
    if current != snapshot.content:
        atomic_write_text(target, snapshot.content.decode("utf-8"))
    os.utime(target, ns=(snapshot.accessed_ns, snapshot.modified_ns))


def _rollback(path: Path, snapshot: _FileSnapshot) -> None:
    try:
        _restore_file(path, snapshot)
    except Exception:
        raise NoteBlockCommandUnavailable from None


def _text(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise NoteBlockCommandInvalid(f"{field} must be a string.")
    if len(value) > maximum:
        raise NoteBlockCommandInvalid(f"{field} is too long.")
    return value


def _block_type(value: object) -> str:
    if not isinstance(value, str) or value not in note_block_store.ALLOWED_BLOCK_TYPES:
        raise NoteBlockCommandInvalid("block_type is unsupported.")
    return value


def _tags(value: object) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_NOTE_BLOCK_TAGS:
        raise NoteBlockCommandInvalid("tags must be a bounded list.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise NoteBlockCommandInvalid("tags must contain strings.")
        tag = item.strip()
        if not tag or len(tag) > MAX_NOTE_BLOCK_TAG_LENGTH:
            raise NoteBlockCommandInvalid("tag is empty or too long.")
        if tag not in result:
            result.append(tag)
    return result


def _normalized_content(values: Mapping[str, Any], *, partial: bool) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        raise NoteBlockCommandInvalid("Note Block content must be an object.")
    if set(values) - NOTE_BLOCK_CONTENT_FIELD_SET:
        raise NoteBlockCommandInvalid("The Note Block contains an unsupported field.")
    if partial and not values:
        raise NoteBlockCommandInvalid("At least one Note Block change is required.")
    if not partial and "block_type" not in values:
        raise NoteBlockCommandInvalid("block_type is required.")
    normalized: dict[str, Any] = {}
    for field, value in values.items():
        if field == "block_type":
            normalized[field] = _block_type(value)
        elif field == "title":
            normalized[field] = _text(value, field, MAX_NOTE_BLOCK_TITLE_LENGTH)
        elif field == "text":
            normalized[field] = _text(value, field, MAX_NOTE_BLOCK_TEXT_LENGTH)
        elif field == "page":
            normalized[field] = _text(value, field, MAX_NOTE_BLOCK_PAGE_LENGTH)
        elif field == "figure":
            normalized[field] = _text(value, field, MAX_NOTE_BLOCK_FIGURE_LENGTH)
        elif field == "quote":
            normalized[field] = _text(value, field, MAX_NOTE_BLOCK_QUOTE_LENGTH)
        elif field == "tags":
            normalized[field] = _tags(value)
    if not partial:
        for field in NOTE_BLOCK_CONTENT_FIELDS:
            if field not in normalized:
                normalized[field] = [] if field == "tags" else ""
    return normalized


class NoteBlockCommandService:
    """Locked, optimistic, atomic command boundary for structured Note Blocks."""

    def __init__(
        self,
        *,
        note_blocks_dir: Path = NOTE_BLOCKS_DIR,
        index_csv: Path = INDEX_CSV,
    ) -> None:
        self.note_blocks_dir = Path(note_blocks_dir)
        self.index_csv = Path(index_csv)

    def _paper_exists(self, paper_id: str) -> bool:
        try:
            index = read_index_snapshot(self.index_csv)
        except Exception:
            raise NoteBlockCommandUnavailable from None
        return "paper_id" in index and paper_id in set(index["paper_id"].astype(str))

    def _load(self, paper_id: str) -> list[dict[str, Any]]:
        try:
            blocks = note_block_store.list_note_blocks(paper_id, self.note_blocks_dir)
            normalized_note_blocks(paper_id, blocks)
            return blocks
        except Exception:
            raise NoteBlockCommandUnavailable from None

    def _persist(
        self,
        paper_id: str,
        blocks: list[dict[str, Any]],
        *,
        expected_block_id: str,
    ) -> list[dict[str, Any]]:
        path = note_block_store.note_blocks_path(paper_id, self.note_blocks_dir)
        try:
            before = _snapshot_file(path)
        except Exception:
            raise NoteBlockCommandUnavailable from None
        try:
            note_block_store.save_note_blocks(paper_id, blocks, self.note_blocks_dir)
            persisted = note_block_store.list_note_blocks(paper_id, self.note_blocks_dir)
            if persisted != blocks:
                raise NoteBlockCommandUnavailable
            if expected_block_id not in {str(block["id"]) for block in persisted}:
                raise NoteBlockCommandUnavailable
            return persisted
        except Exception:
            _rollback(path, before)
            raise NoteBlockCommandUnavailable from None

    def create_note_block(
        self,
        paper_id: str,
        content: Mapping[str, Any],
        expected_revision: str,
    ) -> NoteBlockCommandResult:
        with _persistent_command_lock(self.note_blocks_dir, self.index_csv):
            values = _normalized_content(content, partial=False)
            if not self._paper_exists(paper_id):
                raise NoteBlockCommandNotFound
            blocks = self._load(paper_id)
            if note_blocks_revision(paper_id, blocks) != expected_revision:
                raise NoteBlockCommandConflict
            if len(blocks) >= MAX_NOTE_BLOCKS_PER_PAPER:
                raise NoteBlockCommandInvalid("The Note Block collection is full.")
            timestamp = _utc_now_iso()
            created = {
                "id": str(uuid4()),
                "paper_id": paper_id,
                **values,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            persisted = self._persist(
                paper_id,
                [*blocks, created],
                expected_block_id=created["id"],
            )
            block = next(item for item in persisted if item["id"] == created["id"])
            return NoteBlockCommandResult(
                status="created",
                block=normalized_note_blocks(paper_id, [block])[0],
                note_blocks_revision=note_blocks_revision(paper_id, persisted),
                total=len(persisted),
            )

    def update_note_block(
        self,
        paper_id: str,
        block_id: str,
        changes: Mapping[str, Any],
        expected_revision: str,
    ) -> NoteBlockCommandResult:
        with _persistent_command_lock(self.note_blocks_dir, self.index_csv):
            updates = _normalized_content(changes, partial=True)
            if not self._paper_exists(paper_id):
                raise NoteBlockCommandNotFound
            blocks = self._load(paper_id)
            if note_blocks_revision(paper_id, blocks) != expected_revision:
                raise NoteBlockCommandConflict
            current = next((block for block in blocks if str(block["id"]) == block_id), None)
            if current is None:
                raise NoteBlockCommandNotFound
            if all(current.get(field) == value for field, value in updates.items()):
                return NoteBlockCommandResult(
                    status="no_op",
                    block=normalized_note_blocks(paper_id, [current])[0],
                    note_blocks_revision=note_blocks_revision(paper_id, blocks),
                    total=len(blocks),
                )
            updated = {
                **current,
                **updates,
                "id": current["id"],
                "paper_id": current["paper_id"],
                "created_at": current["created_at"],
                "updated_at": _utc_now_iso(),
            }
            replacement = [updated if str(block["id"]) == block_id else block for block in blocks]
            persisted = self._persist(
                paper_id,
                replacement,
                expected_block_id=block_id,
            )
            block = next(item for item in persisted if str(item["id"]) == block_id)
            return NoteBlockCommandResult(
                status="saved",
                block=normalized_note_blocks(paper_id, [block])[0],
                note_blocks_revision=note_blocks_revision(paper_id, persisted),
                total=len(persisted),
            )
