from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from services.managed_pdf import ManagedPdfState, resolve_indexed_pdf
from services.paper_metadata_mutation import paper_lifecycle_revision, paper_pdf_revision
from services.storage_recovery import StorageRecoveryError, export_recovery_copy
from storage.index_store import read_index_snapshot, set_paper_archived
from storage.workspace_lock import WorkspaceLockUnavailable, workspace_write_lock


class PaperRemovalConflict(RuntimeError):
    """A safe removal confirmation no longer matches the current Paper state."""


class PaperRemovalNotFound(RuntimeError):
    """The requested stable Paper identity does not exist."""


class PaperRemovalUnavailable(RuntimeError):
    """The bounded removal operation could not complete consistently."""


@dataclass(frozen=True)
class RemoveManagedPdfResult:
    status: str
    paper_id: str
    pdf_removed: bool
    recovery_copy_created: bool
    message: str


@dataclass(frozen=True)
class ArchivePaperResult:
    status: str
    paper_id: str
    lifecycle_revision: str
    message: str


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PaperRemovalService:
    """Conservative Library removal commands.

    The service intentionally has no full Paper deletion command.  Removing managed
    bytes creates and verifies a recovery copy first; removing a Paper from the active
    Library is an archive operation that retains metadata, notes, blocks, tags, links,
    and any managed PDF.
    """

    def __init__(self, *, index_csv: Path, papers_dir: Path) -> None:
        self.index_csv = Path(index_csv)
        self.papers_dir = Path(papers_dir).resolve(strict=False)

    @property
    def workspace_root(self) -> Path:
        index_path = self.index_csv.resolve(strict=False)
        return index_path.parent.parent if index_path.parent.name.casefold() == "data" else index_path.parent

    @contextmanager
    def _write_lock(self) -> Iterator[None]:
        try:
            with workspace_write_lock(self.workspace_root):
                yield
        except WorkspaceLockUnavailable:
            raise PaperRemovalUnavailable from None

    def _record(self, paper_id: str) -> dict[str, object] | None:
        dataframe = read_index_snapshot(self.index_csv)
        if "paper_id" not in dataframe:
            return None
        matches = dataframe[dataframe["paper_id"] == paper_id]
        return None if matches.empty else matches.iloc[0].fillna("").to_dict()

    def remove_managed_pdf(
        self,
        paper_id: str,
        expected_pdf_revision: str,
    ) -> RemoveManagedPdfResult:
        """Remove only managed PDF bytes after a verified workspace recovery copy."""

        with self._write_lock():
            try:
                record = self._record(paper_id)
            except Exception:
                raise PaperRemovalUnavailable from None
            if record is None:
                raise PaperRemovalNotFound
            if paper_pdf_revision(record) != expected_pdf_revision:
                raise PaperRemovalConflict
            resolved = resolve_indexed_pdf(record, papers_dir=self.papers_dir)
            if resolved.state is ManagedPdfState.missing:
                return RemoveManagedPdfResult(
                    status="already_missing",
                    paper_id=paper_id,
                    pdf_removed=False,
                    recovery_copy_created=False,
                    message="The managed PDF is already missing. Paper metadata and linked research remain unchanged.",
                )
            if resolved.state is not ManagedPdfState.available or resolved.path is None:
                raise PaperRemovalUnavailable
            source = resolved.path
            try:
                before_digest = _digest(source)
                before_size = source.stat().st_size
                exported = export_recovery_copy(
                    source,
                    workspace_root=self.workspace_root,
                    recovery_dir=self.workspace_root / "exports" / "recovery",
                    storage_class="managed PDF",
                    reason="Explicit Library Remove PDF file command",
                )
                manifest = exported["manifest"]
                if (
                    str(manifest.get("sha256", "")) != before_digest
                    or int(manifest.get("byte_size", -1)) != before_size
                    or _digest(source) != before_digest
                    or source.stat().st_size != before_size
                ):
                    raise StorageRecoveryError("Managed PDF changed during recovery copy verification.")
                source.unlink()
            except (OSError, StorageRecoveryError, ValueError, TypeError):
                raise PaperRemovalUnavailable from None
            return RemoveManagedPdfResult(
                status="removed",
                paper_id=paper_id,
                pdf_removed=True,
                recovery_copy_created=True,
                message="Removed managed PDF bytes after a verified recovery copy. Paper metadata and linked research were preserved.",
            )

    def archive_paper(
        self,
        paper_id: str,
        expected_lifecycle_revision: str,
    ) -> ArchivePaperResult:
        """Remove a Paper from active Library views without deleting owned research data."""

        with self._write_lock():
            try:
                record = self._record(paper_id)
            except Exception:
                raise PaperRemovalUnavailable from None
            if record is None:
                raise PaperRemovalNotFound
            if paper_lifecycle_revision(record) != expected_lifecycle_revision:
                raise PaperRemovalConflict
            already_archived = str(record.get("is_archived", "false") or "false").casefold() == "true"
            if not already_archived:
                try:
                    set_paper_archived(paper_id, True, index_csv=self.index_csv)
                    updated = self._record(paper_id)
                except Exception:
                    raise PaperRemovalUnavailable from None
                if updated is None or str(updated.get("is_archived", "false")).casefold() != "true":
                    raise PaperRemovalUnavailable
            else:
                updated = record
            return ArchivePaperResult(
                status="already_archived" if already_archived else "archived",
                paper_id=paper_id,
                lifecycle_revision=paper_lifecycle_revision(updated),
                message="Archived the Paper from active Library views. Its metadata, managed PDF, notes, blocks, tags, and Project links were preserved.",
            )
