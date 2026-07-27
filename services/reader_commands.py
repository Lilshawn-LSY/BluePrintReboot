from __future__ import annotations

import hashlib
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from services.paper_metadata_mutation import (
    CANONICAL_NOTE_HEADER_FIELDS,
    WEB_EDITABLE_METADATA_FIELDS,
    apply_paper_metadata_change,
    normalized_web_metadata,
    paper_metadata_revision,
)
from services.reading_note_template import (
    reading_note_header_values,
    refresh_reading_note_header,
    render_reading_note_template,
)
from storage.atomic_text import atomic_write_text
from storage.index_store import read_index_snapshot
from storage.note_store import note_path_for, save_note_text
from storage.paths import INDEX_CSV, NOTES_DIR
from storage.workspace_lock import WorkspaceLockUnavailable, workspace_write_lock


EMPTY_NOTE_SHA256 = hashlib.sha256(b"").hexdigest()


class ReaderCommandError(Exception):
    """Base class for controlled Reader command failures."""


class ReaderCommandConflict(ReaderCommandError):
    """The caller's optimistic-concurrency baseline is stale."""


class ReaderCommandNotFound(ReaderCommandError):
    """The requested stable paper identity is unknown."""


class ReaderCommandUnavailable(ReaderCommandError):
    """The persistent command could not complete consistently."""


@dataclass(frozen=True)
class PersistedNote:
    exists: bool
    content: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class MetadataCommandResult:
    status: Literal["saved", "no_op"]
    metadata: dict[str, str]
    metadata_revision: str
    changed_fields: tuple[str, ...]
    note_header_status: Literal["updated", "unchanged", "not_present", "not_required"]
    canonical_note_header: dict[str, str]
    canonical_note_header_text: str
    reading_note: PersistedNote


@dataclass(frozen=True)
class ReadingNoteCommandResult:
    status: Literal["created", "saved", "no_op"]
    content: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class _TextSnapshot:
    exists: bool
    content: str


def _record_for(paper_id: str, index_csv: Path) -> dict[str, str] | None:
    dataframe = read_index_snapshot(index_csv)
    if "paper_id" not in dataframe:
        return None
    matches = dataframe[dataframe["paper_id"] == paper_id]
    if matches.empty:
        return None
    return {
        str(key): str(value)
        for key, value in matches.iloc[0].fillna("").to_dict().items()
    }


@contextmanager
def _persistent_command_lock(index_csv: Path):
    """Serialize Reader check-and-write sections across API and local app processes."""

    index_path = Path(index_csv).resolve(strict=False)
    workspace_root = (
        index_path.parent.parent
        if index_path.parent.name.casefold() == "data"
        else index_path.parent
    )
    try:
        with workspace_write_lock(workspace_root):
            yield
    except WorkspaceLockUnavailable:
        raise ReaderCommandUnavailable from None


def _is_valid_paper_identity(paper_id: str) -> bool:
    """Return whether an identity is one filename component on POSIX and Windows."""

    if not paper_id or paper_id in {".", ".."}:
        return False
    if "/" in paper_id or "\\" in paper_id:
        return False
    if any(unicodedata.category(character) == "Cc" for character in paper_id):
        return False

    posix_path = PurePosixPath(paper_id)
    windows_path = PureWindowsPath(paper_id)
    if posix_path.is_absolute() or windows_path.is_absolute():
        return False
    if windows_path.drive or windows_path.root:
        return False
    return posix_path.parts == (paper_id,) and windows_path.parts == (paper_id,)


def _safe_note_path(record: dict[str, str], notes_dir: Path) -> Path:
    paper_id = record.get("paper_id", "")
    if not _is_valid_paper_identity(paper_id):
        raise ReaderCommandUnavailable from None

    root = Path(notes_dir).resolve(strict=False)
    candidate = note_path_for(record, Path(notes_dir)).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ReaderCommandUnavailable from None
    if candidate.parent != root:
        raise ReaderCommandUnavailable from None
    return candidate


def _snapshot_text(path: Path) -> _TextSnapshot:
    if not path.is_file():
        return _TextSnapshot(exists=False, content="")
    return _TextSnapshot(exists=True, content=path.read_bytes().decode("utf-8"))


def _restore_text(path: Path, snapshot: _TextSnapshot) -> None:
    if snapshot.exists:
        current = path.read_bytes().decode("utf-8") if path.is_file() else None
        if current != snapshot.content:
            atomic_write_text(path, snapshot.content)
    elif path.exists():
        path.unlink()


def _restore_transaction(
    index_path: Path,
    index_snapshot: _TextSnapshot,
    note_path: Path,
    note_snapshot: _TextSnapshot,
) -> None:
    failures = 0
    for path, snapshot in ((note_path, note_snapshot), (index_path, index_snapshot)):
        try:
            _restore_text(path, snapshot)
        except Exception:
            failures += 1
    if failures:
        raise ReaderCommandUnavailable


def _persisted_note(path: Path) -> PersistedNote:
    snapshot = _snapshot_text(path)
    encoded = snapshot.content.encode("utf-8")
    return PersistedNote(
        exists=snapshot.exists,
        content=snapshot.content,
        sha256=hashlib.sha256(encoded).hexdigest(),
        size_bytes=len(encoded),
    )


def _canonicalize_complete_note(content: str, record: dict[str, str]) -> str:
    refreshed = refresh_reading_note_header(content, record)
    if refreshed["action"] != "ignored":
        return str(refreshed["text"])

    return f"{_canonical_note_header_text(record).rstrip()}\n\n{content}"


