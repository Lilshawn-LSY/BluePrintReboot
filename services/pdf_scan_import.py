from __future__ import annotations

import stat
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterator, Mapping

from ingest.scanner import make_paper_id, pdf_hash_metadata_key, pdf_sha256_with_metadata, scan_pdf_path
from storage.index_store import read_index_snapshot, register_scanned_paper_records, save_index
from storage.paths import INDEX_CSV, NOTES_DIR, PAPERS_DIR
from storage.workspace_lock import WorkspaceLockUnavailable, workspace_write_lock


class PdfScanImportUnavailable(RuntimeError):
    """The managed-PDF command could not complete without risking consistency."""


class PdfReconnectConflict(RuntimeError):
    """A reconnect candidate changed or is no longer uniquely safe."""


class PdfReconnectInvalid(ValueError):
    """A reconnect request is outside the bounded managed-PDF contract."""


MAX_UPLOAD_FILES = 100
MAX_UPLOAD_BYTES_PER_FILE = 100 * 1024 * 1024


@dataclass(frozen=True)
class _PdfEvaluation:
    relative_path: str
    filename: str
    status: str
    message: str
    size_bytes: int
    path: Path | None = None
    hash_metadata: Mapping[str, object] | None = None
    reconnect_paper_id: str = ""

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

    def _registry_state(self) -> tuple[dict[str, Mapping[str, object]], set[str], dict[str, list[Mapping[str, object]]]]:
        dataframe = read_index_snapshot(self.index_csv)
        records = dataframe.to_dict("records")
        by_path: dict[str, Mapping[str, object]] = {}
        paper_ids: set[str] = set()
        hashes: dict[str, list[Mapping[str, object]]] = {}
        for record in records:
            paper_id = str(record.get("paper_id", "") or "").strip()
            if paper_id:
                paper_ids.add(paper_id)
            record_path = self._record_path(record)
            if record_path is not None:
                by_path[_path_key(record_path)] = record
            digest = str(record.get("pdf_sha256", "") or "").strip()
            if digest:
                hashes.setdefault(digest, []).append(record)
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
        hashes: Mapping[str, list[Mapping[str, object]]],
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
        if _path_key(resolved) in by_path or paper_id in paper_ids:
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="already_registered",
                message="This PDF is already registered in the local library.",
                size_bytes=file_stat.st_size,
                path=resolved,
                hash_metadata=hash_metadata,
            )
        hash_matches = list(hashes.get(digest, []))
        if hash_matches:
            missing_matches = [
                record for record in hash_matches
                if (record_path := self._record_path(record)) is None or not record_path.is_file()
            ]
            if len(hash_matches) == 1 and len(missing_matches) == 1:
                reconnect_paper_id = str(missing_matches[0].get("paper_id", "") or "").strip()
                if reconnect_paper_id:
                    return _PdfEvaluation(
                        relative_path=safe_relative,
                        filename=filename,
                        status="reconnect_available",
                        message="Exact content matches one Paper whose managed PDF is missing. Review and explicitly reconnect it.",
                        size_bytes=file_stat.st_size,
                        path=resolved,
                        hash_metadata=hash_metadata,
                        reconnect_paper_id=reconnect_paper_id,
                    )
            if missing_matches:
                return _PdfEvaluation(
                    relative_path=safe_relative,
                    filename=filename,
                    status="reconnect_ambiguous",
                    message="Exact content matches multiple registered Papers or file states. No reconnect was selected automatically.",
                    size_bytes=file_stat.st_size,
                    path=resolved,
                    hash_metadata=hash_metadata,
                )
            return _PdfEvaluation(
                relative_path=safe_relative,
                filename=filename,
                status="duplicate_content",
                message="This PDF has the same exact content as a registered Paper at another managed path.",
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
            "can_reconnect": evaluation.status == "reconnect_available" and bool(evaluation.reconnect_paper_id),
            "reconnect_paper_id": evaluation.reconnect_paper_id,
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

    def reconnect(self, *, paper_id: str, relative_path: str) -> dict[str, Any]:
        """Explicitly reconnect one missing Paper to one exact managed PDF.

        The command updates only file identity columns in the existing row. It
        never creates, merges, or deletes Paper records, so all Paper-owned
        notes, blocks, tags, and Project links remain attached to ``paper_id``.
        """

        safe_relative = _safe_relative_path(relative_path)
        if not paper_id.strip() or safe_relative is None or not safe_relative.casefold().endswith(".pdf"):
            raise PdfReconnectInvalid
        try:
            with self._write_lock():
                candidate = self._path_from_relative(safe_relative)
                if candidate is None:
                    raise PdfReconnectInvalid
                evaluations_by_path, paper_ids, hashes = self._registry_state()
                evaluation = self._evaluate(
                    safe_relative,
                    by_path=evaluations_by_path,
                    paper_ids=paper_ids,
                    hashes=hashes,
                )
                if (
                    evaluation.status != "reconnect_available"
                    or evaluation.reconnect_paper_id != paper_id
                    or evaluation.hash_metadata is None
                ):
                    raise PdfReconnectConflict
                dataframe = read_index_snapshot(self.index_csv)
                matches = dataframe[dataframe["paper_id"] == paper_id]
                if len(matches) != 1 or evaluation.path is None:
                    raise PdfReconnectConflict
                row_index = matches.index[0]
                current_path = self._record_path(matches.iloc[0].to_dict())
                if current_path is not None and current_path.is_file():
                    raise PdfReconnectConflict
                # Recheck exact identity after the lock and immediately before
                # persistence; do not trust a stale scan preview.
                refreshed = pdf_sha256_with_metadata(evaluation.path)
                expected_digest = str(evaluation.hash_metadata.get("pdf_sha256", "")).casefold()
                if not expected_digest or str(refreshed.get("pdf_sha256", "")).casefold() != expected_digest:
                    raise PdfReconnectConflict
                dataframe.at[row_index, "filename"] = evaluation.path.name
                dataframe.at[row_index, "filepath"] = str(evaluation.path)
                dataframe.at[row_index, "pdf_sha256"] = refreshed["pdf_sha256"]
                dataframe.at[row_index, "pdf_size_bytes"] = refreshed["pdf_size_bytes"]
                dataframe.at[row_index, "pdf_modified_at"] = refreshed["pdf_modified_at"]
                save_index(dataframe, self.index_csv)
                verified = read_index_snapshot(self.index_csv)
                saved = verified[verified["paper_id"] == paper_id]
                if len(saved) != 1 or str(saved.iloc[0].get("pdf_sha256", "")).casefold() != expected_digest:
                    raise PdfScanImportUnavailable
                return {
                    "status": "reconnected",
                    "paper_id": paper_id,
                    "relative_path": safe_relative,
                    "message": "Reconnected the existing Paper to the exact managed PDF. Paper metadata and linked work were preserved.",
                }
        except (PdfReconnectConflict, PdfReconnectInvalid, PdfScanImportUnavailable):
            raise
        except Exception:
            raise PdfScanImportUnavailable from None

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
                    # Reconnect availability is a scan-preview concern; import
                    # outcomes retain their pre-existing compact contract.
                    payload.pop("can_reconnect", None)
                    payload.pop("reconnect_paper_id", None)
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

    def import_uploaded(self, files: list[tuple[str, Any]]) -> dict[str, Any]:
        """Stage explicit browser uploads inside ``papers/`` then use normal import checks.

        Uploads never bypass the managed-directory scanner.  Each staged file is
        revalidated by :meth:`import_selected`, retaining duplicate detection and the
        same index registration path as explicitly selected managed PDFs.
        """

        if not files or len(files) > MAX_UPLOAD_FILES:
            raise PdfReconnectInvalid
        staged: list[tuple[str, Path]] = []
        immediate_results: list[dict[str, Any]] = []
        try:
            with self._write_lock():
                self.papers_dir.mkdir(parents=True, exist_ok=True)
                for source_name, source in files:
                    filename = PurePosixPath(str(source_name or "").replace("\\", "/")).name
                    if not filename or not filename.casefold().endswith(".pdf"):
                        immediate_results.append(
                            {
                                "relative_path": "",
                                "filename": filename or "Unnamed upload",
                                "status": "invalid",
                                "message": "Only PDF files can be imported.",
                                "can_import": False,
                                "size_bytes": 0,
                                "paper_id": "",
                            }
                        )
                        continue
                    destination = self._available_upload_destination(filename)
                    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.upload")
                    byte_count = 0
                    header = b""
                    try:
                        with temporary.open("xb") as writer:
                            while True:
                                chunk = source.read(1024 * 1024)
                                if not chunk:
                                    break
                                if not isinstance(chunk, bytes):
                                    raise OSError("Upload stream must return bytes.")
                                byte_count += len(chunk)
                                if byte_count > MAX_UPLOAD_BYTES_PER_FILE:
                                    raise ValueError("PDF upload exceeds the configured size limit.")
                                if len(header) < 4096:
                                    header += chunk[: 4096 - len(header)]
                                writer.write(chunk)
                            writer.flush()
                            os.fsync(writer.fileno())
                        if byte_count <= 0 or b"%PDF-" not in header:
                            raise ValueError("The uploaded file does not contain a readable PDF header.")
                        os.replace(temporary, destination)
                    except (OSError, ValueError):
                        if temporary.exists():
                            temporary.unlink()
                        immediate_results.append(
                            {
                                "relative_path": "",
                                "filename": filename,
                                "status": "invalid",
                                "message": "The uploaded file is not a readable PDF within the supported size limit.",
                                "can_import": False,
                                "size_bytes": byte_count,
                                "paper_id": "",
                            }
                        )
                        continue
                    staged.append((self._relative_for_discovered_path(destination), destination))

                imported = self.import_selected([relative_path for relative_path, _path in staged])
                results = [*immediate_results, *imported["results"]]
                outcomes = {str(item.get("relative_path", "")): item for item in imported["results"]}
                # A duplicate or invalid upload has no existing Paper ownership. Remove
                # only that just-created staging target; never touch pre-existing files.
                for relative_path, destination in staged:
                    outcome = outcomes.get(relative_path, {})
                    if outcome.get("status") in {"already_registered", "duplicate_content", "invalid"} and destination.is_file():
                        destination.unlink()
                imported_count = sum(item.get("status") == "imported" for item in results)
                return {
                    "message": f"Processed {len(results)} uploaded file(s); registered {imported_count} new Paper(s).",
                    "imported_count": imported_count,
                    "results": results,
                }
        except (PdfReconnectInvalid, PdfScanImportUnavailable):
            raise
        except Exception:
            raise PdfScanImportUnavailable from None

    def _available_upload_destination(self, filename: str) -> Path:
        """Allocate one collision-free managed filename without trusting browser paths."""

        stem = Path(filename).stem.strip() or "uploaded-paper"
        suffix = ".pdf"
        candidate = self.papers_dir / f"{stem}{suffix}"
        index = 2
        while candidate.exists():
            candidate = self.papers_dir / f"{stem} ({index}){suffix}"
            index += 1
        return candidate
