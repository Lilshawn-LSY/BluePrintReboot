from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from storage.index_store import read_index_snapshot
from storage.paths import INDEX_CSV, PAPERS_DIR


class ManagedPdfState(str, Enum):
    available = "available"
    unknown_paper = "unknown_paper"
    missing = "missing"
    invalid = "invalid"
    unavailable = "unavailable"


@dataclass(frozen=True)
class ManagedPdfResult:
    state: ManagedPdfState
    path: Path | None = None
    filename: str = ""
    stat_result: os.stat_result | None = None


def _indexed_candidate(record: dict[str, object], papers_dir: Path) -> Path | None:
    raw_path = str(record.get("filepath", "") or "").strip()
    filename = str(record.get("filename", "") or "").strip()
    if not raw_path and not filename:
        return None

    candidate = Path(raw_path) if raw_path else Path(filename)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0].casefold() == papers_dir.name.casefold():
        return papers_dir.parent / candidate
    return papers_dir / candidate


def resolve_managed_pdf(
    paper_id: str,
    *,
    index_csv: Path = INDEX_CSV,
    papers_dir: Path = PAPERS_DIR,
) -> ManagedPdfResult:
    dataframe = read_index_snapshot(Path(index_csv))
    matches = dataframe[dataframe["paper_id"] == paper_id]
    if matches.empty:
        return ManagedPdfResult(ManagedPdfState.unknown_paper)

    managed_root = Path(papers_dir).resolve(strict=False)
    candidate = _indexed_candidate(matches.iloc[0].to_dict(), managed_root)
    if candidate is None:
        return ManagedPdfResult(ManagedPdfState.missing)

    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(managed_root)
    except (OSError, RuntimeError, ValueError):
        return ManagedPdfResult(ManagedPdfState.invalid)

    if resolved.suffix.casefold() != ".pdf":
        return ManagedPdfResult(ManagedPdfState.invalid)

    try:
        file_stat = resolved.stat()
    except FileNotFoundError:
        return ManagedPdfResult(ManagedPdfState.missing)
    except OSError:
        return ManagedPdfResult(ManagedPdfState.unavailable)

    if not stat.S_ISREG(file_stat.st_mode):
        return ManagedPdfResult(ManagedPdfState.invalid)
    return ManagedPdfResult(
        ManagedPdfState.available,
        path=resolved,
        filename=resolved.name,
        stat_result=file_stat,
    )
