from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from services.managed_pdf import ManagedPdfState as RecordPdfState, resolve_indexed_pdf
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

    resolved = resolve_indexed_pdf(matches.iloc[0].to_dict(), papers_dir=Path(papers_dir))
    state = ManagedPdfState(resolved.state.value)
    if resolved.state is not RecordPdfState.available:
        return ManagedPdfResult(state)
    return ManagedPdfResult(
        ManagedPdfState.available,
        path=resolved.path,
        filename=resolved.filename,
        stat_result=resolved.stat_result,
    )