def _canonical_note_header_text(record: dict[str, str]) -> str:
    template = render_reading_note_template(record)
    section_index = template.find("## ")
    return (template if section_index < 0 else template[:section_index]).rstrip() + "\n"


class ReaderCommandService:
    """Transaction boundary for the two bounded Reader write commands."""

    def __init__(self, *, index_csv: Path = INDEX_CSV, notes_dir: Path = NOTES_DIR) -> None:
        self.index_csv = Path(index_csv)
        self.notes_dir = Path(notes_dir)

    def save_metadata(
        self,
        paper_id: str,
        changes: dict[str, str],
        expected_revision: str,
    ) -> MetadataCommandResult:
        if set(changes) - set(WEB_EDITABLE_METADATA_FIELDS):
            raise ValueError("Unsupported metadata field.")

        with _persistent_command_lock(self.index_csv):
            try:
                current = _record_for(paper_id, self.index_csv)
            except Exception:
                raise ReaderCommandUnavailable from None
            if current is None:
                raise ReaderCommandNotFound
            if paper_metadata_revision(current) != expected_revision:
                raise ReaderCommandConflict

            note_path = _safe_note_path(current, self.notes_dir)
            try:
                index_before = _snapshot_text(self.index_csv)
                note_before = _snapshot_text(note_path)
            except Exception:
                raise ReaderCommandUnavailable from None
            try:
                mutation = apply_paper_metadata_change(
                    paper_id,
                    changes,
                    index_csv=self.index_csv,
                    notes_dir=self.notes_dir,
                    create_missing_note=False,
                )
            except Exception:
                try:
                    _restore_transaction(self.index_csv, index_before, note_path, note_before)
                except ReaderCommandUnavailable:
                    pass
                raise ReaderCommandUnavailable from None

            if not mutation.ok:
                try:
                    _restore_transaction(self.index_csv, index_before, note_path, note_before)
                except ReaderCommandUnavailable:
                    raise ReaderCommandUnavailable from None
                raise ReaderCommandUnavailable

            try:
                updated = _record_for(paper_id, self.index_csv)
                if updated is None:
                    raise ReaderCommandUnavailable
                persisted_note = _persisted_note(note_path)
                current_metadata = normalized_web_metadata(current)
                updated_metadata = normalized_web_metadata(updated)
                changed_fields = tuple(
                    field_name
                    for field_name in WEB_EDITABLE_METADATA_FIELDS
                    if field_name in changes
                    and current_metadata[field_name] != updated_metadata[field_name]
                )
                header_requested = bool(
                    CANONICAL_NOTE_HEADER_FIELDS.intersection(changed_fields)
                )
                if header_requested and note_before.exists:
                    canonical_note = _canonicalize_complete_note(
                        persisted_note.content,
                        updated,
                    )
                    if canonical_note != persisted_note.content:
                        save_note_text(updated, canonical_note, self.notes_dir)
                        persisted_note = _persisted_note(note_path)
            except Exception:
                try:
                    _restore_transaction(self.index_csv, index_before, note_path, note_before)
                except ReaderCommandUnavailable:
                    pass
                raise ReaderCommandUnavailable from None

            if not header_requested:
                note_header_status: Literal[
                    "updated", "unchanged", "not_present", "not_required"
                ] = "not_required"
            elif not note_before.exists:
                note_header_status = "not_present"
            elif persisted_note.content != note_before.content:
                note_header_status = "updated"
            else:
                note_header_status = "unchanged"

            return MetadataCommandResult(
                status="saved" if changed_fields else "no_op",
                metadata=updated_metadata,
                metadata_revision=paper_metadata_revision(updated),
                changed_fields=changed_fields,
                note_header_status=note_header_status,
                canonical_note_header=reading_note_header_values(updated),
                canonical_note_header_text=_canonical_note_header_text(updated),
                reading_note=persisted_note,
            )

    def save_reading_note(
        self,
        paper_id: str,
        content: str,
        expected_sha256: str,
    ) -> ReadingNoteCommandResult:
        with _persistent_command_lock(self.index_csv):
            try:
                record = _record_for(paper_id, self.index_csv)
            except Exception:
                raise ReaderCommandUnavailable from None
            if record is None:
                raise ReaderCommandNotFound

            note_path = _safe_note_path(record, self.notes_dir)
            try:
                before = _snapshot_text(note_path)
            except Exception:
                raise ReaderCommandUnavailable from None
            before_bytes = before.content.encode("utf-8")
            current_sha256 = hashlib.sha256(before_bytes).hexdigest()
            if current_sha256 != expected_sha256:
                raise ReaderCommandConflict

            normalized = _canonicalize_complete_note(content, record)
            normalized_bytes = normalized.encode("utf-8")
            new_sha256 = hashlib.sha256(normalized_bytes).hexdigest()
            if before.exists and normalized_bytes == before_bytes:
                return ReadingNoteCommandResult(
                    status="no_op",
                    content=normalized,
                    sha256=new_sha256,
                    size_bytes=len(normalized_bytes),
                )

            try:
                save_note_text(record, normalized, self.notes_dir)
                persisted = _persisted_note(note_path)
                if not persisted.exists or persisted.content != normalized:
                    raise ReaderCommandUnavailable
            except Exception:
                try:
                    _restore_text(note_path, before)
                except Exception:
                    pass
                raise ReaderCommandUnavailable from None

            return ReadingNoteCommandResult(
                status="saved" if before.exists else "created",
                content=persisted.content,
                sha256=persisted.sha256,
                size_bytes=persisted.size_bytes,
            )
