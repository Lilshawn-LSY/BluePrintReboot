from __future__ import annotations

import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterator, Mapping

from ingest.scanner import make_paper_id, pdf_hash_metadata_key, pdf_sha256_with_metadata, scan_pdf_path
from storage.index_store import read_index_snapshot, register_scanned_paper_records
from storage.paths import INDEX_CSV, NOTES_DIR, PAPERS_DIR
from storage.workspace_lock import WorkspaceLockUnavailable, workspace_write_lock


class PdfScanImportUnavailable(RuntimeError):
    """The managed-PDF command could not complete without risking consistency."""


@dataclass(frozen=True)
class _PdfEvaluation:
    relative_path: str
    filename: str
    status: str
    message: str
    size_bytes: int
    path: Path | None = None
    hash_metadata: Mapping[str, object] | None = None

    @property
    def can_import(self) -> bool:
        return self.status == "new"


def _path_key(path: Path) -> str:
    return pdf_hash_metadata_key(str(path.resolve(strict=False)))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _safe_relative_path(value: str) -> str | None:
    normalized = str(value or "").strip().replace("\\", "/")
    if not normalized:
        return None
    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(normalized)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or windows_path.root
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        return None
    return posix_path.as_posix()


class PdfScanImportService:
    """Explicit scan/import boundary for PDFs already staged in ``papers/``.

    A scan reads the managed directory and index snapshot only. Import accepts
    safe managed-relative selections, revalidates each file under the shared
    workspace write lock, and then uses the existing scanner/index merge path
    for just those selected records.
    """

    def __init__(
        self,
        *,
        index_csv: Path = INDEX_CSV,
        papers_dir: Path = PAPERS_DIR,
        notes_dir: Path = NOTES_DIR,
    ) -> None:
        self.index_csv = Path(index_csv)
        self.papers_dir = Path(papers_dir).resolve(strict=False)
        self.notes_dir = Path(notes_dir)

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
            raise PdfScanImportUnavailable from None

    def _record_path(self, record: Mapping[str, object]) -> Path | None:
        raw_path = str(record.get("filepath", "") or "").strip()
        filename = str(record.get("filename", "") or "").strip()
        if not raw_path and not filename:
            return None
        candidate = Path(raw_path) if raw_path else Path(filename)
        if not candidate.is_absolute():
            candidate = (
                self.papers_dir.parent / candidate
                if candidate.parts and candidate.parts[0].casefold() == self.papers_dir.name.casefold()
                else self.papers_dir / candidate
            )
        resolved = candidate.resolve(strict=False)
        return resolved if _is_within(resolved, self.papers_dir) else None

    def _registry_state(self) -> tuple[dict[str, Mapping[str, object]], set[str], set[str]]:
        dataframe = read_index_snapshot(self.index_csv)
        records = dataframe.to_dict("records")
        by_path: dict[str, Mapping[str, object]] = {}
        paper_ids: set[str] = set()
        hashes: set[str] = set()
        for record in records:
            paper_id = str(record.get("paper_id", "") or "").strip()
            if paper_id:
                paper_ids.add(paper_id)
            record_path = self._record_path(record)
            if record_path is not None:
                by_path[_path_key(record_path)] = record
            digest = str(record.get("pdf_sha256", "") or "").strip()
            if digest:
                hashes.add(digest)
        return by_path, paper_ids, hashes

    def _relative_for_discovered_path(self, path: Path) -> str:
        return path.relative_to(self.papers_dir).as_posix()

    def _path_from_relative(self, relative_path: str) -> Path | None:
        safe_relative = _safe_relative_path(relative_path)
        if safe_relative is None:
            return None
        candidate = self.papers_dir.joinpath(*PurePosixPath(safe_relative).parts)
        return candidate if _is_within(candidate, self.papers_dir) else None

    def _evaluate(
        self,
        relative_path: str,
        *,
        by_path: Mapping[str, Mapping[str, object]],
        paper_ids: set[str],
        hashes: set[str],
    ) -> _PdfEvaluation:
        safe_relative = _safe_relative_path(relative_path)
        filename = PurePosixPath(safe_relative or relative_path).name
        if safe_relative is None or not safe_relative.casefold().endswith(".pdf"):
            return _PdfEvaluation(
                relative_path=safe_relative or "",
                filename=filename,
                status="invalid",
                message="The selected entry is not a safe managed PDF path.",
                size_bytes=0,
            )
        candidate = self._path_from_relative(safe_relative)
        if candidate is None:
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="invalid",
                message="The selected entry is not inside the managed PDF directory.",
                size_bytes=0,
            )
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(self.papers_dir)
        except (OSError, RuntimeError, ValueError):
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="invalid",
                message="The PDF path is not safely contained in the managed directory.",
                size_bytes=0,
            )
        try:
            file_stat = resolved.stat()
        except FileNotFoundError:
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="missing",
                message="The PDF is no longer available in the managed directory.",
                size_bytes=0,
            )
        except OSError:
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="unavailable",
                message="The managed PDF cannot currently be read.",
                size_bytes=0,
            )
        if not stat.S_ISREG(file_stat.st_mode):
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="invalid",
                message="The managed PDF entry is not a regular file.",
                size_bytes=0,
            )
        try:
            with resolved.open("rb") as source:
                header = source.read(4096)
        except OSError:
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="unavailable",
                message="The managed PDF cannot currently be read.",
                size_bytes=0,
            )
        if file_stat.st_size <= 0 or b"%PDF-" not in header:
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="invalid",
                message="The file does not contain a readable PDF header.",
                size_bytes=file_stat.st_size,
            )
        try:
            hash_metadata = pdf_sha256_with_metadata(resolved)
        except OSError:
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="unavailable",
                message="The managed PDF could not be fingerprinted safely.",
                size_bytes=file_stat.st_size,
            )
        paper_id = make_paper_id(resolved, self.papers_dir)
        digest = str(hash_metadata["pdf_sha256"])
        if _path_key(resolved) in by_path or paper_id in paper_ids or digest in hashes:
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="already_registered",
                message="This PDF is already registered in the local library.",
                size_bytes=file_stat.st_size,
                path=resolved,
                hash_metadata=hash_metadata,
            )
        return _PdfEvaluation(
            relative_path=safe_relative,
            filename=filename,
            status="new",
            message="Ready to register as a new Paper.",
            size_bytes=file_stat.st_size,
            path=resolved,
            hash_metadata=hash_metadata,
        )

    @staticmethod
    def _candidate_payload(
        evaluation: _PdfEvaluation,
        *,
        preserve_missing: bool = False,
    ) -> dict[str, Any]:
        status = evaluation.status if preserve_missing or evaluation.status != "missing" else "unavailable"
        return {
            "relative_path": evaluation.relative_path,
            "filename": evaluation.filename,
            "status": status,
            "message": evaluation.message,
            "can_import": evaluation.can_import,
            "size_bytes": evaluation.size_bytes,
        }

    def scan(self) -> dict[str, Any]:
        """Discover managed PDFs without creating or updating an index record."""

        if not self.papers_dir.exists():
            return {
                "status": "ok",
                "message": "The managed PDF directory has no PDFs to scan.",
                "candidates": [],
            }
        try:
            by_path, paper_ids, hashes = self._registry_state()
            discovered = sorted(self.papers_dir.rglob("*"), key=lambda path: path.as_posix().casefold())
        except (OSError, ValueError):
            return {
                "status": "unavailable",
                "message": "The managed PDF directory or Paper registry cannot currently be read.",
                "candidates": [],
            }

        candidates: list[dict[str, Any]] = []
        for path in discovered:
            try:
                is_pdf = path.suffix.casefold() == ".pdf"
                is_file = path.is_file()
            except OSError:
                is_pdf = path.suffix.casefold() == ".pdf"
                is_file = is_pdf
            if not is_pdf or not is_file:
                continue
            try:
                relative_path = self._relative_for_discovered_path(path)
            except ValueError:
                continue
            candidates.append(
                self._candidate_payload(
                    self._evaluate(
                        relative_path,
                        by_path=by_path,
                        paper_ids=paper_ids,
                        hashes=hashes,
                    )
                )
            )
        return {
            "status": "ok",
            "message": f"Found {len(candidates)} managed PDF candidate(s).",
            "candidates": candidates,
        }

    def import_selected(self, relative_paths: list[str]) -> dict[str, Any]:
        """Register selected new PDFs, reporting safe per-file outcomes."""

        ordered_paths = list(dict.fromkeys(relative_paths))
        try:
            with self._write_lock():
                by_path, paper_ids, hashes = self._registry_state()
                evaluations = [
                    self._evaluate(path, by_path=by_path, paper_ids=paper_ids, hashes=hashes)
                    for path in ordered_paths
                ]
                new_evaluations = [item for item in evaluations if item.status == "new"]
                records: list[dict[str, str]] = []
                record_paths: set[str] = set()
                for item in new_evaluations:
                    if item.path is None:
                        continue
                    try:
                        records.append(
                            scan_pdf_path(
                                item.path,
                                papers_dir=self.papers_dir,
                                notes_dir=self.notes_dir,
                                hash_metadata=item.hash_metadata,
                            )
                        )
                        record_paths.add(_path_key(item.path))
                    except OSError:
                        continue
                persisted = None
                persistence_failed = False
                if records:
                    try:
                        persisted = register_scanned_paper_records(
                            records,
                            index_csv=self.index_csv,
                            papers_dir=self.papers_dir,
                        )
                    except Exception:
                        persistence_failed = True

                persisted_paths: dict[str, str] = {}
                if persisted is not None:
                    for record in persisted.to_dict("records"):
                        record_path = self._record_path(record)
                        if record_path is not None:
                            persisted_paths[_path_key(record_path)] = str(record.get("paper_id", "") or "")

                results: list[dict[str, Any]] = []
                for item in evaluations:
                    payload = self._candidate_payload(item, preserve_missing=True)
                    if item.status == "new":
                        paper_id = persisted_paths.get(_path_key(item.path)) if item.path is not None else ""
                        if item.path is None or _path_key(item.path) not in record_paths:
                            payload.update(
                                status="missing",
                                can_import=False,
                                message="The PDF changed or disappeared before it could be registered.",
                            )
                        elif persistence_failed:
                            payload.update(
                                status="unavailable",
                                can_import=False,
                                message="The Paper registry could not be updated. No selected PDFs were registered.",
                            )
                        elif paper_id:
                            payload.update(
                                status="imported",
                                can_import=False,
                                message="Registered as a new Paper. Metadata enrichment remains an explicit next step.",
                                paper_id=paper_id,
                            )
                        else:
                            payload.update(
                                status="already_registered",
                                can_import=False,
                                message="This PDF became registered while the import was running.",
                            )
                    else:
                        payload["can_import"] = False
                    results.append(payload)
        except PdfScanImportUnavailable:
            raise
        except Exception:
            raise PdfScanImportUnavailable from None

        imported_count = sum(item["status"] == "imported" for item in results)
        return {
            "message": f"Registered {imported_count} PDF(s) as new Papers.",
            "imported_count": imported_count,
            "results": results,
        }
