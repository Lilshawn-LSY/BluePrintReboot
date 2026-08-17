from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


class ManagedPdfState(str, Enum):
    available = "available"
    missing = "missing"
    invalid = "invalid"
    unavailable = "unavailable"


@dataclass(frozen=True)
class ManagedPdfRecordResult:
    state: ManagedPdfState
    path: Path | None = None
    filename: str = ""
    stat_result: os.stat_result | None = None


def indexed_pdf_candidate(record: Mapping[str, object], papers_dir: Path) -> Path | None:
    """Resolve the index filepath/filename fallback without asserting availability."""

    managed_root = Path(papers_dir).resolve(strict=False)
    raw_path = str(record.get("filepath", "") or "").strip()
    filename = str(record.get("filename", "") or "").strip()
    if not raw_path and not filename:
        return None

    candidate = Path(raw_path) if raw_path else Path(filename)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0].casefold() == managed_root.name.casefold():
        return managed_root.parent / candidate
    return managed_root / candidate


def resolve_indexed_pdf(
    record: Mapping[str, object],
    *,
    papers_dir: Path,
) -> ManagedPdfRecordResult:
    """Apply the canonical managed-PDF policy: regular .pdf files below papers/."""

    managed_root = Path(papers_dir).resolve(strict=False)
    candidate = indexed_pdf_candidate(record, managed_root)
    if candidate is None:
        return ManagedPdfRecordResult(ManagedPdfState.missing)
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(managed_root)
    except (OSError, RuntimeError, ValueError):
        return ManagedPdfRecordResult(ManagedPdfState.invalid)
    if resolved.suffix.casefold() != ".pdf":
        return ManagedPdfRecordResult(ManagedPdfState.invalid)
    try:
        file_stat = resolved.stat()
    except FileNotFoundError:
        return ManagedPdfRecordResult(ManagedPdfState.missing, path=resolved, filename=resolved.name)
    except OSError:
        return ManagedPdfRecordResult(ManagedPdfState.unavailable, path=resolved, filename=resolved.name)
    if not stat.S_ISREG(file_stat.st_mode):
        return ManagedPdfRecordResult(ManagedPdfState.invalid)
    return ManagedPdfRecordResult(
        ManagedPdfState.available,
        path=resolved,
        filename=resolved.name,
        stat_result=file_stat,
    )
